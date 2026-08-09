from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R7 = ROOT / "research/archive_inventory/r7"
CONTRACT = R7 / "WALLET_INDEX_RECONSTRUCTION_R7_CONTRACT.json"
DERIVATION = R7 / "R6A_DERIVATION.json"
APPROVAL_TEMPLATE = R7 / "HUMAN_APPROVAL_TEMPLATE.md"
PARENT_ATTESTATION = ROOT / "research/archive_inventory/r6a/evidence/HL-ARCHIVE-LEGACY-USER-KEY-LEXICAL-R6A-001-ATTESTATION.json"
PARENT_CONSUMPTION = ROOT / "research/archive_inventory/r6a/R6A_EXECUTION_RELEASE_002_CONSUMPTION.json"

PARENT_COMMIT = "6b7dcd85e6d0f82b63ab8c4dd50d56ef8dc72a57"
OBJECT_KEY = "node_fills/hourly/20250727/8.lz4"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    contract = load(CONTRACT)
    derivation = load(DERIVATION)
    parent = load(PARENT_ATTESTATION)
    consumption = load(PARENT_CONSUMPTION)
    approval_template = APPROVAL_TEMPLATE.read_text(encoding="utf-8")

    assert contract["pilot_id"] == "HL-ARCHIVE-WALLET-INDEX-RECONSTRUCTION-R7-001"
    assert contract["status"] == "PREREGISTERED_NO_EXECUTION"
    assert contract["parent_r6a_evidence_commit"] == PARENT_COMMIT
    assert contract["parent_r6a_run_id"] == 31328268134
    assert contract["parent_r6a_terminal_result"] == "R6A_LEXICAL_CONFIRMATION_COMPLETE"
    semantic = contract["working_semantic_contract"]
    assert semantic["leading_string_label"] == "HYPERLIQUID_USER_ADDRESS"
    assert semantic["status"] == "HIGH_CONFIDENCE_CONVERGENT_STATIC_AND_LEXICAL_EVIDENCE_NOT_DIRECT_SERIALIZER_PROOF"
    assert semantic["direct_unpublished_serializer_proof_claimed"] is False

    target = contract["exact_future_network_target"]
    assert target["bucket"] == "hl-mainnet-node-data"
    assert target["signing_region"] == "ap-northeast-1"
    assert target["key"] == OBJECT_KEY
    assert target["expected_size_bytes"] == 12726384
    assert target["expected_etag"] == '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"'
    assert target["expected_compressed_sha256"] == "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622"
    assert target["expected_decompressed_byte_count"] == 62169139
    assert target["expected_nonempty_record_count"] == 162815
    assert target["required_top_level_record_type"] == "array"
    assert target["required_array_arity"] == 2
    assert target["required_ordered_element_types"] == ["string", "object"]
    assert target["required_leading_string_pattern"] == "^0x[0-9a-f]{40}$"

    envelope = contract["proposed_future_request_envelope"]
    assert envelope["maximum_one_time_budget_eur"] == 0.10
    assert envelope["maximum_monthly_budget_eur"] == 0
    assert envelope["maximum_get_object_requests"] == 1
    assert envelope["maximum_requests_per_object"] == 1
    assert envelope["maximum_total_compressed_bytes"] == 12726384
    assert envelope["maximum_total_decompressed_bytes"] == 134217728
    assert envelope["maximum_runtime_seconds"] == 120
    assert envelope["maximum_retries_per_request"] == 0
    for key in (
        "requester_pays_required",
        "if_match_etag_required",
        "exact_content_length_required",
        "exact_response_etag_required",
        "exact_compressed_sha256_required",
        "exact_decompressed_byte_count_required",
        "lz4_frame_stream_only",
        "strict_utf8_decode",
        "strict_json_duplicate_keys_rejected",
        "strict_json_nonfinite_constants_rejected",
    ):
        assert envelope[key] is True, key
    for key in (
        "http_redirect_following_authorized",
        "head_object_authorized",
        "range_get_authorized",
        "list_objects_v2_authorized",
        "list_object_versions_authorized",
        "list_all_my_buckets_authorized",
        "alternate_decompressor_fallback_authorized",
    ):
        assert envelope[key] is False, key

    retention = contract["proposed_future_retention_boundary"]
    assert retention["wallet_address_retention_authorized"] is True
    assert retention["leading_string_value_retention_authorized"] is True
    assert retention["normalization"] == "LOWERCASE_EXACT_0X40HEX"
    assert retention["per_wallet_fill_count_retention_authorized"] is True
    assert retention["unique_wallet_count_retention_authorized"] is True
    assert retention["wallet_index_entry_cap"] == 162815
    assert retention["wallet_index_output_byte_cap"] == 16777216
    assert retention["retained_wallet_index_fields_only"] == ["wallet_address", "fill_count"]
    for key, value in retention.items():
        if key.endswith("_retention_authorized") and key not in {
            "wallet_address_retention_authorized",
            "leading_string_value_retention_authorized",
            "per_wallet_fill_count_retention_authorized",
            "unique_wallet_count_retention_authorized",
        }:
            assert value is False, key
    for key in (
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
        "distinct_payload_value_sets_authorized",
    ):
        assert retention[key] is False, key

    deterministic = contract["deterministic_output_contract"]
    assert deterministic["format"] == "UTF8_NDJSON"
    assert deterministic["one_row_per_unique_wallet"] is True
    assert deterministic["wallet_address_unique"] is True
    assert deterministic["wallet_address_sort_order"] == "LEXICOGRAPHIC_ASCENDING"
    assert deterministic["fill_count_positive_integer"] is True
    assert deterministic["sum_fill_count_required"] == 162815
    assert deterministic["duplicate_wallet_rows_authorized"] is False

    assert contract["allowed_research_results"] == [
        "WALLET_INDEX_RECONSTRUCTION_COMPLETE",
        "WALLET_INDEX_RECONSTRUCTION_UNRESOLVED",
    ]
    assert all(value is False for value in contract["current_runtime_authority"].values())
    assert all(value is False for value in contract["downstream_authorizations"].values())
    assert all(value is False for value in contract["trading_authorizations"].values())
    assert contract["human_approval_required_before_implementation"] is True
    assert contract["implementation_required_before_execution_release"] is True
    assert contract["separate_execution_release_required"] is True
    assert contract["network_requests_executed_by_this_preregistration"] == 0
    assert contract["wallet_addresses_retained_by_this_preregistration"] == 0
    assert contract["empirical_result"] is None

    assert derivation["parent_commit"] == PARENT_COMMIT
    assert derivation["parent_run_id"] == 31328268134
    assert derivation["facts_carried_forward"]["leading_string_lowercase_0x40hex_count"] == 162815
    assert derivation["facts_carried_forward"]["working_semantic_label"] == "HYPERLIQUID_USER_ADDRESS"
    assert derivation["new_authority_required"]["wallet_address_retention"] is True
    assert derivation["new_authority_required"]["wallet_index_reconstruction"] is True
    assert all(value is False for value in derivation["authority_explicitly_not_requested"].values())

    assert parent["run_id"] == 31328268134
    assert parent["research_conclusion"] == "ALL_LEADING_STRINGS_MATCH_HYPERLIQUID_ADDRESS_SHAPE"
    assert parent["combined_r6_r6a_interpretation"]["semantic_label"] == "HYPERLIQUID_USER_ADDRESS"
    assert consumption["release_consumed"] is True
    assert consumption["remaining_approved_get_object_budget"] == 0
    assert consumption["future_r6a_dispatch_authorized"] is False

    for required in (
        "APPROVE_HL_ARCHIVE_WALLET_INDEX_RECONSTRUCTION_R7_001",
        "reviewed_commit=<CANONICAL_R7_PREREGISTRATION_MERGE_COMMIT>",
        "wallet_address_retention_authorized=true",
        "retained_wallet_index_fields_only=wallet_address,fill_count",
        "entity_clustering_authorized=false",
        "pnl_or_alpha_analysis_authorized=false",
        "live_authorized=false",
    ):
        assert required in approval_template

    implementation = R7 / "R7_IMPLEMENTATION_CONTRACT.json"
    if not implementation.exists():
        for path in (
            R7 / "collector.py",
            ROOT / ".github/workflows/hyperliquid-archive-wallet-index-r7.yml",
        ):
            assert not path.exists(), path

    print("R7_PREREGISTRATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
