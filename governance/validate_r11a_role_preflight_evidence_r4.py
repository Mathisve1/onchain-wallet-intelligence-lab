#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

try:
    from governance.r11a_stage_common_r4 import (
        ALIGNMENT_RELATIVE,
        APPROVAL_RECEIPT_SHA,
        APPROVED_PERMISSION_SHA,
        APPROVED_TRUST_SHA,
        PREFLIGHT_CANDIDATE_RELATIVE,
        PREFLIGHT_CONSUMPTION_RELATIVE,
        PREFLIGHT_EVIDENCE_RELATIVE,
        PREFLIGHT_RELEASE_RELATIVE,
        ROLE_ATTESTATION_RELATIVE,
        ROLE_ARN,
        ROOT,
        load,
        require,
        require_commit,
        require_distinct_review,
        require_exact,
        require_fresh_review,
        require_green_review,
        require_git_oid,
        require_int,
        require_sha256,
        sha256,
        stage_authority,
        successor_permissions,
        trading_authority,
    )
    from governance.validate_r11a_role_attestation_r4 import validate as validate_role
except ModuleNotFoundError:
    from r11a_stage_common_r4 import (
        ALIGNMENT_RELATIVE,
        APPROVAL_RECEIPT_SHA,
        APPROVED_PERMISSION_SHA,
        APPROVED_TRUST_SHA,
        PREFLIGHT_CANDIDATE_RELATIVE,
        PREFLIGHT_CONSUMPTION_RELATIVE,
        PREFLIGHT_EVIDENCE_RELATIVE,
        PREFLIGHT_RELEASE_RELATIVE,
        ROLE_ATTESTATION_RELATIVE,
        ROLE_ARN,
        ROOT,
        load,
        require,
        require_commit,
        require_distinct_review,
        require_exact,
        require_fresh_review,
        require_green_review,
        require_git_oid,
        require_int,
        require_sha256,
        sha256,
        stage_authority,
        successor_permissions,
        trading_authority,
    )
    from validate_r11a_role_attestation_r4 import validate as validate_role

PREFLIGHT_CANDIDATE = ROOT / PREFLIGHT_CANDIDATE_RELATIVE
PREFLIGHT_RELEASE = ROOT / PREFLIGHT_RELEASE_RELATIVE
EVIDENCE = ROOT / PREFLIGHT_EVIDENCE_RELATIVE
CONSUMPTION = ROOT / PREFLIGHT_CONSUMPTION_RELATIVE

CANDIDATE_KEYS = frozenset(
    {
        "schema_version",
        "preflight_candidate_id",
        "status",
        "role_attestation_review_completed",
        "role_attestation_review_id",
        "role_attestation_review_event",
        "role_attestation_review_verdict",
        "role_attestation_reviewed_head",
        "role_attestation_reviewed_tree",
        "role_attestation_sha256",
        "alignment_record_sha256",
        "approval_receipt_sha256",
        "permission_policy_sha256",
        "oidc_trust_policy_sha256",
        "account_id",
        "role_arn",
        "dispatch_ref_required",
        "workflow_run_attempt_required",
        "maximum_sts_get_caller_identity_calls",
        "authorized_aws_actions_after_release",
        "sts_call_authorized_by_candidate",
        "single_use_sts_preflight_eligible_after_release",
        "s3_requests_authorized",
        "requester_pays_authorized",
        "object_body_access_authorized",
        "decompression_authorized",
        "workflow_installation_authorized",
        "diagnostic_execution_authorized",
        "network_requests_executed_by_candidate",
        "aws_iam_mutations_executed_by_candidate",
        "downstream_authorizations",
        "trading_authorizations",
    }
)
RELEASE_KEYS = frozenset(
    {
        "schema_version",
        "preflight_release_id",
        "preflight_candidate_id",
        "status",
        "preflight_candidate_sha256",
        "candidate_review_completed",
        "candidate_review_id",
        "candidate_review_event",
        "candidate_review_verdict",
        "candidate_reviewed_head",
        "candidate_reviewed_tree",
        "role_attestation_sha256",
        "alignment_record_sha256",
        "approval_receipt_sha256",
        "permission_policy_sha256",
        "oidc_trust_policy_sha256",
        "account_id",
        "role_arn",
        "authorized_aws_actions",
        "maximum_sts_get_caller_identity_calls",
        "single_sts_get_caller_identity_authorized",
        "s3_requests_authorized",
        "requester_pays_authorized",
        "object_body_access_authorized",
        "decompression_authorized",
        "workflow_installation_authorized",
        "release_or_activation_authorized",
        "diagnostic_execution_authorized",
        "single_use",
        "release_consumed",
        "rerun_authorized",
        "network_requests_executed_by_release",
        "aws_iam_mutations_executed_by_release",
        "downstream_authorizations",
        "trading_authorizations",
    }
)

