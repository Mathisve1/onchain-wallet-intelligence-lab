from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "research/archive_inventory/r8"
PREREG = R8 / "MODERN_WALLET_INDEX_BRIDGE_R8A_CONTRACT.json"
APPROVAL = R8 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.json"
APPROVAL_TEXT = R8 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.txt"

R8_MERGE = "526f92cf3666c8bb616ecb61b6f9881387c1d7ed"
APPROVAL_SHA = "cb39246e2e5f345b14f87c15ac2c4d6aa993bcc9fbd28076f5f57eff94420e64"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    prereg = load(PREREG)
    approval = load(APPROVAL)
    assert hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA
    assert prereg["pilot_id"] == "HL-ARCHIVE-MODERN-WALLET-INDEX-BRIDGE-R8A-001"
    assert prereg["status"] == "PREREGISTERED_NO_EXECUTION"
    assert approval["approval_id"] == "APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001"
    assert approval["reviewed_commit"] == R8_MERGE
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert approval["approval_scope"] == "IMPLEMENTATION_AND_LATER_SEPARATE_RELEASE_PATH_ONLY"
    assert approval["execution_authorized_by_this_record"] is False
    assert approval["request_authorized_by_this_record"] is False
    target = prereg["exact_future_network_target"]
    for key, expected in {
        "target_bucket": target["bucket"],
        "signing_region": target["signing_region"],
        "object_key": target["key"],
        "object_size_bytes": target["expected_size_bytes"],
        "object_etag": target["expected_etag"],
        "expected_compressed_sha256": target["expected_compressed_sha256"],
        "expected_decompressed_byte_count": target["expected_decompressed_byte_count"],
        "expected_top_level_block_record_count": target["expected_top_level_block_record_count"],
        "maximum_one_time_budget_eur": 0.10,
        "maximum_monthly_budget_eur": 0,
        "maximum_get_object_requests": 1,
        "maximum_requests_per_object": 1,
        "maximum_total_compressed_bytes": 1517603,
        "maximum_total_decompressed_bytes": 16777216,
        "maximum_runtime_seconds": 120,
        "maximum_retries_per_request": 0,
        "maximum_record_bytes": 16777216,
        "maximum_block_records_parsed": 1000000,
        "maximum_event_pairs_parsed": 5000000,
    }.items():
        assert approval[key] == expected, key
    for key in (
        "requester_pays_authorized_for_later_release", "get_object_authorized_for_later_release",
        "if_match_etag_required", "exact_content_length_required", "exact_response_etag_required",
        "exact_compressed_sha256_required", "exact_decompressed_byte_count_required",
        "decompression_authorized_for_later_release", "lz4_frame_stream_only", "strict_utf8_decode",
        "strict_json_duplicate_keys_rejected", "strict_json_nonfinite_constants_rejected",
    ):
        assert approval[key] is True, key
    for key in (
        "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
        "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "http_redirect_following_authorized", "alternate_decompressor_fallback_authorized",
    ):
        assert approval[key] is False, key
    shape = prereg["required_modern_block_shape"]
    assert approval["required_top_level_record_type"] == shape["top_level_record_type"] == "object"
    assert approval["required_block_fields"] == shape["required_fields"]
    assert approval["required_event_pair_type"] == shape["event_pair_required_type"] == "array"
    assert approval["required_event_pair_arity"] == shape["event_pair_required_arity"] == 2
    assert approval["required_event_pair_ordered_element_types"] == shape["event_pair_required_ordered_element_types"] == ["string", "object"]
    assert approval["required_leading_string_regex"] == shape["required_leading_string_pattern"] == "^0x[0-9a-f]{40}$"
    assert approval["minimum_valid_event_pair_count"] == shape["minimum_valid_event_pair_count"] == 1
    future = approval["future_retention_authorizations"]
    assert future["wallet_address"] is True
    assert future["leading_string_value"] is True
    assert future["per_wallet_fill_count"] is True
    assert future["unique_wallet_count"] is True
    assert future["valid_event_pair_count"] is True
    assert future["wallet_address_normalization"] == "LOWERCASE_EXACT_0X40HEX"
    assert future["wallet_index_entry_cap"] == 1000000
    assert future["wallet_index_output_byte_cap"] == 16777216
    assert future["retained_wallet_index_fields_only"] == ["wallet_address", "fill_count"]
    assert all(value is False for value in approval["forbidden_retention_authorizations"].values())
    assert all(value is False for value in approval["downstream_authorizations"].values())
    assert all(value is False for value in approval["trading_authorizations"].values())
    assert all(value is False for value in approval["current_runtime_authority"].values())
    assert approval["s3_requests_executed_under_r8a"] == 0
    assert approval["wallet_addresses_retained_under_r8a"] == 0
    assert approval["empirical_result"] is None
    print("R8A_APPROVAL_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
