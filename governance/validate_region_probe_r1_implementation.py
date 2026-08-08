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
EVIDENCE = BASE / "evidence"
RUN = EVIDENCE / "run-31273770895"
ATTESTATION = EVIDENCE / "HL-ARCHIVE-REGION-PROBE-R1-001-ATTESTATION.json"
VERIFICATION = RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json"
CONTEXT = RUN / "region-probe-r1-context.json"
RESULT = RUN / "region-probe-r1-result.json"
RC = RUN / "region-probe-r1.rc"
LEDGER = RUN / "REGION_PROBE_R1_FILES.sha256"

APPROVAL_SHA = "56c8d01396b12d0dd783dbc1646ebbca947e51a024bb5c8f091cd0b7a889c541"
PREREG_COMMIT = "910997423f5e008f3c7bca65fd739d6aa14d25a7"
APPROVAL_MERGE = "b86156d71ef438441e6d3903a8bbc2da564a2046"
IMPLEMENTATION_COMMIT = "91687b4c803e331d4b2ef8493df731c99e25a0e5"
RELEASE_COMMIT = "f32901ac1946ff6456c44b3a1f75e4a7b641fa39"
RUN_ID = 31273770895
JOB_ID = 93143945097
ARTIFACT_ID = 9026393705
ARTIFACT_SHA = "5f66d4a961c3f32804af3d40adcd2d2c3f3b35e93896c9861839465e2d83d405"
REGION = "ap-northeast-1"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"REGION_PROBE_R1_EVIDENCE_VALIDATION_FAIL: {message}")


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root not object: {path.relative_to(ROOT)}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> None:
    for path in (WORKFLOW, PROBE, PREREG, IMPLEMENTATION, APPROVAL_TEXT, APPROVAL_JSON, RELEASE, ATTESTATION, VERIFICATION, CONTEXT, RESULT, RC, LEDGER):
        require(path.is_file(), f"missing Region probe evidence path: {path.relative_to(ROOT)}")
    require(not (BASE / "outputs").exists(), "unexpected Region probe outputs directory")

    prereg = load(PREREG)
    require(prereg["status"] == "PREREGISTERED_NOT_AUTHORIZED", "immutable preregistration status rewritten")
    require(prereg["target_bucket"] == "hl-mainnet-node-data" and prereg["operation"] == "HeadBucket", "preregistration target/operation drift")
    require(prereg["maximum_s3_http_requests"] == 1 and prereg["maximum_retries"] == 0, "preregistration request/retry drift")
    require(prereg["execution_authorized"] is False and prereg["fresh_paid_attempt_authorized"] is False, "preregistration self-authorizes runtime")

    approval = load(APPROVAL_JSON)
    require(hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA, "approval text hash drift")
    require(approval["reviewed_commit"] == PREREG_COMMIT and approval["approval_id"] == "APPROVE_HL_ARCHIVE_REGION_PROBE_R1_001", "approval identity drift")
    require(approval["maximum_one_time_budget_eur"] == 0.10 and approval["maximum_head_bucket_requests"] == 1, "approval envelope drift")
    require(approval["execution_authorized"] is False and approval["fresh_paid_attempt_authorized"] is False, "approval self-releases runtime")

    implementation = load(IMPLEMENTATION)
    require(implementation["preregistration_commit"] == PREREG_COMMIT and implementation["approval_merge_commit"] == APPROVAL_MERGE, "implementation provenance drift")
    require(implementation["maximum_s3_http_requests"] == 1 and implementation["maximum_retries"] == 0, "implementation request/retry drift")
    require(implementation["transport"] == "DIRECT_SIGV4_HTTPS_HEAD_NO_REDIRECT_NO_BODY", "implementation transport drift")
    require(implementation["session_s3_policy"] == "EXPLICIT_DENY_ALL_S3", "implementation session policy drift")
    require(implementation["execution_authorized"] is False and implementation["s3_request_executed"] is False, "immutable implementation snapshot rewritten as result")

    release = load(RELEASE)
    require(release["release_id"] == "RELEASE_HL_ARCHIVE_REGION_PROBE_R1_001", "release ID drift")
    require(release["implementation_commit"] == IMPLEMENTATION_COMMIT and release["approval_text_sha256"] == APPROVAL_SHA, "release binding drift")
    require(release["maximum_one_time_budget_eur"] == 0.10 and release["maximum_s3_http_requests"] == 1, "release envelope drift")
    require(release["maximum_retries"] == 0 and release["http_redirect_following_authorized"] is False, "release retry/redirect drift")
    require(release["single_workflow_dispatch_authorized"] is True and release["rerun_authorized"] is False, "release single-use drift")
    require(release["session_s3_policy"] == "EXPLICIT_DENY_ALL_S3", "release session boundary drift")
    for key in ("list_objects_v2_authorized", "get_object_authorized", "head_object_authorized", "get_object_attributes_authorized", "range_get_authorized", "object_body_download_authorized", "market_data_ingestion_authorized", "larger_300_request_inventory_authorized"):
        require(release[key] is False, f"forbidden release capability opened: {key}")
    require(release["s3_request_executed"] is False and release["exact_bucket_region"] is None, "immutable release snapshot rewritten as result")

    context = load(CONTEXT)
    result = load(RESULT)
    require(context["workflow_run_id"] == RUN_ID and context["workflow_run_attempt"] == 1, "run identity drift")
    require(context["checked_out_commit"] == RELEASE_COMMIT and context["reviewed_commit"] == RELEASE_COMMIT, "reviewed/checked-out commit drift")
    require(context["implementation_commit"] == IMPLEMENTATION_COMMIT, "context implementation drift")
    require(context["terminal_status"] == "REGION_PROBE_R1_PASS" and context["technical_result"] == "BUCKET_REGION_OBSERVED", "context terminal result drift")
    require(context["x_amz_bucket_region"] == REGION, "context bucket Region drift")
    require(context["request_attempt_count"] == 1 and context["s3_http_request_count"] == 1, "context request count drift")
    require(context["retries_used"] == 0 and context["http_redirects_followed"] is False, "context retry/redirect drift")
    require(context["response_body_read"] is False and context["list_objects_v2_requested"] is False and context["object_body_requested"] is False, "context forbidden data operation")
    require(context["market_data_ingested"] is False, "context market data ingested")

    require(result["terminal_status"] == "REGION_PROBE_R1_PASS" and result["technical_result"] == "BUCKET_REGION_OBSERVED", "result terminal drift")
    require(result["target_bucket"] == "hl-mainnet-node-data" and result["http_method"] == "HEAD", "result target/method drift")
    require(result["http_status"] == 400 and result["x_amz_bucket_region"] == REGION, "observed HTTP/Region drift")
    require(result["request_attempt_count"] == 1 and result["s3_http_request_count"] == 1, "result request count drift")
    require(result["runtime_seconds"] == 0.688386 and result["retries_used"] == 0 and result["http_redirects_followed"] is False, "result runtime/retry/redirect drift")
    require(result["requester_pays_requested"] is True and result["response_body_read"] is False, "result requester/body drift")
    require(result["list_objects_v2_requested"] is False and result["object_body_requested"] is False and result["market_data_ingested"] is False, "result forbidden access drift")
    require(result["empirical_result"] is None and result["failure_class"] is None, "result invented market/failure state")
    require(RC.read_text(encoding="utf-8") == "0\n", "return code drift")

    expected_ledger = {
        "region-probe-r1-context.json": "b26f3a57ac3e337be10cb0fa4cb09b656fabb7eb37d526c0c6f6f86a1a27d373",
        "region-probe-r1-result.json": "cd2f02900bc5e30bc4ef2a65ba7ebc764eb8c0cddf124c46cc5373d81746c059",
        "region-probe-r1.rc": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
    }
    require(sha(CONTEXT) == expected_ledger[CONTEXT.name], "context hash mismatch")
    require(sha(RESULT) == expected_ledger[RESULT.name], "result hash mismatch")
    require(sha(RC) == expected_ledger[RC.name], "rc hash mismatch")
    ledger_text = LEDGER.read_text(encoding="utf-8")
    for name, digest in expected_ledger.items():
        require(f"{digest}  {name}" in ledger_text, f"ledger missing exact hash: {name}")

    verification = load(VERIFICATION)
    require(verification["workflow_run_id"] == RUN_ID and verification["workflow_job_id"] == JOB_ID and verification["artifact_id"] == ARTIFACT_ID, "artifact identity drift")
    require(verification["github_artifact_digest"] == f"sha256:{ARTIFACT_SHA}", "provider artifact digest drift")
    require(verification["independently_downloaded_zip_sha256"] == ARTIFACT_SHA, "independent artifact digest drift")
    require(verification["provider_digest_match"] is True and verification["internal_hash_ledger_match"] is True and verification["verification_status"] == "PASS", "artifact verification failed")

    attestation = load(ATTESTATION)
    require(attestation["status"] == "ATTESTED_REGION_PROBE_R1_PASS", "attestation status drift")
    require(attestation["release_commit"] == RELEASE_COMMIT and attestation["implementation_commit"] == IMPLEMENTATION_COMMIT, "attestation commit binding drift")
    require(attestation["workflow_run_id"] == RUN_ID and attestation["workflow_job_id"] == JOB_ID and attestation["artifact_id"] == ARTIFACT_ID, "attestation run identity drift")
    require(attestation["artifact_sha256"] == ARTIFACT_SHA and attestation["x_amz_bucket_region"] == REGION, "attestation artifact/Region drift")
    require(attestation["request_attempt_count"] == 1 and attestation["s3_http_request_count"] == 1 and attestation["retries_used"] == 0, "attestation request count drift")
    require(attestation["release_consumed"] is True and attestation["fresh_list_attempt_authorized"] is False, "attestation consumption/list gate drift")
    require(attestation["market_data_ingested"] is False and all(v is False for v in attestation["trading_authorizations"].values()), "attestation opens downstream gates")

    source = PROBE.read_text(encoding="utf-8")
    require(source.count('connection.request("HEAD"') == 1 and "response.read(" not in source, "probe transport/body boundary drift")
    for token in ('connection.request("GET"', "ListObjectsV2", "GetObject", "HeadObject", "GetObjectAttributes", "boto3", "botocore"):
        require(token not in source, f"forbidden probe capability/literal: {token}")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    require("workflow_dispatch:" in workflow and "pull_request:" not in workflow and "push:" not in workflow, "workflow auto-triggered")
    require("Enforce single-use release before AWS OIDC" in workflow, "single-use gate missing")
    require('"Effect":"Deny","Action":"s3:*","Resource":"*"' in workflow and '"Effect":"Allow","Action":"s3:' not in workflow, "workflow S3 session boundary drift")

    state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    for token in (
        "region_probe_r1_execution_release_consumed = true",
        "region_probe_r1_execution_ready = false",
        "region_probe_r1_head_bucket_authorized = false",
        "region_probe_r1_request_executed = true",
        "region_probe_r1_s3_http_requests_executed = 1",
        "region_probe_r1_run_id = 31273770895",
        "region_probe_r1_job_id = 93143945097",
        "region_probe_r1_artifact_id = 9026393705",
        "region_probe_r1_exact_bucket_region = ap-northeast-1",
        "fresh_paid_attempt_authorized = false",
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
    print("REGION_PROBE_R1_EVIDENCE_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