EVIDENCE_KEYS = frozenset(
    {
        "schema_version",
        "preflight_id",
        "status",
        "technical_result",
        "preflight_release_id",
        "preflight_release_sha256",
        "role_attestation_sha256",
        "alignment_record_sha256",
        "approval_receipt_sha256",
        "permission_policy_sha256",
        "oidc_trust_policy_sha256",
        "expected_role_arn",
        "observed_account_id",
        "observed_assumed_role_session_arn",
        "dispatch_sha",
        "dispatch_ref",
        "workflow_run_attempt",
        "explicit_sts_caller_identity_calls",
        "authorized_aws_actions",
        "s3_requests_authorized",
        "requester_pays_authorized",
        "object_body_access_authorized",
        "decompression_authorized",
        "workflow_installation_authorized",
        "release_authorized",
        "activation_authorized",
        "diagnostic_execution_authorized",
        "s3_http_request_count",
        "object_bytes_downloaded",
        "downstream_authorizations",
        "trading_authorizations",
    }
)
CONSUMPTION_KEYS = frozenset(
    {
        "schema_version",
        "consumption_id",
        "status",
        "preflight_id",
        "preflight_release_id",
        "preflight_release_sha256",
        "preflight_evidence_sha256",
        "preflight_release_consumed",
        "rerun_authorized",
        "s3_requests_executed",
        "object_bytes_downloaded",
        "downstream_authorizations",
        "trading_authorizations",
    }
)


