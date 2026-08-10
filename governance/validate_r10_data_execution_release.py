from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RELEASE = BASE / "r10_runtime/R10_EXECUTION_RELEASE_CANONICALIZATION.json"
CANDIDATE = BASE / "r10_data_execution/R10_EXECUTION_RELEASE_CANDIDATE.json"
IMPLEMENTATION = BASE / "r10_data_execution/R10_DATA_WORKFLOW_IMPLEMENTATION_CONTRACT.json"
APPROVAL = BASE / "r10_approval/APPROVE_HL_ARCHIVE_POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_001.json"
STS = BASE / "r10_role_preflight/HL-ARCHIVE-R10-DEDICATED-ROLE-STS-PREFLIGHT-001-ATTESTATION.json"
STS_CONSUMPTION = BASE / "r10_runtime/R10_STS_PREFLIGHT_RELEASE_CONSUMPTION.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml"

WORKFLOW_SHA = "4d3b85c01a5f529e16e8516a47e83931521438e978a17fdabdf8397b0f0c275e"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
WINDOW_START = "2026-08-10T10:00:00Z"
EXPECTED = [
    ("2025-07-27T09:00:00Z", "node_fills_by_block/hourly/20250727/9.lz4", 18147822, '"5a9941a240118a57f77a4c3ee95b8430-3"'),
    ("2025-07-27T10:00:00Z", "node_fills_by_block/hourly/20250727/10.lz4", 21349239, '"cb25fba5dc3be80fd8c46dde03144655-3"'),
    ("2025-07-27T11:00:00Z", "node_fills_by_block/hourly/20250727/11.lz4", 17582600, '"758da733bb2d3913d0fdd8088b6fb63d-3"'),
    ("2025-07-27T12:00:00Z", "node_fills_by_block/hourly/20250727/12.lz4", 21672141, '"d6ee46b1bdfad4026e21d4285ed0cbc5-3"'),
    ("2025-07-27T13:00:00Z", "node_fills_by_block/hourly/20250727/13.lz4", 20840630, '"c3c9db0101ff278b5ced13ab278a2b85-3"'),
    ("2025-07-27T14:00:00Z", "node_fills_by_block/hourly/20250727/14.lz4", 21407266, '"3c6ab944be1ed8bd12932eb390267a21-3"'),
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    r = load(RELEASE)
    c = load(CANDIDATE)
    impl = load(IMPLEMENTATION)
    approval = load(APPROVAL)
    sts = load(STS)
    consumption = load(STS_CONSUMPTION)

    assert r["execution_release_id"] == "RELEASE_HL_ARCHIVE_R10_MULTI_HOUR_FEATURE_001"
    assert r["pilot_id"] == "HL-ARCHIVE-POST-BOUNDARY-MULTI-HOUR-FEATURE-R10-001"
    assert r["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10_RUN"
    assert r["release_candidate_merge_commit"] == "9b4862ac8ea5499da81d5e4ab40090b077dd9357"
    assert r["data_workflow_implementation_merge_commit"] == "791c1c289976346d1fcb2bb6ca8196cebf1a50c7"
    assert r["r10_approval_merge_commit"] == "92761986d8dc6bf818eebf7dc0411d24649a27df"
    assert r["r10_implementation_merge_commit"] == "820d0cbbb0f49f800f36025da27a06754d3fc08d"
    assert r["r10_role_attestation_merge_commit"] == "ba7835c8e8ecb1cdc6a1c44c9b679d8f43e7a40e"
    assert r["r10_sts_preflight_evidence_merge_commit"] == "5e54d346653f2153c21a50c3d25c755b596a651b"
    assert r["approval_text_sha256"] == "ec631e7e6d40cb63383afd012a989419f97cd603ff144e4c5dfb90c18ff90882"
    assert r["data_workflow_sha256"] == WORKFLOW_SHA
    assert r["role_arn"] == ROLE_ARN
    assert r["workflow_name"] == "Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10"
    assert r["workflow_path"] == ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml"
    assert r["canonical_activation_present"] is True
    assert r["single_use_window_start_utc"] == WINDOW_START
    start = datetime.fromisoformat(WINDOW_START.replace("Z", "+00:00")).astimezone(timezone.utc)
    assert start.isoformat() == "2026-08-10T10:00:00+00:00"
    assert r["single_workflow_dispatch_authorized"] is True
    assert r["rerun_authorized"] is False
    assert r["release_consumed"] is False

    for key in (
        "aws_oidc_authorized", "requester_pays_authorized", "get_object_authorized",
        "object_body_download_authorized", "decompression_authorized",
        "selected_fill_field_processing_authorized", "wallet_feature_retention_authorized",
    ):
        assert r[key] is True, key
    for key in (
        "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
        "list_object_versions_authorized", "list_all_my_buckets_authorized",
    ):
        assert r[key] is False, key
    assert all(value is False for value in r["downstream_authorizations"].values())
    assert all(value is False for value in r["trading_authorizations"].values())
    assert all(value is False for value in r["semantic_boundaries"].values())
    assert r["empirical_result"] is None

    assert r["maximum_one_time_budget_eur"] == 0.1
    assert r["maximum_monthly_budget_eur"] == 0
    assert r["maximum_get_object_requests"] == 6
    assert r["maximum_requests_per_object"] == 1
    assert r["maximum_total_compressed_bytes"] == 120999698
    assert r["maximum_individual_compressed_bytes"] == 21672141
    assert r["maximum_total_decompressed_bytes"] == 1073741824
    assert r["maximum_individual_decompressed_bytes"] == 268435456
    assert r["maximum_runtime_seconds"] == 300
    assert r["maximum_retries_per_request"] == 0
    assert r["request_order"] == "PATH_HOUR_ASCENDING"
    assert r["stop_after_first_failed_or_mismatched_object"] is True
    assert r["target_bucket"] == "hl-mainnet-node-data"
    assert r["signing_region"] == "ap-northeast-1"
    assert r["window_start_utc"] == "2025-07-27T09:00:00Z"
    assert r["window_end_exclusive_utc"] == "2025-07-27T15:00:00Z"

    objects = r["exact_objects"]
    assert len(objects) == 6
    for row, expected in zip(objects, EXPECTED, strict=True):
        hour, key, size, etag = expected
        assert row == {"path_hour_utc": hour, "key": key, "expected_size_bytes": size, "expected_etag": etag}
    assert sum(row["expected_size_bytes"] for row in objects) == 120999698

    # Earlier snapshots remain immutable and non-self-authorizing.
    assert c["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert c["canonical_activation_present"] is False
    assert c["single_workflow_dispatch_authorized"] is False
    assert c["aws_oidc_authorized"] is False
    assert c["get_object_authorized"] is False
    assert c["wallet_feature_retention_authorized"] is False
    assert impl["status"] == "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE"
    assert impl["single_workflow_dispatch_authorized"] is False
    assert impl["aws_oidc_authorized_now"] is False
    assert impl["get_object_authorized_now"] is False
    assert approval["execution_authorized_by_this_approval"] is False
    assert approval["separate_execution_release_required"] is True
    assert approval["separate_canonical_activation_required"] is True
    assert sts["terminal_status"] == "R10_STS_PREFLIGHT_PASS"
    assert sts["operator_attestation_independently_verified_by_preflight"] is True
    assert sts["s3_http_request_count"] == 0
    assert consumption["status"] == "CONSUMED_SUCCESS"
    assert consumption["preflight_release_consumed"] is True
    assert consumption["rerun_authorized"] is False
    assert consumption["s3_requests_executed"] == 0
    assert hashlib.sha256(WORKFLOW.read_bytes()).hexdigest() == WORKFLOW_SHA

    print("R10_DATA_EXECUTION_RELEASE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
