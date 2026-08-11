from __future__ import annotations

import dataclasses
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.archive_inventory.r11a_implementation import failure, limits, runtime, schema, storage


def state_and_limits() -> tuple[runtime.ExecutionEvidenceState, limits.R11ALimits]:
    small = dataclasses.replace(
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
    targets = tuple(
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
    return runtime.ExecutionEvidenceState(targets, small), small


class R11AFailureArtifactTests(unittest.TestCase):
    def test_partial_transport_failure_seals_complete_minimal_package(self) -> None:
        state, frozen = state_and_limits()
        state.mark_request_sent(0)
        state.mark_response_metadata(0, etag='"etag-0"', content_length=10)
        state.mark_body_progress(0, 4)
        state.trigger(
            "HTTP_OR_REQUESTER_PAYS_FAILURE",
            phase="AFTER_EACH_REQUEST_ATTEMPT",
            inputs={
                "first_failed_object_ordinal": 0,
                "first_failed_processing_status": "BODY_READ_FAILED_AFTER_RESPONSE_METADATA",
                "requester_pays_header_required": True,
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            meter = storage.WorkspaceMeter(workspace, frozen)
            meter.bootstrap()
            artifact = root / "artifact"
            result = failure.seal_minimal_failure_artifact(
                artifact_directory=artifact,
                meter=meter,
                state=state,
                context={
                    "schema_version": "R11A_EXECUTION_CONTEXT_V1",
                    "diagnostic_id": "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-001",
                },
                failure_class="R11ACollectorError",
                failure_message="synthetic body failure",
                elapsed_runtime_milliseconds=123,
                limits=frozen,
            )
            self.assertEqual(result["terminal_class"], "R11A_DIAGNOSTIC_INCOMPLETE")
            self.assertEqual(result["root_cause_claim_status"], "NOT_PROVEN")
            self.assertEqual((artifact / "r11a.rc").read_bytes(), b"21\n")
            self.assertEqual((artifact / "r11a-wallet-features.ndjson").read_bytes(), b"")
            for _, path in schema.SCIENTIFIC_CONTAINERS:
                self.assertEqual((artifact / path).read_bytes(), b"")
            object_rows = [
                json.loads(line)
                for line in (artifact / "r11a-object-two-pass-conservation.ndjson").read_text().splitlines()
            ]
            self.assertEqual(len(object_rows), 3)
            self.assertEqual(object_rows[0]["processing_status"], "BODY_READ_FAILED_AFTER_RESPONSE_METADATA")
            self.assertEqual(object_rows[0]["compressed_response_body_bytes_received"], 4)
            self.assertEqual(object_rows[1]["processing_status"], "UNATTEMPTED_AFTER_FAIL_CLOSED_STOP")
            reducer_rows = (artifact / "r11a-reducer-partition-conservation.ndjson").read_text().splitlines()
            self.assertEqual(len(reducer_rows), 512)
            stop_rows = json.loads((artifact / "r11a-preflight-stop-evidence.json").read_text())
            self.assertEqual(
                [row["stop_condition"] for row in stop_rows if row["evaluation_status"] == "TRIGGERED"],
                ["HTTP_OR_REQUESTER_PAYS_FAILURE"],
            )
            files = {
                path.name: path.read_bytes()
                for path in artifact.iterdir()
                if path.name not in {"R11A_FILES.sha256", "r11a-package-boundary.txt"}
            }
            schema.verify_hash_manifest(
                (artifact / "R11A_FILES.sha256").read_bytes(),
                files,
            )
            schema.verify_package_boundary(
                (artifact / "r11a-package-boundary.txt").read_bytes()
            )

    def test_failure_message_is_hash_bound_not_retained_verbatim(self) -> None:
        state, frozen = state_and_limits()
        state.trigger(
            "RUNTIME_CAP_REACHED",
            phase="DURING_PARSE",
            inputs={"reserved_runtime_observed_milliseconds": 600000},
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            meter = storage.WorkspaceMeter(root / "workspace", frozen)
            meter.bootstrap()
            secret = "do-not-retain-this-message"
            artifact = root / "artifact"
            failure.seal_minimal_failure_artifact(
                artifact_directory=artifact,
                meter=meter,
                state=state,
                context={"schema_version": "R11A_EXECUTION_CONTEXT_V1"},
                failure_class="R11ARuntimeError",
                failure_message=secret,
                elapsed_runtime_milliseconds=500000,
                limits=frozen,
            )
            context = json.loads((artifact / "r11a-context.json").read_text())
            self.assertNotIn(secret, (artifact / "r11a-context.json").read_text())
            self.assertEqual(
                context["terminal_failure_message_sha256"],
                hashlib.sha256(secret.encode()).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
