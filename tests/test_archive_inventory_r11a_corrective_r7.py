from __future__ import annotations

import dataclasses
import inspect
import tempfile
import unittest
from pathlib import Path

from governance.validate_r11a_execution_artifact_r7 import validate_science
from research.archive_inventory.r11a_corrective.artifact import (
    ArtifactSession,
    validate_artifact,
)
from research.archive_inventory.r11a_corrective.artifact_schema import (
    AUTHORITATIVE_UNIT_UNIVERSES,
    DIAGNOSTIC_ID,
    IMPLEMENTATION_ID,
    SCIENCE_CONTAINERS,
    TAXA,
)
from research.archive_inventory.r11a_corrective.canonical import (
    CanonicalJSONError,
    NumberToken,
    canonical_json_bytes,
    mathematically_integral_number,
    strict_json_loads,
)
from research.archive_inventory.r11a_corrective.join_r7 import (
    DiskJoinLedger,
    JoinBoundaryError,
    JoinValidationResult,
)
from research.archive_inventory.r11a_corrective.limits import DEFAULT_LIMITS
from research.archive_inventory.r11a_corrective.meter_r7 import R7WorkspaceMeter
from research.archive_inventory.r11a_corrective.preflight_artifact_r7 import (
    write_preflight_failure_artifact,
)
from research.archive_inventory.r11a_corrective.runtime import (
    ExecutionEvidenceState,
    RuntimeGuard,
)
from research.archive_inventory.r11a_corrective.selection import DEFAULT_SELECTION
from research.archive_inventory.r11a_corrective.storage_r7 import (
    ExactSQLiteMultiplicityLedger,
    StorageBoundaryError,
)
from research.archive_inventory.r11a_corrective.taxonomy import (
    TaxonomyResult,
    Taxon,
    UnitUniverse,
)


class CanonicalR7Tests(unittest.TestCase):
    def test_extreme_integral_exponents_are_bounded_before_expansion(self) -> None:
        with self.assertRaises(CanonicalJSONError):
            mathematically_integral_number(NumberToken("1e100000000", False))
        self.assertEqual(
            mathematically_integral_number(NumberToken("0e-100000000", False)),
            "0",
        )
        self.assertEqual(
            mathematically_integral_number(NumberToken("-0.000e+999", False)),
            "0",
        )

    def test_canonical_mapping_is_deeply_immutable_and_utf8_sorted(self) -> None:
        left = strict_json_loads(b'{"z":{"b":2,"a":1},"a":0}')
        right = strict_json_loads(b'{"a":0,"z":{"a":1,"b":2}}')
        self.assertEqual(canonical_json_bytes(left), canonical_json_bytes(right))
        with self.assertRaises(TypeError):
            left["a"] = "mutated"  # type: ignore[index]


class ExactDiskEvidenceTests(unittest.TestCase):
    def meter(self, root: Path) -> R7WorkspaceMeter:
        guard = RuntimeGuard(DEFAULT_LIMITS)
        meter = R7WorkspaceMeter(root, DEFAULT_LIMITS, guard)
        meter.bootstrap()
        return meter

    def test_exact_sqlite_blob_multiplicity_detects_loss_and_duplication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            ledger = ExactSQLiteMultiplicityLedger(
                meter.root / "multiplicity.sqlite",
                meter,
                maximum_source_bytes=1024,
            )
            ledger.add_source_batch((b"a", b"a", b"b"))
            ledger.add_destination_batch((b"a", b"b", b"b"))
            with self.assertRaises(StorageBoundaryError):
                ledger.validate()
            ledger.close_delete()

    def test_disk_join_requires_exact_foreign_keys_projections_and_row_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            unit_projection = b"unit"
            proof_projection = b"proof"
            joins.add_unit("u", "LEGACY_REPEAT_OCCURRENCE", 1, unit_projection)
            joins.add_proof("p", "proof-type", proof_projection)
            joins.add_reference(
                "u", "p", "proof-type", unit_projection, proof_projection
            )
            joins.add_retained_row("r", "u", unit_projection)
            result = joins.validate()
            self.assertTrue(
                result.all_nonnull_proof_references_resolve_exactly_once
            )
            self.assertTrue(result.all_referenced_projections_are_byte_equal)
            self.assertTrue(
                result.all_retained_row_counts_match_unit_occurrence_counts
            )
            joins.close_delete()

    def test_duplicate_unit_ids_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            joins.add_unit("u", "LEGACY_REPEAT_OCCURRENCE", 1, b"one")
            joins.add_unit("u", "LEGACY_REPEAT_OCCURRENCE", 1, b"two")
            with self.assertRaises(JoinBoundaryError):
                joins.validate()
            joins.database.close_delete()


