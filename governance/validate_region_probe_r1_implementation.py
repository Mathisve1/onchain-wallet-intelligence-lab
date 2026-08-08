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
IMPLEMENTATION_COMMIT = "91687b4c803e331d4b2ef8493df731c99e25a0e5"
APPROVAL_TIME = "2026-08-08T14:52:00Z"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"REGION_PROBE_R1_IMPLEMENTATION_VALIDATION_FAIL: {message}")


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root not object: {path.relative_to(ROOT)}")
    return value


def validate() -> None:
    for path in (WORKFLOW, PROBE, PREREG, IMPLEMENTATION, APPROVAL_TEXT, APPROVAL_JSON, RELEASE):
        require(path.is_file(), f"missing Region probe release path: {path.relative_to(ROOT)}")
    require(not (BASE / "evidence").exists(), "Region probe evidence exists before canonical run")
    require(not (BASE / "outputs").exists(), "Region probe outputs exist before canonical run")

    prereg = load(PREREG)
    require(prereg["status"] == "PREREGISTERED_NOT_AUTHORIZED", "immutable preregistration status rewritten")
    require(prereg["target_bucket"] == "hl-mainnet-node-data", "preregistration target drift")
    require(prereg["operation"] == "HeadBucket" and prereg["http_method"] == "HEAD", "preregistration operation drift")
    require(prereg["maximum_s3_http_requests"] == 1, "preregistration request cap drift")
    require(prereg["implementation_authorized"] is False, "preregistration self-authorizes implementation")
    require(prereg["execution_authorized"] is False and prereg["fresh_paid_attempt_authorized"] is False, "preregistration self-authorizes runtime")

    approval = load(APPROVAL_JSON)
    require(hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA, "approval text hash drift")
    require(approval["approval_id"] == "APPROVE_HL_ARCHIVE_REGION_PROBE_R1_001", "approval ID drift")
    require(approval["reviewed_commit"] == PREREG_COMMIT, "approval reviewed commit drift")
    require(approval["exact_approval_text_sha256"] == APPROVAL_SHA, "approval hash record drift")
    require(approval["approval_status"] == "APPROVED_SCOPE_AND_BUDGET_AWAITING_IMPLEMENTATION", "immutable approval status rewritten")
    require(approval["maximum_one_time_budget_eur"] == 0.10 and approval["maximum_monthly_budget_eur"] == 0, "approval budget drift")
    require(approval["maximum_head_bucket_requests"] == 1 and approval["maximum_runtime_seconds"] == 30, "approval caps drift")
    require(approval["maximum_retries"] == 0 and approval["http_redirect_following_authorized"] is False, "approval retry/redirect opened")
    require(approval["head_bucket_scope_approved"] is True and approval["requester_pays_acknowledgement_scope_approved"] is True, "approved scope drift")
    require(approval["execution_authorized"] is False and approval["fresh_paid_attempt_authorized"] is False, "approval self-releases runtime")

    implementation = load(IMPLEMENTATION)
    require(implementation["status"] == "IMPLEMENTATION_CANDIDATE_REQUIRES_SEPARATE_EXECUTION_RELEASE", "immutable implementation status drift")
    require(implementation["preregistration_commit"] == PREREG_COMMIT, "implementation preregistration binding drift")
    require(implementation["approval_merge_commit"] == APPROVAL_MERGE, "implementation approval binding drift")
    require(implementation["approval_text_sha256"] == APPROVAL_SHA, "implementation approval hash drift")
    require(implementation["target_bucket"] == "hl-mainnet-node-data", "implementation target drift")
    require(implementation["maximum_s3_http_requests"] == 1 and implementation["maximum_runtime_seconds"] == 30, "implementation caps drift")
    require(implementation["maximum_retries"] == 0 and implementation["http_redirect_following_authorized"] is False, "implementation retry/redirect opened")
    require(implementation["transport"] == "DIRECT_SIGV4_HTTPS_HEAD_NO_REDIRECT_NO_BODY", "transport drift")
    require(implementation["session_s3_policy"] == "EXPLICIT_DENY_ALL_S3", "session S3 boundary drift")
    require(implementation["persistent_role_permission_expansion_required"] is False, "persistent role expansion introduced")
    require(implementation["separate_execution_release_required"] is True and implementation["implementation_self_releases_execution"] is False, "separate release boundary disabled")
    require(implementation["execution_authorized"] is False and implementation["fresh_paid_attempt_authorized"] is False, "implementation self-releases runtime")
    require(implementation["s3_request_executed"] is False and implementation["exact_bucket_region"] is None, "implementation invents execution/result")
    for key in ("request_body_authorized","response_body_authorized","response_body_read_authorized","list_objects_v2_authorized","get_object_authorized","head_object_authorized","get_object_attributes_authorized","range_get_authorized","object_body_download_authorized","pagination_authorized","decompression_authorized","market_data_ingestion_authorized","larger_300_request_inventory_authorized"):
        require(implementation[key] is False, f"forbidden implementation capability opened: {key}")
    require(all(value is False for value in implementation["trading_authorizations"].values()), "implementation trading/capital gate opened")

    release = load(RELEASE)
    require(release["release_id"] == "RELEASE_HL_ARCHIVE_REGION_PROBE_R1_001", "release ID drift")
    require(release["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_REGION_PROBE_RUN", "release status drift")
    require(release["probe_id"] == "HL-ARCHIVE-REGION-PROBE-R1-001", "release probe drift")
    require(release["preregistration_commit"] == PREREG_COMMIT, "release preregistration binding drift")
    require(release["approval_merge_commit"] == APPROVAL_MERGE, "release approval merge binding drift")
    require(release["approval_text_sha256"] == APPROVAL_SHA and release["approval_recorded_at_utc"] == APPROVAL_TIME, "release approval provenance drift")
    require(release["implementation_pr"] == 29 and release["implementation_commit"] == IMPLEMENTATION_COMMIT, "release implementation binding drift")
    require(release["implementation_exact_head_ci_commit"] == "4354f9a4e80c77b7250f95f79cab3f107ee8b54a", "release implementation CI head drift")
    require(release["implementation_ci_run"] == 31271673630 and release["implementation_ci_job"] == 93138596154, "release implementation CI evidence drift")
    require(release["implementation_test_count"] == 143, "release implementation test-count drift")
    require(release["single_use_window_start_utc"] == APPROVAL_TIME, "release single-use window drift")
    require(release["target_bucket"] == "hl-mainnet-node-data" and release["operation"] == "HeadBucket" and release["http_method"] == "HEAD", "release target/operation drift")
    require(release["maximum_one_time_budget_eur"] == 0.10 and release["maximum_monthly_budget_eur"] == 0, "release budget drift")
    require(release["maximum_head_bucket_requests"] == 1 and release["maximum_s3_http_requests"] == 1, "release request cap drift")
    require(release["maximum_runtime_seconds"] == 30 and release["maximum_retries"] == 0, "release runtime/retry drift")
    require(release["http_redirect_following_authorized"] is False, "release redirect following opened")
    require(release["single_workflow_dispatch_authorized"] is True and release["rerun_authorized"] is False, "release single-use drift")
    require(release["head_bucket_authorized"] is True and release["requester_pays_acknowledgement_authorized"] is True, "release HeadBucket scope drift")
    require(release["session_s3_policy"] == "EXPLICIT_DENY_ALL_S3" and release["persistent_role_permission_expansion_required"] is False, "release IAM boundary drift")
    for key in ("request_body_authorized","response_body_authorized","response_body_read_authorized","list_objects_v2_authorized","get_object_authorized","head_object_authorized","get_object_attributes_authorized","range_get_authorized","object_body_download_authorized","pagination_authorized","decompression_authorized","market_data_ingestion_authorized","larger_300_request_inventory_authorized"):
        require(release[key] is False, f"forbidden release capability opened: {key}")
    require(release["s3_request_executed"] is False and release["exact_bucket_region"] is None and release["empirical_result"] is None, "release invents execution/result")
    require(all(value is False for value in release["trading_authorizations"].values()), "release trading/capital gate opened")

    source = PROBE.read_text(encoding="utf-8")
    require(source.count('connection.request("HEAD"') == 1, "probe must contain exactly one HEAD transport construction")
    for token in ("response.read(", 'connection.request("GET"', 'connection.request("POST"', 'connection.request("PUT"', 'connection.request("DELETE"', "boto3", "botocore", "import requests", "urllib.request", "ListObjectsV2", "GetObject", "HeadObject", "GetObjectAttributes"):
        require(token not in source, f"forbidden probe capability/literal: {token}")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    require("workflow_dispatch:" in workflow and "pull_request:" not in workflow and "push:" not in workflow, "workflow auto-triggered")
    require("actions: read" in workflow and "contents: read" in workflow and "id-token: write" in workflow, "workflow permissions drift")
    require(IMPLEMENTATION_COMMIT in workflow and "PENDING_CANONICAL_IMPLEMENTATION_MERGE" not in workflow, "canonical implementation binding missing")
    require("Prove canonical implementation and single-use release before AWS OIDC" in workflow, "release proof gate missing")
    require("Enforce single-use release before AWS OIDC" in workflow, "single-use gate missing")
    require("CURRENT_RUN_ATTEMPT" in workflow and "len(eligible) == 1" in workflow, "single-use count gate missing")
    require("a previous Region probe dispatch already consumed this release" in workflow, "release consumption failure missing")
    require("arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-metadata-canary" in workflow, "role binding drift")
    require("allowed-account-ids: '630956766927'" in workflow, "account binding missing")
    require('"Effect":"Deny","Action":"s3:*","Resource":"*"' in workflow, "deny-all-S3 session policy missing")
    require('"Effect":"Allow","Action":"s3:' not in workflow and '"Action":"s3:ListBucket"' not in workflow, "workflow contains S3 allow")
    require("python research/archive_inventory/region_probe_r1/probe.py" in workflow, "probe execution command missing")
    for token in ("aws s3api", "aws s3 ", "curl ", "wget ", "secrets.AWS_ACCESS_KEY_ID", "secrets.AWS_SECRET_ACCESS_KEY"):
        require(token not in workflow, f"forbidden workflow capability/reference: {token}")
    require(workflow.index("Prove canonical implementation and single-use release before AWS OIDC") < workflow.index("Assume exact AWS role with explicit deny-all-S3 session policy"), "release gate occurs after OIDC")
    require(workflow.index("Enforce single-use release before AWS OIDC") < workflow.index("Assume exact AWS role with explicit deny-all-S3 session policy"), "single-use gate occurs after OIDC")

    state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    for token in (
        "region_probe_r1_human_approved = true",
        "region_probe_r1_implementation_canonical = true",
        f"region_probe_r1_implementation_commit = {IMPLEMENTATION_COMMIT}",
        "region_probe_r1_execution_release_present = true",
        "region_probe_r1_execution_ready = true",
        "region_probe_r1_head_bucket_authorized = true",
        "region_probe_r1_request_executed = false",
        "region_probe_r1_exact_bucket_region = null",
        "fresh_list_attempt_authorized = false",
        "list_objects_authorized = false",
        "get_object_authorized = false",
        "object_body_download_authorized = false",
        "market_data_ingested = false",
        "empirical_result = null",
    ):
        require(token in state, f"project state boundary missing: {token}")


def main() -> int:
    validate()
    print("REGION_PROBE_R1_RELEASE_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
