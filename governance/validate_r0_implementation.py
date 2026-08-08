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
APPROVAL_SHA = "d70008eac7521b324f61161bcc0075e28cc3a116dd30f0c52b48d8cf5eb6ed46"
RELEASE_PATH = R0 / "R0_EXECUTION_RELEASE.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"R0_IMPLEMENTATION_VALIDATION_FAIL: {message}")


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root not object: {path}")
    return value


def validate() -> None:
    required = {
        WORKFLOW,
        R0 / "R0_IMPLEMENTATION_CONTRACT.json",
        R0 / "README.md",
        R0 / "collector.py",
        APPROVAL_TEXT,
        APPROVAL_JSON,
    }
    for path in required:
        require(path.is_file(), f"missing R0 implementation path: {path.relative_to(ROOT)}")
    require(not RELEASE_PATH.exists(), "execution release exists on implementation candidate before canonical merge")
    require(not (R0 / "evidence").exists(), "R0 evidence exists before canonical run")
    require(not (R0 / "outputs").exists(), "R0 outputs exist before canonical run")

    approval = load(APPROVAL_JSON)
    require(hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA, "approval text hash drift")
    require(approval["exact_approval_text_sha256"] == APPROVAL_SHA, "approval record hash drift")
    require(approval["reviewed_commit"] == "9af4b21863e47fb3bb2997ce77b9940eecf4597f", "approval reviewed commit drift")
    require(approval["maximum_one_time_budget_eur"] == 1.0, "approval budget drift")
    require(approval["maximum_monthly_budget_eur"] == 0, "monthly budget opened")
    require(approval["maximum_list_requests"] == 7, "approval request cap drift")
    require(approval["maximum_keys_per_request"] == 25, "approval max-keys drift")
    require(approval["maximum_total_entries"] == 175, "approval entry cap drift")
    require(approval["maximum_total_response_bytes"] == 8388608, "approval byte cap drift")
    require(approval["maximum_runtime_seconds"] == 180, "approval runtime drift")
    require(approval["maximum_retries_per_request"] == 0, "approval retry drift")
    require(approval["pagination_authorized"] is False, "approval pagination opened")

    implementation = load(R0 / "R0_IMPLEMENTATION_CONTRACT.json")
    require(implementation["status"] == "IMPLEMENTATION_CANDIDATE_PENDING_CANONICAL_MERGE", "implementation status drift")
    require(implementation["canary_id"] == "HL-ARCHIVE-METADATA-CANARY-R0-001", "canary identity drift")
    require(implementation["implementation_base_commit"] == "62e0750382216afb5875ad52cb7443d43265e862", "implementation base drift")
    require(implementation["human_approval_text_sha256"] == APPROVAL_SHA, "implementation approval hash drift")
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
    require(implementation["manual_execution_authorized_after_canonical_merge"] is False, "implementation merge bypasses release gate")
    require(implementation["post_merge_execution_release_required"] is True, "post-merge release gate disabled")
    require(implementation["execution_release_path"] == "research/archive_inventory/r0/R0_EXECUTION_RELEASE.json", "execution release path drift")
    require(implementation["execution_release_present_on_implementation_candidate"] is False, "candidate self-releases execution")
    require(implementation["market_data_ingestion_authorized"] is False, "market-data gate opened")
    require(all(value is False for value in implementation["authorizations"].values()), "trading/capital gate opened")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    require("workflow_dispatch:" in workflow, "R0 workflow is not manual")
    require("pull_request:" not in workflow and "push:" not in workflow, "R0 network workflow can auto-trigger")
    require("actions: read" in workflow and "id-token: write" in workflow and "contents: read" in workflow, "workflow permissions drift")
    require("arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-metadata-canary" in workflow, "R0 role drift")
    require("allowed-account-ids: '630956766927'" in workflow, "R0 account restriction missing")
    require("DIRECT_SIGV4_HTTPS_NO_REDIRECT_FOLLOW" in workflow, "direct transport binding missing")
    require("python research/archive_inventory/r0/collector.py" in workflow, "collector invocation missing")
    require("aws s3api" not in workflow and "aws s3 " not in workflow, "workflow contains direct AWS S3 CLI call")
    require('"Action":"s3:ListBucket"' in workflow, "session ListBucket scope missing")
    require(workflow.count('"s3:max-keys":"25"') == 2, "session max-keys scope drift")
    require("secrets.AWS_ACCESS_KEY_ID" not in workflow and "secrets.AWS_SECRET_ACCESS_KEY" not in workflow, "static AWS credential reference")
    require("R0_EXECUTION_RELEASE.json" in workflow, "execution release gate missing from workflow")
    require("RELEASED_FOR_EXACTLY_ONE_CANONICAL_R0_RUN" in workflow, "single-use release state missing")
    require("CURRENT_RUN_ATTEMPT" in workflow and "test \"${CURRENT_RUN_ATTEMPT}\" = '1'" in workflow, "rerun attempt gate missing")
    require("api.github.com" in workflow and "actions/workflows/" in workflow, "single-use run-history check missing")
    require("len(eligible) == 1" in workflow, "single-use eligible run count gate missing")
    require("a previous R0 dispatch already consumed this release" in workflow, "release consumption failure missing")

    collector = (R0 / "collector.py").read_text(encoding="utf-8")
    for required_token in (
        "http.client.HTTPSConnection",
        'connection.request("GET"',
        "x-amz-request-payer",
        "list-type",
        "max-keys",
        "DIRECT_SIGV4_HTTPS_NO_REDIRECT_FOLLOW",
    ):
        require(required_token in collector or required_token in implementation["s3_transport"], f"collector boundary missing: {required_token}")
    for forbidden in (
        "subprocess",
        "urllib.request",
        "boto3",
        "botocore",
        '"aws"',
        "GetObject",
        "HeadObject",
        "GetObjectAttributes",
        "ListObjectVersions",
        "ListAllMyBuckets",
        "PutObject",
        "DeleteObject",
        "RestoreObject",
    ):
        require(forbidden not in collector, f"forbidden collector capability/literal: {forbidden}")

    state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    require("human_r0_scope_budget_approved = true" in state, "human approval state missing")
    require("r0_execution_ready = false" in state, "execution readiness prematurely opened")
    require("requester_pays_authorized = false" in state, "operational Requester Pays gate prematurely opened")
    require("list_objects_authorized = false" in state, "operational LIST gate prematurely opened")
    require("paid_request_authorized = false" in state, "operational paid request gate prematurely opened")
    require("market_data_ingested = false" in state, "market data gate opened")


def main() -> int:
    validate()
    print("R0_IMPLEMENTATION_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
