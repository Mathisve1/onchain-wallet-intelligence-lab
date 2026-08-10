from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RELEASE = BASE / "r10b_runtime/R10B_EXECUTION_RELEASE.json"
CANDIDATE = BASE / "r10b_runtime/R10B_EXECUTION_RELEASE_CANDIDATE.json"
IMPLEMENTATION = BASE / "r10b_implementation/R10B_IMPLEMENTATION_CONTRACT.json"
APPROVAL = BASE / "r10b_approval/APPROVE_HL_ARCHIVE_R10B_BATCH_METADATA_LEXICAL_DIAGNOSTIC_001.json"
PREREG = BASE / "r10b/R10B_BATCH_METADATA_LEXICAL_PREREGISTRATION.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r10b-batch-metadata-lexical-diagnostic.yml"
FROZEN_WORKFLOW = BASE / "r10b_implementation/workflows/hyperliquid-archive-r10b-batch-metadata-lexical-diagnostic.yml"

PREREG_MERGE = "8ba7b0928ac45c66dd6df756491928fddbe2a060"
APPROVAL_MERGE = "0ca8bc4da2dbb3cda073a41c45a72e5f051419cc"
IMPLEMENTATION_MERGE = "e926713ed5e65a0902b8a90d0d54de5c19c22fbb"
CANDIDATE_MERGE = "4e623e558dafe780e5bf472ca799d21780996951"
APPROVAL_SHA = "981b9277b652117c2a3648fa3870015d3efe590a595e84bcba22cf0b3f8f8061"
WORKFLOW_BLOB_SHA = "e093fe6a95b543dc3cfd860f460debd8f8a4f944"
ROLE = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
START = "2026-08-10T13:40:00Z"
KEY = "node_fills_by_block/hourly/20250727/9.lz4"
OBJECT_SHA = "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def main() -> int:
    r = load(RELEASE)
    c = load(CANDIDATE)
    i = load(IMPLEMENTATION)
    a = load(APPROVAL)
    p = load(PREREG)

    assert r["execution_release_id"] == "RELEASE_HL_ARCHIVE_R10B_BATCH_METADATA_LEXICAL_001"
    assert r["release_candidate_id"] == c["release_candidate_id"] == "CANDIDATE_RELEASE_HL_ARCHIVE_R10B_BATCH_METADATA_LEXICAL_001"
    assert r["diagnostic_id"] == c["diagnostic_id"] == i["diagnostic_id"] == a["diagnostic_id"] == p["diagnostic_id"] == "HL-ARCHIVE-R10B-BATCH-METADATA-LEXICAL-DIAGNOSTIC-001"
    assert r["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10B_RUN"
    assert r["r10b_preregistration_merge_commit"] == PREREG_MERGE
    assert r["r10b_approval_merge_commit"] == APPROVAL_MERGE
    assert r["r10b_implementation_merge_commit"] == IMPLEMENTATION_MERGE
    assert r["release_candidate_merge_commit"] == CANDIDATE_MERGE
    assert r["approval_text_sha256"] == APPROVAL_SHA

    assert r["workflow_path"] == ".github/workflows/hyperliquid-archive-r10b-batch-metadata-lexical-diagnostic.yml"
    assert r["workflow_name"] == "Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10"
    assert r["workflow_run_name"] == "R10B batch metadata lexical diagnostic"
    assert r["workflow_git_blob_sha"] == WORKFLOW_BLOB_SHA == git_blob_sha(WORKFLOW.read_bytes())
    assert WORKFLOW.read_bytes() == FROZEN_WORKFLOW.read_bytes()
    assert r["role_arn"] == ROLE and r["role_reuse_without_mutation"] is True

    assert r["single_use_window_start_utc"] == START
    start = datetime.fromisoformat(START.replace("Z", "+00:00")).astimezone(timezone.utc)
    assert start.isoformat() == "2026-08-10T13:40:00+00:00"
    assert r["single_workflow_dispatch_authorized"] is True
    assert r["rerun_authorized"] is False
    assert r["release_consumed"] is False

    assert r["maximum_one_time_budget_eur"] == 0.10 and r["maximum_monthly_budget_eur"] == 0
    assert r["maximum_get_object_requests"] == 1
    assert r["maximum_requests_per_object"] == 1
    assert r["maximum_retries_per_request"] == 0
    assert r["maximum_total_compressed_bytes"] == 18147822
    assert r["maximum_total_decompressed_bytes"] == 268435456
    assert r["maximum_runtime_seconds"] == 120
    assert r["target_bucket"] == "hl-mainnet-node-data"
    assert r["signing_region"] == "ap-northeast-1"
    assert r["object_key"] == KEY
    assert r["object_expected_size_bytes"] == 18147822
    assert r["object_expected_etag"] == '"5a9941a240118a57f77a4c3ee95b8430-3"'
    assert r["object_expected_compressed_sha256"] == OBJECT_SHA

    for key in ("requester_pays_authorized", "get_object_authorized", "object_body_download_authorized", "decompression_authorized", "metadata_lexical_processing_authorized", "aggregate_lexical_retention_authorized"):
        assert r[key] is True, key
    for key in (
        "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
        "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "get_object_attributes_authorized", "get_object_version_authorized",
        "http_redirect_following_authorized", "timezone_parsing_authorized",
        "timezone_inference_authorized", "datetime_conversion_authorized",
        "individual_metadata_value_retention_authorized", "event_array_contents_inspection_authorized",
        "event_pair_count_retention_authorized", "block_number_value_retention_authorized",
        "wallet_address_retention_authorized", "wallet_aggregation_authorized",
        "economic_fill_field_processing_authorized", "individual_fill_time_processing_authorized",
        "raw_object_retention_authorized", "raw_block_event_fill_retention_authorized",
    ):
        assert r[key] is False, key
    assert r["network_requests_executed_by_release_creation"] == 0
    assert r["aws_iam_mutations_executed_by_release_creation"] == 0
    assert r["empirical_result"] is None
    assert all(v is False for v in r["downstream_authorizations"].values())
    assert all(v is False for v in r["trading_authorizations"].values())

    # All predecessors remain immutable, inert snapshots.
    assert p["status"] == "PREREGISTERED_NO_EXECUTION"
    assert all(v is False for v in p["current_runtime_authority"].values())
    assert a["status"] == "OWNER_APPROVED_IMPLEMENTATION_NO_EXECUTION"
    assert a["execution_authorized_by_this_approval"] is False
    assert all(v is False for v in a["current_runtime_authority"].values())
    assert i["status"] == "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE"
    assert i["execution_release_present"] is False
    assert i["canonical_activation_present"] is False
    assert i["single_workflow_dispatch_authorized"] is False
    assert c["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert c["canonical_activation_present"] is False
    assert c["single_workflow_dispatch_authorized"] is False
    assert c["aws_oidc_authorized"] is False
    assert c["get_object_authorized"] is False
    assert c["release_consumed"] is False
    assert c["rerun_authorized"] is False

    text = WORKFLOW.read_text(encoding="utf-8")
    assert "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10B_RUN" in text
    assert text.index("Prove exact single-use R10B release before OIDC") < text.index("Assume existing R10 role with exact one-object session scope")
    assert "CURRENT_RUN_ATTEMPT" in text and "R10B rerun forbidden" in text
    assert f"role-to-assume: {ROLE}" in text
    assert "role-duration-seconds: 900" in text
    assert "retry-max-attempts: 1" in text
    assert '"Action":"s3:GetObject"' in text
    assert f"arn:aws:s3:::hl-mainnet-node-data/{KEY}" in text
    assert OBJECT_SHA in text

    print("R10B_EXECUTION_RELEASE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
