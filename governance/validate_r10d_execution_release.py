from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RELEASE = BASE / "r10d_runtime/R10D_EXECUTION_RELEASE.json"
CANDIDATE = BASE / "r10d_runtime/R10D_EXECUTION_RELEASE_CANDIDATE.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r10d-record-anchored-multihour-feature.yml"
FROZEN = BASE / "r10d_implementation/workflows/hyperliquid-archive-r10d-record-anchored-multihour-feature.yml"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def main() -> int:
    r = load(RELEASE)
    c = load(CANDIDATE)
    assert r["execution_release_id"] == "RELEASE_HL_ARCHIVE_R10D_RECORD_ANCHORED_MULTI_HOUR_FEATURE_001"
    assert r["release_candidate_id"] == c["release_candidate_id"]
    assert r["pilot_id"] == c["pilot_id"] == "HL-ARCHIVE-R10D-RECORD-ANCHORED-MULTI-HOUR-FEATURE-REPAIR-001"
    assert r["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10D_RUN"
    assert r["r10d_preregistration_merge_commit"] == "b8e8d1080be27ff9db3fb639804b4040fdc7c2a0"
    assert r["r10d_approval_merge_commit"] == "95bc1a8c2f929e9266f0ae8c43e7cc2b38b40f11"
    assert r["r10d_implementation_merge_commit"] == "641e36ffdaab96865f475103cc1fc1b389fba613"
    assert r["release_candidate_merge_commit"] == "6baf1da89e4341ea8e411885128816ac4b643981"
    assert r["approval_text_sha256"] == "d8d1466a5da40c4fe32523ba81bfa165e0b88221cc70534f0f0a118870c1275f"
    assert r["workflow_git_blob_sha"] == git_blob_sha(WORKFLOW.read_bytes()) == "8b63ac4f00e05e0533793cd91c6b0d13cad26213"
    assert WORKFLOW.read_bytes() == FROZEN.read_bytes()
    assert r["single_use_window_start_utc"] == "2026-08-10T18:20:00Z"
    start = datetime.fromisoformat(r["single_use_window_start_utc"].replace("Z", "+00:00")).astimezone(timezone.utc)
    assert start.isoformat() == "2026-08-10T18:20:00+00:00"
    assert r["single_workflow_dispatch_authorized"] is True
    assert r["rerun_authorized"] is False
    assert r["release_consumed"] is False
    assert r["maximum_one_time_budget_eur"] == 0.10 and r["maximum_monthly_budget_eur"] == 0
    assert r["maximum_get_object_requests"] == 6 and r["maximum_requests_per_object"] == 1
    assert r["maximum_retries_per_request"] == 0
    assert r["maximum_total_compressed_bytes"] == 120999698
    assert r["maximum_individual_compressed_bytes"] == 21672141
    assert r["maximum_total_decompressed_bytes"] == 1073741824
    assert r["maximum_individual_decompressed_bytes"] == 268435456
    assert r["maximum_runtime_seconds"] == 300
    assert r["request_order"] == "PATH_HOUR_ASCENDING"
    assert r["stop_after_first_failed_or_mismatched_object"] is True
    for key in ("requester_pays_authorized", "get_object_authorized", "object_body_download_authorized", "decompression_authorized", "metadata_prefix_processing_authorized", "selected_fill_field_processing_authorized", "wallet_feature_retention_authorized"):
        assert r[key] is True, key
    for key in ("numeric_tolerance_authorized", "metadata_timezone_parsing_authorized", "metadata_timezone_inference_authorized", "metadata_datetime_conversion_authorized", "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized", "get_object_attributes_authorized", "get_object_version_authorized", "http_redirect_following_authorized"):
        assert r[key] is False, key
    assert r["record_anchored_rule_id"] == "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1"
    assert r["network_requests_executed_by_release_creation"] == 0
    assert r["aws_iam_mutations_executed_by_release_creation"] == 0
    assert r["wallet_feature_rows_created_by_release_creation"] == 0
    assert r["empirical_result"] is None
    assert all(v is False for v in r["semantic_boundaries"].values())
    assert all(v is False for v in r["downstream_authorizations"].values())
    assert all(v is False for v in r["trading_authorizations"].values())
    assert c["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert c["canonical_activation_present"] is False
    assert c["single_workflow_dispatch_authorized"] is False
    assert c["release_consumed"] is False
    print("R10D_EXECUTION_RELEASE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
