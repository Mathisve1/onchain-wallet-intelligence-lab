from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CANDIDATE = BASE / "r10b_runtime/R10B_EXECUTION_RELEASE_CANDIDATE.json"
IMPLEMENTATION = BASE / "r10b_implementation/R10B_IMPLEMENTATION_CONTRACT.json"
APPROVAL = BASE / "r10b_approval/APPROVE_HL_ARCHIVE_R10B_BATCH_METADATA_LEXICAL_DIAGNOSTIC_001.json"
PREREG = BASE / "r10b/R10B_BATCH_METADATA_LEXICAL_PREREGISTRATION.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r10b-batch-metadata-lexical-diagnostic.yml"
FROZEN_WORKFLOW = BASE / "r10b_implementation/workflows/hyperliquid-archive-r10b-batch-metadata-lexical-diagnostic.yml"

PREREG_MERGE = "8ba7b0928ac45c66dd6df756491928fddbe2a060"
APPROVAL_MERGE = "0ca8bc4da2dbb3cda073a41c45a72e5f051419cc"
IMPLEMENTATION_MERGE = "e926713ed5e65a0902b8a90d0d54de5c19c22fbb"
APPROVAL_SHA = "981b9277b652117c2a3648fa3870015d3efe590a595e84bcba22cf0b3f8f8061"
WORKFLOW_BLOB_SHA = "e093fe6a95b543dc3cfd860f460debd8f8a4f944"
ROLE = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
OBJECT_KEY = "node_fills_by_block/hourly/20250727/9.lz4"
OBJECT_SHA = "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def main() -> int:
    c = load(CANDIDATE)
    i = load(IMPLEMENTATION)
    a = load(APPROVAL)
    p = load(PREREG)

    assert c["release_candidate_id"] == "CANDIDATE_RELEASE_HL_ARCHIVE_R10B_BATCH_METADATA_LEXICAL_001"
    assert c["diagnostic_id"] == i["diagnostic_id"] == a["diagnostic_id"] == p["diagnostic_id"] == "HL-ARCHIVE-R10B-BATCH-METADATA-LEXICAL-DIAGNOSTIC-001"
    assert c["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert c["r10b_preregistration_merge_commit"] == PREREG_MERGE
    assert c["r10b_approval_merge_commit"] == APPROVAL_MERGE
    assert c["r10b_implementation_merge_commit"] == IMPLEMENTATION_MERGE
    assert c["approval_text_sha256"] == APPROVAL_SHA

    assert c["workflow_path"] == ".github/workflows/hyperliquid-archive-r10b-batch-metadata-lexical-diagnostic.yml"
    assert c["workflow_candidate_path"] == "research/archive_inventory/r10b_implementation/workflows/hyperliquid-archive-r10b-batch-metadata-lexical-diagnostic.yml"
    assert c["workflow_name"] == "Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10"
    assert c["workflow_run_name"] == "R10B batch metadata lexical diagnostic"
    assert c["workflow_git_blob_sha"] == WORKFLOW_BLOB_SHA
    assert git_blob_sha(WORKFLOW.read_bytes()) == WORKFLOW_BLOB_SHA
    assert WORKFLOW.read_bytes() == FROZEN_WORKFLOW.read_bytes()

    assert c["role_arn"] == ROLE and c["role_reuse_without_mutation"] is True
    target = c["exact_network_target"]
    assert target == {
        "bucket": "hl-mainnet-node-data",
        "region": "ap-northeast-1",
        "key": OBJECT_KEY,
        "expected_size_bytes": 18147822,
        "expected_etag": '"5a9941a240118a57f77a4c3ee95b8430-3"',
        "expected_compressed_sha256": OBJECT_SHA,
    }
    e = c["execution_envelope"]
    assert e["maximum_one_time_budget_eur"] == 0.10 and e["maximum_monthly_budget_eur"] == 0
    assert e["maximum_get_object_requests"] == 1 and e["maximum_requests_per_object"] == 1 and e["maximum_retries_per_request"] == 0
    assert e["maximum_total_compressed_bytes"] == 18147822 and e["maximum_total_decompressed_bytes"] == 268435456
    assert e["maximum_runtime_seconds"] == 120
    for key in ("requester_pays_required", "if_match_etag_required", "exact_content_length_required", "exact_response_etag_required", "exact_compressed_sha256_required"):
        assert e[key] is True, key
    for key in ("http_redirect_following_authorized", "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized", "get_object_attributes_authorized", "get_object_version_authorized"):
        assert e[key] is False, key

    future = c["future_processing_authority_if_separately_activated"]
    for key in ("decompression", "metadata_lexical_processing", "aggregate_lexical_retention"):
        assert future[key] is True, key
    for key in ("timezone_parsing", "timezone_inference", "datetime_conversion", "individual_metadata_value_retention", "event_array_contents_inspection", "event_pair_count_retention", "block_number_value_retention", "wallet_address_retention", "wallet_aggregation", "economic_fill_field_processing", "individual_fill_time_processing", "raw_object_retention", "raw_block_event_fill_retention"):
        assert future[key] is False, key

    assert c["canonical_activation_required"] is True
    assert c["canonical_activation_present"] is False
    assert c["single_use_window_start_utc"] is None
    for key in ("single_workflow_dispatch_authorized", "aws_oidc_authorized", "requester_pays_authorized", "get_object_authorized", "object_body_download_authorized", "decompression_authorized", "metadata_lexical_processing_authorized", "aggregate_lexical_retention_authorized", "release_consumed", "rerun_authorized"):
        assert c[key] is False, key
    assert c["network_requests_executed"] == 0
    assert c["aws_iam_mutations_executed"] == 0
    assert c["empirical_result"] is None
    assert all(v is False for v in c["downstream_authorizations"].values())
    assert all(v is False for v in c["trading_authorizations"].values())

    assert p["status"] == "PREREGISTERED_NO_EXECUTION"
    assert all(v is False for v in p["current_runtime_authority"].values())
    assert a["status"] == "OWNER_APPROVED_IMPLEMENTATION_NO_EXECUTION"
    assert a["execution_authorized_by_this_approval"] is False
    assert all(v is False for v in a["current_runtime_authority"].values())
    assert i["status"] == "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE"
    assert i["execution_release_present"] is False
    assert i["canonical_activation_present"] is False
    assert i["single_workflow_dispatch_authorized"] is False
    assert i["network_requests_executed"] == 0
    assert i["aws_iam_mutations_executed"] == 0

    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.startswith("name: Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10\nrun-name: R10B batch metadata lexical diagnostic\n")
    assert "workflow_dispatch:" in text and "schedule:" not in text
    assert "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10B_RUN" in text
    assert text.index("Prove exact single-use R10B release before OIDC") < text.index("Assume existing R10 role with exact one-object session scope")
    assert f"role-to-assume: {ROLE}" in text
    assert "role-duration-seconds: 900" in text and "retry-max-attempts: 1" in text
    assert '"Action":"s3:GetObject"' in text
    assert f"arn:aws:s3:::hl-mainnet-node-data/{OBJECT_KEY}" in text
    assert OBJECT_SHA in text
    assert "research.archive_inventory.r10b_implementation.collector" in text

    print("R10B_EXECUTION_RELEASE_CANDIDATE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
