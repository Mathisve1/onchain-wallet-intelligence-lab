from __future__ import annotations

import hashlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from governance.validate_r11a_execution_artifact_r7 import (
    EvidenceValidationError,
    validate_science,
)
from governance.validate_r11a_runtime_binding_r7 import (
    BINDING,
    RuntimeBindingError,
    validate as validate_runtime_binding,
)
from research.archive_inventory.r11a_corrective.artifact import (
    SharedMetadataWriter,
    StreamingScientificEmitter,
    ArtifactSession,
    validate_artifact,
)
from research.archive_inventory.r11a_corrective.artifact_schema import (
    AUTHORITATIVE_UNIT_UNIVERSES,
    BOUNDARY_FILE,
    CONSERVATION_FILE,
    DIAGNOSTIC_ID,
    IMPLEMENTATION_ID,
    SCIENCE_CONTAINERS,
    TAXA,
    zero_taxon_counts,
)
from research.archive_inventory.r11a_corrective.canonical import (
    CanonicalJSONError,
    NumberToken,
    canonical_json_bytes,
    mathematically_integral_number,
    strict_json_loads,
)
from research.archive_inventory.r11a_corrective.identity import frame
from research.archive_inventory.r11a_corrective.join_r7 import (
    DiskJoinLedger,
    JoinBoundaryError,
    JoinValidationResult,
)
from research.archive_inventory.r11a_corrective.limits import (
    DEFAULT_LIMITS,
    PREREGISTRATION_PATH,
    SELECTION_PATH,
)
from research.archive_inventory.r11a_corrective.meter_r7 import R7WorkspaceMeter
from research.archive_inventory.r11a_corrective.preflight_artifact_r7 import (
    write_preflight_failure_artifact,
)
from research.archive_inventory.r11a_corrective.runtime import (
    ExecutionEvidenceState,
    RuntimeGuard,
)
from research.archive_inventory.r11a_corrective.selection import (
    DEFAULT_SELECTION,
    R11_RESULT_PATH,
    SelectionError,
    load_selection,
)
from research.archive_inventory.r11a_corrective.storage_r7 import (
    AtomicArtifactDirectory,
    ExactSQLiteMultiplicityLedger,
    ReservedBinaryWriter,
    StorageBoundaryError,
    directory_size,
)
from research.archive_inventory.r11a_corrective.taxonomy import (
    TaxonomyResult,
    Taxon,
    UnitUniverse,
)

UNIT_FILE = "r11a-v2-taxonomy-units.ndjson"
LEGACY_ROWS_FILE = "r11a-v2-duplicate-observations.ndjson"


def fixture_unit_projection(
    *,
    occurrence_count: int = 1,
    key_value: str = "fixture",
    unit_universe: str = "LEGACY_REPEAT_OCCURRENCE",
    primary_taxon: str = "TID_SCOPE_FALSE_POSITIVE",
) -> bytes:
    return canonical_json_bytes(
        {
            "diagnostic_id": DIAGNOSTIC_ID,
            "unit_universe": unit_universe,
            "key_projection": {"fixture": key_value},
            "primary_taxon": primary_taxon,
            "occurrence_count": occurrence_count,
        },
        final_newline=False,
    )


def zero_universe_rows() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "unit_universe": universe,
            "group_count": 0,
            "occurrence_count": 0,
            "primary_taxon_group_counts": zero_taxon_counts(),
            "primary_taxon_occurrence_counts": zero_taxon_counts(),
            "unclassifiable_group_count": 0,
            "unclassifiable_occurrence_count": 0,
        }
        for universe in AUTHORITATIVE_UNIT_UNIVERSES
    )


def one_legacy_universe_rows() -> tuple[dict[str, object], ...]:
    rows = [dict(row) for row in zero_universe_rows()]
    group_counts = zero_taxon_counts()
    occurrence_counts = zero_taxon_counts()
    group_counts["TID_SCOPE_FALSE_POSITIVE"] = 1
    occurrence_counts["TID_SCOPE_FALSE_POSITIVE"] = 1
    rows[0] = {
        "unit_universe": "LEGACY_REPEAT_OCCURRENCE",
        "group_count": 1,
        "occurrence_count": 1,
        "primary_taxon_group_counts": group_counts,
        "primary_taxon_occurrence_counts": occurrence_counts,
        "unclassifiable_group_count": 0,
        "unclassifiable_occurrence_count": 0,
    }
    return tuple(rows)


