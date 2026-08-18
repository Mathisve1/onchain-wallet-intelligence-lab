from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping

from .artifact_schema import DIAGNOSTIC_ID, IMPLEMENTATION_ID
from .canonical import FrozenObject, NumberToken, strict_json_loads

_ACCOUNT_ID = "630956766927"
_ROLE_NAME = "onchain-wallet-intelligence-hl-archive-identity-r11a"
_SESSION_NAME = "HLArchiveR11AIdentityBoundary"
_SESSION_ARN = re.compile(
    rf"arn:aws:sts::{_ACCOUNT_ID}:assumed-role/{_ROLE_NAME}/{_SESSION_NAME}\Z"
)


class ContextBoundaryError(ValueError):
    pass


def _object(value: object, label: str) -> FrozenObject:
    if not isinstance(value, FrozenObject):
        raise ContextBoundaryError(f"{label} must be object")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContextBoundaryError(f"{label} must be nonempty text")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, NumberToken) and value.is_integer_token:
        return int(value.token)
    raise ContextBoundaryError(f"{label} must be exact integer")


def _sha(value: object, label: str) -> str:
    text = _text(value, label)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise ContextBoundaryError(f"{label} must be lowercase SHA-256")
    return text


def _commit(value: object, label: str) -> str:
    text = _text(value, label)
    if re.fullmatch(r"[0-9a-f]{40}", text) is None:
        raise ContextBoundaryError(f"{label} must be full Git commit")
    return text


@dataclasses.dataclass(frozen=True, slots=True)
class WorkflowContext:
    event_name: str
    dispatch_ref: str
    dispatch_sha: str
    checked_out_commit: str
    workflow_run_id: int
    workflow_run_attempt: int
    workflow_start_epoch_ns: int
    repository: str
    workflow_name: str
    approval_id: str
    approval_text_sha256: str
    execution_release_id: str
    execution_release_blob_sha256: str
    activation_id: str
    implementation_contract_sha256: str
    workflow_sha256: str
    collector_sha256: str
    validator_sha256: str
    selection_sha256: str
    pricing_snapshot_sha256: str
    single_use_window_start_utc: str

    @classmethod
    def from_bytes(cls, raw: bytes) -> "WorkflowContext":
        root = _object(strict_json_loads(raw), "workflow context")
        value = cls(
            event_name=_text(root["event_name"], "event_name"),
            dispatch_ref=_text(root["dispatch_ref"], "dispatch_ref"),
            dispatch_sha=_commit(root["dispatch_sha"], "dispatch_sha"),
            checked_out_commit=_commit(root["checked_out_commit"], "checked_out_commit"),
            workflow_run_id=_integer(root["workflow_run_id"], "workflow_run_id"),
            workflow_run_attempt=_integer(root["workflow_run_attempt"], "workflow_run_attempt"),
            workflow_start_epoch_ns=_integer(
                root["workflow_start_epoch_ns"], "workflow_start_epoch_ns"
            ),
            repository=_text(root["repository"], "repository"),
            workflow_name=_text(root["workflow_name"], "workflow_name"),
            approval_id=_text(root["approval_id"], "approval_id"),
            approval_text_sha256=_sha(root["approval_text_sha256"], "approval_text_sha256"),
            execution_release_id=_text(root["execution_release_id"], "execution_release_id"),
            execution_release_blob_sha256=_sha(
                root["execution_release_blob_sha256"], "execution_release_blob_sha256"
            ),
            activation_id=_text(root["activation_id"], "activation_id"),
            implementation_contract_sha256=_sha(
                root["implementation_contract_sha256"], "implementation_contract_sha256"
            ),
            workflow_sha256=_sha(root["workflow_sha256"], "workflow_sha256"),
            collector_sha256=_sha(root["collector_sha256"], "collector_sha256"),
            validator_sha256=_sha(root["validator_sha256"], "validator_sha256"),
            selection_sha256=_sha(root["selection_sha256"], "selection_sha256"),
            pricing_snapshot_sha256=_sha(
                root["pricing_snapshot_sha256"], "pricing_snapshot_sha256"
            ),
            single_use_window_start_utc=_text(
                root["single_use_window_start_utc"], "single_use_window_start_utc"
            ),
        )
        value.validate()
        return value

    def validate(self) -> None:
        if self.event_name != "workflow_dispatch":
            raise ContextBoundaryError("R11A requires workflow_dispatch")
        if self.dispatch_ref != "refs/heads/main":
            raise ContextBoundaryError("R11A requires canonical main")
        if self.dispatch_sha != self.checked_out_commit:
            raise ContextBoundaryError("checked-out commit differs from dispatch SHA")
        if self.workflow_run_id <= 0 or self.workflow_run_attempt != 1:
            raise ContextBoundaryError("R11A requires positive run ID at attempt one")
        if self.workflow_start_epoch_ns <= 0:
            raise ContextBoundaryError("workflow start epoch must be positive")
        if self.repository != "Mathisve1/onchain-wallet-intelligence-lab":
            raise ContextBoundaryError("repository identity drift")
        if self.workflow_name != "Hyperliquid Archive R11A Identity Boundary Diagnostic":
            raise ContextBoundaryError("workflow name drift")

    def mapping(self) -> dict[str, object]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True, slots=True)