def validate_candidate(
    root: Path = ROOT,
    *,
    permitted_successor_paths: frozenset[str] = frozenset(),
    runtime_pricing_projection_permitted: bool = False,
) -> dict[str, object]:
    permitted = successor_permissions(
        frozenset(permitted_successor_paths) | {PREFLIGHT_CANDIDATE_RELATIVE}
    )
    role_attestation = validate_role(
        root,
        permitted_successor_paths=permitted,
        runtime_pricing_projection_permitted=runtime_pricing_projection_permitted,
    )
    candidate = load(
        root,
        PREFLIGHT_CANDIDATE_RELATIVE,
        missing_label="STS preflight candidate is absent",
    )
    require_exact(candidate, CANDIDATE_KEYS, "STS preflight candidate")
    require(candidate["schema_version"] == "1.0", "preflight candidate schema drift")
    require(
        candidate["preflight_candidate_id"]
        == "CANDIDATE_HL_ARCHIVE_R11A_STS_ONLY_PREFLIGHT_001",
        "preflight candidate ID drift",
    )
    require(
        candidate["status"]
        == "CANDIDATE_AWAITING_INDEPENDENT_STS_ONLY_PREFLIGHT_RELEASE_REVIEW_NO_AWS",
        "preflight candidate status drift",
    )
    require_green_review(candidate, "role_attestation_review", "role attestation review")
    require_distinct_review(
        candidate,
        "role_attestation_review",
        role_attestation,
        "identity_creation_and_configuration_review",
        "role attestation review",
    )
    require_fresh_review(
        candidate,
        "role_attestation_review",
        "role attestation review",
        ancestors=(
            (role_attestation, "alignment_review"),
            (role_attestation, "identity_creation_and_configuration_review"),
        ),
    )
    bindings = {
        "role_attestation_sha256": ROLE_ATTESTATION_RELATIVE,
        "alignment_record_sha256": ALIGNMENT_RELATIVE,
    }
    for key, relative in bindings.items():
        require_sha256(candidate[key], key)
        require(candidate[key] == sha256(root, relative), f"preflight candidate {key} drift")
    require_sha256(candidate["approval_receipt_sha256"], "approval_receipt_sha256")
    require(candidate["approval_receipt_sha256"] == APPROVAL_RECEIPT_SHA, "preflight candidate approval binding drift")
    require_sha256(candidate["permission_policy_sha256"], "permission_policy_sha256")
    require(candidate["permission_policy_sha256"] == APPROVED_PERMISSION_SHA, "preflight candidate permission-policy drift")
    require_sha256(candidate["oidc_trust_policy_sha256"], "oidc_trust_policy_sha256")
    require(candidate["oidc_trust_policy_sha256"] == APPROVED_TRUST_SHA, "preflight candidate trust-policy drift")
    require(candidate["account_id"] == "630956766927", "preflight candidate account drift")
    require(candidate["role_arn"] == ROLE_ARN, "preflight candidate role ARN drift")
    require(candidate["dispatch_ref_required"] == "refs/heads/main", "preflight candidate main-ref drift")
    require_int(candidate["workflow_run_attempt_required"], "preflight candidate workflow attempt")
    require(candidate["workflow_run_attempt_required"] == 1, "preflight candidate rerun authority drift")
    require_int(candidate["maximum_sts_get_caller_identity_calls"], "preflight candidate STS call cap")
    require(candidate["maximum_sts_get_caller_identity_calls"] == 1, "preflight candidate STS call cap drift")
    require(
        type(candidate["authorized_aws_actions_after_release"]) is list
        and candidate["authorized_aws_actions_after_release"] == ["sts:GetCallerIdentity"],
        "preflight candidate AWS action scope drift",
    )
    require(candidate["sts_call_authorized_by_candidate"] is False, "preflight candidate self-authorizes STS")
    require(candidate["single_use_sts_preflight_eligible_after_release"] is True, "preflight candidate omits release gate")
    for key, label in (
        ("s3_requests_authorized", "S3"),
        ("requester_pays_authorized", "Requester Pays"),
        ("object_body_access_authorized", "object body"),
        ("decompression_authorized", "decompression"),
        ("workflow_installation_authorized", "workflow installation"),
        ("diagnostic_execution_authorized", "diagnostic execution"),
    ):
        require(candidate[key] is False, f"preflight candidate authorizes {label}")
    require_int(candidate["network_requests_executed_by_candidate"], "preflight-candidate network count")
    require(candidate["network_requests_executed_by_candidate"] == 0, "preflight candidate performed network request")
    require_int(candidate["aws_iam_mutations_executed_by_candidate"], "preflight-candidate IAM count")
    require(candidate["aws_iam_mutations_executed_by_candidate"] == 0, "preflight candidate mutated IAM")
    stage_authority(candidate["downstream_authorizations"], "preflight-candidate downstream authority")
    trading_authority(candidate["trading_authorizations"], "preflight-candidate trading authority")
    return candidate


