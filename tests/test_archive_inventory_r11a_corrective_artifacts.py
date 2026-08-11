from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research.archive_inventory.r11a_corrective.artifact_r3 import (
    ArtifactSession,
    SCIENCE_CONTAINERS,
    validate_artifact,
)
from research.archive_inventory.r11a_corrective.limits import DEFAULT_LIMITS
from research.archive_inventory.r11a_corrective.runtime import (
    ExecutionEvidenceState,
    RuntimeGuard,
    RuntimeTarget,
)
from research.archive_inventory.r11a_corrective.storage import (
    AtomicArtifactDirectory,
    MultisetCommitment,
    ReservedBinaryWriter,
    SortEvidence,
    StorageBoundaryError,
    WorkspaceMeter,
)
from research.archive_inventory.r11a_corrective.taxonomy_r4 import TaxonomyResult


class CorrectiveArtifactTests(unittest.TestCase):
    @staticmethod
    def targets() -> tuple[RuntimeTarget, ...]:
        return tuple(
            RuntimeTarget(
                object_ordinal_zero_based=index,
                object_key=f"node_fills_by_block/hourly/202507{28 + index // 24:02d}/{index % 24}.lz4",
                expected_size_bytes=1,
                expected_etag='"' + f"{index:032x}" + '"',
                expected_compressed_sha256=f"{index:064x}",
                source_path_hour_utc=f"2025-07-{28 + index // 24:02d}T{index % 24:02d}:00:00Z",
            )
            for index in range(72)
        )

    @staticmethod
    def context() -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "workflow_run_id": 123456,
            "workflow_run_attempt": 1,
            "dispatch_ref": "refs/heads/main",
            "dispatch_sha": "1" * 40,
            "checked_out_commit": "1" * 40,
            "rerun_authorized": False,
        }

    def prepared(self, root: Path):
        guard = RuntimeGuard(DEFAULT_LIMITS, monotonic_ns=lambda: 0)
        meter = WorkspaceMeter(root, DEFAULT_LIMITS, guard)
        meter.bootstrap()
        state = ExecutionEvidenceState(self.targets(), DEFAULT_LIMITS)
        session = ArtifactSession(root, meter, DEFAULT_LIMITS)
        return guard, meter, state, session

    def test_every_early_failure_has_exact_empty_science_and_complete_ledgers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            _, _, state, session = self.prepared(root)
            state.stop("SYNTHETIC_PRECOLLECTOR_FAILURE", phase="PRECOLLECTOR", evidence={})
            outcome = session.finalize_empty(
                state=state,
                context=self.context(),
                reducer_rows=(),
                resource_rows=(
                    {
                        "record_type": "RESOURCE_MEASUREMENT",
                        "phase": "PRECOLLECTOR",
                        "elapsed_runtime_seconds_floor": 0,
                        "tracked_workspace_bytes": 0,
                        "reserved_workspace_bytes": 0,
                        "network_request_count": 0,
                    },
                ),
                terminal_class="R11A_DIAGNOSTIC_INCOMPLETE",
                research_conclusion="ROOT_CAUSE_NOT_PROVEN_FAIL_CLOSED_EMPTY_ARTIFACT",
                return_code=21,
            )
            validate_artifact(outcome.final_directory, DEFAULT_LIMITS)
            for name in SCIENCE_CONTAINERS:
                self.assertEqual((outcome.final_directory / name).read_bytes(), b"")
            self.assertEqual(
                len((outcome.final_directory / "r11a-object-ledger.ndjson").read_bytes().splitlines()),
                72,
            )
            self.assertEqual(
                len((outcome.final_directory / "r11a-reducer-ledger.ndjson").read_bytes().splitlines()),
                512,
            )

    def test_fully_materialized_incomplete_science_is_not_labeled_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            _, _, state, session = self.prepared(root)
            session.emitter.emit(
                "r11a-taxonomy-units.ndjson",
                {
                    "record_type": "TAXONOMY_UNIT",
                    "taxonomy_unit_id": "a" * 64,
                    "unit_universe": "LEGACY_WEAK_KEY_REPEAT",
                    "equality_key_sha256": "b" * 64,
                    "primary_taxon": "UNCLASSIFIABLE",
                    "occurrence_count": 2,
                    "proof_references": [],
                },
            )
            universe_rows = tuple(
                {
                    "unit_universe": universe,
                    "group_count": 1 if universe == "LEGACY_WEAK_KEY_REPEAT" else 0,
                    "occurrence_count": 2 if universe == "LEGACY_WEAK_KEY_REPEAT" else 0,
                    "taxon_group_counts": {"UNCLASSIFIABLE": 1} if universe == "LEGACY_WEAK_KEY_REPEAT" else {},
                    "taxon_occurrence_counts": {"UNCLASSIFIABLE": 2} if universe == "LEGACY_WEAK_KEY_REPEAT" else {},
                    "unclassifiable_group_count": 1 if universe == "LEGACY_WEAK_KEY_REPEAT" else 0,
                    "unclassifiable_occurrence_count": 2 if universe == "LEGACY_WEAK_KEY_REPEAT" else 0,
                }
                for universe in (
                    "BLOCK_NUMBER_REPEAT",
                    "LEGACY_WEAK_KEY_REPEAT",
                    "WALLET_FILL_REPEAT",
                    "PROTOCOL_TRADE_GROUP",
                )
            )
            taxonomy = TaxonomyResult(
                conservation_rows=universe_rows,
                secondary_sort_rows=(),
                join_partition_rows=(),
                block_proof_count=0,
                pair_proof_count=0,
                proof_reference_count=0,
                all_proof_references_resolve=True,
                all_unit_ids_unique=True,
                all_duplicate_rows_reference_one_unit=True,
                terminal_unclassifiable_group_count=1,
                terminal_unclassifiable_occurrence_count=2,
            )
            state.stop(
                "FULLY_MATERIALIZED_TAXONOMY_INCOMPLETE",
                phase="FINAL_SCIENTIFIC_VALIDATION",
                evidence={"unclassifiable_group_count": 1},
            )
            outcome = session.finalize_full(
                state=state,
                context=self.context(),
                reducer_rows=(),
                resource_rows=(
                    {
                        "record_type": "RESOURCE_MEASUREMENT",
                        "phase": "SCIENCE_COMPLETE_BEFORE_PACKAGING",
                        "elapsed_runtime_seconds_floor": 0,
                        "tracked_workspace_bytes": 0,
                        "reserved_workspace_bytes": 0,
                        "network_request_count": 0,
                        "aggregate_parse_conservation": {
                            "status": "EXACT_TWO_PASS_LAYER_CONSERVATION_PASS",
                            "first_pass_totals": {},
                            "second_pass_totals": {},
                        },
                    },
                ),
                terminal_class="R11A_DIAGNOSTIC_INCOMPLETE",
                research_conclusion="ROOT_CAUSE_NOT_FULLY_PROVEN_NO_REPAIR_AUTHORIZED",
                return_code=20,
                taxonomy_result=taxonomy,
            )
            validate_artifact(outcome.final_directory, DEFAULT_LIMITS)
            result = json.loads((outcome.final_directory / "r11a-result.json").read_text())
            self.assertEqual(result["scientific_container_status"], "FULLY_MATERIALIZED")
            self.assertGreater(
                (outcome.final_directory / "r11a-taxonomy-units.ndjson").stat().st_size,
                0,
            )

    def test_atomic_commit_never_exposes_final_directory_when_validator_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            guard = RuntimeGuard(DEFAULT_LIMITS, monotonic_ns=lambda: 0)
            meter = WorkspaceMeter(root, DEFAULT_LIMITS, guard)
            meter.bootstrap()
            atomic = AtomicArtifactDirectory(root, meter, "final")
            with self.assertRaisesRegex(RuntimeError, "synthetic validator failure"):
                with atomic as staging:
                    writer = ReservedBinaryWriter(
                        staging / "payload.bin",
                        meter,
                        maximum_bytes=4,
                        label="synthetic payload",
                    )
                    writer.write(b"data")
                    writer.close()
                    atomic.commit(
                        lambda _: (_ for _ in ()).throw(
                            RuntimeError("synthetic validator failure")
                        )
                    )
            self.assertFalse((root / "final").exists())
            self.assertFalse((root / ".final.staging").exists())


