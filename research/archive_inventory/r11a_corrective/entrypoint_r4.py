from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from .canonical import FrozenObject, NumberToken, strict_json_loads
from .context import PrincipalEvidence, WorkflowContext, combined_context
from .network import AWSCredentials
from .pricing import PricingSnapshot
from .runner_r4 import RunInputs, prepare, run_network
from .selection import DEFAULT_SELECTION


class EntrypointError(ValueError):
    pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bounded R11A identity-boundary diagnostic")
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--workflow-context", required=True, type=Path)
    parser.add_argument("--principal-evidence", type=Path)
    parser.add_argument("--mode", choices=("execute", "pre-oidc-failure"), default="execute")
    parser.add_argument("--failure-code", default="PRE_OIDC_STATIC_GATE_FAILURE")
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--run-attempt", type=int)
    return parser


def _object(value: object, label: str) -> FrozenObject:
    if not isinstance(value, FrozenObject):
        raise EntrypointError(f"{label} must be object")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, NumberToken) and value.is_integer_token:
        return int(value.token, 10)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise EntrypointError(f"{label} must be exact integer")


def _minimal_context(raw: bytes, run_id: int | None, run_attempt: int | None) -> dict[str, object]:
    root = _object(strict_json_loads(raw), "pending workflow context")
    observed_run_id = _integer(root["workflow_run_id"], "workflow_run_id")
    observed_attempt = _integer(root["workflow_run_attempt"], "workflow_run_attempt")
    if run_id is not None and run_id != observed_run_id:
        raise EntrypointError("CLI run ID differs from pending context")
    if run_attempt is not None and run_attempt != observed_attempt:
        raise EntrypointError("CLI run attempt differs from pending context")
    if observed_run_id <= 0 or observed_attempt != 1:
        raise EntrypointError("pre-OIDC artifact requires positive run ID and attempt one")
    required = (
        "event_name",
        "dispatch_ref",
        "dispatch_sha",
        "checked_out_commit",
        "repository",
        "workflow_name",
    )
    for key in required:
        if not isinstance(root[key], str) or not root[key]:
            raise EntrypointError(f"pending context field is absent: {key}")
    return {
        "schema_version": "1.0",
        "diagnostic_id": "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-001",
        "execution_phase": "PRE_OIDC_STATIC_FAILURE",
        "event_name": root["event_name"],
        "dispatch_ref": root["dispatch_ref"],
        "dispatch_sha": root["dispatch_sha"],
        "checked_out_commit": root["checked_out_commit"],
        "workflow_run_id": observed_run_id,
        "workflow_run_attempt": observed_attempt,
        "repository": root["repository"],
        "workflow_name": root["workflow_name"],
        "pending_workflow_context_sha256": hashlib.sha256(raw).hexdigest(),
        "principal_observed": False,
        "s3_requests_executed": 0,
        "object_bytes_downloaded": 0,
        "rerun_authorized": False,
    }


def pre_oidc_failure(
    *,
    workspace: Path,
    context_path: Path,
    failure_code: str,
    run_id: int | None,
    run_attempt: int | None,
) -> int:
    raw = context_path.read_bytes()
    context = _minimal_context(raw, run_id, run_attempt)
    inputs = RunInputs(workspace=workspace, context=context)
    guard, meter, state, session = prepare(inputs)
    state.stop(
        failure_code,
        phase="PRE_OIDC_STATIC_GATES",
        evidence={"pending_workflow_context_sha256": context["pending_workflow_context_sha256"]},
    )
    outcome = session.finalize_empty(
        state=state,
        context=context,
        reducer_rows=(),
        resource_rows=(
            {
                "record_type": "RESOURCE_MEASUREMENT",
                "phase": "PRE_OIDC_STATIC_FAILURE",
                "elapsed_runtime_seconds_floor": guard.elapsed_seconds_floor(),
                "tracked_workspace_bytes": meter.known_bytes,
                "reserved_workspace_bytes": meter.reserved_bytes,
                "network_request_count": 0,
            },
        ),
        terminal_class="R11A_DIAGNOSTIC_INCOMPLETE",
        research_conclusion="ROOT_CAUSE_NOT_PROVEN_PRE_OIDC_FAIL_CLOSED_EMPTY_ARTIFACT",
        return_code=21,
    )
    print(outcome.final_directory)
    return 21


def execute(workspace: Path, context_path: Path, principal_path: Path) -> int:
    workflow = WorkflowContext.from_bytes(context_path.read_bytes())
    principal = PrincipalEvidence.from_bytes(principal_path.read_bytes())
    snapshot = PricingSnapshot.load()
    projected = snapshot.projected_eur_micros(72, DEFAULT_SELECTION.aggregate_expected_compressed_bytes)
    context = combined_context(workflow, principal, pricing_projection_eur_micros=projected)
    result = run_network(
        inputs=RunInputs(workspace=workspace, context=context),
        credentials=AWSCredentials.from_environment(),
        pricing_snapshot=snapshot,
    )
    print(result.artifact.final_directory)
    return result.artifact.return_code


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.mode == "pre-oidc-failure":
        return pre_oidc_failure(
            workspace=arguments.workspace,
            context_path=arguments.workflow_context,
            failure_code=arguments.failure_code,
            run_id=arguments.run_id,
            run_attempt=arguments.run_attempt,
        )
    if arguments.principal_evidence is None:
        raise SystemExit("--principal-evidence is required in execute mode")
    return execute(arguments.workspace, arguments.workflow_context, arguments.principal_evidence)


if __name__ == "__main__":
    raise SystemExit(main())