def one_universe_rows(
    unit_universe: str,
    primary_taxon: str,
) -> tuple[dict[str, object], ...]:
    rows = [dict(row) for row in zero_universe_rows()]
    ordinal = AUTHORITATIVE_UNIT_UNIVERSES.index(unit_universe)
    group_counts = zero_taxon_counts()
    occurrence_counts = zero_taxon_counts()
    group_counts[primary_taxon] = 1
    occurrence_counts[primary_taxon] = 1
    rows[ordinal] = {
        "unit_universe": unit_universe,
        "group_count": 1,
        "occurrence_count": 1,
        "primary_taxon_group_counts": group_counts,
        "primary_taxon_occurrence_counts": occurrence_counts,
        "unclassifiable_group_count": int(primary_taxon == "UNCLASSIFIABLE"),
        "unclassifiable_occurrence_count": int(primary_taxon == "UNCLASSIFIABLE"),
    }
    return tuple(rows)


class CanonicalR7Tests(unittest.TestCase):
    def test_extreme_integral_exponents_are_bounded_before_expansion(self) -> None:
        with self.assertRaises(CanonicalJSONError):
            mathematically_integral_number(
                NumberToken("1e100000000", False)
            )
        self.assertEqual(
            mathematically_integral_number(
                NumberToken("0e-100000000", False)
            ),
            "0",
        )
        self.assertEqual(
            mathematically_integral_number(
                NumberToken("-0.000e+999", False)
            ),
            "0",
        )

    def test_canonical_mapping_is_deeply_immutable_and_utf8_sorted(self) -> None:
        left = strict_json_loads(b'{"z":{"b":2,"a":1},"a":0}')
        right = strict_json_loads(b'{"a":0,"z":{"a":1,"b":2}}')
        self.assertEqual(canonical_json_bytes(left), canonical_json_bytes(right))
        with self.assertRaises(TypeError):
            left["a"] = "mutated"  # type: ignore[index]