class CorrectiveMultisetTests(unittest.TestCase):
    def test_multiplicity_sensitive_commitment_detects_record_loss_or_duplication(self) -> None:
        first = MultisetCommitment()
        second = MultisetCommitment()
        third = MultisetCommitment()
        for record in (b"a", b"b", b"b"):
            first.add(record)
        for record in (b"b", b"a", b"b"):
            second.add(record)
        for record in (b"a", b"b"):
            third.add(record)
        self.assertEqual(first.as_mapping(), second.as_mapping())
        self.assertNotEqual(first.as_mapping(), third.as_mapping())
        SortEvidence(
            input_records=3,
            output_records=3,
            input_logical_bytes=3,
            output_logical_bytes=3,
            source_commitment=first.as_mapping(),
            destination_commitment=second.as_mapping(),
            sorted_stream_sha256="0" * 64,
            output_bytes=3,
        ).validate()
        with self.assertRaises(StorageBoundaryError):
            SortEvidence(
                input_records=3,
                output_records=2,
                input_logical_bytes=3,
                output_logical_bytes=2,
                source_commitment=first.as_mapping(),
                destination_commitment=third.as_mapping(),
                sorted_stream_sha256="0" * 64,
                output_bytes=2,
            ).validate()


class CorrectiveWorkflowTests(unittest.TestCase):
    def test_candidate_separates_stages_and_validates_before_upload(self) -> None:
        root = Path(__file__).resolve().parents[1]
        candidate = root / "research/archive_inventory/r11a_corrective/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r3.yml"
        text = candidate.read_text(encoding="utf-8")
        self.assertIn("validate_r11a_corrective_implementation.py --approval-eligible", text)
        self.assertNotIn("validate_r11a_implementation.py", text)
        self.assertEqual(text.count("aws sts get-caller-identity --output json"), 1)
        self.assertNotIn("aws s3 ", text.lower())
        self.assertLess(
            text.index("Validate complete artifact before any upload"),
            text.index("Upload only the already validated R11A artifact"),
        )
        self.assertLess(text.index("free-space threshold"), text.index("configure-aws-credentials"))


if __name__ == "__main__":
    unittest.main()
