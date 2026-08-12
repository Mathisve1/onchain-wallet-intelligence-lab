from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Final

from .artifact import complete_reducer_rows, validate_artifact
from .artifact_schema import (
    AUTHORITATIVE_UNIT_UNIVERSES,
    BOUNDARY_FILE,
    CONSERVATION_FILE,
    CONTEXT_FILE,
    DIAGNOSTIC_ID,
    EXPECTED_ARTIFACT_FILES,
    HASH_MANIFEST_FILE,
    IMPLEMENTATION_ID,
    OBJECT_LEDGER_FILE,
    PHASES,
    REDUCER_LEDGER_FILE,
    RESOURCE_LEDGER_FILE,
    RESULT_FILE,
    RETURN_CODE_FILE,
    SCIENCE_CONTAINERS,
    STOP_LEDGER_FILE,
    WALLET_FEATURE_FILE,
)
from .canonical import canonical_json_bytes
from .limits import DEFAULT_LIMITS
from .runtime import ExecutionEvidenceState
from .selection import DEFAULT_SELECTION

_MAX_MINIMAL_ARTIFACT_BYTES: Final[int] = 4_194_304


class PreflightArtifactError(RuntimeError):
    pass


def _checked_remove(path: Path) -> None:
    if not path.exists():
        return
    if path.is_symlink():
        raise PreflightArtifactError("refusing to remove symlink")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    if path.exists():
        raise PreflightArtifactError("checked cleanup failed")


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        if handle.write(payload) != len(payload):
            raise PreflightArtifactError("short minimal artifact write")
        handle.flush()
        os.fsync(handle.fileno())


