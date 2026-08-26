#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

try:
    from governance.r11a_stage_common_r4 import (
        APPROVED_PRICING_SOURCE_SHA,
        APPROVED_WORKFLOW_SHA,
        CANDIDATE_RELATIVE,
        INSTALLATION_RELATIVE,
        PREFLIGHT_CANDIDATE_RELATIVE,
        PREFLIGHT_CONSUMPTION_RELATIVE,
        PREFLIGHT_EVIDENCE_RELATIVE,
        PREFLIGHT_RELEASE_RELATIVE,
        PRICING_SOURCE_RELATIVE,
        PRICING_TARGET_RELATIVE,
        ROLE_ATTESTATION_RELATIVE,
        ROOT,
        WORKFLOW_NAME,
        WORKFLOW_RELATIVE,
        load,
        pricing_projection,
        read_bytes,
        require,
        require_distinct_review,
        require_exact,
        require_fresh_review,
        require_green_review,
        require_int,
        require_sha256,
        sha256,
        stage_authority,
        successor_permissions,
        trading_authority,
    )
    from governance.validate_r11a_role_preflight_evidence_r4 import validate as validate_preflight
except ModuleNotFoundError:
    from r11a_stage_common_r4 import (
        APPROVED_PRICING_SOURCE_SHA,
        APPROVED_WORKFLOW_SHA,
        CANDIDATE_RELATIVE,
        INSTALLATION_RELATIVE,
        PREFLIGHT_CANDIDATE_RELATIVE,
        PREFLIGHT_CONSUMPTION_RELATIVE,
        PREFLIGHT_EVIDENCE_RELATIVE,
        PREFLIGHT_RELEASE_RELATIVE,
        PRICING_SOURCE_RELATIVE,
        PRICING_TARGET_RELATIVE,
        ROLE_ATTESTATION_RELATIVE,
        ROOT,
        WORKFLOW_NAME,
        WORKFLOW_RELATIVE,
        load,
        pricing_projection,
        read_bytes,
        require,
        require_distinct_review,
        require_exact,
        require_fresh_review,
        require_green_review,
        require_int,
        require_sha256,
        sha256,
        stage_authority,
        successor_permissions,
        trading_authority,
    )
    from validate_r11a_role_preflight_evidence_r4 import validate as validate_preflight

CONTRACT = ROOT / INSTALLATION_RELATIVE
CONTRACT_KEYS = frozenset(
    {
        "schema_version",
        "installation_id",
        "status",
        "preflight_candidate_sha256",
        "preflight_release_sha256",
        "preflight_evidence_sha256",
        "preflight_consumption_sha256",
        "sts_preflight_review_completed",
        "sts_preflight_review_id",
        "sts_preflight_review_event",
        "sts_preflight_review_verdict",
        "sts_preflight_reviewed_head",
        "sts_preflight_reviewed_tree",
        "workflow_name",
        "candidate_workflow_path",
        "workflow_path",
        "workflow_sha256",
        "runtime_pricing_source_path",
        "runtime_pricing_source_sha256",
        "runtime_pricing_installed_path",
        "runtime_pricing_installed_sha256",
        "single_workflow_dispatch_authorized",
        "execution_release_present",
        "canonical_activation_present",
        "aws_oidc_authorized_now",
        "get_object_authorized_now",
        "network_requests_executed_by_installation",
        "aws_iam_mutations_executed_by_installation",
        "downstream_authorizations",
        "trading_authorizations",
    }
)


