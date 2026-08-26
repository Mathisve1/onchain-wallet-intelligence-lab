#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

try:
    from governance.r11a_stage_common_r4 import (
        APPROVED_PERMISSION_SHA,
        APPROVED_TRUST_SHA,
        ALIGNMENT_ID,
        ALIGNMENT_PREDECESSOR_HEAD,
        ALIGNMENT_PREDECESSOR_TREE,
        ALIGNMENT_RELATIVE,
        APPROVAL_RECEIPT_SHA,
        G2_REVIEW_ID,
        PERMISSION_POLICY_RELATIVE,
        ROLE_ARN,
        ROLE_ATTESTATION_RELATIVE,
        ROOT,
        TRUST_POLICY_RELATIVE,
        load,
        require,
        require_exact,
        require_fresh_review,
        require_int,
        require_commit,
        require_git_oid,
        require_sha256,
        sha256,
        stage_authority,
        successor_permissions,
        trading_authority,
    )
    from governance.validate_r11a_approval_r4 import validate as validate_approval
except ModuleNotFoundError:
    from r11a_stage_common_r4 import (
        APPROVED_PERMISSION_SHA,
        APPROVED_TRUST_SHA,
        ALIGNMENT_ID,
        ALIGNMENT_PREDECESSOR_HEAD,
        ALIGNMENT_PREDECESSOR_TREE,
        ALIGNMENT_RELATIVE,
        APPROVAL_RECEIPT_SHA,
        G2_REVIEW_ID,
        PERMISSION_POLICY_RELATIVE,
        ROLE_ARN,
        ROLE_ATTESTATION_RELATIVE,
        ROOT,
        TRUST_POLICY_RELATIVE,
        load,
        require,
        require_exact,
        require_fresh_review,
        require_int,
        require_commit,
        require_git_oid,
        require_sha256,
        sha256,
        stage_authority,
        successor_permissions,
        trading_authority,
    )
    from validate_r11a_approval_r4 import validate as validate_approval

ATTESTATION = ROOT / ROLE_ATTESTATION_RELATIVE
ATTESTATION_KEYS = frozenset(
    {
        "schema_version",
        "attestation_id",
        "status",
        "alignment_id",
        "alignment_record_sha256",
        "approval_receipt_sha256",
        "g2_review_id",
        "alignment_review_completed",
        "alignment_review_id",
        "alignment_review_event",
        "alignment_review_verdict",
        "alignment_reviewed_head",
        "alignment_reviewed_tree",
        "identity_creation_and_configuration_review_completed",
        "identity_creation_and_configuration_review_id",
        "identity_creation_and_configuration_review_event",
        "identity_creation_and_configuration_review_verdict",
        "identity_creation_and_configuration_reviewed_head",
        "identity_creation_and_configuration_reviewed_tree",
        "account_id",
        "role_arn",
        "role_max_session_duration_seconds",
        "persistent_permission_resource_count",
        "persistent_permission_resources_match_exact_selection",
        "additional_managed_policies_attached",
        "additional_inline_policies_attached",
        "additional_role_created",
        "reusable_credentials_present",
        "access_keys_present",
        "secrets_present",
        "existing_r11_role_mutated",
        "existing_r11_role_reused",
        "trust_policy_sha256",
        "permission_policy_sha256",
        "s3_requests_performed_during_operator_step",
        "object_bytes_downloaded_during_operator_step",
        "sts_only_preflight_required",
        "sts_only_preflight_completed",
        "downstream_authorizations",
        "trading_authorizations",
    }
)