def validate_release(
    root: Path = ROOT,
    *,
    permitted_successor_paths: frozenset[str] = frozenset(),
    runtime_pricing_projection_permitted: bool = False,
) -> dict[str, object]:
    permitted = successor_permissions(
        frozenset(permitted_successor_paths)
        | {PREFLIGHT_CANDIDATE_RELATIVE, PREFLIGHT_RELEASE_RELATIVE}
    )
    candidate = validate_candidate(
        root,
        permitted_successor_paths=permitted,
        runtime_pricing_projection_permitted=runtime_pricing_projection_permitted,
    )
    role_attestation = load(root, ROLE_ATTESTATION_RELATIVE)
    release = load(
        root,
        PREFLIGHT_RELEASE_RELATIVE,
        missing_label="STS preflight release is absent",
    )
    require_exact(release, RELEASE_KEYS, "STS preflight release")
    require(release["schema_version"] == "1.0", "preflight release schema drift")
    require(release["preflight_release_id"] == "RELEASE_HL_ARCHIVE_R11A_STS_ONLY_PREFLIGHT_001", "preflight release ID drift")
    require(release["preflight_candidate_id"] == candidate["preflight_candidate_id"], "preflight release candidate ID drift")
    require(release["status"] == "RELEASED_FOR_EXACTLY_ONE_STS_GET_CALLER_IDENTITY_NO_S3", "preflight release status drift")
    require_sha256(release["preflight_candidate_sha256"], "preflight_candidate_sha256")
    require(release["preflight_candidate_sha256"] == sha256(root, PREFLIGHT_CANDIDATE_RELATIVE), "preflight release candidate hash drift")
    require(release["candidate_review_completed"] is True, "preflight candidate review is not complete")
    require_int(release["candidate_review_id"], "preflight candidate review ID")
    require(release["candidate_review_id"] > 0, "preflight candidate review ID must be positive")
    require(release["candidate_review_event"] == "COMMENTED", "preflight candidate review event drift")
    require(release["candidate_review_verdict"] == "GREEN", "preflight candidate review verdict is not GREEN")
    require_commit(release["candidate_reviewed_head"], "candidate_reviewed_head")
    require_git_oid(release["candidate_reviewed_tree"], "candidate_reviewed_tree")
    require_distinct_review(
        release,
        "candidate_review",
        candidate,
        "role_attestation_review",
        "STS preflight candidate review",
    )
    require_fresh_review(
        release,
        "candidate_review",
        "STS preflight candidate review",
        ancestors=(
            (role_attestation, "alignment_review"),
            (role_attestation, "identity_creation_and_configuration_review"),
            (candidate, "role_attestation_review"),
        ),
    )
    bindings = {
        "role_attestation_sha256": ROLE_ATTESTATION_RELATIVE,
        "alignment_record_sha256": ALIGNMENT_RELATIVE,
    }
    for key, relative in bindings.items():
        require_sha256(release[key], key)
        require(release[key] == sha256(root, relative), f"preflight release {key} drift")
    require_sha256(release["approval_receipt_sha256"], "approval_receipt_sha256")
    require(release["approval_receipt_sha256"] == APPROVAL_RECEIPT_SHA, "preflight release approval binding drift")
    require_sha256(release["permission_policy_sha256"], "permission_policy_sha256")
    require(release["permission_policy_sha256"] == APPROVED_PERMISSION_SHA, "preflight release permission-policy drift")
    require_sha256(release["oidc_trust_policy_sha256"], "oidc_trust_policy_sha256")
    require(release["oidc_trust_policy_sha256"] == APPROVED_TRUST_SHA, "preflight release trust-policy drift")
    require(release["account_id"] == "630956766927", "preflight release account drift")
    require(release["role_arn"] == ROLE_ARN, "preflight release role ARN drift")
    require(type(release["authorized_aws_actions"]) is list and release["authorized_aws_actions"] == ["sts:GetCallerIdentity"], "preflight release AWS action scope drift")
    require_int(release["maximum_sts_get_caller_identity_calls"], "preflight release STS call cap")
    require(release["maximum_sts_get_caller_identity_calls"] == 1, "preflight release STS call cap drift")
    require(release["single_sts_get_caller_identity_authorized"] is True, "preflight release does not authorize exact STS-only probe")
    for key, label in (
        ("s3_requests_authorized", "S3"),
        ("requester_pays_authorized", "Requester Pays"),
        ("object_body_access_authorized", "object body"),
        ("decompression_authorized", "decompression"),
        ("workflow_installation_authorized", "workflow installation"),
        ("release_or_activation_authorized", "release or activation"),
        ("diagnostic_execution_authorized", "diagnostic execution"),
    ):
        require(release[key] is False, f"preflight release authorizes {label}")
    require(release["single_use"] is True, "preflight release is not single-use")
    require(release["release_consumed"] is False, "preflight release is already consumed")
    require(release["rerun_authorized"] is False, "preflight release authorizes rerun")
    require_int(release["network_requests_executed_by_release"], "preflight-release network count")
    require(release["network_requests_executed_by_release"] == 0, "preflight release performed network request")
    require_int(release["aws_iam_mutations_executed_by_release"], "preflight-release IAM count")
    require(release["aws_iam_mutations_executed_by_release"] == 0, "preflight release mutated IAM")
    stage_authority(release["downstream_authorizations"], "preflight-release downstream authority")
    trading_authority(release["trading_authorizations"], "preflight-release trading authority")
    return release


