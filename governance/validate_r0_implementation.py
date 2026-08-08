#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "research/archive_inventory"
R0 = ARCHIVE / "r0"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-metadata-canary-r0.yml"
APPROVAL_TEXT = ARCHIVE / "approvals/APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001.txt"
APPROVAL_JSON = ARCHIVE / "approvals/APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001.json"
RELEASE_PATH = R0 / "R0_EXECUTION_RELEASE.json"
APPROVAL_SHA = "d70008eac7521b324f61161bcc0075e28cc3a116dd30f0c52b48d8cf5eb6ed46"
APPROVAL_COMMIT = "9af4b21863e47fb3bb2997ce77b9940eecf4597f"
APPROVAL_TIME = "2026-08-08T10:10:00Z"
IMPLEMENTATION_COMMIT = "cd5c46b25502b671693dd5ebb091e7273399bccf"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"R0_IMPLEMENTATION_VALIDATION_FAIL: {message}")


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root not object: {path}")
    return value


def validate() -> None:
    for path in (
        WORKFLOW,
        R0 / "R0_IMPLEMENTATION_CONTRACT.json",
        R0 / "README.md",
        R0 / "collector.py",
        RELEASE_PATH,
        APPROVAL_TEXT,
        APPROVAL_JSON,
    ):
        require(path.is_file(), f"missing R0 release path: {path.relative_to(ROOT)}")
    require(not (R0 / "evidence").exists(), "R0 evidence exists before canonical run")
    require(not (R0 / "outputs").exists(), "R0 outputs exist before canonical run")

    approval = load(APPROVAL_JSON)
    require(hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA, "approval text hash drift")
    require(approval["exact_approval_text_sha256"] == APPROVAL_SHA, "approval record hash drift")
    require(approval["reviewed_commit"] == APPROVAL_COMMIT, "approval reviewed commit drift")
    require(approval["recorded_at_utc"] == APPROVAL_TIME, "approval timestamp drift")
    require(approval["maximum_one_time_budget_eur"] == 1.0, "approval budget drift")
    require(approval["maximum_monthly_budget_eur"] == 0, "monthly budget opened")
    require(approval["maximum_list_requests"] == 7, "approval request cap drift")
    require(approval["maximum_keys_per_request"] == 25, "approval max-keys drift")
    require(approval["maximum_total_entries"] == 175, "approval entry cap drift")
    require(approval["maximum_total_response_bytes"] == 8388608, "approval byte cap drift")
    require(approval["maximum_runtime_seconds"] == 180, "approval runtime drift")
    require(approval["maximum_retries_per_request"] == 0, "approval retry drift")
    require(approval["pagination_authorized"] is False, "approval pagination opened")
    require(approval["requester_pays_scope_approved"] is True, "approval Requester Pays scope closed")
    require(approval["list_objects_v2_scope_approved"] is True, "approval LIST scope closed")

    implementation = load(R0 / "R0_IMPLEMENTATION_CONTRACT.json")
    require(implementation["status"] == "CANONICAL_IMPLEMENTATION_PENDING_SEPARATE_EXECUTION_RELEASE", "implementation status drift")
    require(implementation["canonical_implementation_commit"] == IMPLEMENTATION_COMMIT, "canonical implementation commit drift")
    require(implementation["human_approval_text_sha256"] == APPROVAL_SHA, "implementation approval binding drift")
    require(implementation["maximum_list_requests"] == 7 and implementation["s3_http_request_cap"] == 7, "HTTP request cap drift")
    require(implementation["maximum_keys_per_request"] == 25, "implementation max-keys drift")
    require(implementation["maximum_total_entries"] == 175, "implementation entry cap drift")
    require(implementation["maximum_total_response_bytes"] == 8388608, "implementation byte cap drift")
    require(implementation["maximum_runtime_seconds"] == 180, "implementation runtime drift")
    require(implementation["maximum_retries_per_request"] == 0, "implementation retry opened")
    require(implementation["pagination_authorized"] is False, "implementation pagination opened")
    require(implementation["continuation_token_follow_authorized"] is False, "continuation following opened")
    require(implementation["http_redirect_following_authorized"] is False, "HTTP redirect following opened")
    require(implementation["s3_transport"] == "DIRECT_SIGV4_HTTPS_NO_REDIRECT_FOLLOW", "transport drift")
    require(implementation["implementation_self_releases_execution"] is False, "implementation self-releases execution")
    require(implementation["post_merge_execution_release_required"] is True, "separate release gate disabled")
    require(implementation["execution_authorized_only_by_separate_release"] is True, "separate release authority disabled")
    require(implementation["execution_release_path"] == "research/archive_inventory/r0/R0_EXECUTION_RELEASE.json", "release path drift")
    require(implementation["market_data_ingestion_authorized"] is False, "implementation market-data gate opened")
    require(all(value is False for value in implementation["authorizations"].values()), "implementation trading/capital gate opened")

    release = load(RELEASE_PATH)
    require(release["schema_version"] == "1.0", "release schema drift")
    require(release["release_id"] == "RELEASE_HL_ARCHIVE_METADATA_CANARY_R0_001", "release ID drift")
    require(release["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R0_RUN", "release status drift")
    require(release["canary_id"] == "HL-ARCHIVE-METADATA-CANARY-R0-001", "release canary drift")
    require(release["inventory_id"] == "HL-ARCHIVE-INVENTORY-001", "release inventory drift")
    require(release["implementation_pr"] == 22, "implementation PR drift")
    require(release["implementation_commit"] == IMPLEMENTATION_COMMIT, "release implementation commit drift")
    require(release["implementation_exact_head_ci_commit"] == "41dcd5c2788af60ce9337b0c7eff4395264c4682", "implementation exact-head CI drift")
    require(release["implementation_ci_run"] == 31257261899 and release["implementation_ci_job"] == 93102453441, "implementation CI evidence drift")
    require(release["implementation_test_count"] == 108, "implementation test-count drift")
    require(release["human_approval_id"] == "APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001", "release approval ID drift")
    require(release["human_approval_reviewed_commit"] == APPROVAL_COMMIT, "release approval commit drift")
    require(release["human_approval_text_sha256"] == APPROVAL_SHA, "release approval hash drift")
    require(release["single_use_window_start_utc"] == APPROVAL_TIME, "single-use window drift")
    require(release["single_use_window_start_utc"] == approval["recorded_at_utc"], "release window not approval-bound")
    require(release["single_use_window_source"] == "CANONICAL_HUMAN_APPROVAL_RECORDED_AT_UTC", "release window provenance drift")
    require(release["maximum_one_time_budget_eur"] == 1.0 and release["maximum_monthly_budget_eur"] == 0, "release budget drift")
    require(release["maximum_list_requests"] == 7 and release["maximum_keys_per_request"] == 25, "release request caps drift")
    require(release["maximum_total_entries"] == 175 and release["maximum_total_response_bytes"] == 8388608, "release retention caps drift")
    require(release["maximum_runtime_seconds"] == 180 and release["maximum_retries_per_request"] == 0, "release runtime/retry drift")
    require(release["pagination_authorized"] is False and release["http_redirect_following_authorized"] is False, "release pagination/redirect opened")
    require(release["continuation_token_follow_authorized"] is False, "release continuation follow opened")
    require(release["requester_pays_authorized"] is True and release["list_objects_v2_authorized"] is True, "R0 listing release closed")
    require(release["single_workflow_dispatch_authorized"] is True and release["rerun_authorized"] is False, "single-use release drift")
    for key in (
        "get_object_authorized", "head_object_authorized", "get_object_attributes_authorized",
        "range_get_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "object_body_download_authorized", "decompression_authorized", "market_data_ingestion_authorized",
        "larger_300_request_inventory_authorized",
    ):
        require(release[key] is False, f"forbidden release capability opened: {key}")
    require(release["s3_requests_executed"] == 0 and release["empirical_result"] is None, "release invents execution/result")
    require(all(value is False for value in release["trading_authorizations"].values()), "release opens trading/capital authorization")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    require("workflow_dispatch:" in workflow and "pull_request:" not in workflow and "push:" not in workflow, "R0 workflow auto-triggered")
    require("actions: read" in workflow and "contents: read" in workflow and "id-token: write" in workflow, "workflow permissions drift")
    require(IMPLEMENTATION_COMMIT in workflow, "workflow implementation binding missing")
    require(APPROVAL_TIME in workflow, "workflow approval-window binding missing")
    require("single_use_window_start_utc" in workflow and "CANONICAL_HUMAN_APPROVAL_RECORDED_AT_UTC" in workflow, "approval-window release gate missing")
    require("CURRENT_RUN_ATTEMPT" in workflow and "test \"${CURRENT_RUN_ATTEMPT}\" = '1'" in workflow, "rerun gate missing")
    require("api.github.com" in workflow and "event=workflow_dispatch&branch=main&per_page=100" in workflow, "single-use history check missing")
    require("len(runs) < 100" in workflow and "len(eligible) == 1" in workflow, "single-use fail-closed count gate missing")
    require("previous R0 dispatch already consumed this approval-window release" in workflow, "release consumption failure missing")
    require("arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-metadata-canary" in workflow, "R0 role drift")
    require("allowed-account-ids: '630956766927'" in workflow, "R0 account restriction missing")
    require('"Action":"s3:ListBucket"' in workflow and workflow.count('"s3:max-keys":"25"') == 2, "session ListBucket scope drift")
    require("aws s3api" not in workflow and "aws s3 " not in workflow, "workflow contains AWS S3 CLI call")
    require("secrets.AWS_ACCESS_KEY_ID" not in workflow and "secrets.AWS_SECRET_ACCESS_KEY" not in workflow, "static AWS credential reference")

    collector = (R0 / "collector.py").read_text(encoding="utf-8")
    for required_token in ("http.client.HTTPSConnection", 'connection.request("GET"', "x-amz-request-payer", "list-type", "max-keys"):
        require(required_token in collector, f"collector boundary missing: {required_token}")
    for forbidden in ("subprocess", "urllib.request", "boto3", "botocore", '"aws"', "GetObject", "HeadObject", "PutObject", "DeleteObject"):
        require(forbidden not in collector, f"forbidden collector capability/literal: {forbidden}")

    state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    require("r0_implementation_canonical = true" in state, "canonical implementation state missing")
    require("r0_execution_release_present = true" in state, "release state missing")
    require("r0_execution_ready = true" in state, "single-use execution readiness missing")
    require("r0_requester_pays_authorized = true" in state, "R0 Requester Pays release missing")
    require("r0_list_objects_v2_authorized = true" in state, "R0 LIST release missing")
    require("r0_paid_request_authorized = true" in state, "R0 paid request release missing")
    require("requester_pays_authorized = false" in state and "list_objects_authorized = false" in state, "broader archive listing gate opened")
    require("paid_request_authorized = false" in state, "broader archive paid-request gate opened")
    require("get_object_authorized = false" in state and "object_body_download_authorized = false" in state, "object-body gate opened")
    require("market_data_ingested = false" in state and "empirical_result = null" in state, "market result created")


def main() -> int:
    validate()
    print("R0_IMPLEMENTATION_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
