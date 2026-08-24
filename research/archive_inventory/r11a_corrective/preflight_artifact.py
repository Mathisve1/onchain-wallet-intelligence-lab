from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from .artifact_r3 import (
    BOUNDARY_FILE,
    CONSERVATION_FILE,
    CONTEXT_FILE,
    HASH_MANIFEST_FILE,
    OBJECT_LEDGER_FILE,
    REDUCER_LEDGER_FILE,
    RESOURCE_LEDGER_FILE,
    RESULT_FILE,
    RETURN_CODE_FILE,
    SCIENCE_CONTAINERS,
    STOP_LEDGER_FILE,
    WALLET_FEATURE_FILE,
    _boundary_bytes,
    _manifest_bytes,
    complete_reducer_rows,
    validate_artifact,
)
from .canonical import canonical_json_bytes
from .limits import DEFAULT_LIMITS, R11ALimits
from .runtime import ExecutionEvidenceState
from .selection import DEFAULT_SELECTION

_MINIMAL_FREE_BYTES = 16 << 20


class PreOIDCArtifactError(RuntimeError):
    pass


def _checked_remove(path: Path) -> None:
    if not path.exists():
        return
    if path.is_symlink():
        path.unlink()
        return
    if path.is_file():
        path.unlink()
        return
    for child in sorted(path.iterdir(), key=lambda item: item.name.encode("utf-8"), reverse=True):
        _checked_remove(child)
    path.rmdir()


def _write(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        if handle.write(data) != len(data):
            raise PreOIDCArtifactError("short pre-OIDC artifact write")
        handle.flush()
        os.fsync(handle.fileno())


def _ndjson(rows) -> bytes:  # type: ignore[no-untyped-def]
    result = bytearray()
    for row in rows:
        result.extend(canonical_json_bytes(row))
    return bytes(result)


def write_pre_oidc_failure_artifact(
    *,
    workspace: Path,
    context: dict[str, object],
    failure_code: str,
    limits: R11ALimits = DEFAULT_LIMITS,
) -> Path:
    workspace.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(workspace.parent).free < _MINIMAL_FREE_BYTES:
        raise PreOIDCArtifactError("insufficient space even for minimal pre-OIDC evidence")
    workspace.mkdir(parents=True, exist_ok=False)
    staging = workspace / ".r11a-artifact.staging"
    final = workspace / "r11a-artifact"
    staging.mkdir(exist_ok=False)
    try:
        state = ExecutionEvidenceState(DEFAULT_SELECTION.targets, limits)
        state.stop(
            failure_code,
            phase="PRE_OIDC_STATIC_GATES",
            evidence={
                "pending_workflow_context_sha256": context["pending_workflow_context_sha256"]
            },
        )
        for name in SCIENCE_CONTAINERS:
            _write(staging / name, b"")
        _write(staging / WALLET_FEATURE_FILE, b"")
        _write(staging / OBJECT_LEDGER_FILE, _ndjson(state.object_rows()))
        _write(
            staging / REDUCER_LEDGER_FILE,
            _ndjson(complete_reducer_rows((), "NOT_STARTED_OR_INCOMPLETE")),
        )
        _write(staging / STOP_LEDGER_FILE, _ndjson(state.stop_rows()))
        _write(
            staging / RESOURCE_LEDGER_FILE,
            _ndjson(
                (
                    {
                        "record_type": "RESOURCE_MEASUREMENT",
                        "phase": "PRE_OIDC_STATIC_FAILURE",
                        "elapsed_runtime_seconds_floor": 0,
                        "tracked_workspace_bytes": 0,
                        "reserved_workspace_bytes": 0,
                        "network_request_count": 0,
                    },
                )
            ),
        )
        _write(staging / CONTEXT_FILE, canonical_json_bytes(context))
        conservation = {
            "status": "NOT_AVAILABLE_EARLY_STOP_OR_CAP_FALLBACK",
            "universe_rows": [],
            "secondary_sort_rows": [],
            "block_proof_count": 0,
            "pair_proof_count": 0,
            "proof_reference_count": 0,
            "all_proof_references_resolve": False,
            "all_unit_ids_unique": False,
            "all_duplicate_rows_reference_one_unit": False,
            "terminal_unclassifiable_group_count": 0,
            "terminal_unclassifiable_occurrence_count": 0,
        }
        _write(staging / CONSERVATION_FILE, canonical_json_bytes(conservation))
        result = {
            "schema_version": "1.0",
            "diagnostic_id": "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-001",
            "terminal_class": "R11A_DIAGNOSTIC_INCOMPLETE",
            "research_conclusion": "ROOT_CAUSE_NOT_PROVEN_PRE_OIDC_FAIL_CLOSED_EMPTY_ARTIFACT",
            "scientific_container_status": "EMPTY_EARLY_STOP_OR_CAP_FALLBACK",
            "exact_scope_complete": False,
            "aggregate_object_counts": state.aggregate_counts(),
            "scientific_files": {
                name: {
                    "path": name,
                    "byte_count": 0,
                    "row_count": 0,
                    "sha256": hashlib.sha256(b"").hexdigest(),
                }
                for name in SCIENCE_CONTAINERS
            },
            "wallet_feature_file": {
                "path": WALLET_FEATURE_FILE,
                "byte_count": 0,
                "row_count": 0,
                "sha256": hashlib.sha256(b"").hexdigest(),
            },
            "return_code": 21,
            "deduplication_performed": False,
            "block_replay_suppression_performed": False,
            "wallet_feature_publication_performed": False,
            "wallet_ranking_performed": False,
            "pnl_or_alpha_analysis_performed": False,
            "copyability_analysis_performed": False,
            "strategy_inference_performed": False,
            "trading_authority_opened": False,
        }
        _write(staging / RESULT_FILE, canonical_json_bytes(result))
        _write(staging / RETURN_CODE_FILE, b"21\n")
        manifest_names = [
            *SCIENCE_CONTAINERS,
            WALLET_FEATURE_FILE,
            OBJECT_LEDGER_FILE,
            REDUCER_LEDGER_FILE,
            STOP_LEDGER_FILE,
            RESOURCE_LEDGER_FILE,
            CONTEXT_FILE,
            CONSERVATION_FILE,
            RESULT_FILE,
            RETURN_CODE_FILE,
        ]
        manifest = _manifest_bytes(staging, manifest_names)
        _write(staging / HASH_MANIFEST_FILE, manifest)
        preboundary = sum(path.stat().st_size for path in staging.iterdir())
        _write(
            staging / BOUNDARY_FILE,
            _boundary_bytes(
                preboundary_file_count=len(manifest_names) + 1,
                preboundary_bytes=preboundary,
                metadata_bytes=preboundary,
                limits=limits,
            ),
        )
        validate_artifact(staging, limits)
        staging.rename(final)
        return final
    except Exception:
        _checked_remove(staging)
        _checked_remove(final)
        _checked_remove(workspace)
        raise
