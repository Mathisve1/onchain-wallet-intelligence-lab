from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Final

from .artifact import (
    _reducer_summary,
    complete_reducer_rows,
    validate_artifact,
)
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
    TAXA,
    TERMINAL_GATE_NAMES,
    WALLET_FEATURE_FILE,
    zero_taxon_counts,
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
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        if handle.write(payload) != len(payload):
            raise PreflightArtifactError("short minimal artifact write")
        handle.flush()
        os.fsync(handle.fileno())


def _zero_universe_rows() -> list[dict[str, object]]:
    return [
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
    ]


def _zero_join_mapping() -> dict[str, object]:
    return {
        "unit_count": 0,
        "proof_count": 0,
        "proof_reference_count": 0,
        "retained_row_reference_count": 0,
        "all_unit_ids_unique": True,
        "all_proof_ids_unique": True,
        "all_nonnull_proof_references_resolve_exactly_once": True,
        "all_retained_rows_reference_exactly_one_unit": True,
        "all_referenced_projections_are_byte_equal": True,
        "all_retained_row_counts_match_unit_occurrence_counts": True,
    }


def _empty_terminal_gates() -> dict[str, bool]:
    value = {name: False for name in TERMINAL_GATE_NAMES}
    value.update(
        {
            "authoritative_unit_universes_are_exact_and_ordered": True,
            "every_authoritative_unit_receives_exactly_one_primary_taxon": True,
            "supporting_taxa_do_not_increment_primary_counts": True,
            "all_nonnull_proof_and_provenance_foreign_keys_resolve_exactly_once": True,
            "all_retained_rows_reference_exactly_one_unit": True,
            "all_retained_row_counts_match_unit_occurrence_counts": True,
            "all_referenced_projections_are_byte_equal": True,
            "all_taxonomy_counts_recomputed_from_retained_rows": True,
            "every_unit_universe_has_zero_unclassifiable_groups_and_occurrences": True,
            "all_caps_respected": True,
        }
    )
    return value


def _boundary_payload(
    staging: Path,
    *,
    elapsed_seconds_floor: int,
) -> bytes:
    preboundary = [value for value in staging.iterdir() if value.is_file()]
    preboundary_bytes = sum(value.stat().st_size for value in preboundary)
    metadata_bytes = sum(
        value.stat().st_size
        for value in preboundary
        if value.name not in SCIENCE_CONTAINERS
    )
    remaining_metadata_reservation = (
        DEFAULT_LIMITS.reserved_non_scientific_package_metadata_bytes
        - metadata_bytes
    )
    value = {
        "schema_version": "2.0",
        "record_type": "R11A_V2_PACKAGE_BOUNDARY",
        "diagnostic_id": DIAGNOSTIC_ID,
        "implementation_id": IMPLEMENTATION_ID,
        "preboundary_file_count": len(preboundary),
        "preboundary_bytes": preboundary_bytes,
        "metadata_bytes": metadata_bytes,
        "boundary_elapsed_seconds_floor": elapsed_seconds_floor,
        "maximum_runtime_seconds": DEFAULT_LIMITS.maximum_runtime_seconds,
        "minimum_upload_window_seconds": DEFAULT_LIMITS.minimum_upload_window_seconds,
        "maximum_retained_artifact_bytes": (
            DEFAULT_LIMITS.maximum_retained_artifact_bytes
        ),
        "maximum_ephemeral_workspace_bytes": (
            DEFAULT_LIMITS.maximum_ephemeral_workspace_bytes
        ),
        "reserved_non_scientific_package_metadata_bytes": (
            DEFAULT_LIMITS.reserved_non_scientific_package_metadata_bytes
        ),
        "workspace_tracked_bytes_before_boundary": preboundary_bytes,
        "workspace_reserved_bytes_before_boundary": (
            remaining_metadata_reservation
        ),
        "metadata_within_reservation": (
            metadata_bytes + DEFAULT_LIMITS.package_boundary_bytes
            <= DEFAULT_LIMITS.reserved_non_scientific_package_metadata_bytes
        ),
        "final_staging_within_artifact_limit": (
            preboundary_bytes + DEFAULT_LIMITS.package_boundary_bytes
            <= DEFAULT_LIMITS.maximum_retained_artifact_bytes
        ),
        "preupload_runtime_within_hard_limit_after_upload_window": (
            elapsed_seconds_floor
            < DEFAULT_LIMITS.maximum_runtime_seconds
            - DEFAULT_LIMITS.minimum_upload_window_seconds
        ),
        "boundary_write_within_workspace_limit": (
            preboundary_bytes + DEFAULT_LIMITS.package_boundary_bytes
            <= DEFAULT_LIMITS.maximum_ephemeral_workspace_bytes
            and remaining_metadata_reservation
            >= DEFAULT_LIMITS.package_boundary_bytes
        ),
    }
    prefix = canonical_json_bytes(value, final_newline=False)
    if len(prefix) + 1 > DEFAULT_LIMITS.package_boundary_bytes:
        raise PreflightArtifactError(
            "minimal package boundary exceeds exact 1,024 bytes"
        )
    return (
        prefix
        + b" "
        * (DEFAULT_LIMITS.package_boundary_bytes - len(prefix) - 1)
        + b"\n"
    )


