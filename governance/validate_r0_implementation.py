#!/usr/bin/env python3
from __future__ import annotations

import base64
import gzip
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
EVIDENCE = R0 / "evidence"
RUN_ID = 31260043109
JOB_ID = 93109335453
ARTIFACT_ID = 9022511541
RUN_ROOT = EVIDENCE / f"run-{RUN_ID}"
ATTESTATION = EVIDENCE / "HL-ARCHIVE-METADATA-CANARY-R0-001-ATTESTATION.json"
APPROVAL_SHA = "d70008eac7521b324f61161bcc0075e28cc3a116dd30f0c52b48d8cf5eb6ed46"
APPROVAL_COMMIT = "9af4b21863e47fb3bb2997ce77b9940eecf4597f"
APPROVAL_TIME = "2026-08-08T10:10:00Z"
IMPLEMENTATION_COMMIT = "cd5c46b25502b671693dd5ebb091e7273399bccf"
RELEASE_COMMIT = "bc8a47a1cdeb1163657ea243d6694286d6612bed"
ARTIFACT_SHA = "40b26e33833b54a872a75be066a87b7e57a0e2f3930adada76ca3829a1142c8e"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"R0_IMPLEMENTATION_VALIDATION_FAIL: {message}")


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root not object: {path}")
    return value


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate() -> None:
    for path in (
        WORKFLOW,
        R0 / "R0_IMPLEMENTATION_CONTRACT.json",
        R0 / "README.md",
        R0 / "collector.py",
        RELEASE_PATH,
        APPROVAL_TEXT,
        APPROVAL_JSON,
        EVIDENCE / "CLEAN_CONTEXT_REVIEW.md",
        ATTESTATION,
        RUN_ROOT / "r0-metadata-context.json",
        RUN_ROOT / "r0-metadata-result.json.gz.b64",
        RUN_ROOT / "r0-metadata.rc",
        RUN_ROOT / "R0_METADATA_FILES.sha256",
        RUN_ROOT / "EVIDENCE_ENCODING.json",
        RUN_ROOT / "INDEPENDENT_ARTIFACT_VERIFICATION.json",
    ):
        require(path.is_file(), f"missing R0 evidence path: {path.relative_to(ROOT)}")
    require(not (R0 / "outputs").exists(), "R0 outputs created from metadata-only canary")

    approval = load(APPROVAL_JSON)
    require(sha256(APPROVAL_TEXT.read_bytes()) == APPROVAL_SHA, "approval text hash drift")
    require(approval["exact_approval_text_sha256"] == APPROVAL_SHA, "approval record hash drift")
    require(approval["reviewed_commit"] == APPROVAL_COMMIT, "approval reviewed commit drift")
    require(approval["recorded_at_utc"] == APPROVAL_TIME, "approval timestamp drift")
    require(approval["maximum_one_time_budget_eur"] == 1.0, "approval budget drift")
    require(approval["maximum_monthly_budget_eur"] == 0, "monthly budget opened")
    require(approval["maximum_list_requests"] == 7, "approval request cap drift")
    require(approval["maximum_keys_per_request"] == 25, "approval max-keys drift")
    require(approval["maximum_retries_per_request"] == 0, "approval retry drift")
    require(approval["pagination_authorized"] is False, "approval pagination opened")

    implementation = load(R0 / "R0_IMPLEMENTATION_CONTRACT.json")
    require(implementation["canonical_implementation_commit"] == IMPLEMENTATION_COMMIT, "implementation commit drift")
    require(implementation["implementation_self_releases_execution"] is False, "implementation self-releases")
    require(implementation["execution_authorized_only_by_separate_release"] is True, "release authority drift")
    require(implementation["maximum_list_requests"] == 7 and implementation["s3_http_request_cap"] == 7, "implementation request cap drift")
    require(implementation["maximum_retries_per_request"] == 0, "implementation retry opened")
    require(implementation["pagination_authorized"] is False, "implementation pagination opened")
    require(implementation["http_redirect_following_authorized"] is False, "implementation redirect opened")
    require(implementation["market_data_ingestion_authorized"] is False, "implementation market-data gate opened")
    require(all(value is False for value in implementation["authorizations"].values()), "implementation trading gate opened")

    release = load(RELEASE_PATH)
    require(release["release_id"] == "RELEASE_HL_ARCHIVE_METADATA_CANARY_R0_001", "release ID drift")
    require(release["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R0_RUN", "immutable release snapshot drift")
    require(release["implementation_commit"] == IMPLEMENTATION_COMMIT, "release implementation drift")
    require(release["human_approval_text_sha256"] == APPROVAL_SHA, "release approval hash drift")
    require(release["single_use_window_start_utc"] == APPROVAL_TIME, "release window drift")
    require(release["maximum_one_time_budget_eur"] == 1.0 and release["maximum_monthly_budget_eur"] == 0, "release budget drift")
    require(release["maximum_list_requests"] == 7 and release["maximum_keys_per_request"] == 25, "release request caps drift")
    require(release["maximum_retries_per_request"] == 0, "release retry opened")
    require(release["pagination_authorized"] is False and release["http_redirect_following_authorized"] is False, "release pagination/redirect opened")
    require(release["single_workflow_dispatch_authorized"] is True and release["rerun_authorized"] is False, "single-use release drift")
    require(release["s3_requests_executed"] == 0 and release["empirical_result"] is None, "immutable release snapshot rewritten as result")
    require(release["market_data_ingestion_authorized"] is False, "release market-data gate opened")
    require(all(value is False for value in release["trading_authorizations"].values()), "release trading gate opened")

    context_bytes = (RUN_ROOT / "r0-metadata-context.json").read_bytes()
    context = json.loads(context_bytes)
    require(sha256(context_bytes) == "07856ce390e26413ebc272aa373f429490dbe71cadf005fd0c0172e5ead4cefc", "run context hash drift")
    require(context["workflow_run_id"] == RUN_ID and context["workflow_run_attempt"] == 1, "run context identity drift")
    require(context["dispatch_ref"] == "refs/heads/main", "dispatch ref drift")
    for key in ("dispatch_sha", "reviewed_commit", "checked_out_commit"):
        require(context[key] == RELEASE_COMMIT, f"run context commit drift: {key}")
    require(context["configure_aws_outcome"] == "success", "OIDC configure result drift")
    require(context["execution_release_id"] == release["release_id"], "run release identity drift")
    require(context["implementation_commit"] == IMPLEMENTATION_COMMIT, "run implementation identity drift")
    require(context["terminal_status"] == "R0_METADATA_CANARY_FAIL", "terminal status drift")
    require(context["request_attempt_count"] == 7 and context["s3_http_request_count"] == 7, "actual request count drift")
    require(context["successful_request_count"] == 2 and context["failed_request_count"] == 5, "success/failure count drift")
    require(context["total_entries"] == 50 and context["total_response_bytes"] == 14229, "retained metadata totals drift")
    require(context["retries_used"] == 0 and context["pagination_followed"] is False and context["http_redirects_followed"] is False, "runtime guard drift")
    require(context["object_body_requested"] is False and context["market_data_ingested"] is False and context["empirical_result"] is None, "body/market boundary opened")

    encoding = load(RUN_ROOT / "EVIDENCE_ENCODING.json")
    encoded = (RUN_ROOT / encoding["encoded_file"]).read_bytes()
    require(len(encoded) == encoding["encoded_size_in_bytes"], "encoded result size drift")
    require(sha256(encoded) == encoding["encoded_sha256"], "encoded result hash drift")
    compressed = base64.b64decode(encoded, validate=True)
    require(len(compressed) == encoding["gzip_size_in_bytes"], "gzip size drift")
    require(sha256(compressed) == encoding["gzip_sha256"], "gzip hash drift")
    raw_result = gzip.decompress(compressed)
    require(len(raw_result) == encoding["raw_size_in_bytes"], "raw result size drift")
    require(sha256(raw_result) == encoding["raw_sha256"], "raw result hash drift")
    require(sha256(raw_result) == "36dcae87be0ce9f8d107cf4519d9e15ad7987b82309b66691ab5c5bf97ef7a4e", "canonical result hash drift")
    result = json.loads(raw_result)
    require(result["terminal_status"] == "R0_METADATA_CANARY_FAIL", "decoded result terminal drift")
    require(result["request_attempt_count"] == 7 and result["s3_http_request_count"] == 7, "decoded request count drift")
    require(result["successful_request_count"] == 2 and result["failed_request_count"] == 5, "decoded request outcomes drift")
    require(result["total_entries"] == 50 and len(result["observations"]) == 7, "decoded observation count drift")
    require(result["retries_used"] == 0 and result["pagination_followed"] is False and result["http_redirects_followed"] is False, "decoded guard drift")
    require(result["object_body_requested"] is False and result["market_data_ingested"] is False and result["empirical_result"] is None, "decoded market/body boundary drift")

    successes = [row for row in result["observations"] if row["http_or_sdk_status_class"] == "SUCCESS"]
    failures = [row for row in result["observations"] if row["http_or_sdk_status_class"] != "SUCCESS"]
    require({row["dataset_family_id"] for row in successes} == {"market_data", "asset_ctxs"}, "successful family set drift")
    require(all(row["bucket"] == "hyperliquid-archive" for row in successes), "successful bucket drift")
    require(all(row["key_count"] == 25 and row["is_truncated"] is True and row["next_continuation_token_present"] is True for row in successes), "successful metadata shape drift")
    require(all(row["request_charged"] == "requester" for row in successes), "Requester Pays success evidence drift")
    require(len(failures) == 5 and all(row["bucket"] == "hl-mainnet-node-data" for row in failures), "failed bucket/family count drift")
    require(all(row["http_or_sdk_status_class"] == "S3_AuthorizationHeaderMalformed" for row in failures), "failure class drift")

    ledger = (RUN_ROOT / "R0_METADATA_FILES.sha256").read_text(encoding="utf-8").splitlines()
    expected_ledger = {
        "r0-metadata-context.json": sha256(context_bytes),
        "r0-metadata-result.json": sha256(raw_result),
        "r0-metadata.rc": sha256((RUN_ROOT / "r0-metadata.rc").read_bytes()),
    }
    observed_ledger = {}
    for line in ledger:
        digest, name = line.split("  ", 1)
        observed_ledger[name] = digest
    require(observed_ledger == expected_ledger, "internal R0 hash ledger mismatch")
    require((RUN_ROOT / "r0-metadata.rc").read_text(encoding="utf-8") == "0\n", "collector return code drift")

    verification = load(RUN_ROOT / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
    require(verification["workflow_run_id"] == RUN_ID and verification["workflow_job_id"] == JOB_ID, "independent verification identity drift")
    require(verification["artifact"]["artifact_id"] == ARTIFACT_ID, "artifact ID drift")
    require(verification["artifact"]["provider_digest"] == "sha256:" + ARTIFACT_SHA, "provider artifact digest drift")
    require(verification["artifact"]["downloaded_zip_sha256"] == ARTIFACT_SHA, "downloaded artifact digest drift")
    require(all(verification["validation"].values()), "independent artifact validation not all-pass")

    attestation = load(ATTESTATION)
    require(attestation["status"] == "ATTESTED_CONSUMED_PARTIAL_FAILURE_REGION_UNRESOLVED", "attestation status drift")
    require(attestation["canonical_release_commit"] == RELEASE_COMMIT, "attestation release commit drift")
    require(attestation["workflow_run_id"] == RUN_ID and attestation["workflow_job_id"] == JOB_ID and attestation["artifact_id"] == ARTIFACT_ID, "attestation run identity drift")
    require(attestation["artifact_sha256"] == ARTIFACT_SHA, "attestation artifact digest drift")
    require(attestation["release_consumed"] is True and attestation["rerun_authorized"] is False and attestation["fresh_paid_attempt_authorized"] is False, "consumption/authorization drift")
    require(attestation["root_cause_assessment"]["classification"] == "STRONGLY_CONSISTENT_WITH_SIGNING_REGION_MISMATCH", "root-cause classification drift")
    require(attestation["root_cause_assessment"]["exact_bucket_region"] is None, "exact Region invented")
    require(attestation["market_data_ingestion_authorized"] is False and all(value is False for value in attestation["trading_authorizations"].values()), "attestation opens downstream authorization")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    require("workflow_dispatch:" in workflow and "pull_request:" not in workflow and "push:" not in workflow, "R0 workflow auto-triggered")
    require("test \"${CURRENT_RUN_ATTEMPT}\" = '1'" in workflow, "rerun gate missing")
    require("len(eligible) == 1" in workflow, "single-use history gate missing")
    require('"Action":"s3:ListBucket"' in workflow and workflow.count('"s3:max-keys":"25"') == 2, "session policy drift")
    require("aws s3api" not in workflow and "aws s3 " not in workflow, "workflow contains AWS S3 CLI call")

    collector = (R0 / "collector.py").read_text(encoding="utf-8")
    for forbidden in (
        "subprocess", "urllib.request", "boto3", "botocore", '"aws"',
        "GetObject", "HeadObject", "GetObjectAttributes", "ListObjectVersions",
        "ListAllMyBuckets", "PutObject", "DeleteObject", "RestoreObject",
    ):
        require(forbidden not in collector, f"forbidden collector capability/literal: {forbidden}")

    state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    require("r0_execution_release_consumed = true" in state, "release consumption state missing")
    require("r0_execution_ready = false" in state, "consumed release still execution-ready")
    require("r0_s3_requests_executed = 7" in state, "actual S3 request count state missing")
    require("r0_successful_requests = 2" in state and "r0_failed_requests = 5" in state, "request outcome state drift")
    require("r0_requester_pays_authorized = false" in state and "r0_list_objects_v2_authorized = false" in state and "r0_paid_request_authorized = false" in state, "consumed R0 authorization still open")
    require("fresh_paid_attempt_authorized = false" in state, "fresh paid attempt prematurely authorized")
    require("larger_300_request_inventory_authorized = false" in state, "larger inventory gate opened")
    require("get_object_authorized = false" in state and "object_body_download_authorized = false" in state, "object body gate opened")
    require("market_data_ingested = false" in state and "empirical_result = null" in state, "market result created")


def main() -> int:
    validate()
    print("R0_IMPLEMENTATION_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
