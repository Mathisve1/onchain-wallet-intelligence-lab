from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R9 = ROOT / "research/archive_inventory/r9"
CONTRACT = R9 / "MODERN_WALLET_FEATURE_PILOT_R9_CONTRACT.json"
DERIVATION = R9 / "R8B_DERIVATION.json"
TEMPLATE = R9 / "HUMAN_APPROVAL_TEMPLATE_R9.md"
STATUS = R9 / "APPROVAL_STATUS.md"
APPROVAL = R9 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001.json"
IMPLEMENTATION = R9 / "R9_IMPLEMENTATION_CONTRACT.json"
R8B = ROOT / "research/archive_inventory/r8b/CUTOVER_FORENSICS_R8B_CONTRACT.json"
R8A_RESULT = ROOT / "research/archive_inventory/r8/evidence/run-31333421763/r8a-result.json"

EXPECTED_FIELDS = [
    "wallet_address",
    "fill_count",
    "first_fill_time",
    "last_fill_time",
    "distinct_coin_count",
    "side_a_count",
    "side_b_count",
    "crossed_true_count",
    "liquidation_associated_fill_count",
    "duplicate_tid_count",
    "sum_abs_px_times_sz_notional_proxy",
    "sum_closed_pnl_fill_statistic",
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    c = load(CONTRACT)
    d = load(DERIVATION)
    r8b = load(R8B)
    r8a = load(R8A_RESULT)
    template = TEMPLATE.read_text(encoding="utf-8")
    status = STATUS.read_text(encoding="utf-8")

    assert c["pilot_id"] == "HL-ARCHIVE-MODERN-WALLET-FEATURE-PILOT-R9-001"
    assert c["status"] == "PREREGISTERED_NO_EXECUTION"
    assert c["parent_r8_design_commit"] == "526f92cf3666c8bb616ecb61b6f9881387c1d7ed"
    assert c["parent_r8b_cutover_commit"] == "b77debdf57cbe07bfa190fd40946f2fe897e3a33"
    assert c["parent_r8a_evidence_commit"] == "04c23127a553c53e9c3c9b80dabb4a9b7e61de61"
    assert c["parent_r8a_run_id"] == 31333421763

    fixture = c["fixture_role"]
    assert fixture["role"] == "SERIALIZER_AND_FEATURE_PIPELINE_FIXTURE_ONLY"
    assert fixture["transition_censored_by_r8b"] is True
    assert fixture["canonical_cross_format_history_eligible"] is False
    assert fixture["historical_representativeness_inferred"] is False
    assert fixture["population_performance_inferred"] is False
    assert r8b["canonical_cross_format_rule"]["rule_id"] == "CUTOVER_CENSOR_HOUR_20250727_08"
    assert r8b["canonical_cross_format_rule"]["include_modern_boundary_hour"] is False
    assert d["boundary_fixture_canonical_history_eligible"] is False
    assert d["new_network_authority_created"] is False
    assert d["new_retention_authority_created"] is False
    assert d["new_trading_authority_created"] is False

    target = c["exact_future_network_target"]
    summary = r8a["wallet_index_summary"]
    assert target["bucket"] == "hl-mainnet-node-data"
    assert target["signing_region"] == "ap-northeast-1"
    assert target["key"] == r8a["object_key"] == "node_fills_by_block/hourly/20250727/8.lz4"
    assert target["expected_size_bytes"] == r8a["compressed_bytes"] == 1517603
    assert target["expected_etag"] == r8a["expected_etag"] == '"60d4c1277f76651b5f04666bbe8d7594"'
    assert target["expected_compressed_sha256"] == r8a["compressed_sha256"] == "928e1cd6bd7d69ad7243c263bacee48e53e4762ae9e99ef75f45007f6c0e6105"
    assert target["expected_decompressed_byte_count"] == r8a["decompressed_bytes"] == 7380378
    assert target["expected_top_level_block_record_count"] == summary["top_level_block_record_count"] == 4345
    assert target["expected_valid_event_pair_count"] == summary["valid_event_pair_count"] == 17516

    envelope = c["proposed_request_envelope"]
    assert envelope["maximum_one_time_budget_eur"] == 0.10
    assert envelope["maximum_monthly_budget_eur"] == 0
    assert envelope["maximum_get_object_requests"] == 1
    assert envelope["maximum_requests_per_object"] == 1
    assert envelope["maximum_total_compressed_bytes"] == 1517603
    assert envelope["maximum_total_decompressed_bytes"] == 16777216
    assert envelope["maximum_runtime_seconds"] == 120
    assert envelope["maximum_retries_per_request"] == 0
    for key in (
        "requester_pays_required",
        "if_match_etag_required",
        "exact_content_length_required",
        "exact_response_etag_required",
        "exact_compressed_sha256_required",
        "exact_decompressed_byte_count_required",
        "exact_top_level_block_record_count_required",
        "exact_valid_event_pair_count_required",
    ):
        assert envelope[key] is True, key
    for key in (
        "http_redirect_following_authorized",
        "head_object_authorized",
        "range_get_authorized",
        "list_objects_v2_authorized",
        "list_object_versions_authorized",
        "list_all_my_buckets_authorized",
    ):
        assert envelope[key] is False, key

    shape = c["required_input_shape"]
    assert shape["strict_utf8_decode"] is True
    assert shape["strict_json_duplicate_keys_rejected"] is True
    assert shape["strict_json_nonfinite_constants_rejected"] is True
    assert shape["top_level_record_type"] == "object"
    assert shape["required_block_fields"] == {"local_time":"string","block_time":"string","block_number":"integer","events":"array"}
    assert shape["event_pair_type"] == "array"
    assert shape["event_pair_arity"] == 2
    assert shape["event_pair_ordered_element_types"] == ["string", "object"]
    assert shape["leading_string_regex"] == "^0x[0-9a-f]{40}$"

    assert c["selected_fill_fields_for_transient_processing"] == [
        "coin", "side", "time", "px", "sz", "closedPnl", "tid", "crossed", "liquidation"
    ]
    rules = c["selected_field_processing_rules"]
    assert rules["maximum_numeric_token_characters"] == 128
    assert rules["exact_decimal_arithmetic_required"] is True
    assert rules["floating_point_aggregation_authorized"] is False

    out = c["proposed_per_wallet_output"]
    assert out["format"] == "UTF8_NDJSON"
    assert out["one_row_per_unique_wallet"] is True
    assert out["sort_order"] == "WALLET_ADDRESS_LEXICOGRAPHIC_ASCENDING"
    assert out["fields_only"] == EXPECTED_FIELDS
    assert out["decimal_output_encoding"] == "CANONICAL_BASE10_STRING_NO_EXPONENT"
    assert out["wallet_feature_entry_cap"] == 1000000
    assert out["wallet_feature_output_byte_cap"] == 33554432
    assert out["fill_count_conservation_required"] is True
    assert out["side_count_conservation_required"] is True
    assert out["first_time_lte_last_time_required"] is True
    assert out["nonnegative_notional_proxy_required"] is True

    semantic = c["semantic_boundaries"]
    assert semantic["sum_closed_pnl_fill_statistic_is_exact_account_return"] is False
    assert semantic["sum_closed_pnl_fill_statistic_is_wallet_ranking_score"] is False
    assert semantic["sum_abs_px_times_sz_notional_proxy_is_copyable_notional"] is False
    assert semantic["boundary_fixture_is_historically_representative"] is False

    assert all(value is False for value in c["raw_or_disallowed_retention"].values())
    assert all(value is False for value in c["downstream_authorizations"].values())
    assert all(value is False for value in c["current_runtime_authority"].values())
    assert all(value is False for value in c["trading_authorizations"].values())
    assert c["human_approval_required_before_implementation"] is True
    assert c["implementation_required_before_execution_release"] is True
    assert c["separate_execution_release_required"] is True
    assert c["separate_canonical_activation_required"] is True
    assert c["network_requests_executed_by_r9_preregistration"] == 0
    assert c["wallet_feature_rows_created_by_r9_preregistration"] == 0
    assert c["empirical_result"] is None

    assert "APPROVE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001" in template
    assert "reviewed_commit=<CANONICAL_R9_PREREGISTRATION_MERGE_COMMIT>" in template
    assert "boundary_fixture_role=SERIALIZER_AND_FEATURE_PIPELINE_FIXTURE_ONLY" in template
    assert "selected_fill_fields_processed=coin,side,time,px,sz,closedPnl,tid,crossed,liquidation" in template
    assert "sum_closed_pnl_is_exact_account_return=false" in template
    assert "wallet_ranking_authorized=false" in template
    assert "historical_multi_hour_ingestion_authorized=false" in template
    assert "approval_reason_code=ONE_EXACT_R8A_BOUND_MODERN_TRANSITION_FIXTURE_FOR_PER_WALLET_AGGREGATE_FEATURE_PIPELINE_ONLY" in template

    if APPROVAL.exists():
        approval = load(APPROVAL)
        assert approval["reviewed_commit"] == "62ce0009c3c4aad70d2a91f242a690cd26ace355"
        assert approval["implementation_authorized"] is True
        assert approval["execution_authorized_by_this_record"] is False
        assert all(value is False for value in approval["current_runtime_authority"].values())
        assert all(value is False for value in approval["downstream_authorizations"].values())
        assert all(value is False for value in approval["trading_authorizations"].values())
        assert "HUMAN_APPROVAL_RECORDED_IMPLEMENTATION_ALLOWED_NO_EXECUTION" in status
    else:
        assert "AWAITING_SEPARATE_HUMAN_APPROVAL" in status

    collector = R9 / "collector.py"
    workflow = ROOT / ".github/workflows/hyperliquid-archive-modern-wallet-feature-r9.yml"
    if IMPLEMENTATION.exists():
        impl = load(IMPLEMENTATION)
        assert APPROVAL.exists()
        assert impl["approval_merge_commit"] == "332aa535b0de19a18befb8529450ae88acf35762"
        assert impl["status"] == "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION"
        assert all(value is False for value in impl["current_runtime_authority"].values())
        assert all(value is False for value in impl["downstream_authorizations"].values())
        assert all(value is False for value in impl["trading_authorizations"].values())
        assert impl["s3_requests_executed"] == 0
        assert impl["wallet_feature_rows_created"] == 0
        assert impl["empirical_result"] is None
        assert collector.is_file()
        assert workflow.is_file()
    else:
        assert not collector.exists()
        assert not workflow.exists()

    release_path = R9 / "R9_EXECUTION_RELEASE.json"
    if release_path.exists():
        release = load(release_path)
        assert release["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
        assert release["execution_ready"] is False
        assert release["single_workflow_dispatch_authorized"] is False
        assert release["rerun_authorized"] is False
        assert release["s3_requests_executed"] == 0
        assert release["wallet_feature_rows_created"] == 0
        assert release["empirical_result"] is None
    activation_path = R9 / "R9_EXECUTION_RELEASE_CANONICALIZATION.json"
    if activation_path.exists():
        activation = load(activation_path)
        assert release_path.exists()
        assert activation["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R9_RUN"
        assert activation["single_workflow_dispatch_authorized"] is True
        assert activation["rerun_authorized"] is False
        assert activation["release_consumed"] is False
        assert activation["s3_requests_executed"] == 0
        assert activation["wallet_feature_rows_created"] == 0
        assert activation["empirical_result"] is None

    print("R9_PREREGISTRATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
