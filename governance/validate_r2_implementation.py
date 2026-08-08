from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r2"
CONTRACT = BASE / "R2_IMPLEMENTATION_CONTRACT.json"
COLLECTOR = BASE / "collector.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-nodedata-canary-r2.yml"
RELEASE = BASE / "R2_EXECUTION_RELEASE.json"

EXPECTED_PREFIXES = [
    "node_fills_by_block/",
    "node_fills/",
    "node_trades/",
    "explorer_blocks/",
    "replica_cmds/",
]


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> int:
    if not CONTRACT.is_file() or not COLLECTOR.is_file() or not WORKFLOW.is_file():
        fail("R2 implementation candidate incomplete")
    if RELEASE.exists():
        fail("R2 execution release must be absent during implementation review")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("canary_id") != "HL-ARCHIVE-NODEDATA-METADATA-CANARY-R2-001":
        fail("R2 implementation canary mismatch")
    if contract.get("status") != "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION":
        fail("R2 implementation status mismatch")
    if contract.get("preregistration_commit") != "39b40cccc7e9a3fdbc439d06fb188e946d9da2aa":
        fail("R2 preregistration binding mismatch")
    if contract.get("approval_merge_commit") != "151e08f54037ca7d3a0a9c17d3bdfb84d707a66e":
        fail("R2 approval merge binding mismatch")
    if contract.get("human_approval_text_sha256") != "728f4e21c045eb10e883bdf0f2e970686f0e6b6cc4dc67a4f214a882cf1831c6":
        fail("R2 approval hash mismatch")
    if contract.get("target_bucket") != "hl-mainnet-node-data":
        fail("R2 bucket mismatch")
    if contract.get("signing_region") != "ap-northeast-1":
        fail("R2 signing Region mismatch")
    if contract.get("regional_virtual_hosted_endpoint") != "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com":
        fail("R2 endpoint mismatch")
    if [row.get("prefix") for row in contract.get("dataset_families", [])] != EXPECTED_PREFIXES:
        fail("R2 prefix scope mismatch")
    expected_caps = {
        "maximum_list_requests": 5,
        "maximum_keys_per_request": 25,
        "maximum_total_entries": 125,
        "maximum_total_response_bytes": 8388608,
        "maximum_runtime_seconds": 120,
        "maximum_retries_per_request": 0,
    }
    for key, value in expected_caps.items():
        if contract.get(key) != value:
            fail(f"R2 cap mismatch: {key}")
    for key in (
        "pagination_authorized",
        "continuation_token_follow_authorized",
        "http_redirect_following_authorized",
        "execution_release_present",
        "execution_authorized",
        "paid_request_authorized",
        "requester_pays_authorized",
        "list_objects_v2_authorized",
        "get_object_authorized",
        "head_object_authorized",
        "get_object_attributes_authorized",
        "range_get_authorized",
        "list_object_versions_authorized",
        "list_all_my_buckets_authorized",
        "object_body_download_authorized",
        "decompression_authorized",
        "market_data_ingestion_authorized",
        "larger_300_request_inventory_authorized",
    ):
        if contract.get(key) is not False:
            fail(f"R2 forbidden flag opened: {key}")
    if contract.get("expected_canonical_implementation_commit") != "PENDING_CANONICAL_IMPLEMENTATION_MERGE":
        fail("R2 implementation commit must remain pending during review")
    if contract.get("execution_release_required") is not True:
        fail("R2 release requirement missing")
    if not all(value is False for value in contract.get("trading_authorizations", {}).values()):
        fail("R2 trading authorization opened")

    source = COLLECTOR.read_text(encoding="utf-8")
    ast.parse(source)
    required_source = (
        'SIGNING_REGION = "ap-northeast-1"',
        'TARGET_BUCKET = "hl-mainnet-node-data"',
        'REGIONAL_ENDPOINT = f"{TARGET_BUCKET}.s3.{SIGNING_REGION}.amazonaws.com"',
        '"x-amz-request-payer": "requester"',
        '"continuation_token_values_retained": False',
        '"object_body_requested": False',
        '"market_data_ingested": False',
    )
    for token in required_source:
        if token not in source:
            fail(f"R2 collector missing invariant: {token}")
    forbidden_source = ("boto3", "botocore", "requests.", "urllib.request", "GetObject", "HeadObject")
    for token in forbidden_source:
        if token in source:
            fail(f"R2 collector contains forbidden transport/capability token: {token}")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    if "workflow_dispatch:" not in workflow:
        fail("R2 workflow is not manual-only")
    for trigger in ("pull_request:", "schedule:", "push:"):
        if trigger in workflow:
            fail(f"R2 workflow opens forbidden trigger: {trigger}")
    required_workflow = (
        "EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE",
        "EXECUTION_RELEASE_PATH: research/archive_inventory/r2/R2_EXECUTION_RELEASE.json",
        "APPROVAL_MERGE_COMMIT: 151e08f54037ca7d3a0a9c17d3bdfb84d707a66e",
        "APPROVAL_TEXT_SHA256: 728f4e21c045eb10e883bdf0f2e970686f0e6b6cc4dc67a4f214a882cf1831c6",
        "aws-region: ap-northeast-1",
        '"Action":"s3:ListBucket"',
        '"Resource":"arn:aws:s3:::hl-mainnet-node-data"',
        '"NumericLessThanEquals":{"s3:max-keys":"25"}',
    )
    for token in required_workflow:
        if token not in workflow:
            fail(f"R2 workflow missing invariant: {token}")
    pre_oidc = workflow.find("Prove canonical implementation and single-use release before AWS OIDC")
    configure = workflow.find("aws-actions/configure-aws-credentials@")
    if pre_oidc < 0 or configure < 0 or pre_oidc >= configure:
        fail("R2 release proof must occur before AWS OIDC")
    if "PENDING_CANONICAL_IMPLEMENTATION_MERGE" not in workflow:
        fail("R2 workflow is not fail-closed during implementation review")

    print("R2_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