def write_preflight_failure_artifact(
    *,
    workspace: Path,
    context: dict[str, object],
    failure_code: str,
    execution_phase: str,
) -> Path:
    if execution_phase not in PHASES:
        raise PreflightArtifactError("unknown precollector failure phase")
    workspace.mkdir(parents=True, exist_ok=True)
    final = workspace / "r11a-v2-artifact"
    staging = workspace / ".r11a-v2-artifact.staging"
    _checked_remove(final)
    _checked_remove(staging)
    staging.mkdir()
    try:
        for name in SCIENCE_CONTAINERS:
            _write(staging / name, b"")
        state = ExecutionEvidenceState(DEFAULT_SELECTION.targets, DEFAULT_LIMITS)
        state.mark_phase(execution_phase)
        state.stop(
            failure_code,
            phase=execution_phase,
            evidence={"failure_code_sha256": hashlib.sha256(failure_code.encode()).hexdigest()},
        )
        full_context = {
            **context,
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "implementation_id": IMPLEMENTATION_ID,
            "execution_phase": execution_phase,
            "s3_requests_executed": 0,
            "object_bytes_downloaded": 0,
            "rerun_authorized": False,
        }
        result = {
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "implementation_id": IMPLEMENTATION_ID,
            "terminal_class": "R11A_V2_FAIL_CLOSED_EARLY_STOP",
            "research_conclusion": "ROOT_CAUSE_NOT_PROVEN_FAIL_CLOSED_EMPTY_ARTIFACT",
            "scientific_output_status": "EMPTY",
            "root_cause_claim_status": "NOT_PROVEN",
            "return_code": 21,
            "scientific_files": {
                name: {
                    "path": name,
                    "byte_count": 0,
                    "row_count": 0,
                    "sha256": hashlib.sha256(b"").hexdigest(),
                }
                for name in SCIENCE_CONTAINERS
            },
            "wallet_feature_rows": 0,
            "rerun_authorized": False,
            "R11_CLOSED": False,
            "R12_READY": False,
        }
        object_rows = state.object_rows()
        reducers = complete_reducer_rows((), "R11A_V2_FAIL_CLOSED_EARLY_STOP")
        conservation = {
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "implementation_id": IMPLEMENTATION_ID,
            "aggregate_execution_counts": state.aggregate_counts(),
            "unit_universes": [
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
            ],
            "join_validation": {
                "unit_count": 0,
                "proof_count": 0,
                "proof_reference_count": 0,
                "retained_row_reference_count": 0,
                "all_unit_ids_unique": True,
                "all_proof_ids_unique": True,
                "all_nonnull_proof_references_resolve_exactly_once": True,
                "all_retained_rows_reference_exactly_one_unit": True,
                "all_referenced_projections_are_byte_equal": True,
            },
            "secondary_reducer_rows": [],
            "supporting_taxon_counts": {},
            "terminal_gates": {
                "exact_72_object_scope_complete": False,
                "exact_three_complete_utc_days": False,
                "all_objects_parsed_twice_with_equal_counts_and_commitments": False,
                "raw_block_count_conserves_to_singleton_plus_repeated_observations": False,
                "raw_event_count_conserves_separately_for_tid_coin_and_wallet_validation": False,
                "legacy_repeat_occurrence_count_conserves_to_valid_plus_invalid_tid_repeat_occurrences": False,
                "every_authoritative_unit_receives_exactly_one_primary_taxon": False,
                "supporting_taxa_do_not_increment_primary_counts": False,
                "all_nonnull_proof_and_provenance_foreign_keys_resolve_exactly_once": True,
                "all_referenced_projections_are_byte_equal": True,
                "all_taxonomy_counts_recomputed_from_retained_rows": False,
                "every_unit_universe_has_zero_unclassifiable_groups_and_occurrences": True,
                "all_caps_respected": True,
            },
        }
        resource = {
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "measurements": [],
            "tracked_workspace_bytes_before_packaging": 0,
            "reserved_workspace_bytes_before_packaging": 0,
            "maximum_ephemeral_workspace_bytes": DEFAULT_LIMITS.maximum_ephemeral_workspace_bytes,
            "package_flags": {
                "preupload_runtime_within_hard_limit_after_upload_window": True,
                "scientific_runtime_completed_before_packaging_reservation": True,
            },
        }
        stop = {
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "declared_phase_order": list(PHASES),
            "entries": list(state.stop_rows()),
        }
        _write(staging / CONTEXT_FILE, canonical_json_bytes(full_context))
        _write(staging / RESULT_FILE, canonical_json_bytes(result))
        _write(
            staging / OBJECT_LEDGER_FILE,
            b"".join(canonical_json_bytes(row) for row in object_rows),
        )
        _write(
            staging / REDUCER_LEDGER_FILE,
            b"".join(canonical_json_bytes(row) for row in reducers),
        )
        _write(staging / CONSERVATION_FILE, canonical_json_bytes(conservation))
        _write(staging / RESOURCE_LEDGER_FILE, canonical_json_bytes(resource))
        _write(staging / STOP_LEDGER_FILE, canonical_json_bytes(stop))
        _write(staging / WALLET_FEATURE_FILE, b"")
        _write(staging / RETURN_CODE_FILE, b"21\n")
        names = sorted(
            EXPECTED_ARTIFACT_FILES - {HASH_MANIFEST_FILE, BOUNDARY_FILE},
            key=lambda value: value.encode("utf-8"),
        )
        manifest = ("\n".join(f"{_hash(staging / name)}  {name}" for name in names) + "\n").encode(
            "ascii"
        )
        _write(staging / HASH_MANIFEST_FILE, manifest)
        preboundary = [value for value in staging.iterdir() if value.is_file()]
        preboundary_bytes = sum(value.stat().st_size for value in preboundary)
        metadata_bytes = sum(
            value.stat().st_size for value in preboundary if value.name not in SCIENCE_CONTAINERS
        )
        boundary_value = {
            "schema_version": "2.0",
            "record_type": "R11A_V2_PACKAGE_BOUNDARY",
            "diagnostic_id": DIAGNOSTIC_ID,
            "implementation_id": IMPLEMENTATION_ID,
            "preboundary_file_count": len(preboundary),
            "preboundary_bytes": preboundary_bytes,
            "metadata_bytes": metadata_bytes,
            "maximum_retained_artifact_bytes": DEFAULT_LIMITS.maximum_retained_artifact_bytes,
            "maximum_ephemeral_workspace_bytes": DEFAULT_LIMITS.maximum_ephemeral_workspace_bytes,
            "metadata_within_reservation": metadata_bytes
            <= DEFAULT_LIMITS.reserved_non_scientific_package_metadata_bytes,
            "final_staging_within_artifact_limit": preboundary_bytes
            + DEFAULT_LIMITS.package_boundary_bytes
            <= DEFAULT_LIMITS.maximum_retained_artifact_bytes,
            "preupload_runtime_within_hard_limit_after_upload_window": True,
            "boundary_write_within_workspace_limit": True,
        }
        prefix = canonical_json_bytes(boundary_value, final_newline=False)
        boundary = prefix + b" " * (DEFAULT_LIMITS.package_boundary_bytes - len(prefix) - 1) + b"\n"
        _write(staging / BOUNDARY_FILE, boundary)
        if sum(value.stat().st_size for value in staging.iterdir()) > _MAX_MINIMAL_ARTIFACT_BYTES:
            raise PreflightArtifactError("minimal failure artifact exceeds fixed metadata reservation")
        validate_artifact(staging, DEFAULT_LIMITS)
        staging.rename(final)
        return final
    except Exception:
        _checked_remove(staging)
        _checked_remove(final)
        raise
