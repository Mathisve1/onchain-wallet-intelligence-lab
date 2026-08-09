from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R9 = ROOT / "research/archive_inventory/r9"
CONTRACT = R9 / "MODERN_WALLET_FEATURE_PILOT_R9_CONTRACT.json"
APPROVAL = R9 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001.json"
APPROVAL_TEXT = R9 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001.txt"

PREREG_MERGE = "62ce0009c3c4aad70d2a91f242a690cd26ace355"
APPROVAL_SHA = "1e4642ef2eef660f7971c2632864cf78894340e3408f15d15597e4eb12a04330"
FIELDS = [
    "wallet_address", "fill_count", "first_fill_time", "last_fill_time",
    "distinct_coin_count", "side_a_count", "side_b_count", "crossed_true_count",
    "liquidation_associated_fill_count", "duplicate_tid_count",
    "sum_abs_px_times_sz_notional_proxy", "sum_closed_pnl_fill_statistic",
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    contract = load(CONTRACT)
    approval = load(APPROVAL)
    raw = APPROVAL_TEXT.read_bytes()

    assert hashlib.sha256(raw).hexdigest() == APPROVAL_SHA
    text = raw.decode("utf-8")
    assert text.startswith("APPROVE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001\n")
    assert text.endswith("approval_reason_code=ONE_EXACT_R8A_BOUND_MODERN_TRANSITION_FIXTURE_FOR_PER_WALLET_AGGREGATE_FEATURE_PIPELINE_ONLY\n")
    assert f"reviewed_commit={PREREG_MERGE}\n" in text

    assert contract["status"] == "PREREGISTERED_NO_EXECUTION"
    assert all(v is False for v in contract["current_runtime_authority"].values())
    assert all(v is False for v in contract["downstream_authorizations"].values())
    assert all(v is False for v in contract["trading_authorizations"].values())

    assert approval["approval_id"] == "APPROVE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001"
    assert approval["pilot_id"] == contract["pilot_id"]
    assert approval["status"] == "HUMAN_APPROVAL_RECORDED_IMPLEMENTATION_ALLOWED_NO_EXECUTION"
    assert approval["reviewed_commit"] == PREREG_MERGE
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert approval["implementation_authorized"] is True
    assert approval["execution_authorized_by_this_record"] is False
    assert approval["separate_execution_release_required"] is True
    assert approval["separate_canonical_activation_required"] is True

    target = contract["exact_future_network_target"]
    assert approval["target_bucket"] == target["bucket"] == "hl-mainnet-node-data"
    assert approval["signing_region"] == target["signing_region"] == "ap-northeast-1"
    assert approval["object_key"] == target["key"] == "node_fills_by_block/hourly/20250727/8.lz4"
    assert approval["object_size_bytes"] == target["expected_size_bytes"] == 1517603
    assert approval["object_etag"] == target["expected_etag"] == '"60d4c1277f76651b5f04666bbe8d7594"'
    assert approval["expected_compressed_sha256"] == target["expected_compressed_sha256"]
    assert approval["expected_decompressed_byte_count"] == target["expected_decompressed_byte_count"] == 7380378
    assert approval["expected_top_level_block_record_count"] == target["expected_top_level_block_record_count"] == 4345
    assert approval["expected_valid_event_pair_count"] == target["expected_valid_event_pair_count"] == 17516

    envelope = contract["proposed_request_envelope"]
    for key in (
        "maximum_one_time_budget_eur", "maximum_monthly_budget_eur",
        "maximum_get_object_requests", "maximum_requests_per_object",
        "maximum_total_compressed_bytes", "maximum_total_decompressed_bytes",
        "maximum_runtime_seconds", "maximum_retries_per_request",
    ):
        assert approval[key] == envelope[key], key

    req = approval["request_constraints"]
    assert req["requester_pays_authorized"] is True
    assert req["get_object_authorized_for_future_separate_release"] is True
    for key in (
        "if_match_etag_required", "exact_content_length_required", "exact_response_etag_required",
        "exact_compressed_sha256_required", "exact_decompressed_byte_count_required",
        "exact_top_level_block_record_count_required", "exact_valid_event_pair_count_required",
        "lz4_frame_stream_only",
    ):
        assert req[key] is True, key
    for key in (
        "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
        "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "http_redirect_following_authorized", "alternate_decompressor_fallback_authorized",
    ):
        assert req[key] is False, key

    fixture = approval["fixture_boundary"]
    assert fixture["boundary_fixture_role"] == "SERIALIZER_AND_FEATURE_PIPELINE_FIXTURE_ONLY"
    assert fixture["boundary_fixture_historical_representativeness_authorized"] is False
    assert fixture["canonical_cross_format_history_use_authorized"] is False

    proc = approval["selected_fill_field_processing"]
    assert proc["authorized_for_future_separate_release"] is True
    assert proc["fields"] == ["coin", "side", "time", "px", "sz", "closedPnl", "tid", "crossed", "liquidation"]
    for key in ("coin", "side", "time", "px", "sz", "closedPnl", "tid", "crossed", "liquidation_presence"):
        assert proc[key] is True, key
    for key in ("fee", "feeToken", "dir", "startPosition", "hash", "oid", "cloid"):
        assert proc[key] is False, key
    assert proc["exact_decimal_arithmetic_required"] is True
    assert proc["floating_point_aggregation_authorized"] is False
    assert proc["maximum_numeric_token_characters"] == 128

    assert approval["retained_wallet_feature_fields_only"] == FIELDS
    assert approval["wallet_address_normalization"] == "LOWERCASE_EXACT_0X40HEX"
    assert approval["decimal_output_encoding"] == "CANONICAL_BASE10_STRING_NO_EXPONENT"
    assert approval["wallet_feature_entry_cap"] == 1000000
    assert approval["wallet_feature_output_byte_cap"] == 33554432
    assert all(v is True for v in approval["future_retention_authorizations"].values())
    assert all(v is False for v in approval["forbidden_retention_authorizations"].values())
    assert all(v is False for v in approval["semantic_boundaries"].values())
    assert all(v is False for v in approval["downstream_authorizations"].values())
    assert all(v is False for v in approval["current_runtime_authority"].values())
    assert all(v is False for v in approval["trading_authorizations"].values())
    assert approval["s3_requests_executed"] == 0
    assert approval["wallet_feature_rows_created"] == 0
    assert approval["empirical_result"] is None

    print("R9_APPROVAL_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