class ArtifactCompatibilityTests(unittest.TestCase):
    @staticmethod
    def zero_universes() -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "unit_universe": universe,
                "group_count": 0,
                "occurrence_count": 0,
                "primary_taxon_group_counts": {},
                "primary_taxon_occurrence_counts": {},
                "unclassifiable_group_count": 0,
                "unclassifiable_occurrence_count": 0,
            }
            for universe in AUTHORITATIVE_UNIT_UNIVERSES
        )

    def test_pre_oidc_failure_artifact_passes_same_external_validator_as_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            context = {
                "event_name": "workflow_dispatch",
                "dispatch_ref": "refs/heads/main",
                "dispatch_sha": "1" * 40,
                "checked_out_commit": "1" * 40,
                "workflow_run_id": 1,
                "workflow_run_attempt": 1,
                "repository": "Mathisve1/onchain-wallet-intelligence-lab",
                "workflow_name": "Hyperliquid Archive R11A Identity Boundary Diagnostic",
                "principal_observed": False,
            }
            artifact = write_preflight_failure_artifact(
                workspace=workspace,
                context=context,
                failure_code="PRE_OIDC_STATIC_GATE_FAILURE",
                execution_phase="PRE_OIDC_STATIC_GATE",
            )
            validate_artifact(artifact, DEFAULT_LIMITS)
            validate_science(artifact)
            self.assertEqual((artifact / "r11a-v2.rc").read_text(), "21\n")
            for name in SCIENCE_CONTAINERS:
                self.assertEqual((artifact / name).read_bytes(), b"")

    def test_fully_materialized_incomplete_artifact_uses_rc20_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            guard = RuntimeGuard(DEFAULT_LIMITS)
            meter = R7WorkspaceMeter(workspace, DEFAULT_LIMITS, guard)
            meter.bootstrap()
            state = ExecutionEvidenceState(DEFAULT_SELECTION.targets, DEFAULT_LIMITS)
            session = ArtifactSession(workspace, meter, DEFAULT_LIMITS, guard)
            joins = JoinValidationResult(
                unit_count=0,
                proof_count=0,
                proof_reference_count=0,
                retained_row_reference_count=0,
                all_unit_ids_unique=True,
                all_proof_ids_unique=True,
                all_nonnull_proof_references_resolve_exactly_once=True,
                all_retained_rows_reference_exactly_one_unit=True,
                all_referenced_projections_are_byte_equal=True,
                all_retained_row_counts_match_unit_occurrence_counts=True,
            )
            taxonomy = TaxonomyResult(
                universe_rows=self.zero_universes(),
                secondary_reducer_rows=(),
                join_validation=joins,
                repeated_block_group_count=0,
                repeated_block_observation_count=0,
                legacy_repeat_group_count=0,
                legacy_repeat_observation_count=0,
                legacy_repeat_occurrence_count=0,
                valid_tid_legacy_repeat_occurrence_count=0,
                invalid_tid_legacy_repeat_occurrence_count=0,
                supporting_taxon_counts={taxon: 0 for taxon in TAXA},
                exact_three_utc_days=False,
            )
            outcome = session.finalize_full(
                state=state,
                context={"test_fixture": "full-incomplete"},
                reducer_rows=(),
                resource_rows=(),
                terminal_class="R11A_V2_DIAGNOSTIC_INCOMPLETE",
                research_conclusion="ROOT_CAUSE_NOT_FULLY_PROVEN_NO_REPAIR_AUTHORIZED",
                taxonomy_result=taxonomy,
            )
            self.assertEqual(outcome.return_code, 20)
            validate_artifact(outcome.final_directory, DEFAULT_LIMITS)
            validate_science(outcome.final_directory)


class FrozenTaxonomyAndWorkflowTests(unittest.TestCase):
    def test_exact_authoritative_universes_and_taxa(self) -> None:
        self.assertEqual(tuple(value.value for value in UnitUniverse), AUTHORITATIVE_UNIT_UNIVERSES)
        self.assertEqual(tuple(value.value for value in Taxon), TAXA)
        self.assertEqual(DIAGNOSTIC_ID, "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-002")
        self.assertEqual(
            IMPLEMENTATION_ID,
            "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-CORRECTIVE-R7",
        )

    def test_workflow_has_no_inline_https_and_no_inert_validator(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow = (
            root
            / "research/archive_inventory/r11a_corrective/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r7.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("urllib.request", workflow)
        self.assertNotIn("validate_r11a_corrective_implementation", workflow)
        self.assertIn("validate_r11a_runtime_binding_r7.py", workflow)
        self.assertIn("validate_r11a_execution_artifact_r7.py", workflow)
        self.assertLess(
            workflow.index("validate_r11a_execution_artifact_r7.py"),
            workflow.index("actions/upload-artifact"),
        )

    def test_taxonomy_uses_disk_backed_group_state_not_first_current_shortcuts(self) -> None:
        import research.archive_inventory.r11a_corrective.taxonomy as taxonomy

        source = inspect.getsource(taxonomy)
        self.assertIn("BlockScratch", source)
        self.assertIn("EventScratch", source)
        self.assertNotIn("first/current", source)
        self.assertNotIn("block_rows: list", source)


if __name__ == "__main__":
    unittest.main()
