#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).absolute().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))
import difflib as _r11a_bytecode_boundary  # noqa: E402,F401

try:
    from governance.r11a_stage_common_r4 import (
        ALIGNMENT_ID,
        ALIGNMENT_RELATIVE,
        APPROVAL_JSON_RELATIVE,
        APPROVAL_RECEIPT_SHA,
        APPROVAL_TEXT_RELATIVE,
        APPROVED_PERMISSION_SHA,
        APPROVED_TRUST_SHA,
        G2_REVIEW_ID,
        PERMISSION_POLICY_RELATIVE,
        REVIEW_EVIDENCE_PATHS,
        ROLE_ARN,
        ROLE_CONFIGURATION_CANDIDATE_RELATIVE,
        ROOT,
        TRUST_POLICY_RELATIVE,
        alignment_review_target_files,
        load,
        require,
        require_exact,
        require_gate_review,
        require_int,
        require_sha256,
        sha256,
        stage_authority,
        successor_permissions,
        trading_authority,
    )
    from governance.validate_r11a_approval_r4 import validate as validate_approval
except ModuleNotFoundError:
    from r11a_stage_common_r4 import (
        ALIGNMENT_ID,
        ALIGNMENT_RELATIVE,
        APPROVAL_JSON_RELATIVE,
        APPROVAL_RECEIPT_SHA,
        APPROVAL_TEXT_RELATIVE,
        APPROVED_PERMISSION_SHA,
        APPROVED_TRUST_SHA,
        G2_REVIEW_ID,
        PERMISSION_POLICY_RELATIVE,
        REVIEW_EVIDENCE_PATHS,
        ROLE_ARN,
        ROLE_CONFIGURATION_CANDIDATE_RELATIVE,
        ROOT,
        TRUST_POLICY_RELATIVE,
        alignment_review_target_files,
        load,
        require,
        require_exact,
        require_gate_review,
        require_int,
        require_sha256,
        sha256,
        stage_authority,
        successor_permissions,
        trading_authority,
    )
    from validate_r11a_approval_r4 import validate as validate_approval


ALIGNMENT_REVIEW_GATE = "R11A_ALIGNMENT_REVIEW"
CANDIDATE_KEYS = frozenset(
    {
        "schema_version",
        "configuration_candidate_id",
        "status",
        "alignment_id",
        "alignment_record_sha256",
        "approval_receipt_sha256",
        "g2_review_id",
        "alignment_review_evidence_sha256",
        "account_id",
        "role_arn",
        "role_max_session_duration_seconds",
        "persistent_permission_resource_count",
        "persistent_permission_resources_match_exact_selection",
        "trust_policy_sha256",
        "permission_policy_sha256",
        "additional_managed_policies_authorized",
        "additional_inline_policies_authorized",
        "additional_role_authorized",
        "reusable_credentials_authorized",
        "access_keys_authorized",
        "secrets_authorized",
        "existing_r11_role_mutation_authorized",
        "existing_r11_role_reuse_authorized",
        "role_creation_authorized_by_candidate",
        "role_creation_eligible_after_separate_review",
        "network_requests_executed_by_candidate",
        "aws_iam_mutations_executed_by_candidate",
        "downstream_authorizations",
        "trading_authorizations",
    }
)


