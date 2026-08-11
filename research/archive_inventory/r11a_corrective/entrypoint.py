from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from .context import PrincipalEvidence, WorkflowContext, combined_context
from .network import AWSCredentials
from .pricing import PricingSnapshot
from .runner import RunInputs, _prepare, run_network
from .selection import DEFAULT_SELECTION


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bounded R11A identity-boundary diagnostic")
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--workflow-context", required=True, type=Path)
    parser.add_argument("--principal-evidence", type=Path)
    parser.add_argument(
        "--mode",
        choices=("execute", "pre-oidc-failure"),
        default="execute",
    )
    parser.add_argument("--failure-code", default="PRE_OIDC_STATIC_GATE_FAILURE")
    return parser


def _pre_oidc_failure(workspace: Path, context_path: Path, failure_code: str) -> int:
    raw_context = context_path.read_bytes()
    context_sha = hashlib.sha256(raw_context).hexdigest()
    inputs = RunInputs(
        workspace=workspace,
        context={
            "schema_version": "1.0",
            "diagnostic_id": "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-001",
            "execution_phase": "PRE_OIDC_STATIC_FAILURE",
            "pending_workflow_context_sha256": context_sha,
            "principal_observed": False,
            "s3_requests_executed": 0,
            "object_bytes_downloaded": 0,
            "rerun_authorized": False,
        },
    )
    guard, meter, state, session = _prepare(inputs)
    state.stop(
        failure_code,
        phase="PRE_OIDC_STATIC_GATES",
        evidence={"pending_workflow_context_sha256": context_sha},
    )
    outcome = session.finalize_empty(
        state=state,
        context=inputs.context,
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


def _execute(workspace: Path, context_path: Path, principal_path: Path) -> int:
    workflow = WorkflowContext.from_bytes(context_path.read_bytes())
    principal = PrincipalEvidence.from_bytes(principal_path.read_bytes())
    snapshot = PricingSnapshot.load()
    projected = snapshot.projected_eur_micros(
        72, DEFAULT_SELECTION.aggregate_expected_compressed_bytes
    )
    context = combined_context(
        workflow,
        principal,
        pricing_projection_eur_micros=projected,
    )
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
        return _pre_oidc_failure(
            arguments.workspace,
            arguments.workflow_context,
            arguments.failure_code,
        )
    if arguments.principal_evidence is None:
        raise SystemExit("--principal-evidence is required in execute mode")
    return _execute(
        arguments.workspace,
        arguments.workflow_context,
        arguments.principal_evidence,
    )


if __name__ == "__main__":
    raise SystemExit(main())
