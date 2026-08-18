from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from pathlib import Path

from .artifact import ArtifactSession
from .artifact_schema import PHASES
from .limits import DEFAULT_LIMITS
from .runtime import ExecutionEvidenceState, RuntimeGuard
from .selection import DEFAULT_SELECTION
from .storage_r7 import WorkspaceMeter


class PreflightArtifactError(RuntimeError):
    pass


def write_preflight_failure_artifact(
    *,
    workspace: Path,
    context: dict[str, object],
    failure_code: str,
    execution_phase: str,
    wall_time_ns: Callable[[], int] = time.time_ns,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
) -> Path:
    """Materialize an RC21 artifact through the main runtime/storage path."""
    if execution_phase not in PHASES:
        raise PreflightArtifactError("unknown precollector failure phase")
    if not isinstance(failure_code, str) or not failure_code:
        raise PreflightArtifactError("failure code must be nonempty")
    start_epoch_ns = context.get("workflow_start_epoch_ns")
    if type(start_epoch_ns) is not int:
        raise PreflightArtifactError(
            "persisted workflow start epoch is required for failure evidence"
        )
    guard = RuntimeGuard.from_start_epoch_ns(
        DEFAULT_LIMITS,
        start_epoch_ns,
        wall_time_ns=wall_time_ns,
        monotonic_ns=monotonic_ns,
    )
    meter = WorkspaceMeter(workspace, DEFAULT_LIMITS, guard)
    meter.bootstrap()
    state = ExecutionEvidenceState(DEFAULT_SELECTION.targets, DEFAULT_LIMITS)
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
    session = ArtifactSession(workspace, meter, DEFAULT_LIMITS, guard)
    try:
        outcome = session.finalize_empty(
            state=state,
            context=context,
            reducer_rows=(),
            resource_rows=(
                {
                    "record_type": "R11A_V2_RESOURCE_MEASUREMENT",
                    "phase": execution_phase,
                    "elapsed_runtime_seconds_floor": guard.elapsed_seconds_floor(),
                    "tracked_workspace_bytes": meter.known_bytes,
                    "reserved_workspace_bytes": meter.reserved_bytes,
                    "peak_tracked_workspace_bytes": meter.peak_known_bytes,
                    "peak_bounded_workspace_bytes": meter.peak_bounded_bytes,
                    "network_request_count": 0,
                },
            ),
            terminal_class="R11A_V2_FAIL_CLOSED_EARLY_STOP",
            research_conclusion=(
                "ROOT_CAUSE_NOT_PROVEN_FAIL_CLOSED_EMPTY_ARTIFACT"
            ),
        )
        return outcome.final_directory
    except Exception:
        session.abort()
        raise


__all__ = ["PreflightArtifactError", "write_preflight_failure_artifact"]