def validate(
    root: Path = ROOT,
    *,
    permitted_successor_paths: frozenset[str] = frozenset(),
    runtime_pricing_projection_permitted: bool = False,
    _review_lineage: list[object] | None = None,
) -> dict[str, object]:
    lineage = [] if _review_lineage is None else _review_lineage
    evidence_relative = REVIEW_EVIDENCE_PATHS[ALIGNMENT_REVIEW_GATE]
    permitted = successor_permissions(
        frozenset(permitted_successor_paths)
        | {ROLE_CONFIGURATION_CANDIDATE_RELATIVE, evidence_relative}
    )
    validate_approval(
        root,
        permitted_successor_paths=permitted,
        runtime_pricing_projection_permitted=runtime_pricing_projection_permitted,
    )
    candidate = load(
        root,
        ROLE_CONFIGURATION_CANDIDATE_RELATIVE,
        missing_label="successor role creation/configuration candidate is absent",
    )
    require_exact(candidate, CANDIDATE_KEYS, "role configuration candidate")
    require(candidate["schema_version"] == "1.0", "role configuration candidate schema drift")
    require(
        candidate["configuration_candidate_id"]
        == "R11A-SUCCESSOR-IDENTITY-CREATION-AND-CONFIGURATION-001",
        "role configuration candidate ID drift",
    )
    require(
        candidate["status"]
        == "CANDIDATE_AWAITING_EXACT_HEAD_COMMENTED_GREEN_IDENTITY_CONFIGURATION_REVIEW_NO_AWS",
        "role configuration candidate status drift",
    )
    require(candidate["alignment_id"] == ALIGNMENT_ID, "role configuration alignment ID drift")
    require_sha256(candidate["alignment_record_sha256"], "alignment_record_sha256")
    require(
        candidate["alignment_record_sha256"] == sha256(root, ALIGNMENT_RELATIVE),
        "role configuration alignment record binding drift",
    )
    require_sha256(candidate["approval_receipt_sha256"], "approval_receipt_sha256")
    require(
        candidate["approval_receipt_sha256"] == APPROVAL_RECEIPT_SHA,
        "role configuration approval receipt binding drift",
    )
    require_int(candidate["g2_review_id"], "G2 review ID")
    require(candidate["g2_review_id"] == G2_REVIEW_ID, "role configuration G2 review lineage drift")
    require_gate_review(
        root,
        candidate,
        "alignment_review_evidence_sha256",
        ALIGNMENT_REVIEW_GATE,
        target_files=alignment_review_target_files(root),
        predecessor_files={
            APPROVAL_JSON_RELATIVE: sha256(root, APPROVAL_JSON_RELATIVE),
            APPROVAL_TEXT_RELATIVE: sha256(root, APPROVAL_TEXT_RELATIVE),
        },
        lineage=lineage,
        expected_pr_number=151,
    )
    require(candidate["account_id"] == "630956766927", "role configuration AWS account drift")
    require(candidate["role_arn"] == ROLE_ARN, "role configuration ARN drift")
    require_int(candidate["role_max_session_duration_seconds"], "role max session duration")
    require(candidate["role_max_session_duration_seconds"] == 21600, "role max session duration drift")
    require_int(candidate["persistent_permission_resource_count"], "persistent permission resource count")
    require(candidate["persistent_permission_resource_count"] == 72, "persistent permission resource count drift")
    require(
        candidate["persistent_permission_resources_match_exact_selection"] is True,
        "persistent policy differs from exact selection",
    )
    require_sha256(candidate["trust_policy_sha256"], "trust_policy_sha256")
    require(candidate["trust_policy_sha256"] == APPROVED_TRUST_SHA, "trust policy is not owner-bound")
    require(candidate["trust_policy_sha256"] == sha256(root, TRUST_POLICY_RELATIVE), "trust policy hash drift")
    require_sha256(candidate["permission_policy_sha256"], "permission_policy_sha256")
    require(candidate["permission_policy_sha256"] == APPROVED_PERMISSION_SHA, "permission policy is not owner-bound")
    require(candidate["permission_policy_sha256"] == sha256(root, PERMISSION_POLICY_RELATIVE), "permission policy hash drift")
    for key, label in (
        ("additional_managed_policies_authorized", "managed policy"),
        ("additional_inline_policies_authorized", "additional inline policy"),
        ("additional_role_authorized", "additional role"),
        ("reusable_credentials_authorized", "reusable credentials"),
        ("access_keys_authorized", "access keys"),
        ("secrets_authorized", "secrets"),
        ("existing_r11_role_mutation_authorized", "consumed R11 role mutation"),
        ("existing_r11_role_reuse_authorized", "consumed R11 role reuse"),
        ("role_creation_authorized_by_candidate", "unreviewed role creation"),
    ):
        require(candidate[key] is False, f"role configuration candidate authorizes {label}")
    require(
        candidate["role_creation_eligible_after_separate_review"] is True,
        "role configuration candidate omits separate review gate",
    )
    require_int(candidate["network_requests_executed_by_candidate"], "candidate network count")
    require(candidate["network_requests_executed_by_candidate"] == 0, "role configuration candidate performed network request")
    require_int(candidate["aws_iam_mutations_executed_by_candidate"], "candidate IAM count")
    require(candidate["aws_iam_mutations_executed_by_candidate"] == 0, "role configuration candidate mutated IAM")
    stage_authority(candidate["downstream_authorizations"], "role-configuration downstream authority")
    trading_authority(candidate["trading_authorizations"], "role-configuration trading authority")
    return candidate


def main() -> int:
    validate()
    print("R11A_SUCCESSOR_ROLE_CONFIGURATION_CANDIDATE_R4_VALID_INERT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
