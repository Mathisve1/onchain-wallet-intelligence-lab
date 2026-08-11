from __future__ import annotations

import dataclasses
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.archive_inventory.r11a_implementation import failure, limits, runtime, schema, storage


def small_limits() -> limits.R11ALimits:
    return dataclasses.replace(
        limits.DEFAULT_LIMITS,
        maximum_get_object_requests=3,
        maximum_ephemeral_workspace_bytes=64 * 1024 * 1024,
        minimum_free_workspace_bytes_before_oidc=128 * 1024 * 1024,
        maximum_retained_artifact_bytes=8 * 1024 * 1024,
        maximum_retained_scientific_output_bytes=8 * 1024 * 1024,
        reserved_non_scientific_package_metadata_bytes=4 * 1024 * 1024,
        maximum_runtime_seconds=600,
        post_measurement_packaging_reservation_seconds=60,
        minimum_upload_window_seconds=30,
    )


def targets() -> tuple[runtime.RuntimeTarget, ...]:
    return tuple(
        runtime.RuntimeTarget(
            object_ordinal_zero_based=index,
            path_hour_utc=f"2025-07-28T{index:02d}:00:00Z",
            source_object_key=f"node_fills_by_block/hourly/20250728/{index}.lz4",
            expected_etag=f'"etag-{index}"',
            expected_content_length=10,
            expected_compressed_object_sha256=f"{index + 1:064x}",
        )
        for index in range(3)
    )


class RuntimeGuardTests(unittest.TestCase):
    def test_runtime_reserve_is_enforced_before_hard_timeout(self) -> None:
        values = iter((0, 500_000_000, 1_100_000_000))
        frozen = dataclasses.replace(
            limits.DEFAULT_LIMITS,
            maximum_runtime_seconds=2,
            post_measurement_packaging_reservation_seconds=1,
        )
        guard = runtime.RuntimeGuard(frozen, monotonic_ns=lambda: next(values))
        self.assertEqual(guard.check("first"), 500)
        with self.assertRaises(runtime.R11ARuntimeError):
            guard.check("second")

    def test_guarded_workspace_meter_checks_runtime_on_each_checkpoint(self) -> None:
        ticks = iter((0, 100_000_000, 200_000_000, 300_000_000, 400_000_000))
        guard = runtime.RuntimeGuard(monotonic_ns=lambda: next(ticks))
        with tempfile.TemporaryDirectory() as directory:
            meter = runtime.GuardedWorkspaceMeter(
                Path(directory) / "workspace",
                runtime_guard=guard,
            )
            meter.bootstrap()
            self.assertGreaterEqual(meter.checkpoint("synthetic"), 0)


class EvidenceStateTests(unittest.TestCase):
    def state(self) -> runtime.ExecutionEvidenceState:
        return runtime.ExecutionEvidenceState(targets(), small_limits())

    def test_transport_and_parse_lifecycle_is_exact_and_one_request_only(self) -> None:
        state = self.state()
        state.mark_request_sent(0)
        with self.assertRaises(runtime.R11ARuntimeError):
            state.mark_request_sent(0)
        state.mark_response_metadata(0, etag='"etag-0"', content_length=10)
        state.mark_body_progress(0, 10)
        state.mark_body_complete(0, "1".zfill(64))
        state.mark_first_parse(0, {"decompressed_byte_count": 100})
        state.mark_second_parse(0, {"decompressed_byte_count": 100})
        row = state.object_rows()[0]
        self.assertEqual(row["processing_status"], "COMPLETE_TWO_LOCAL_PASSES")
        self.assertEqual(row["last_completed_stage"], "SECOND_LOCAL_PARSE_COMPLETE")
        self.assertEqual(row["get_object_request_count"], 1)
        self.assertEqual(row["retry_count"], 0)

    def test_partial_body_failure_and_stop_ledger_are_truthful(self) -> None:
        state = self.state()
        state.mark_request_sent(0)
        state.mark_response_metadata(0, etag='"etag-0"', content_length=10)
        state.mark_body_progress(0, 4)
        state.trigger(
            "HTTP_OR_REQUESTER_PAYS_FAILURE",
            phase="AFTER_EACH_REQUEST_ATTEMPT",
            inputs={"first_failed_object_ordinal": 0},
        )
        row = state.object_rows()[0]
        self.assertEqual(row["processing_status"], "BODY_READ_FAILED_AFTER_RESPONSE_METADATA")
        self.assertEqual(row["compressed_response_body_bytes_received"], 4)
        stops = state.stop_rows()
        self.assertEqual(
            [item["stop_condition"] for item in stops if item["evaluation_status"] == "TRIGGERED"],
            ["HTTP_OR_REQUESTER_PAYS_FAILURE"],
        )


class FailureArtifactTests(unittest.TestCase):
    def test_failure_always_seals_minimal_complete_package(self) -> None:
        frozen = small_limits()
        state = runtime.ExecutionEvidenceState(targets(), frozen)
        state.mark_request_sent(0)
        state.mark_response_metadata(0, etag='"etag-0"', content_length=10)
        state.mark_body_progress(0, 4)
        state.trigger(
            "HTTP_OR_REQUESTER_PAYS_FAILURE",
            phase="AFTER_EACH_REQUEST_ATTEMPT",
            inputs={"first_failed_object_ordinal": 0},
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            meter = storage.WorkspaceMeter(root / "workspace", frozen)
            meter.bootstrap()
            artifact = root / "artifact"
            result = failure.seal_minimal_failure_artifact(
                artifact_directory=artifact,
                meter=meter,
                state=state,
                context={"schema_version": "R11A_EXECUTION_CONTEXT_V1"},
                failure_class="R11ACollectorError",
                failure_message="sensitive synthetic failure",
                elapsed_runtime_milliseconds=123,
                limits=frozen,
            )
            self.assertEqual(result["terminal_class"], "R11A_DIAGNOSTIC_INCOMPLETE")
            self.assertEqual(result["root_cause_claim_status"], "NOT_PROVEN")
            self.assertEqual((artifact / "r11a.rc").read_bytes(), b"21\n")
            self.assertEqual((artifact / "r11a-wallet-features.ndjson").read_bytes(), b"")
            for _, path in schema.SCIENTIFIC_CONTAINERS:
                self.assertEqual((artifact / path).read_bytes(), b"")
            self.assertEqual(
                len((artifact / "r11a-reducer-partition-conservation.ndjson").read_text().splitlines()),
                512,
            )
            context = json.loads((artifact / "r11a-context.json").read_text())
            self.assertNotIn("sensitive synthetic failure", (artifact / "r11a-context.json").read_text())
            self.assertEqual(
                context["terminal_failure_message_sha256"],
                hashlib.sha256(b"sensitive synthetic failure").hexdigest(),
            )
            files = {
                item.name: item.read_bytes()
                for item in artifact.iterdir()
                if item.name not in {"R11A_FILES.sha256", "r11a-package-boundary.txt"}
            }
            schema.verify_hash_manifest((artifact / "R11A_FILES.sha256").read_bytes(), files)
            schema.verify_package_boundary((artifact / "r11a-package-boundary.txt").read_bytes())


if __name__ == "__main__":
    unittest.main()