def validate(
    root: Path = ROOT,
    *,
    permitted_successor_paths: frozenset[str] = frozenset(),
    runtime_pricing_projection_permitted: bool = True,
) -> dict[str, object]:
    require(
        type(runtime_pricing_projection_permitted) is bool,
        "runtime pricing projection mode must be boolean",
    )
    permitted = successor_permissions(
        frozenset(permitted_successor_paths) | {INSTALLATION_RELATIVE, WORKFLOW_RELATIVE}
    )
    projection_present = sha256(root, PRICING_TARGET_RELATIVE) == APPROVED_PRICING_SOURCE_SHA
    preflight = validate_preflight(
        root,
        permitted_successor_paths=permitted,
        runtime_pricing_projection_permitted=projection_present,
    )
    role_attestation = load(root, ROLE_ATTESTATION_RELATIVE)
    preflight_candidate = load(root, PREFLIGHT_CANDIDATE_RELATIVE)
    contract = load(
        root,
        INSTALLATION_RELATIVE,
        missing_label="workflow installation contract is absent",
    )
    require(projection_present, "workflow installation requires approved runtime pricing projection")
    require_exact(contract, CONTRACT_KEYS, "workflow installation contract")
    require(contract["schema_version"] == "1.0", "installation schema drift")
    require(
        contract["installation_id"] == "HL-ARCHIVE-R11A-WORKFLOW-INSTALLATION-001",
        "installation ID drift",
    )
    require(
        contract["status"] == "INSTALLED_AWAITING_SEPARATE_EXECUTION_RELEASE",
        "installation status drift",
    )
    require_sha256(contract["preflight_evidence_sha256"], "preflight_evidence_sha256")
    require_sha256(contract["preflight_candidate_sha256"], "preflight_candidate_sha256")
    require(
        contract["preflight_candidate_sha256"] == sha256(root, PREFLIGHT_CANDIDATE_RELATIVE),
        "installation preflight-candidate binding drift",
    )
    require_sha256(contract["preflight_release_sha256"], "preflight_release_sha256")
    require(
        contract["preflight_release_sha256"] == sha256(root, PREFLIGHT_RELEASE_RELATIVE),
        "installation preflight-release binding drift",
    )
    require(
        contract["preflight_evidence_sha256"] == sha256(root, PREFLIGHT_EVIDENCE_RELATIVE),
        "installation preflight-evidence binding drift",
    )
    require_sha256(contract["preflight_consumption_sha256"], "preflight_consumption_sha256")
    require(
        contract["preflight_consumption_sha256"] == sha256(root, PREFLIGHT_CONSUMPTION_RELATIVE),
        "installation preflight-consumption binding drift",
    )
    require_green_review(contract, "sts_preflight_review", "STS preflight review")
    require_distinct_review(
        contract,
        "sts_preflight_review",
        preflight["release"],
        "candidate_review",
        "STS preflight review",
    )
    require_fresh_review(
        contract,
        "sts_preflight_review",
        "STS preflight review",
        ancestors=(
            (role_attestation, "alignment_review"),
            (role_attestation, "identity_creation_and_configuration_review"),
            (preflight_candidate, "role_attestation_review"),
            (preflight["release"], "candidate_review"),
        ),
    )
    require(contract["workflow_name"] == WORKFLOW_NAME, "workflow name drift")
    require(contract["candidate_workflow_path"] == CANDIDATE_RELATIVE, "candidate workflow path drift")
    require(contract["workflow_path"] == WORKFLOW_RELATIVE, "installed workflow path drift")
    candidate_raw = read_bytes(root, CANDIDATE_RELATIVE)
    installed_raw = read_bytes(root, WORKFLOW_RELATIVE, missing_label="installed workflow is absent")
    require(candidate_raw == installed_raw, "installed workflow differs from approved R7 candidate")
    try:
        workflow_text = installed_raw.decode("utf-8")
    except UnicodeError:
        require(False, "installed workflow is not UTF-8")
        workflow_text = ""  # unreachable, retained for static type narrowing
    require("\non:\n  workflow_dispatch:\n" in "\n" + workflow_text, "workflow is not manual-dispatch only")
    require("workflow_call:" not in workflow_text, "workflow exposes reusable workflow authority")
    require("pull_request:" not in workflow_text and "push:" not in workflow_text, "workflow exposes automatic trigger")
    require("permissions:\n  actions: read\n  contents: read\n  id-token: write\n" in workflow_text, "workflow permissions drift")
    require('test "${EVENT_NAME}" = workflow_dispatch' in workflow_text, "workflow event guard missing")
    require('test "${DISPATCH_REF}" = refs/heads/main' in workflow_text, "workflow main-ref guard missing")
    require('test "${CURRENT_RUN_ATTEMPT}" = 1' in workflow_text, "workflow attempt-one guard missing")
    require("${{ secrets." not in workflow_text, "workflow references repository secret")
    require_sha256(contract["workflow_sha256"], "workflow_sha256")
    require(contract["workflow_sha256"] == APPROVED_WORKFLOW_SHA, "installed workflow is not owner-bound")
    require(contract["workflow_sha256"] == sha256(root, WORKFLOW_RELATIVE), "installed workflow SHA-256 drift")

    pricing_projection(root)
    require(contract["runtime_pricing_source_path"] == PRICING_SOURCE_RELATIVE, "runtime pricing source path drift")
    require_sha256(contract["runtime_pricing_source_sha256"], "runtime_pricing_source_sha256")
    require(contract["runtime_pricing_source_sha256"] == APPROVED_PRICING_SOURCE_SHA, "runtime pricing source is not owner-bound")
    require(contract["runtime_pricing_source_sha256"] == sha256(root, PRICING_SOURCE_RELATIVE), "runtime pricing source hash drift")
    require(contract["runtime_pricing_installed_path"] == PRICING_TARGET_RELATIVE, "runtime pricing target path drift")
    require_sha256(contract["runtime_pricing_installed_sha256"], "runtime_pricing_installed_sha256")
    require(contract["runtime_pricing_installed_sha256"] == APPROVED_PRICING_SOURCE_SHA, "runtime pricing target is not exact approved projection")
    require(contract["runtime_pricing_installed_sha256"] == sha256(root, PRICING_TARGET_RELATIVE), "runtime pricing target hash drift")

    require(contract["single_workflow_dispatch_authorized"] is False, "installation self-authorizes dispatch")
    require(contract["execution_release_present"] is False, "historical installation snapshot rewritten after release")
    require(contract["canonical_activation_present"] is False, "historical installation snapshot rewritten after activation")
    require(contract["aws_oidc_authorized_now"] is False, "installation opens OIDC")
    require(contract["get_object_authorized_now"] is False, "installation opens GetObject")
    require_int(contract["network_requests_executed_by_installation"], "installation network request count")
    require(contract["network_requests_executed_by_installation"] == 0, "installation performed network request")
    require_int(contract["aws_iam_mutations_executed_by_installation"], "installation IAM mutation count")
    require(contract["aws_iam_mutations_executed_by_installation"] == 0, "installation mutated IAM")
    stage_authority(contract["downstream_authorizations"], "installation downstream authority")
    trading_authority(contract["trading_authorizations"], "installation trading authority")
    return contract


def main() -> int:
    validate()
    print("R11A_WORKFLOW_INSTALLATION_R4_VALID_INERT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