def validate(
    root: Path = ROOT,
    *,
    permitted_successor_paths: frozenset[str] = frozenset(),
    runtime_pricing_projection_permitted: bool = False,
) -> dict[str, object]:
    permitted = successor_permissions(
        frozenset(permitted_successor_paths) | {ROLE_ATTESTATION_RELATIVE}
    )
    validate_approval(
        root,
        permitted_successor_paths=permitted,
        runtime_pricing_projection_permitted=runtime_pricing_projection_permitted,
    )
    attestation = load(
        root,
        ROLE_ATTESTATION_RELATIVE,
        missing_label="successor role attestation is absent",
    )
    require_exact(attestation, ATTESTATION_KEYS, "role attestation")
    require(attestation["schema_version"] == "1.0", "role attestation schema drift")
    require(
        attestation["attestation_id"] == "ATTEST_HL_ARCHIVE_R11A_SUCCESSOR_ROLE_001",
        "role attestation ID drift",
    )
    require(
        attestation["status"] == "ROLE_CREATED_POLICIES_APPLIED_AWAITING_STS_PREFLIGHT",
        "role attestation status drift",
    )
    require(attestation["alignment_id"] == ALIGNMENT_ID, "role alignment ID drift")
    require_sha256(attestation["alignment_record_sha256"], "alignment_record_sha256")
    require(
        attestation["alignment_record_sha256"] == sha256(root, ALIGNMENT_RELATIVE),
        "role alignment record binding drift",
    )
    require_sha256(attestation["approval_receipt_sha256"], "approval_receipt_sha256")
    require(
        attestation["approval_receipt_sha256"] == APPROVAL_RECEIPT_SHA,
        "role approval receipt binding drift",
    )
    require_int(attestation["g2_review_id"], "G2 review ID")
    require(attestation["g2_review_id"] == G2_REVIEW_ID, "role G2 review lineage drift")
    require(attestation["alignment_review_completed"] is True, "alignment review is not complete")
    require_int(attestation["alignment_review_id"], "alignment review ID")
    require(attestation["alignment_review_id"] > 0, "alignment review ID must be positive")
    require(attestation["alignment_review_id"] != G2_REVIEW_ID, "alignment review reuses G2 review")
    require(attestation["alignment_review_event"] == "COMMENTED", "alignment review event drift")
    require(attestation["alignment_review_verdict"] == "GREEN", "alignment review verdict is not GREEN")
    require_commit(attestation["alignment_reviewed_head"], "alignment_reviewed_head")
    require_git_oid(attestation["alignment_reviewed_tree"], "alignment_reviewed_tree")
    require(
        attestation["alignment_reviewed_head"] != ALIGNMENT_PREDECESSOR_HEAD,
        "alignment review does not review an alignment successor",
    )
    require(
        attestation["alignment_reviewed_tree"] != ALIGNMENT_PREDECESSOR_TREE,
        "alignment review tree reuses predecessor tree",
    )
    require_fresh_review(attestation, "alignment_review", "alignment review")
    require(
        attestation["identity_creation_and_configuration_review_completed"] is True,
        "identity creation/configuration review is not complete",
    )
    require_int(
        attestation["identity_creation_and_configuration_review_id"],
        "identity creation/configuration review ID",
    )
    require(
        attestation["identity_creation_and_configuration_review_id"] > 0,
        "identity creation/configuration review ID must be positive",
    )
    require(
        attestation["identity_creation_and_configuration_review_id"]
        != attestation["alignment_review_id"],
        "identity creation/configuration review is not separate from alignment review",
    )
    require(
        attestation["identity_creation_and_configuration_review_event"] == "COMMENTED",
        "identity creation/configuration review event drift",
    )
    require(
        attestation["identity_creation_and_configuration_review_verdict"] == "GREEN",
        "identity creation/configuration review verdict is not GREEN",
    )
    require_commit(
        attestation["identity_creation_and_configuration_reviewed_head"],
        "identity_creation_and_configuration_reviewed_head",
    )
    require_git_oid(
        attestation["identity_creation_and_configuration_reviewed_tree"],
        "identity_creation_and_configuration_reviewed_tree",
    )
    require(
        attestation["identity_creation_and_configuration_reviewed_head"]
        != attestation["alignment_reviewed_head"],
        "identity creation/configuration review reuses alignment-reviewed head",
    )
    require(
        attestation["identity_creation_and_configuration_reviewed_tree"]
        != attestation["alignment_reviewed_tree"],
        "identity creation/configuration review reuses alignment-reviewed tree",
    )
    require_fresh_review(
        attestation,
        "identity_creation_and_configuration_review",
        "identity creation/configuration review",
        ancestors=((attestation, "alignment_review"),),
    )
    require(attestation["account_id"] == "630956766927", "role AWS account drift")
    require(attestation["role_arn"] == ROLE_ARN, "successor role ARN drift")
    require_int(attestation["role_max_session_duration_seconds"], "role max session duration")
    require(attestation["role_max_session_duration_seconds"] == 21600, "role max session duration drift")
    require_int(attestation["persistent_permission_resource_count"], "persistent permission resource count")
    require(attestation["persistent_permission_resource_count"] == 72, "persistent permission resource count drift")
    require(
        attestation["persistent_permission_resources_match_exact_selection"] is True,
        "persistent policy differs from exact selection",
    )
    require(attestation["additional_managed_policies_attached"] is False, "managed policy attached")
    require(attestation["additional_inline_policies_attached"] is False, "additional inline policy attached")
    require(attestation["additional_role_created"] is False, "additional role created")
    require(attestation["reusable_credentials_present"] is False, "reusable credentials present")
    require(attestation["access_keys_present"] is False, "access keys present")
    require(attestation["secrets_present"] is False, "secrets present")
    require(attestation["existing_r11_role_mutated"] is False, "consumed R11 role mutated")
    require(attestation["existing_r11_role_reused"] is False, "consumed R11 role reused")
    require_sha256(attestation["trust_policy_sha256"], "trust_policy_sha256")
    require_sha256(attestation["permission_policy_sha256"], "permission_policy_sha256")
    require(attestation["trust_policy_sha256"] == APPROVED_TRUST_SHA, "installed trust policy is not owner-bound")
    require(attestation["permission_policy_sha256"] == APPROVED_PERMISSION_SHA, "installed permission policy is not owner-bound")
    require(attestation["trust_policy_sha256"] == sha256(root, TRUST_POLICY_RELATIVE), "installed trust policy hash drift")
    require(attestation["permission_policy_sha256"] == sha256(root, PERMISSION_POLICY_RELATIVE), "installed permission policy hash drift")
    require_int(attestation["s3_requests_performed_during_operator_step"], "operator S3 request count")
    require(attestation["s3_requests_performed_during_operator_step"] == 0, "operator role step performed S3 request")
    require_int(attestation["object_bytes_downloaded_during_operator_step"], "operator downloaded bytes")
    require(attestation["object_bytes_downloaded_during_operator_step"] == 0, "operator role step downloaded object bytes")
    require(attestation["sts_only_preflight_required"] is True, "STS preflight requirement missing")
    require(attestation["sts_only_preflight_completed"] is False, "historical role snapshot rewritten after preflight")
    stage_authority(attestation["downstream_authorizations"], "role-attestation downstream authority")
    trading_authority(attestation["trading_authorizations"], "role-attestation trading authority")
    return attestation


def main() -> int:
    validate()
    print("R11A_SUCCESSOR_ROLE_ATTESTATION_R4_VALID_AWAITING_STS_PREFLIGHT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