def validate(
    root: Path = ROOT,
    *,
    permitted_successor_paths: frozenset[str] = frozenset(),
    runtime_pricing_projection_permitted: bool = False,
) -> dict[str, object]:
    permitted = successor_permissions(
        frozenset(permitted_successor_paths)
        | {
            PREFLIGHT_CANDIDATE_RELATIVE,
            PREFLIGHT_RELEASE_RELATIVE,
            PREFLIGHT_EVIDENCE_RELATIVE,
            PREFLIGHT_CONSUMPTION_RELATIVE,
        }
    )
    preflight_release = validate_release(
        root,
        permitted_successor_paths=permitted,
        runtime_pricing_projection_permitted=runtime_pricing_projection_permitted,
    )
    evidence = load(
        root,
        PREFLIGHT_EVIDENCE_RELATIVE,
        missing_label="STS preflight evidence is absent",
    )
    consumption = load(
        root,
        PREFLIGHT_CONSUMPTION_RELATIVE,
        missing_label="STS preflight release consumption is absent",
    )
    require_exact(evidence, EVIDENCE_KEYS, "STS preflight evidence")
    require_exact(consumption, CONSUMPTION_KEYS, "STS preflight consumption")
    require(evidence["schema_version"] == "1.0", "preflight evidence schema drift")
    require(
        evidence["preflight_id"]
        == "HL-ARCHIVE-R11A-SUCCESSOR-ROLE-STS-PREFLIGHT-001",
        "preflight ID drift",
    )
    require(evidence["status"] == "R11A_STS_PREFLIGHT_PASS", "preflight did not pass")
    require(
        evidence["technical_result"]
        == "DEDICATED_R11A_ROLE_ASSUMEABLE_FROM_CANONICAL_MAIN",
        "preflight technical result drift",
    )
    require(
        evidence["preflight_release_id"] == preflight_release["preflight_release_id"],
        "preflight evidence release ID binding drift",
    )
    require_sha256(evidence["preflight_release_sha256"], "preflight_release_sha256")
    require(
        evidence["preflight_release_sha256"] == sha256(root, PREFLIGHT_RELEASE_RELATIVE),
        "preflight evidence release hash drift",
    )
    require_sha256(evidence["role_attestation_sha256"], "role_attestation_sha256")
    require(
        evidence["role_attestation_sha256"] == sha256(root, ROLE_ATTESTATION_RELATIVE),
        "preflight role-attestation binding drift",
    )
    require_sha256(evidence["alignment_record_sha256"], "alignment_record_sha256")
    require(evidence["alignment_record_sha256"] == sha256(root, ALIGNMENT_RELATIVE), "preflight alignment binding drift")
    require_sha256(evidence["approval_receipt_sha256"], "approval_receipt_sha256")
    require(evidence["approval_receipt_sha256"] == APPROVAL_RECEIPT_SHA, "preflight approval binding drift")
    require_sha256(evidence["permission_policy_sha256"], "permission_policy_sha256")
    require(evidence["permission_policy_sha256"] == APPROVED_PERMISSION_SHA, "preflight permission-policy binding drift")
    require_sha256(evidence["oidc_trust_policy_sha256"], "oidc_trust_policy_sha256")
    require(evidence["oidc_trust_policy_sha256"] == APPROVED_TRUST_SHA, "preflight trust-policy binding drift")
    require(evidence["expected_role_arn"] == ROLE_ARN, "expected role ARN drift")
    require(evidence["observed_account_id"] == "630956766927", "AWS account drift")
    observed_session = evidence["observed_assumed_role_session_arn"]
    require(
        isinstance(observed_session, str)
        and re.fullmatch(
            r"arn:aws:sts::630956766927:assumed-role/"
            r"onchain-wallet-intelligence-hl-archive-identity-r11a/"
            r"HLArchiveR11ASTSPreflight",
            observed_session,
        )
        is not None,
        "observed STS principal drift",
    )
    require_commit(evidence["dispatch_sha"], "dispatch_sha")
    require(evidence["dispatch_ref"] == "refs/heads/main", "preflight was not main")
    require_int(evidence["workflow_run_attempt"], "preflight workflow run attempt")
    require(evidence["workflow_run_attempt"] == 1, "preflight rerun detected")
    require_int(evidence["explicit_sts_caller_identity_calls"], "STS caller-identity count")
    require(evidence["explicit_sts_caller_identity_calls"] == 1, "preflight STS call count drift")
    require(
        type(evidence["authorized_aws_actions"]) is list
        and evidence["authorized_aws_actions"] == ["sts:GetCallerIdentity"],
        "preflight AWS action authority drift",
    )
    require(evidence["s3_requests_authorized"] is False, "preflight authorized S3")
    require(evidence["requester_pays_authorized"] is False, "preflight authorized Requester Pays")
    require(evidence["object_body_access_authorized"] is False, "preflight authorized object body access")
    require(evidence["decompression_authorized"] is False, "preflight authorized decompression")
    require(evidence["workflow_installation_authorized"] is False, "preflight authorized workflow installation")
    require(evidence["release_authorized"] is False, "preflight authorized release")
    require(evidence["activation_authorized"] is False, "preflight authorized activation")
    require(evidence["diagnostic_execution_authorized"] is False, "preflight authorized diagnostic execution")
    require_int(evidence["s3_http_request_count"], "preflight S3 request count")
    require(evidence["s3_http_request_count"] == 0, "preflight performed S3 request")
    require_int(evidence["object_bytes_downloaded"], "preflight downloaded bytes")
    require(evidence["object_bytes_downloaded"] == 0, "preflight downloaded data")
    stage_authority(evidence["downstream_authorizations"], "preflight downstream authority")
    trading_authority(evidence["trading_authorizations"], "preflight trading authority")

    require(consumption["schema_version"] == "1.0", "preflight consumption schema drift")
    require(
        consumption["consumption_id"]
        == "CONSUME_HL_ARCHIVE_R11A_STS_PREFLIGHT_RELEASE_001",
        "preflight consumption ID drift",
    )
    require(consumption["status"] == "CONSUMED_SUCCESS", "preflight not consumed")
    require(consumption["preflight_id"] == evidence["preflight_id"], "preflight consumption ID binding drift")
    require(
        consumption["preflight_release_id"] == preflight_release["preflight_release_id"],
        "preflight consumption release ID binding drift",
    )
    require_sha256(consumption["preflight_release_sha256"], "preflight_release_sha256")
    require(
        consumption["preflight_release_sha256"] == sha256(root, PREFLIGHT_RELEASE_RELATIVE),
        "preflight consumption release hash drift",
    )
    require_sha256(consumption["preflight_evidence_sha256"], "preflight_evidence_sha256")
    require(
        consumption["preflight_evidence_sha256"] == sha256(root, PREFLIGHT_EVIDENCE_RELATIVE),
        "preflight consumption evidence hash drift",
    )
    require(consumption["preflight_release_consumed"] is True, "preflight consumption flag false")
    require(consumption["rerun_authorized"] is False, "preflight rerun reopened")
    require_int(consumption["s3_requests_executed"], "preflight consumption S3 count")
    require(consumption["s3_requests_executed"] == 0, "preflight consumption reports S3")
    require_int(consumption["object_bytes_downloaded"], "preflight consumption downloaded bytes")
    require(consumption["object_bytes_downloaded"] == 0, "preflight consumption reports download")
    stage_authority(consumption["downstream_authorizations"], "preflight-consumption downstream authority")
    trading_authority(consumption["trading_authorizations"], "preflight-consumption trading authority")
    return {
        "release": preflight_release,
        "evidence": evidence,
        "consumption": consumption,
    }


def main() -> int:
    validate()
    print("R11A_STS_PREFLIGHT_EVIDENCE_R4_VALID_ZERO_S3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