def write_preflight_failure_artifact(
    *,
    workspace: Path,
    context: dict[str, object],
    failure_code: str,
    execution_phase: str,
) -> Path:
    if execution_phase not in PHASES:
        raise PreflightArtifactError("unknown precollector failure phase")
    if not failure_code:
        raise PreflightArtifactError("failure code must be nonempty")
    workspace.mkdir(parents=True, exist_ok=True)
    final = workspace / "r11a-v2-artifact"
    staging = workspace / ".r11a-v2-artifact.staging"
    _checked_remove(final)
    _checked_remove(staging)
    staging.mkdir()
    try:
        for name in SCIENCE_CONTAINERS:
            _write(staging / name, b"")

        state = ExecutionEvidenceState(
            DEFAULT_SELECTION.targets,
            DEFAULT_LIMITS,
        )
        state.mark_phase(execution_phase)
        state.stop(
            failure_code,
            phase=execution_phase,
            evidence={
                "failure_code_sha256": hashlib.sha256(
                    failure_code.encode("utf-8")
                ).hexdigest()
            },
        )
        object_rows = state.object_rows()
        reducers = complete_reducer_rows(
            (),
            "R11A_V2_FAIL_CLOSED_EARLY_STOP",
        )
        reducer_summary = _reducer_summary(reducers)
        elapsed_seconds_floor = 0

        full_context = {
            **context,
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "implementation_id": IMPLEMENTATION_ID,
            "execution_phase": execution_phase,
            "s3_requests_executed": state.network_request_count,
            "object_bytes_downloaded": sum(
                int(row["body"]["bytes_received"])
                for row in object_rows
            ),
            "rerun_authorized": False,
        }
        result = {
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "implementation_id": IMPLEMENTATION_ID,
            "terminal_class": "R11A_V2_FAIL_CLOSED_EARLY_STOP",
            "research_conclusion": (
                "ROOT_CAUSE_NOT_PROVEN_FAIL_CLOSED_EMPTY_ARTIFACT"
            ),
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
        conservation = {
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "implementation_id": IMPLEMENTATION_ID,
            "aggregate_execution_counts": state.aggregate_counts(),
            "primary_reducer_summary": reducer_summary,
            "unit_universes": _zero_universe_rows(),
            "join_validation": _zero_join_mapping(),
            "secondary_reducer_rows": [],
            "supporting_taxon_counts": zero_taxon_counts(),
            "terminal_gates": _empty_terminal_gates(),
        }
        resource = {
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "measurements": [],
            "tracked_workspace_bytes_before_packaging": 0,
            "reserved_workspace_bytes_before_packaging": (
                DEFAULT_LIMITS.reserved_non_scientific_package_metadata_bytes
            ),
            "maximum_ephemeral_workspace_bytes": (
                DEFAULT_LIMITS.maximum_ephemeral_workspace_bytes
            ),
            "packaging_elapsed_seconds_floor": elapsed_seconds_floor,
            "package_flags": {
                "preupload_runtime_within_hard_limit_after_upload_window": (
                    elapsed_seconds_floor
                    < DEFAULT_LIMITS.maximum_runtime_seconds
                    - DEFAULT_LIMITS.minimum_upload_window_seconds
                ),
                "scientific_runtime_completed_before_packaging_reservation": (
                    elapsed_seconds_floor
                    < DEFAULT_LIMITS.maximum_runtime_seconds
                ),
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
            b"".join(
                canonical_json_bytes(row) for row in object_rows
            ),
        )
        _write(
            staging / REDUCER_LEDGER_FILE,
            b"".join(canonical_json_bytes(row) for row in reducers),
        )
        _write(
            staging / CONSERVATION_FILE,
            canonical_json_bytes(conservation),
        )
        _write(
            staging / RESOURCE_LEDGER_FILE,
            canonical_json_bytes(resource),
        )
        _write(
            staging / STOP_LEDGER_FILE,
            canonical_json_bytes(stop),
        )
        _write(staging / WALLET_FEATURE_FILE, b"")
        _write(staging / RETURN_CODE_FILE, b"21\n")

        names = sorted(
            EXPECTED_ARTIFACT_FILES
            - {HASH_MANIFEST_FILE, BOUNDARY_FILE},
            key=lambda value: value.encode("utf-8"),
        )
        manifest = (
            "\n".join(
                f"{_hash(staging / name)}  {name}" for name in names
            )
            + "\n"
        ).encode("ascii")
        _write(staging / HASH_MANIFEST_FILE, manifest)
        _write(
            staging / BOUNDARY_FILE,
            _boundary_payload(
                staging,
                elapsed_seconds_floor=elapsed_seconds_floor,
            ),
        )

        artifact_bytes = sum(
            value.stat().st_size for value in staging.iterdir()
        )
        if artifact_bytes > _MAX_MINIMAL_ARTIFACT_BYTES:
            raise PreflightArtifactError(
                "minimal failure artifact exceeds fixed metadata reservation"
            )
        validate_artifact(staging, DEFAULT_LIMITS)
        staging.rename(final)
        if not final.is_dir() or staging.exists():
            raise PreflightArtifactError(
                "minimal artifact atomic rename failed"
            )
        return final
    except Exception:
        _checked_remove(staging)
        _checked_remove(final)
        raise