class SelectionBindingTests(unittest.TestCase):
    def test_exact_72_targets_are_bound_to_prior_r11_compressed_hashes(self) -> None:
        self.assertEqual(len(DEFAULT_SELECTION.targets), 72)
        self.assertEqual(
            sum(target.expected_size_bytes for target in DEFAULT_SELECTION.targets),
            2_107_738_436,
        )
        self.assertEqual(
            len(
                {
                    target.expected_compressed_sha256
                    for target in DEFAULT_SELECTION.targets
                }
            ),
            72,
        )

    def test_tampered_prior_r11_result_is_rejected_before_target_loading(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "r11-result.json"
            tampered.write_bytes(R11_RESULT_PATH.read_bytes() + b"\n")
            with self.assertRaises(SelectionError):
                load_selection(
                    path=SELECTION_PATH,
                    prior_result_path=tampered,
                    preregistration_path=PREREGISTRATION_PATH,
                )


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
            unit_projection = fixture_unit_projection()
            proof_projection = b"proof"
            joins.add_unit(
                "u",
                "LEGACY_REPEAT_OCCURRENCE",
                1,
                unit_projection,
            )
            joins.add_proof("p", "proof-type", proof_projection)
            joins.add_reference(
                "u",
                "p",
                "proof-type",
                unit_projection,
                proof_projection,
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

    def test_retained_row_loss_is_detected_for_every_unit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            projection = fixture_unit_projection(occurrence_count=2)
            joins.add_unit(
                "u",
                "LEGACY_REPEAT_OCCURRENCE",
                2,
                projection,
            )
            joins.add_retained_row("r1", "u", projection)
            result = joins.validate()
            self.assertFalse(
                result.all_retained_row_counts_match_unit_occurrence_counts
            )
            joins.close_delete()

    def test_wrong_retained_projection_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            projection = fixture_unit_projection()
            joins.add_unit(
                "u",
                "LEGACY_REPEAT_OCCURRENCE",
                1,
                projection,
            )
            joins.add_retained_row("r", "u", b"wrong-projection")
            result = joins.validate()
            self.assertFalse(result.all_referenced_projections_are_byte_equal)
            joins.close_delete()

    def test_dangling_proof_reference_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            projection = fixture_unit_projection()
            joins.add_unit(
                "u",
                "LEGACY_REPEAT_OCCURRENCE",
                1,
                projection,
            )
            joins.add_reference(
                "u",
                "missing",
                "proof-type",
                projection,
                b"missing-proof",
            )
            joins.add_retained_row("r", "u", projection)
            result = joins.validate()
            self.assertFalse(
                result.all_nonnull_proof_references_resolve_exactly_once
            )
            joins.close_delete()

    def test_duplicate_unit_ids_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            joins.add_unit(
                "u",
                "LEGACY_REPEAT_OCCURRENCE",
                1,
                fixture_unit_projection(key_value="one"),
            )
            joins.add_unit(
                "u",
                "LEGACY_REPEAT_OCCURRENCE",
                1,
                fixture_unit_projection(key_value="two"),
            )
            with self.assertRaises(JoinBoundaryError):
                joins.validate()
            joins.database.close_delete()

    def test_extra_retained_row_is_detected_for_every_unit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            projection = fixture_unit_projection()
            joins.add_unit("u", "LEGACY_REPEAT_OCCURRENCE", 1, projection)
            joins.add_retained_row("r1", "u", projection)
            joins.add_retained_row("r2", "u", projection)
            result = joins.validate()
            self.assertFalse(
                result.all_retained_row_counts_match_unit_occurrence_counts
            )
            joins.close_delete()

    def test_duplicate_proof_ids_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            joins.add_proof("p", "proof-type", b"one")
            joins.add_proof("p", "proof-type", b"two")
            with self.assertRaises(JoinBoundaryError):
                joins.validate()
            joins.database.close_delete()

    def test_duplicate_proof_foreign_keys_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            projection = fixture_unit_projection()
            joins.add_unit("u", "LEGACY_REPEAT_OCCURRENCE", 1, projection)
            joins.add_proof("p", "proof-type", b"proof")
            for _ in range(2):
                joins.add_reference(
                    "u",
                    "p",
                    "proof-type",
                    projection,
                    b"proof",
                )
            with self.assertRaises(JoinBoundaryError):
                joins.validate()
            joins.database.close_delete()

    def test_wrong_proof_projection_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            projection = fixture_unit_projection()
            joins.add_unit("u", "LEGACY_REPEAT_OCCURRENCE", 1, projection)
            joins.add_proof("p", "proof-type", b"proof")
            joins.add_reference(
                "u",
                "p",
                "proof-type",
                projection,
                b"wrong-proof",
            )
            joins.add_retained_row("r", "u", projection)
            result = joins.validate()
            self.assertFalse(result.all_referenced_projections_are_byte_equal)
            joins.close_delete()

    def test_unreferenced_proof_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            joins = DiskJoinLedger(meter)
            joins.add_proof("p", "proof-type", b"proof")
            result = joins.validate()
            self.assertFalse(
                result.all_nonnull_proof_references_resolve_exactly_once
            )
            joins.close_delete()


class WorkspaceAccountingTests(unittest.TestCase):
    def meter(self, root: Path) -> R7WorkspaceMeter:
        guard = RuntimeGuard(DEFAULT_LIMITS)
        meter = R7WorkspaceMeter(root, DEFAULT_LIMITS, guard)
        meter.bootstrap()
        return meter

    def write_payload(
        self,
        meter: R7WorkspaceMeter,
        path: Path,
        payload: bytes = b"payload",
    ) -> None:
        with ReservedBinaryWriter(
            path,
            meter,
            maximum_bytes=1024,
            label="atomic fixture",
            packaging=True,
            buffer_bytes=1,
        ) as writer:
            writer.write(payload)

    def test_atomic_rename_preserves_identical_bytes_and_accounting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            atomic = AtomicArtifactDirectory(meter.root, meter, "artifact")
            staging = atomic.__enter__()
            self.write_payload(meter, staging / "payload.bin")
            before = (staging / "payload.bin").read_bytes()
            tracked = meter.verify_actual_usage()
            final = atomic.commit(
                lambda candidate: self.assertEqual(
                    (candidate / "payload.bin").read_bytes(),
                    before,
                )
            )
            self.assertEqual((final / "payload.bin").read_bytes(), before)
            self.assertEqual(meter.known_bytes, tracked)
            self.assertEqual(meter.verify_actual_usage(), directory_size(final))
            meter.checked_rmtree(final)
            self.assertEqual(meter.verify_actual_usage(), 0)

    def test_post_rename_runtime_failure_removes_final_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            atomic = AtomicArtifactDirectory(meter.root, meter, "artifact")
            staging = atomic.__enter__()
            self.write_payload(meter, staging / "payload.bin")
            original = RuntimeGuard.check_packaging_phase

            def fail_after_rename(guard: RuntimeGuard, phase: str) -> None:
                if phase == "artifact rename after":
                    raise RuntimeError("injected post-rename runtime failure")
                original(guard, phase)

            with mock.patch.object(
                RuntimeGuard,
                "check_packaging_phase",
                side_effect=fail_after_rename,
                autospec=True,
            ):
                with self.assertRaises(RuntimeError):
                    atomic.commit(lambda _: None)
            self.assertFalse(atomic.final_path.exists())
            self.assertFalse(atomic.staging_path.exists())
            self.assertEqual(meter.verify_actual_usage(), 0)

    def test_post_rename_workspace_failure_removes_final_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            atomic = AtomicArtifactDirectory(meter.root, meter, "artifact")
            staging = atomic.__enter__()
            self.write_payload(meter, staging / "payload.bin")
            tracked = meter.known_bytes
            with mock.patch.object(
                meter,
                "verify_actual_usage",
                side_effect=(
                    tracked,
                    StorageBoundaryError("injected post-rename workspace failure"),
                ),
            ):
                with self.assertRaises(StorageBoundaryError):
                    atomic.commit(lambda _: None)
            self.assertFalse(atomic.final_path.exists())
            self.assertFalse(atomic.staging_path.exists())
            self.assertEqual(meter.verify_actual_usage(), 0)

    def test_final_directory_cleanup_failure_remains_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            atomic = AtomicArtifactDirectory(meter.root, meter, "artifact")
            staging = atomic.__enter__()
            self.write_payload(meter, staging / "payload.bin")
            original = RuntimeGuard.check_packaging_phase

            def fail_after_rename(guard: RuntimeGuard, phase: str) -> None:
                if phase == "artifact rename after":
                    raise RuntimeError("injected post-rename runtime failure")
                original(guard, phase)

            with mock.patch.object(
                RuntimeGuard,
                "check_packaging_phase",
                side_effect=fail_after_rename,
                autospec=True,
            ), mock.patch(
                "research.archive_inventory.r11a_corrective.storage_r7.shutil.rmtree",
                side_effect=OSError("injected cleanup failure"),
            ):
                with self.assertRaises(OSError):
                    atomic.commit(lambda _: None)
            self.assertTrue(atomic.final_path.exists())
            meter.checked_rmtree(atomic.final_path)
            self.assertEqual(meter.verify_actual_usage(), 0)

    def test_metadata_close_and_shared_directory_reservations_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            staging = meter.root / "staging"
            staging.mkdir()
            science = StreamingScientificEmitter(staging, meter, DEFAULT_LIMITS)
            science.emit(UNIT_FILE, {"fixture": "science"})
            science.close()
            metadata = SharedMetadataWriter(staging, meter, DEFAULT_LIMITS)
            metadata.write("fixture-metadata.json", b"{}\n")
            metadata.close()
            self.assertEqual(meter.known_bytes, directory_size(staging))
            self.assertEqual(meter.verify_actual_usage(), directory_size(staging))
            meter.checked_rmtree(staging)
            self.assertEqual(meter.verify_actual_usage(), 0)

    def test_fail_closed_scientific_replacement_is_exactly_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            session = ArtifactSession(
                meter.root,
                meter,
                DEFAULT_LIMITS,
                meter.runtime_guard,
            )
            session.emitter.emit(UNIT_FILE, {"fixture": "x" * 70_000})
            self.assertGreater((session.staging / UNIT_FILE).stat().st_size, 0)
            evidence = session._discard_science_and_create_empty()
            self.assertTrue(all(item.byte_count == 0 for item in evidence))
            self.assertTrue(
                all((session.staging / name).read_bytes() == b"" for name in SCIENCE_CONTAINERS)
            )
            self.assertEqual(meter.verify_actual_usage(), 0)
            session.abort()

    def test_tracked_bytes_must_equal_actual_disk_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meter = self.meter(Path(temporary) / "workspace")
            payload = meter.root / "payload.bin"
            self.write_payload(meter, payload)
            self.assertEqual(meter.verify_actual_usage(), len(b"payload"))
            with payload.open("ab") as handle:
                handle.write(b"unmetered")
            with self.assertRaises(StorageBoundaryError):
                meter.verify_actual_usage()


class ArtifactCompatibilityTests(unittest.TestCase):
    def build_one_unit_incomplete_artifact(
        self,
        workspace: Path,
        *,
        retain_occurrence: bool,
    ) -> Path:
        guard = RuntimeGuard(DEFAULT_LIMITS)
        meter = R7WorkspaceMeter(workspace, DEFAULT_LIMITS, guard)
        meter.bootstrap()
        state = ExecutionEvidenceState(
            DEFAULT_SELECTION.targets,
            DEFAULT_LIMITS,
        )
        session = ArtifactSession(
            workspace,
            meter,
            DEFAULT_LIMITS,
            guard,
        )
        projection = fixture_unit_projection()
        unit_id = hashlib.sha256(
            frame(b"LEGACY_REPEAT_OCCURRENCE", projection)
        ).hexdigest()
        projection_sha = hashlib.sha256(projection).hexdigest()
        session.emitter.emit(
            UNIT_FILE,
            {
                "record_type": "R11A_V2_TAXONOMY_UNIT",
                "diagnostic_id": DIAGNOSTIC_ID,
                "taxonomy_unit_id": unit_id,
                "unit_universe": "LEGACY_REPEAT_OCCURRENCE",
                "unit_projection_sha256": projection_sha,
                "key_projection": {"fixture": "fixture"},
                "primary_taxon": "TID_SCOPE_FALSE_POSITIVE",
                "supporting_taxa": [],
                "occurrence_count": 1,
                "proof_references": [],
            },
        )
        if retain_occurrence:
            retained = {
                "record_type": "R11A_V2_LEGACY_REPEAT_OCCURRENCE",
                "primary_taxon": "TID_SCOPE_FALSE_POSITIVE",
                "supporting_taxa": [],
                "raw_locator": {
                    "object_key": DEFAULT_SELECTION.targets[0].object_key,
                    "verified_compressed_sha256": (
                        DEFAULT_SELECTION.targets[0].expected_compressed_sha256
                    ),
                    "decompressed_record_ordinal_zero_based": 0,
                    "event_ordinal_zero_based": 1,
                },
                "block_number": 1,
                "exact_raw_local_time": "2025-07-28T00:00:00Z",
                "exact_raw_block_time": "2025-07-28T00:00:00Z",
                "canonical_wallet": "0x" + "1" * 40,
                "exact_raw_coin_string": "BTC",
                "validated_tid": 1,
                "exact_raw_side_string": "A",
                "full_event_sha256": "2" * 64,
                "fill_payload_sha256": "3" * 64,
                "schema_errors": [],
                "selected_fill_payload": {},
                "diagnostic_id": DIAGNOSTIC_ID,
                "taxonomy_unit_id": unit_id,
                "unit_projection_sha256": projection_sha,
            }
            retained["retained_row_id"] = hashlib.sha256(
                canonical_json_bytes(retained, final_newline=False)
            ).hexdigest()
            session.emitter.emit(LEGACY_ROWS_FILE, retained)
        joins = JoinValidationResult(
            unit_count=1,
            proof_count=0,
            proof_reference_count=0,
            retained_row_reference_count=1,
            all_unit_ids_unique=True,
            all_proof_ids_unique=True,
            all_nonnull_proof_references_resolve_exactly_once=True,
            all_retained_rows_reference_exactly_one_unit=True,
            all_referenced_projections_are_byte_equal=True,
            all_retained_row_counts_match_unit_occurrence_counts=True,
        )
        taxonomy = TaxonomyResult(
            universe_rows=one_legacy_universe_rows(),
            secondary_reducer_rows=(),
            join_validation=joins,
            repeated_block_group_count=0,
            repeated_block_observation_count=0,
            legacy_repeat_group_count=1,
            legacy_repeat_observation_count=2,
            legacy_repeat_occurrence_count=1,
            valid_tid_legacy_repeat_occurrence_count=1,
            invalid_tid_legacy_repeat_occurrence_count=0,
            supporting_taxon_counts=zero_taxon_counts(),
            exact_three_utc_days=False,
        )
        outcome = session.finalize_full(
            state=state,
            context={"test_fixture": "one-unit-incomplete"},
            reducer_rows=(),
            resource_rows=(),
            terminal_class="R11A_V2_DIAGNOSTIC_INCOMPLETE",
            research_conclusion=(
                "ROOT_CAUSE_NOT_FULLY_PROVEN_NO_REPAIR_AUTHORIZED"
            ),
            taxonomy_result=taxonomy,
        )
        return outcome.final_directory

    def build_one_schema_incomplete_artifact(self, workspace: Path) -> Path:
        unit_universe = "REPEAT_INTERSECTING_TID_SCHEMA_VIOLATION"
        primary_taxon = "TID_SCHEMA_VIOLATION"
        guard = RuntimeGuard(DEFAULT_LIMITS)
        meter = R7WorkspaceMeter(workspace, DEFAULT_LIMITS, guard)
        meter.bootstrap()
        state = ExecutionEvidenceState(
            DEFAULT_SELECTION.targets,
            DEFAULT_LIMITS,
        )
        session = ArtifactSession(
            workspace,
            meter,
            DEFAULT_LIMITS,
            guard,
        )
        projection = fixture_unit_projection(
            key_value="schema",
            unit_universe=unit_universe,
            primary_taxon=primary_taxon,
        )
        unit_id = hashlib.sha256(
            frame(unit_universe.encode("ascii"), projection)
        ).hexdigest()
        projection_sha = hashlib.sha256(projection).hexdigest()
        session.emitter.emit(
            UNIT_FILE,
            {
                "record_type": "R11A_V2_TAXONOMY_UNIT",
                "diagnostic_id": DIAGNOSTIC_ID,
                "taxonomy_unit_id": unit_id,
                "unit_universe": unit_universe,
                "unit_projection_sha256": projection_sha,
                "key_projection": {"fixture": "schema"},
                "primary_taxon": primary_taxon,
                "supporting_taxa": [],
                "occurrence_count": 1,
                "proof_references": [],
            },
        )
        retained = {
            "record_type": "R11A_V2_REPEAT_INTERSECTING_SCHEMA_EVIDENCE",
            "primary_taxon": primary_taxon,
            "schema_universe": unit_universe,
            "raw_locator": {
                "object_key": DEFAULT_SELECTION.targets[0].object_key,
                "verified_compressed_sha256": (
                    DEFAULT_SELECTION.targets[0].expected_compressed_sha256
                ),
                "decompressed_record_ordinal_zero_based": 0,
                "event_ordinal_zero_based": 1,
            },
            "schema_errors": ["TID_NOT_STRICT_UINT50"],
            "diagnostic_id": DIAGNOSTIC_ID,
            "taxonomy_unit_id": unit_id,
            "unit_projection_sha256": projection_sha,
        }
        retained["retained_row_id"] = hashlib.sha256(
            canonical_json_bytes(retained, final_newline=False)
        ).hexdigest()
        session.emitter.emit(
            "r11a-v2-repeat-intersecting-schema-evidence.ndjson",
            retained,
        )
        joins = JoinValidationResult(
            unit_count=1,
            proof_count=0,
            proof_reference_count=0,
            retained_row_reference_count=1,
            all_unit_ids_unique=True,
            all_proof_ids_unique=True,
            all_nonnull_proof_references_resolve_exactly_once=True,
            all_retained_rows_reference_exactly_one_unit=True,
            all_referenced_projections_are_byte_equal=True,
            all_retained_row_counts_match_unit_occurrence_counts=True,
        )
        taxonomy = TaxonomyResult(
            universe_rows=one_universe_rows(unit_universe, primary_taxon),
            secondary_reducer_rows=(),
            join_validation=joins,
            repeated_block_group_count=0,
            repeated_block_observation_count=0,
            legacy_repeat_group_count=0,
            legacy_repeat_observation_count=0,
            legacy_repeat_occurrence_count=0,
            valid_tid_legacy_repeat_occurrence_count=0,
            invalid_tid_legacy_repeat_occurrence_count=0,
            supporting_taxon_counts=zero_taxon_counts(),
            exact_three_utc_days=False,
        )
        return session.finalize_full(
            state=state,
            context={"test_fixture": "one-schema-unit-incomplete"},
            reducer_rows=(),
            resource_rows=(),
            terminal_class="R11A_V2_DIAGNOSTIC_INCOMPLETE",
            research_conclusion=(
                "ROOT_CAUSE_NOT_FULLY_PROVEN_NO_REPAIR_AUTHORIZED"
            ),
            taxonomy_result=taxonomy,
        ).final_directory

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
                "workflow_name": (
                    "Hyperliquid Archive R11A Identity Boundary Diagnostic"
                ),
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
            self.assertEqual(
                (artifact / "r11a-v2.rc").read_text(),
                "21\n",
            )
            self.assertEqual(
                (artifact / BOUNDARY_FILE).stat().st_size,
                1024,
            )
            for name in SCIENCE_CONTAINERS:
                self.assertEqual((artifact / name).read_bytes(), b"")

    def test_fully_materialized_incomplete_artifact_uses_rc20_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            guard = RuntimeGuard(DEFAULT_LIMITS)
            meter = R7WorkspaceMeter(workspace, DEFAULT_LIMITS, guard)
            meter.bootstrap()
            state = ExecutionEvidenceState(
                DEFAULT_SELECTION.targets,
                DEFAULT_LIMITS,
            )
            session = ArtifactSession(
                workspace,
                meter,
                DEFAULT_LIMITS,
                guard,
            )
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
                universe_rows=zero_universe_rows(),
                secondary_reducer_rows=(),
                join_validation=joins,
                repeated_block_group_count=0,
                repeated_block_observation_count=0,
                legacy_repeat_group_count=0,
                legacy_repeat_observation_count=0,
                legacy_repeat_occurrence_count=0,
                valid_tid_legacy_repeat_occurrence_count=0,
                invalid_tid_legacy_repeat_occurrence_count=0,
                supporting_taxon_counts=zero_taxon_counts(),
                exact_three_utc_days=False,
            )
            outcome = session.finalize_full(
                state=state,
                context={"test_fixture": "full-incomplete"},
                reducer_rows=(),
                resource_rows=(),
                terminal_class="R11A_V2_DIAGNOSTIC_INCOMPLETE",
                research_conclusion=(
                    "ROOT_CAUSE_NOT_FULLY_PROVEN_NO_REPAIR_AUTHORIZED"
                ),
                taxonomy_result=taxonomy,
            )
            self.assertEqual(outcome.return_code, 20)
            validate_artifact(outcome.final_directory, DEFAULT_LIMITS)
            validate_science(outcome.final_directory)

    def test_nonempty_incomplete_science_passes_external_recomputation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact = self.build_one_unit_incomplete_artifact(
                Path(temporary) / "workspace",
                retain_occurrence=True,
            )
            validate_artifact(artifact, DEFAULT_LIMITS)
            validate_science(artifact)

    def test_external_validator_rejects_claimed_but_missing_retained_occurrence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact = self.build_one_unit_incomplete_artifact(
                Path(temporary) / "workspace",
                retain_occurrence=False,
            )
            validate_artifact(artifact, DEFAULT_LIMITS)
            with self.assertRaises(EvidenceValidationError):
                validate_science(artifact)

    def test_external_validator_rejects_wrong_unit_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact = self.build_one_unit_incomplete_artifact(
                Path(temporary) / "workspace",
                retain_occurrence=True,
            )
            unit_path = artifact / UNIT_FILE
            unit = json.loads(unit_path.read_bytes())
            unit["key_projection"] = {"fixture": "tampered"}
            unit_path.write_bytes(canonical_json_bytes(unit))
            with self.assertRaises(EvidenceValidationError):
                validate_science(artifact)

    def test_external_validator_rejects_wrong_retained_container(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact = self.build_one_unit_incomplete_artifact(
                Path(temporary) / "workspace",
                retain_occurrence=True,
            )
            legacy = artifact / LEGACY_ROWS_FILE
            protocol = artifact / "r11a-v2-protocol-trade-group-members.ndjson"
            protocol.write_bytes(legacy.read_bytes())
            legacy.write_bytes(b"")
            with self.assertRaises(EvidenceValidationError):
                validate_science(artifact)

    def test_external_validator_rejects_wrong_primary_taxon(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact = self.build_one_unit_incomplete_artifact(
                Path(temporary) / "workspace",
                retain_occurrence=True,
            )
            retained_path = artifact / LEGACY_ROWS_FILE
            retained = json.loads(retained_path.read_bytes())
            retained["primary_taxon"] = "UNCLASSIFIABLE"
            retained_without_id = {
                key: value
                for key, value in retained.items()
                if key != "retained_row_id"
            }
            retained["retained_row_id"] = hashlib.sha256(
                canonical_json_bytes(retained_without_id, final_newline=False)
            ).hexdigest()
            retained_path.write_bytes(canonical_json_bytes(retained))
            with self.assertRaises(EvidenceValidationError):
                validate_science(artifact)

    def test_external_validator_rejects_wrong_schema_universe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact = self.build_one_schema_incomplete_artifact(
                Path(temporary) / "workspace"
            )
            validate_science(artifact)
            retained_path = (
                artifact / "r11a-v2-repeat-intersecting-schema-evidence.ndjson"
            )
            retained = json.loads(retained_path.read_bytes())
            retained["schema_universe"] = (
                "REPEAT_INTERSECTING_COIN_SCHEMA_VIOLATION"
            )
            retained_without_id = {
                key: value
                for key, value in retained.items()
                if key != "retained_row_id"
            }
            retained["retained_row_id"] = hashlib.sha256(
                canonical_json_bytes(retained_without_id, final_newline=False)
            ).hexdigest()
            retained_path.write_bytes(canonical_json_bytes(retained))
            with self.assertRaises(EvidenceValidationError):
                validate_science(artifact)

    def test_supporting_taxon_cannot_increase_primary_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact = self.build_one_unit_incomplete_artifact(
                Path(temporary) / "workspace",
                retain_occurrence=True,
            )
            conservation_path = artifact / CONSERVATION_FILE
            conservation = json.loads(conservation_path.read_bytes())
            legacy = conservation["unit_universes"][0]
            legacy["primary_taxon_group_counts"]["TID_SCOPE_FALSE_POSITIVE"] = 0
            legacy["primary_taxon_occurrence_counts"]["TID_SCOPE_FALSE_POSITIVE"] = 0
            legacy["primary_taxon_group_counts"]["EXPECTED_COUNTERPARTY_PAIR"] = 1
            legacy["primary_taxon_occurrence_counts"]["EXPECTED_COUNTERPARTY_PAIR"] = 1
            conservation_path.write_bytes(canonical_json_bytes(conservation))
            with self.assertRaises(EvidenceValidationError):
                validate_science(artifact)


class FrozenTaxonomyAndWorkflowTests(unittest.TestCase):
    def test_exact_authoritative_universes_and_taxa(self) -> None:
        self.assertEqual(
            tuple(value.value for value in UnitUniverse),
            AUTHORITATIVE_UNIT_UNIVERSES,
        )
        self.assertEqual(tuple(value.value for value in Taxon), TAXA)
        self.assertEqual(
            DIAGNOSTIC_ID,
            "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-002",
        )
        self.assertEqual(
            IMPLEMENTATION_ID,
            "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-CORRECTIVE-R7",
        )

    def test_workflow_has_no_inline_https_and_no_inert_validator(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow = (
            root
            / "research/archive_inventory/r11a_corrective/workflows/"
            "hyperliquid-archive-r11a-identity-boundary-diagnostic-r7.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("urllib.request", workflow)
        self.assertNotIn(
            "validate_r11a_corrective_implementation",
            workflow,
        )
        self.assertIn("validate_r11a_runtime_binding_r7.py", workflow)
        self.assertIn("validate_r11a_execution_artifact_r7.py", workflow)
        self.assertIn("R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT_R7.json", workflow)
        self.assertLess(
            workflow.index("validate_r11a_execution_artifact_r7.py"),
            workflow.index("actions/upload-artifact"),
        )

    def test_current_draft_has_no_active_runtime_binding(self) -> None:
        self.assertFalse(BINDING.exists())
        with self.assertRaises(RuntimeBindingError):
            validate_runtime_binding("1" * 40, 1)

    def test_r7_seal_is_distinct_fail_closed_and_covers_private_cores(self) -> None:
        root = Path(__file__).resolve().parents[1]
        contract = json.loads(
            (
                root
                / "research/archive_inventory/r11a_corrective/"
                "R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT_R7.json"
            ).read_bytes()
        )
        status = json.loads(
            (
                root
                / "research/archive_inventory/r11a_corrective/"
                "R11A_CORRECTIVE_STATUS_R7.json"
            ).read_bytes()
        )
        self.assertEqual(contract["implementation_id"], IMPLEMENTATION_ID)
        self.assertFalse(contract["implementation_review_green"])
        self.assertTrue(contract["pricing_binding_pending"])
        self.assertFalse(contract["owner_approval_eligible"])
        self.assertFalse(
            contract["authority_reconciliation"][
                "referenced_amendment_002_present"
            ]
        )
        self.assertFalse(status["implementation_review_green"])
        self.assertFalse(status["owner_approval_eligible"])
        sealed = set(contract["implementation_file_hashes"])
        for relative in (
            "governance/_validate_r11a_runtime_binding_core_r7.py",
            "research/archive_inventory/r11a_corrective/_artifact_contract_core_r7.py",
            "research/archive_inventory/r11a_corrective/_artifact_core_r7.py",
            "research/archive_inventory/r11a_corrective/_artifact_schema_core_r7.py",
            "research/archive_inventory/r11a_corrective/_runner_core_r7.py",
            "research/archive_inventory/r11a_corrective/_taxonomy_contract_core_r7.py",
            "research/archive_inventory/r11a_corrective/_taxonomy_core_r7.py",
            "research/archive_inventory/r11a_corrective/taxonomy_precedence_r7.py",
        ):
            self.assertIn(relative, sealed)

    def test_taxonomy_uses_disk_backed_group_state_not_first_current_shortcuts(self) -> None:
        import research.archive_inventory.r11a_corrective.taxonomy as taxonomy

        source = inspect.getsource(taxonomy)
        self.assertIn("BlockScratch", source)
        self.assertIn("EventScratch", source)
        self.assertNotIn("first/current", source)
        self.assertNotIn("block_rows: list", source)


if __name__ == "__main__":
    unittest.main()