class PrincipalEvidence:
    account: str
    arn: str
    user_id: str

    @classmethod
    def from_bytes(cls, raw: bytes) -> "PrincipalEvidence":
        root = _object(strict_json_loads(raw), "STS caller identity")
        value = cls(
            account=_text(root["Account"], "Account"),
            arn=_text(root["Arn"], "Arn"),
            user_id=_text(root["UserId"], "UserId"),
        )
        value.validate()
        return value

    def validate(self) -> None:
        if self.account != _ACCOUNT_ID:
            raise ContextBoundaryError("observed AWS account drift")
        if _SESSION_ARN.fullmatch(self.arn) is None:
            raise ContextBoundaryError("observed principal is not exact successor role session")
        if ":" not in self.user_id or not self.user_id.endswith(_SESSION_NAME):
            raise ContextBoundaryError("observed STS UserId session drift")

    def mapping(self) -> dict[str, object]:
        return {
            "observed_account_id": self.account,
            "observed_assumed_role_session_arn": self.arn,
            "observed_session_name": _SESSION_NAME,
            "expected_role_arn": f"arn:aws:iam::{_ACCOUNT_ID}:role/{_ROLE_NAME}",
        }


def combined_context(
    workflow: WorkflowContext,
    principal: PrincipalEvidence,
    *,
    pricing_projection_eur_micros: int,
) -> dict[str, object]:
    workflow.validate()
    principal.validate()
    return {
        "schema_version": "2.0",
        "diagnostic_id": DIAGNOSTIC_ID,
        "implementation_id": IMPLEMENTATION_ID,
        **workflow.mapping(),
        **principal.mapping(),
        "pricing_projection_eur_micros": pricing_projection_eur_micros,
        "principal_observed": True,
        "raw_aws_credentials_retained": False,
        "raw_oidc_token_retained": False,
        "raw_sts_response_retained": False,
        "rerun_authorized": False,
    }


def minimal_context_from_pending(
    raw: bytes,
    *,
    phase: str,
    principal_observed: bool,
    extra: Mapping[str, object] | None = None,
) -> dict[str, object]:
    root = _object(strict_json_loads(raw), "pending workflow context")
    result: dict[str, object] = {
        "schema_version": "2.0",
        "diagnostic_id": DIAGNOSTIC_ID,
        "implementation_id": IMPLEMENTATION_ID,
        "execution_phase": phase,
        "event_name": _text(root["event_name"], "event_name"),
        "dispatch_ref": _text(root["dispatch_ref"], "dispatch_ref"),
        "dispatch_sha": _commit(root["dispatch_sha"], "dispatch_sha"),
        "checked_out_commit": _commit(root["checked_out_commit"], "checked_out_commit"),
        "workflow_run_id": _integer(root["workflow_run_id"], "workflow_run_id"),
        "workflow_run_attempt": _integer(
            root["workflow_run_attempt"], "workflow_run_attempt"
        ),
        "workflow_start_epoch_ns": _integer(
            root["workflow_start_epoch_ns"], "workflow_start_epoch_ns"
        ),
        "repository": _text(root["repository"], "repository"),
        "workflow_name": _text(root["workflow_name"], "workflow_name"),
        "principal_observed": principal_observed,
        "s3_requests_executed": 0,
        "object_bytes_downloaded": 0,
        "rerun_authorized": False,
    }
    if extra is not None:
        result.update(extra)
    return result
