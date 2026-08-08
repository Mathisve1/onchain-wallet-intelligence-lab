from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r2"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-nodedata-canary-r2.yml"
PREDECESSOR = BASE / "R2_EXECUTION_RELEASE.json"
CONSUMPTION = BASE / "R2_EXECUTION_RELEASE_001_CONSUMPTION.json"
SUCCESSOR = BASE / "R2_EXECUTION_RELEASE_002.json"

PREREGISTRATION_COMMIT = "39b40cccc7e9a3fdbc439d06fb188e946d9da2aa"
APPROVAL_MERGE_COMMIT = "151e08f54037ca7d3a0a9c17d3bdfb84d707a66e"
APPROVAL_SHA256 = "728f4e21c045eb10e883bdf0f2e970686f0e6b6cc4dc67a4f214a882cf1831c6"
IMPLEMENTATION_COMMIT = "142ce50be20507761c4cce37b325ac69d57f8b25"
PREDECESSOR_MERGE = "0dd6f32ab3a202b0c58f37821d1038ac917d84ce"


def fail(message: str) -> None:
    raise SystemExit(message)


def load(path: Path) -> dict:
    if not path.is_file():
        fail(f"missing required R2 successor file: {path.relative_to(ROOT)}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"JSON root must be object: {path.relative_to(ROOT)}")
    return value


def main() -> int:
    predecessor = load(PREDECESSOR)
    consumption = load(CONSUMPTION)
    successor = load(SUCCESSOR)
    if not WORKFLOW.is_file():
        fail("R2 workflow missing")
    workflow = WORKFLOW.read_text(encoding="utf-8")

    if predecessor.get("release_id") != "RELEASE_HL_ARCHIVE_NODEDATA_CANARY_R2_001":
        fail("predecessor release identity drift")
    if predecessor.get("status") != "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R2_RUN":
        fail("predecessor release status rewritten")
    if predecessor.get("implementation_commit") != IMPLEMENTATION_COMMIT:
        fail("predecessor implementation binding drift")
    if predecessor.get("s3_requests_executed") != 0 or predecessor.get("metadata_entries_observed") != 0:
        fail("predecessor immutable release snapshot rewritten")
    if predecessor.get("empirical_result") is not None:
        fail("predecessor immutable release result rewritten")

    if consumption.get("attestation_id") != "ATTEST_HL_ARCHIVE_NODEDATA_CANARY_R2_RELEASE_001_CONSUMED_PRE_OIDC":
        fail("R2 predecessor consumption attestation identity mismatch")
    if consumption.get("predecessor_release_id") != predecessor.get("release_id"):
        fail("consumption predecessor release mismatch")
    if consumption.get("predecessor_release_merge_commit") != PREDECESSOR_MERGE:
        fail("consumption predecessor merge mismatch")
    if consumption.get("status") != "CONSUMED_BY_FIRST_DISPATCH_PRE_OIDC_NO_S3_EXECUTION":
        fail("consumption status mismatch")
    if consumption.get("visible_exact_reviewed_commit") != PREDECESSOR_MERGE:
        fail("consumption reviewed commit evidence mismatch")
    if consumption.get("visible_dispatch_ref") != "refs/heads/main":
        fail("consumption dispatch ref evidence mismatch")
    if consumption.get("visible_dispatch_sha") != PREDECESSOR_MERGE:
        fail("consumption dispatch SHA evidence mismatch")
    for key in ("aws_oidc_role_assumption_step_executed", "collector_step_executed"):
        if consumption.get(key) is not False:
            fail(f"predecessor non-execution proof drift: {key}")
    for key in (
        "s3_http_requests_executed",
        "list_objects_v2_requests_executed",
        "metadata_entries_observed",
        "requester_pays_s3_requests_executed",
    ):
        if consumption.get(key) != 0:
            fail(f"predecessor zero-use proof drift: {key}")
    if consumption.get("rerun_authorized") is not False:
        fail("predecessor rerun opened")
    if consumption.get("successor_release_required_for_any_new_dispatch") is not True:
        fail("successor release requirement missing")

    if successor.get("release_id") != "RELEASE_HL_ARCHIVE_NODEDATA_CANARY_R2_002":
        fail("successor release ID mismatch")
    if successor.get("status") != "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R2_SUCCESSOR_RUN_AFTER_MERGE":
        fail("successor status mismatch")
    if successor.get("predecessor_release_id") != predecessor.get("release_id"):
        fail("successor predecessor binding mismatch")
    if successor.get("predecessor_release_consumed") is not True:
        fail("successor does not acknowledge consumed predecessor")
    if successor.get("predecessor_s3_requests_executed") != 0 or successor.get("predecessor_metadata_entries_observed") != 0:
        fail("successor predecessor usage mismatch")
    if successor.get("preregistration_commit") != PREREGISTRATION_COMMIT:
        fail("successor preregistration binding mismatch")
    if successor.get("approval_merge_commit") != APPROVAL_MERGE_COMMIT:
        fail("successor approval merge binding mismatch")
    if successor.get("approval_text_sha256") != APPROVAL_SHA256:
        fail("successor approval hash mismatch")
    if successor.get("implementation_commit") != IMPLEMENTATION_COMMIT:
        fail("successor implementation binding mismatch")
    if successor.get("github_event_required") != "workflow_dispatch":
        fail("successor event binding mismatch")
    if successor.get("canonical_dispatch_ref_required") != "refs/heads/main":
        fail("successor main ref binding mismatch")
    if successor.get("canonical_dispatch_sha_source") != "github.sha":
        fail("successor dispatch SHA source mismatch")
    if successor.get("manual_reviewed_commit_input_required") is not False:
        fail("successor retained redundant reviewed-commit input")

    exact = {
        "target_bucket": "hl-mainnet-node-data",
        "signing_region": "ap-northeast-1",
        "regional_virtual_hosted_endpoint": "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com",
        "operation": "ListObjectsV2",
        "request_payer": "requester",
        "dataset_family_count": 5,
        "maximum_one_time_budget_eur": 0.10,
        "maximum_monthly_budget_eur": 0,
        "maximum_list_requests": 5,
        "maximum_keys_per_request": 25,
        "maximum_total_entries": 125,
        "maximum_total_response_bytes": 8388608,
        "maximum_runtime_seconds": 120,
        "maximum_retries_per_request": 0,
        "session_s3_policy": "ALLOW_LISTBUCKET_EXACT_FIVE_PREFIXES_MAX25_ONLY",
    }
    for key, expected in exact.items():
        if successor.get(key) != expected:
            fail(f"successor envelope drift: {key}")
    for key in ("pagination_authorized", "continuation_token_follow_authorized", "http_redirect_following_authorized"):
        if successor.get(key) is not False:
            fail(f"successor transport widening: {key}")
    if successor.get("requester_pays_authorized") is not True or successor.get("list_objects_v2_authorized") is not True:
        fail("successor approved LIST scope not opened")
    if successor.get("single_workflow_dispatch_authorized") is not True or successor.get("rerun_authorized") is not False:
        fail("successor single-use boundary drift")
    for key in (
        "get_object_authorized", "head_object_authorized", "get_object_attributes_authorized",
        "range_get_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "object_body_download_authorized", "decompression_authorized", "market_data_ingestion_authorized",
        "larger_300_request_inventory_authorized",
    ):
        if successor.get(key) is not False:
            fail(f"successor forbidden capability opened: {key}")
    if successor.get("s3_requests_executed") != 0 or successor.get("metadata_entries_observed") != 0 or successor.get("empirical_result") is not None:
        fail("successor pre-dispatch snapshot contains execution evidence")
    if not all(value is False for value in successor.get("trading_authorizations", {}).values()):
        fail("successor trading authorization opened")

    if "workflow_dispatch:" not in workflow:
        fail("successor workflow is not manual-only")
    for trigger in ("pull_request:", "schedule:", "push:"):
        if trigger in workflow:
            fail(f"successor workflow opens forbidden trigger: {trigger}")
    required_tokens = (
        "EVENT_NAME: ${{ github.event_name }}",
        "DISPATCH_REF: ${{ github.ref }}",
        "DISPATCH_SHA: ${{ github.sha }}",
        "SUCCESSOR_EXECUTION_RELEASE_PATH: research/archive_inventory/r2/R2_EXECUTION_RELEASE_002.json",
        "PREDECESSOR_CONSUMPTION_PATH: research/archive_inventory/r2/R2_EXECUTION_RELEASE_001_CONSUMPTION.json",
        "ref: ${{ env.DISPATCH_SHA }}",
        'if [[ "${EVENT_NAME}" != "workflow_dispatch" ]]',
        'if [[ "${DISPATCH_REF}" != "refs/heads/main" ]]',
        'if [[ ! "${DISPATCH_SHA}" =~ ^[0-9a-f]{40}$ ]]',
        'if [[ "${observed_head}" != "${DISPATCH_SHA}" ]]',
        "exit 41", "exit 42", "exit 43", "exit 44",
        "validate_r2_successor_release.py",
        "Enforce successor single-use release before AWS OIDC",
        "a previous dispatch already consumed R2 successor release 002",
        "aws-region: ap-northeast-1",
        '"Action":"s3:ListBucket"',
        '"Resource":"arn:aws:s3:::hl-mainnet-node-data"',
        '"s3:max-keys":"25"',
    )
    for token in required_tokens:
        if token not in workflow:
            fail(f"successor workflow missing invariant: {token}")
    if "reviewed_commit:" in workflow or "inputs.reviewed_commit" in workflow:
        fail("successor workflow retains manual reviewed-commit input")
    identity = workflow.find("Verify canonical manual main dispatch and checked-out identity")
    proof = workflow.find("Prove canonical implementation and single-use release before AWS OIDC")
    single_use = workflow.find("Enforce successor single-use release before AWS OIDC")
    configure = workflow.find("aws-actions/configure-aws-credentials@")
    execute = workflow.find("Execute bounded five-prefix R2 collector")
    if min(identity, proof, single_use, configure, execute) < 0:
        fail("successor workflow step ordering incomplete")
    if not (identity < proof < single_use < configure < execute):
        fail("successor pre-OIDC ordering drift")

    print("R2_SUCCESSOR_RELEASE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
