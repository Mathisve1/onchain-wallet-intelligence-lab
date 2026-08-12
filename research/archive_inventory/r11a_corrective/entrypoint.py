from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from .artifact_schema import PHASES
from .context import (
    PrincipalEvidence,
    WorkflowContext,
    combined_context,
    minimal_context_from_pending,
)
from .network import AWSCredentials
from .preflight_artifact_r7 import write_preflight_failure_artifact
from .pricing import PricingSnapshot
from .runner import RunInputs, run_network
from .selection import DEFAULT_SELECTION


class EntrypointBoundaryError(ValueError):
    pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bounded corrective R11A diagnostic")
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--workflow-context", required=True, type=Path)
    parser.add_argument("--principal-evidence", type=Path)
    parser.add_argument("--mode", choices=("execute", "failure"), default="execute")
    parser.add_argument("--failure-phase", choices=PHASES)
    parser.add_argument("--failure-code")
    parser.add_argument("--principal-observed", action="store_true")
    return parser


def _failure(
    *,
    workspace: Path,
    raw_context: bytes,
    phase: str,
    failure_code: str,
    principal_observed: bool,
    exception_type: type[BaseException] | None = None,
) -> int:
    extra: dict[str, object] = {}
    if exception_type is not None:
        extra["failure_exception_type_sha256"] = hashlib.sha256(
            exception_type.__name__.encode("utf-8")
        ).hexdigest()
    context = minimal_context_from_pending(
        raw_context,
        phase=phase,
        principal_observed=principal_observed,
        extra=extra,
    )
    final = write_preflight_failure_artifact(
        workspace=workspace,
        context=context,
        failure_code=failure_code,
        execution_phase=phase,
    )
    print(final)
    return 21


def execute(workspace: Path, context_path: Path, principal_path: Path) -> int:
    raw_context = context_path.read_bytes()
    try:
        workflow = WorkflowContext.from_bytes(raw_context)
        principal = PrincipalEvidence.from_bytes(principal_path.read_bytes())
        snapshot = PricingSnapshot.load()
        projected = snapshot.projected_eur_micros(
            72,
            DEFAULT_SELECTION.aggregate_expected_compressed_bytes,
        )
        context = combined_context(
            workflow,
            principal,
            pricing_projection_eur_micros=projected,
        )
        credentials = AWSCredentials.from_environment()
    except Exception as exc:
        return _failure(
            workspace=workspace,
            raw_context=raw_context,
            phase="POST_STS_PRECOLLECTOR",
            failure_code="POST_STS_PRECOLLECTOR_SETUP_FAILURE",
            principal_observed=principal_path.exists(),
            exception_type=type(exc),
        )
    result = run_network(
        inputs=RunInputs(workspace=workspace, context=context),
        credentials=credentials,
        pricing_snapshot=snapshot,
    )
    print(result.artifact.final_directory)
    return result.artifact.return_code


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    raw_context = arguments.workflow_context.read_bytes()
    if arguments.mode == "failure":
        if arguments.failure_phase is None or arguments.failure_code is None:
            raise SystemExit("failure mode requires --failure-phase and --failure-code")
        return _failure(
            workspace=arguments.workspace,
            raw_context=raw_context,
            phase=arguments.failure_phase,
            failure_code=arguments.failure_code,
            principal_observed=arguments.principal_observed,
        )
    if arguments.principal_evidence is None:
        raise SystemExit("execute mode requires --principal-evidence")
    return execute(
        arguments.workspace,
        arguments.workflow_context,
        arguments.principal_evidence,
    )


if __name__ == "__main__":
    raise SystemExit(main())
