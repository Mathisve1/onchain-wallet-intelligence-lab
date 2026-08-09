from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r3"
PREREG = BASE / "HOURLY_METADATA_INVENTORY_R3_CONTRACT.json"
APPROVAL = BASE / "approvals/APPROVE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001.json"
APPROVAL_TEXT = BASE / "approvals/APPROVE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001.txt"
IMPLEMENTATION = BASE / "R3_IMPLEMENTATION_CONTRACT.json"
COLLECTOR = BASE / "collector.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-hourly-metadata-inventory-r3.yml"
RELEASE = BASE / "R3_EXECUTION_RELEASE.json"

PREREG_COMMIT = "ab4d42be02fe49d7f90f933317ef856f0322fd85"
APPROVAL_MERGE_COMMIT = "e562f3fbd8f1dac1b4d7e93eed2f5ee6b77c5da6"
APPROVAL_SHA = "3c3931133fb8b0dd322d7a296b7b70fca65dd341401a6eda2b6372938ed6cd10"
PENDING = "PENDING_CANONICAL_IMPLEMENTATION_MERGE"
EXPECTED_PREFIXES = [
    "node_fills_by_block/hourly/",
    "node_fills/hourly/",
    "node_trades/hourly/",
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    prereg = load(PREREG)
    approval = load(APPROVAL)
    impl = load(IMPLEMENTATION)
    collector = COLLECTOR.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA
    assert prereg["inventory_id"] == "HL-ARCHIVE-HOURLY-METADATA-INVENTORY-R3-001"
    assert approval["approval_id"] == "APPROVE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001"
    assert approval["reviewed_commit"] == PREREG_COMMIT
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert impl["preregistration_commit"] == PREREG_COMMIT
    assert impl["approval_merge_commit"] == APPROVAL_MERGE_COMMIT
    assert impl["approval_text_sha256"] == APPROVAL_SHA

    expected = [("node_fills_by_block", EXPECTED_PREFIXES[0]), ("node_fills", EXPECTED_PREFIXES[1]), ("node_trades", EXPECTED_PREFIXES[2])]
    assert [(r["dataset_family_id"], r["prefix"]) for r in impl["dataset_families"]] == expected
    assert impl["target_bucket"] == "hl-mainnet-node-data"
    assert impl["signing_region"] == "ap-northeast-1"
    assert impl["regional_virtual_hosted_endpoint"] == "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com"
    assert impl["maximum_keys_per_request"] == 1000
    assert impl["maximum_pages_per_family"] == 16
    assert impl["maximum_list_requests"] == 48
    assert impl["maximum_total_entries"] == 48000
    assert impl["maximum_total_response_bytes"] == 33554432
    assert impl["maximum_runtime_seconds"] == 300
    assert impl["maximum_retries_per_request"] == 0
    assert impl["pagination_authorized"] is True
    assert impl["continuation_token_follow_authorized"] is True
    assert impl["continuation_token_values_retained"] is False
    assert impl["repeated_continuation_token_fails_closed"] is True
    assert impl["duplicate_key_fails_closed"] is True
    assert impl["http_redirect_following_authorized"] is False
    assert impl["start_after_authorized"] is False
    assert impl["delimiter_authorized"] is False
    assert impl["fetch_owner"] is False
    assert impl["request_counter_incremented_before_transport"] is True
    assert impl["s3_transport"] == "DIRECT_SIGV4_HTTPS_REGIONAL_ENDPOINT_NO_REDIRECT_FOLLOW"
    assert impl["session_s3_policy"] == "ALLOW_LISTBUCKET_EXACT_THREE_HOURLY_PREFIXES_MAX1000_ONLY"
    assert impl["execution_release_required"] is True
    assert impl["execution_release_present"] is False
    assert impl["execution_authorized"] is False
    assert impl["paid_request_authorized"] is False
    assert impl["requester_pays_authorized"] is False
    assert impl["list_objects_v2_authorized"] is False
    for key in (
        "get_object_authorized", "head_object_authorized", "get_object_attributes_authorized",
        "range_get_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "object_body_download_authorized", "decompression_authorized",
        "explorer_blocks_inventory_authorized", "replica_cmds_inventory_authorized",
        "market_data_ingestion_authorized", "larger_300_request_inventory_authorized",
    ):
        assert impl[key] is False, key
    assert all(value is False for value in impl["trading_authorizations"].values())
    assert impl["s3_requests_executed"] == 0
    assert impl["metadata_entries_observed"] == 0
    assert impl["empirical_result"] is None

    tree = ast.parse(collector)
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    assert not imported_roots.intersection({"boto3", "botocore", "requests", "urllib3", "subprocess"})
    assert "http.client.HTTPSConnection" in collector
    assert "continuation-token" in collector
    assert "StartAfter" not in collector
    assert "fetch-owner" not in collector
    assert "response.read(maximum_body_bytes + 1)" in collector
    assert "request_attempt_count += 1" in collector
    assert "if next_token in seen_tokens" in collector
    assert "if key in family_seen_keys" in collector
    assert "CENSORED_BY_LIMIT" in collector
    assert "UNRESOLVED_LAYOUT" in collector
    assert "THREE_HOURLY_FAMILIES_COMPLETE_OR_CENSORED" in collector

    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "push:" not in workflow
    assert "persist-credentials: false" in workflow
    assert "EVENT_NAME: ${{ github.event_name }}" in workflow
    assert "DISPATCH_REF: ${{ github.ref }}" in workflow
    assert "DISPATCH_SHA: ${{ github.sha }}" in workflow
    assert "refs/heads/main" in workflow
    assert "PENDING_CANONICAL_IMPLEMENTATION_MERGE" in workflow or re.search(r"EXPECTED_IMPLEMENTATION_COMMIT: [0-9a-f]{40}", workflow)
    assert "R3_EXECUTION_RELEASE.json" in workflow
    assert "s3:ListBucket" in workflow
    for prefix in ("node_fills_by_block/hourly/*", "node_fills/hourly/*", "node_trades/hourly/*"):
        assert prefix in workflow
    assert '"s3:max-keys":"1000"' in workflow
    for forbidden in ("s3:GetObject", "s3:GetObjectAttributes", "s3:ListBucketVersions", "s3:ListAllMyBuckets"):
        assert forbidden not in workflow
    assert workflow.index("Prove canonical implementation and release before AWS OIDC") < workflow.index("Assume exact AWS role with R3-only session permissions")

    expected_commit = impl["expected_canonical_implementation_commit"]
    assert expected_commit == PENDING
    if RELEASE.exists():
        release = load(RELEASE)
        assert re.fullmatch(r"[0-9a-f]{40}", release["implementation_commit"])
        assert release["preregistration_commit"] == PREREG_COMMIT
        assert release["approval_merge_commit"] == APPROVAL_MERGE_COMMIT
        assert release["approval_text_sha256"] == APPROVAL_SHA

    print("R3_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
