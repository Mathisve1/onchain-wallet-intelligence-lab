from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping
from typing import Final

from .canonical import FrozenObject, NumberToken, strict_json_loads

_ACCOUNT_ID: Final[str] = "630956766927"
_ROLE_NAME: Final[str] = "onchain-wallet-intelligence-hl-archive-identity-r11a"
_SESSION_NAME: Final[str] = "HLArchiveR11AIdentityBoundary"
_EXPECTED_SESSION_ARN: Final[re.Pattern[str]] = re.compile(
    rf"arn:aws:sts::{_ACCOUNT_ID}:assumed-role/{_ROLE_NAME}/{_SESSION_NAME}\Z"
)


class ContextError(ValueError):
    pass


def _object(value: object, label: str) -> FrozenObject:
    if not isinstance(value, FrozenObject):
        raise ContextError(f"{label} must be an object")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContextError(f"{label} must be a nonempty string")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, NumberToken) and value.is_integer_token:
        return int(value.token, 10)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ContextError(f"{label} must be an exact integer")


def _sha(value: object, label: str) -> str:
    text = _text(value, label)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise ContextError(f"{label} must be a lowercase SHA-256")
    return text


def _commit(value: object, label: str) -> str:
    text = _text(value, label)
    if re.fullmatch(r"[0-9a-f]{40}", text) is None:
        raise ContextError(f"{label} must be a full lowercase Git commit")
    return text


@dataclasses.dataclass(frozen=True, slots=True)
class WorkflowContext:
    event_name: str
    dispatch_ref: str
    dispatch_sha: str
    checked_out_commit: str
    workflow_run_id: int
    workflow_run_attempt: int
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
        )
        value.validate()
        return value

    def validate(self) -> None:
        if self.event_name != "workflow_dispatch":
            raise ContextError("R11A execution requires workflow_dispatch")
        if self.dispatch_ref != "refs/heads/main":
            raise ContextError("R11A execution requires canonical main")
        if self.dispatch_sha != self.checked_out_commit:
            raise ContextError("checked-out commit differs from dispatch SHA")
        if self.workflow_run_id <= 0 or self.workflow_run_attempt != 1:
            raise ContextError("R11A run must be one positive run ID at attempt one")
        if self.repository != "Mathisve1/onchain-wallet-intelligence-lab":
            raise ContextError("repository identity drift")
        if self.workflow_name != "Hyperliquid Archive R11A Identity Boundary Diagnostic":
            raise ContextError("workflow name drift")

    def as_mapping(self) -> dict[str, object]:
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
            raise ContextError("observed AWS account differs from approved account")
        if _EXPECTED_SESSION_ARN.fullmatch(self.arn) is None:
            raise ContextError("observed principal is not the exact R11A role session")
        if ":" not in self.user_id or not self.user_id.endswith(_SESSION_NAME):
            raise ContextError("observed STS UserId session binding drift")

    def minimized_mapping(self) -> dict[str, object]:
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
        "schema_version": "1.0",
        "diagnostic_id": "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-001",
        **workflow.as_mapping(),
        **principal.minimized_mapping(),
        "pricing_projection_eur_micros": pricing_projection_eur_micros,
        "raw_aws_credentials_retained": False,
        "raw_oidc_token_retained": False,
        "raw_sts_response_retained": False,
        "rerun_authorized": False,
    }
