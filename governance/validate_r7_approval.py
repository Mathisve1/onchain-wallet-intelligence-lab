from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R7 = ROOT / "research/archive_inventory/r7"
CONTRACT = R7 / "WALLET_INDEX_RECONSTRUCTION_R7_CONTRACT.json"
APPROVAL_TEXT = R7 / "approvals/APPROVE_HL_ARCHIVE_WALLET_INDEX_RECONSTRUCTION_R7_001.txt"
APPROVAL = R7 / "approvals/APPROVE_HL_ARCHIVE_WALLET_INDEX_RECONSTRUCTION_R7_001.json"
STATUS = R7 / "APPROVAL_STATUS.md"

PREREG_MERGE = "795281b2992466785ba48314d59feb61ac0b3aef"
APPROVAL_SHA = "43f32634859eb39e4b1e464276f9721ed4ef8bcc30161f1f301f82e0312042a6"
OBJECT_KEY = "node_fills/hourly/20250727/8.lz4"
OBJECT_ETAG = '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"'
OBJECT_SHA = "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    contract = load(CONTRACT)
    approval = load(APPROVAL)
    status = STATUS.read_text(encoding="utf-8")

    assert hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA
    assert approval["approval_id"] == "APPROVE_HL_ARCHIVE_WALLET_INDEX_RECONSTRUCTION_R7_001"
    assert approval["reviewed_commit"] == PREREG_MERGE
    assert approval["approval_received_at_utc"] == "2026-08-09T18:24:00Z"
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert approval["approval_scope"] == "IMPLEMENTATION_AND_LATER_SEPARATE_RELEASE_PATH_ONLY"
    assert approval["execution_authorized_by_this_record"] is False
    assert approval["request_authorized_by_this_record"] is False
    assert approval["aws_role_mutation_authorized"] is False

    assert contract["pilot_id"] == "HL-ARCHIVE-WALLET-INDEX-RECONSTRUCTION-R7-001"
    assert contract["status"] == "PREREGISTERED_NO_EXECUTION"
    assert contract["parent_r6a_evidence_commit"] == "6b7dcd85e6d0f82b63ab8c4dd50d56ef8dc72a57"

    target = contract["exact_future_network_target"]
    assert approval["target_bucket"] == target["bucket"] == "hl-mainnet-node-data"
    assert approval["signing_region"] == target["signing_region"] == "ap-northeast-1"
    assert approval["object_key"] == target["key"] == OBJECT_KEY
    assert approval["object_size_bytes"] == target["expected_size_bytes"] == 12726384
    assert approval["object_etag"] == target["expected_etag"] == OBJECT_ETAG
    assert approval["expected_compressed_sha256"] == target["expected_compressed_sha256"] == OBJECT_SHA
    assert approval["expected_decompressed_byte_count"] == target["expected_decompressed_byte_count"] == 62169139
    assert approval["expected_nonempty_record_count"] == target["expected_nonempty_record_count"] == 162815
    assert approval["required_top_level_record_type"] == target["required_top_level_record_type"] == "array"
    assert approval["required_array_arity"] == target["required_array_arity"] == 2
    assert approval["required_ordered_element_types"] == target["required_ordered_element_types"] == ["string", "object"]
    assert approval["required_leading_string_regex"] == target["required_leading_string_pattern"] == "^0x[0-9a-f]{40}$"

    envelope = contract["proposed_future_request_envelope"]
    for key, expected in {
        "maximum_one_time_budget_eur": 0.10,
        "maximum_monthly_budget_eur": 0,
        "maximum_get_object_requests": 1,
        "maximum_requests_per_object": 1,
        "maximum_total_compressed_bytes": 12726384,
        "maximum_total_decompressed_bytes": 134217728,
        "maximum_runtime_seconds": 120,
        "maximum_retries_per_request": 0,
        "maximum_record_bytes": 16777216,
        "maximum_records_parsed": 5000000,
    }.items():
        assert approval[key] == envelope[key] == expected, key
    assert approval["requester_pays_authorized_for_later_release"] is True
    assert approval["get_object_authorized_for_later_release"] is True
    assert approval["decompression_authorized_for_later_release"] is True
    assert envelope["requester_pays_required"] is True
    for key in (
        "if_match_etag_required",
        "exact_content_length_required",
        "exact_compressed_sha256_required",
        "exact_decompressed_byte_count_required",
        "lz4_frame_stream_only",
        "strict_utf8_decode",
        "strict_json_duplicate_keys_rejected",
        "strict_json_nonfinite_constants_rejected",
    ):
        assert approval[key] is True and envelope[key] is True, key
    for key in (
        "head_object_authorized",
        "range_get_authorized",
        "list_objects_v2_authorized",
        "list_object_versions_authorized",
        "list_all_my_buckets_authorized",
        "http_redirect_following_authorized",
        "alternate_decompressor_fallback_authorized",
    ):
        assert approval[key] is False and envelope[key] is False, key

    proposed_retention = contract["proposed_future_retention_boundary"]
    future = approval["future_retention_authorizations"]
    assert future["wallet_address"] is proposed_retention["wallet_address_retention_authorized"] is True
    assert future["leading_string_value"] is proposed_retention["leading_string_value_retention_authorized"] is True
    assert future["per_wallet_fill_count"] is proposed_retention["per_wallet_fill_count_retention_authorized"] is True
    assert future["unique_wallet_count"] is proposed_retention["unique_wallet_count_retention_authorized"] is True
    assert future["wallet_address_normalization"] == proposed_retention["normalization"] == "LOWERCASE_EXACT_0X40HEX"
    assert future["wallet_index_entry_cap"] == proposed_retention["wallet_index_entry_cap"] == 162815
    assert future["wallet_index_output_byte_cap"] == proposed_retention["wallet_index_output_byte_cap"] == 16777216
    assert future["retained_wallet_index_fields_only"] == proposed_retention["retained_wallet_index_fields_only"] == ["wallet_address", "fill_count"]

    forbidden = approval["forbidden_retention_authorizations"]
    assert all(value is False for value in forbidden.values())
    for key in (
        "raw_compressed_object_retention_authorized",
        "raw_decompressed_payload_retention_authorized",
        "record_payload_retention_authorized",
        "fill_object_retention_authorized",
        "payload_values_in_evidence_authorized",
        "coin_value_retention_authorized",
        "price_value_retention_authorized",
        "size_value_retention_authorized",
        "side_value_retention_authorized",
        "time_value_retention_authorized",
        "closed_pnl_value_retention_authorized",
        "fee_value_retention_authorized",
        "transaction_hash_retention_authorized",
        "order_id_retention_authorized",
        "trade_id_retention_authorized",
        "client_order_id_retention_authorized",
    ):
        assert proposed_retention[key] is False, key

    assert all(value is False for value in approval["downstream_authorizations"].values())
    assert all(value is False for value in approval["trading_authorizations"].values())
    assert all(value is False for value in approval["current_runtime_authority"].values())
    assert approval["approval_reason_code"] == "ONE_EXACT_LEGACY_OBJECT_FOR_MINIMAL_ADDRESS_PLUS_FILL_COUNT_WALLET_INDEX_ONLY"
    assert approval["s3_requests_executed_under_r7"] == 0
    assert approval["compressed_bytes_downloaded_under_r7"] == 0
    assert approval["decompressed_bytes_processed_under_r7"] == 0
    assert approval["wallet_addresses_retained_under_r7"] == 0
    assert approval["empirical_result"] is None

    assert all(value is False for value in contract["current_runtime_authority"].values())
    assert all(value is False for value in contract["downstream_authorizations"].values())
    assert all(value is False for value in contract["trading_authorizations"].values())

    assert "HUMAN_APPROVED_IMPLEMENTATION_LANE_ONLY_NO_RUNTIME" in status
    assert PREREG_MERGE in status
    assert APPROVAL_SHA in status

    print("R7_APPROVAL_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
