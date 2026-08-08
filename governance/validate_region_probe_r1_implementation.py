#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/region_probe_r1"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-region-probe-r1.yml"
PROBE = BASE / "probe.py"
PREREG = BASE / "REGION_PROBE_CONTRACT.json"
IMPLEMENTATION = BASE / "REGION_PROBE_IMPLEMENTATION_CONTRACT.json"
APPROVAL_TEXT = BASE / "approvals/APPROVE_HL_ARCHIVE_REGION_PROBE_R1_001.txt"
APPROVAL_JSON = BASE / "approvals/APPROVE_HL_ARCHIVE_REGION_PROBE_R1_001.json"
RELEASE = BASE / "REGION_PROBE_EXECUTION_RELEASE.json"
APPROVAL_SHA = "56c8d01396b12d0dd783dbc1646ebbca947e51a024bb5c8f091cd0b7a889c541"
PREREG_COMMIT = "910997423f5e008f3c7bca65fd739d6aa14d25a7"
APPROVAL_MERGE = "b86156d71ef438441e6d3903a8bbc2da564a2046"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"REGION_PROBE_R1_IMPLEMENTATION_VALIDATION_FAIL: {message}")


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root not object: {path.relative_to(ROOT)}")
    return value


def validate() -> None:
    for path in (WORKFLOW, PROBE, PREREG, IMPLEMENTATION, APPROVAL_TEXT, APPROVAL_JSON):
        require(path.is_file(), f"missing implementation path: {path.relative_to(ROOT)}")
    require(not RELEASE.exists(), "execution release exists during implementation review")
    require(not (BASE / "evidence").exists(), "Region probe evidence exists before canonical run")
    require(not (BASE / "outputs").exists(), "Region probe outputs exist before canonical run")

    prereg = load(PREREG)
    require(prereg["status"] == "PREREGISTERED_NOT_AUTHORIZED", "immutable preregistration status rewritten")
    require(prereg["target_bucket"] == "hl-mainnet-node-data", "preregistration target drift")
    require(prereg["operation"] == "HeadBucket" and prereg["http_method"] == "HEAD", "preregistration operation drift")
    require(prereg["maximum_s3_http_requests"] == 1, "preregistration request cap drift")
    require(prereg["maximum_retries"] == 0 and prereg["http_redirect_following_authorized"] is False, "preregistration retry/redirect opened")
    require(prereg["implementation_authorized"] is False, "preregistration self-authorizes implementation")
    require(prereg["execution_authorized"] is False and prereg["fresh_paid_attempt_authorized"] is False, "preregistration self-authorizes runtime")

    approval = load(APPROVAL_JSON)
    require(hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA, "approval text hash drift")
    require(approval["approval_id"] == "APPROVE_HL_ARCHIVE_REGION_PROBE_R1_001", "approval ID drift")
    require(approval["reviewed_commit"] == PREREG_COMMIT, "approval reviewed commit drift")
    require(approval["exact_approval_text_sha256"] == APPROVAL_SHA, "approval hash record drift")
    require(approval["approval_status"] == "APPROVED_SCOPE_AND_BUDGET_AWAITING_IMPLEMENTATION", "approval status drift")
    require(approval["maximum_one_time_budget_eur"] == 0.10 and approval["maximum_monthly_budget_eur"] == 0, "approval budget drift")
    require(approval["maximum_head_bucket_requests"] == 1 and approval["maximum_runtime_seconds"] == 30, "approval caps drift")
    require(approval["maximum_retries"] == 0 and approval["http_redirect_following_authorized"] is False, "approval retry/redirect opened")
    require(approval["head_bucket_scope_approved"] is True, "HeadBucket scope not approved")
    require(approval["requester_pays_acknowledgement_scope_approved"] is True, "Requester Pays acknowledgement not approved")
    require(approval["execution_authorized"] is False and approval["fresh_paid_attempt_authorized"] is False, "approval self-releases runtime")

    implementation = load(IMPLEMENTATION)
    require(implementation["status"] == "IMPLEMENTATION_CANDIDATE_REQUIRES_SEPARATE_EXECUTION_RELEASE", "implementation status drift")
    require(implementation["preregistration_commit"] == PREREG_COMMIT, "implementation preregistration binding drift")
    require(implementation["approval_merge_commit"] == APPROVAL_MERGE, "implementation approval merge binding drift")
    require(implementation["approval_text_sha256"] == APPROVAL_SHA, "implementation approval hash drift")
    require(implementation["target_bucket"] == "hl-mainnet-node-data", "implementation target drift")
    require(implementation["operation"] == "HeadBucket" and implementation["http_method"] == "HEAD", "implementation operation drift")
    require(implementation["maximum_s3_http_requests"] == 1, "implementation request cap drift")
    require(implementation["maximum_runtime_seconds"] == 30 and implementation["maximum_retries"] == 0, "implementation runtime/retry drift")
    require(implementation["http_redirect_following_authorized"] is False, "implementation redirect following opened")
    require(implementation["transport"] == "DIRECT_SIGV4_HTTPS_HEAD_NO_REDIRECT_NO_BODY", "transport drift")
    require(implementation["session_s3_policy"] == "EXPLICIT_DENY_ALL_S3", "session S3 boundary drift")
    require(implementation["persistent_role_permission_expansion_required"] is False, "persistent role expansion introduced")
    require(implementation["separate_execution_release_required"] is True, "separate release gate disabled")
    require(implementation["implementation_self_releases_execution"] is False, "implementation self-releases execution")
    require(implementation["execution_authorized"] is False and implementation["fresh_paid_attempt_authorized"] is False, "implementation runtime opened")
    require(implementation["s3_request_executed"] is False, "implementation invents execution")
    require(implementation["exact_bucket_region"] is None and implementation["empirical_result"] is None, "implementation invents result")
    for key in (
        "request_body_authorized", "response_body_authorized", "response_body_read_authorized",
        "list_objects_v2_authorized", "get_object_authorized", "head_object_authorized",
        "get_object_attributes_authorized", "range_get_authorized", "object_body_download_authorized",
        "pagination_authorized", "decompression_authorized", "market_data_ingestion_authorized",
        "larger_300_request_inventory_authorized",
    ):
        require(implementation[key] is False, f"forbidden implementation capability opened: {key}")
    require(all(value is False for value in implementation["trading_authorizations"].values()), "trading/capital authorization opened")

    source = PROBE.read_text(encoding="utf-8")
    for token in (
        "http.client.HTTPSConnection",
        'connection.request("HEAD", target, body=None, headers=headers)',
        "x-amz-request-payer",
        "x-amz-bucket-region",
        "AWS_SESSION_TOKEN",
    ):
        require(token in source, f"required probe boundary missing: {token}")
    require(source.count('connection.request("HEAD"') == 1, "probe contains more than one HEAD transport construction")
    for token in (
        "response.read(", 'connection.request("GET"', 'connection.request("POST"',
        'connection.request("PUT"', 'connection.request("DELETE"', "subprocess",
        "boto3", "botocore", "import requests", "from requests", "urllib.request", "ListObjectsV2",
        "GetObject", "HeadObject", "GetObjectAttributes",
    ):
        require(token not in source, f"forbidden probe capability/literal: {token}")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    require("workflow_dispatch:" in workflow and "pull_request:" not in workflow and "push:" not in workflow, "workflow auto-triggered")
    require("actions: read" in workflow and "contents: read" in workflow and "id-token: write" in workflow, "workflow permissions drift")
    require("PENDING_CANONICAL_IMPLEMENTATION_MERGE" in workflow, "implementation placeholder missing before canonical merge")
    require("post-implementation Region probe execution release is absent" in workflow, "release gate missing")
    require("Enforce single-use release before AWS OIDC" in workflow, "single-use gate missing")
    require("CURRENT_RUN_ATTEMPT" in workflow and "len(eligible) == 1" in workflow, "single-use count gate missing")
    require("a previous Region probe dispatch already consumed this release" in workflow, "single-use consumption failure missing")
    require("arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-metadata-canary" in workflow, "role binding drift")
    require("allowed-account-ids: '630956766927'" in workflow, "account binding missing")
    require('"Effect":"Deny","Action":"s3:*","Resource":"*"' in workflow, "deny-all-S3 session policy missing")
    require('"Effect":"Allow","Action":"s3:' not in workflow, "Region workflow contains S3 allow")
    require('"Action":"s3:ListBucket"' not in workflow, "Region workflow allows ListBucket")
    require("python research/archive_inventory/region_probe_r1/probe.py" in workflow, "probe execution command missing")
    for token in ("aws s3api", "aws s3 ", "curl ", "wget ", "secrets.AWS_ACCESS_KEY_ID", "secrets.AWS_SECRET_ACCESS_KEY"):
        require(token not in workflow, f"forbidden workflow capability/reference: {token}")
    for sha in (
        "11d5960a326750d5838078e36cf38b85af677262",
        "a26af69be951a213d495a4c3e4e4022e16d87065",
        "e6de054238d6b7531b4efff3b6587d9aade6a06c",
        "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    ):
        require(f"@{sha}" in workflow, f"unpinned/missing action: {sha}")
    require(workflow.index("Prove approval implementation and separate execution release before AWS OIDC") < workflow.index("Assume exact AWS role with explicit deny-all-S3 session policy"), "release gate occurs after OIDC")
    require(workflow.index("Enforce single-use release before AWS OIDC") < workflow.index("Assume exact AWS role with explicit deny-all-S3 session policy"), "single-use gate occurs after OIDC")

    state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    for token in (
        "region_probe_r1_human_approved = true",
        "region_probe_r1_implementation_phase_authorized = true",
        "region_probe_r1_implementation_candidate_present = true",
        "region_probe_r1_workflow_candidate_present = true",
        "region_probe_r1_executable_candidate_present = true",
        "region_probe_r1_implementation_canonical = false",
        "region_probe_r1_execution_release_present = false",
        "region_probe_r1_execution_authorized = false",
        "region_probe_r1_request_executed = false",
        "region_probe_r1_exact_bucket_region = null",
        "fresh_paid_attempt_authorized = false",
        "list_objects_authorized = false",
        "get_object_authorized = false",
        "object_body_download_authorized = false",
        "market_data_ingested = false",
        "empirical_result = null",
    ):
        require(token in state, f"project state boundary missing: {token}")


def main() -> int:
    validate()
    print("REGION_PROBE_R1_IMPLEMENTATION_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
