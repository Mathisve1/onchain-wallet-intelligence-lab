from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "research/archive_inventory/r8"
DESIGN = R8 / "PERFORMANCE_COPYABILITY_DATA_DESIGN_R8_CONTRACT.json"
R8A = R8 / "MODERN_WALLET_INDEX_BRIDGE_R8A_CONTRACT.json"
SOURCES = R8 / "OFFICIAL_SOURCE_EVIDENCE.json"
DERIVATION = R8 / "R7_DERIVATION.json"
REPORT = R8 / "DESIGN_REPORT.md"
TEMPLATE = R8 / "HUMAN_APPROVAL_TEMPLATE_R8A.md"
STATUS = R8 / "APPROVAL_STATUS.md"

PARENT_R7 = "7802d741f193671e50356c6001dcae149e0fc88a"
MODERN_KEY = "node_fills_by_block/hourly/20250727/8.lz4"
MODERN_SHA = "928e1cd6bd7d69ad7243c263bacee48e53e4762ae9e99ef75f45007f6c0e6105"
MODERN_ETAG = '"60d4c1277f76651b5f04666bbe8d7594"'


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    design = load(DESIGN)
    r8a = load(R8A)
    sources = load(SOURCES)
    derivation = load(DERIVATION)
    report = REPORT.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    status = STATUS.read_text(encoding="utf-8")

    assert design["study_id"] == "HL-WALLET-PERFORMANCE-COPYABILITY-DATA-DESIGN-R8-001"
    assert design["status"] == "STATIC_DESIGN_PREREGISTERED_NO_EXECUTION"
    assert design["parent_r7_evidence_commit"] == PARENT_R7
    assert design["parent_r7_run_id"] == 31330248235
    assert design["parent_r7_terminal_result"] == "WALLET_INDEX_RECONSTRUCTION_COMPLETE"
    assert design["parent_r7_unique_wallet_count"] == 4637
    assert design["parent_r7_sum_fill_count"] == 162815

    fields = design["minimum_archive_candidate_field_set"]
    flat_fields = {value for values in fields.values() for value in values}
    for required in (
        "wallet_address", "time", "coin", "side", "dir", "px", "sz", "startPosition",
        "closedPnl", "fee", "feeToken", "tid", "crossed", "liquidation_presence",
    ):
        assert required in flat_fields, required
    for excluded in ("hash", "oid", "cloid", "builder", "builderFee"):
        assert excluded in fields["explicitly_not_required_for_initial_candidate_screen"]

    semantics = design["semantic_boundaries"]
    assert semantics["closed_pnl_sum_is_exact_account_return"] is False
    assert semantics["closed_pnl_may_be_used_as_fill_derived_statistic"] is True
    assert semantics["fee_must_not_be_blindly_subtracted_from_closed_pnl_without_formula_proof"] is True
    assert semantics["crossed_maker_taker_semantics_proven"] is False
    assert semantics["one_wallet_address_equals_one_human_or_economic_entity"] is False
    assert semantics["portfolio_graphs_are_precise_accounting"] is False

    pipeline = design["proposed_research_pipeline"]
    assert [row["stage"] for row in pipeline] == [
        "A_GLOBAL_ARCHIVE_SCREEN",
        "B_CANDIDATE_REDUCTION",
        "C_SHORTLIST_PUBLIC_API_ENRICHMENT",
        "D_COPYABILITY_EXECUTION_RESEARCH",
    ]
    assert pipeline[0]["per_wallet_api_calls"] is False
    assert all(row.get("ranking_authorized_by_r8", False) is False for row in pipeline)
    assert design["api_scaling_constraint"]["per_address_user_fills_is_not_primary_population_scan"] is True
    assert design["api_scaling_constraint"]["shortlist_first_required"] is True
    assert design["first_empirical_scaling_prerequisite"]["gate_id"] == "HL-ARCHIVE-MODERN-WALLET-INDEX-BRIDGE-R8A-001"
    assert design["first_empirical_scaling_prerequisite"]["network_authorized_by_r8"] is False
    assert all(value is False for value in design["current_authority"].values())
    assert all(value is False for value in design["trading_authorizations"].values())
    assert design["network_requests_executed_by_r8"] == 0
    assert design["wallets_ranked_by_r8"] == 0
    assert design["empirical_result"] is None

    assert derivation["parent_commit"] == PARENT_R7
    assert derivation["parent_run_id"] == 31330248235
    facts = derivation["facts_carried_forward"]
    assert facts["unique_wallet_count"] == 4637
    assert facts["sum_fill_count"] == 162815
    assert facts["wallet_index_fields_only"] == ["wallet_address", "fill_count"]
    assert facts["r7_release_consumed"] is True
    assert facts["r7_remaining_get_object_budget"] == 0
    assert all(value is False for value in derivation["facts_not_carried_forward_as_proven"].values())
    assert derivation["r8_static_design_uses_concrete_wallet_rows"] is False
    assert derivation["r8_static_design_ranks_parent_wallets"] is False
    assert derivation["r8_static_design_queries_parent_wallets"] is False

    assert sources["source_policy"] == "PRIMARY_OFFICIAL_SOURCES_ONLY"
    source_ids = {row["source_id"] for row in sources["sources"]}
    for source_id in (
        "HL-NODE-README", "HL-DOC-HISTORICAL-DATA", "HL-DOC-INFO-ENDPOINT",
        "HL-DOC-RATE-LIMITS", "HL-DOC-PORTFOLIO-GRAPHS", "HL-DOC-ENTRY-PRICE-PNL",
        "HL-DOC-NOTATION", "HL-DOC-MAX-DRAWDOWN",
    ):
        assert source_id in source_ids
    assert len(sources["inferences_explicitly_not_direct_source_claims"]) >= 4

    assert r8a["pilot_id"] == "HL-ARCHIVE-MODERN-WALLET-INDEX-BRIDGE-R8A-001"
    assert r8a["status"] == "PREREGISTERED_NO_EXECUTION"
    assert r8a["parent_r7_evidence_commit"] == PARENT_R7
    assert r8a["parent_r4_evidence_commit"] == "fe06874aeeb958d375a27100378f89bd25b4741b"
    assert r8a["parent_r4_run_id"] == 31313913525
    target = r8a["exact_future_network_target"]
    assert target["bucket"] == "hl-mainnet-node-data"
    assert target["signing_region"] == "ap-northeast-1"
    assert target["key"] == MODERN_KEY
    assert target["expected_size_bytes"] == 1517603
    assert target["expected_etag"] == MODERN_ETAG
    assert target["expected_compressed_sha256"] == MODERN_SHA
    assert target["expected_decompressed_byte_count"] == 7380378
    assert target["expected_top_level_block_record_count"] == 4345

    envelope = r8a["proposed_future_request_envelope"]
    for key, expected in {
        "maximum_one_time_budget_eur": 0.10,
        "maximum_monthly_budget_eur": 0,
        "maximum_get_object_requests": 1,
        "maximum_requests_per_object": 1,
        "maximum_total_compressed_bytes": 1517603,
        "maximum_total_decompressed_bytes": 16777216,
        "maximum_runtime_seconds": 120,
        "maximum_retries_per_request": 0,
    }.items():
        assert envelope[key] == expected, key
    for key in (
        "requester_pays_required", "if_match_etag_required", "exact_content_length_required",
        "exact_response_etag_required", "exact_compressed_sha256_required",
        "exact_decompressed_byte_count_required", "lz4_frame_stream_only", "strict_utf8_decode",
        "strict_json_duplicate_keys_rejected", "strict_json_nonfinite_constants_rejected",
    ):
        assert envelope[key] is True, key
    for key in (
        "http_redirect_following_authorized", "head_object_authorized", "range_get_authorized",
        "list_objects_v2_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "alternate_decompressor_fallback_authorized",
    ):
        assert envelope[key] is False, key

    shape = r8a["required_modern_block_shape"]
    assert shape["top_level_record_type"] == "object"
    assert shape["required_fields"] == {
        "local_time": "string",
        "block_time": "string",
        "block_number": "integer",
        "events": "array",
    }
    assert shape["expected_top_level_block_record_count"] == 4345
    assert shape["event_pair_required_type"] == "array"
    assert shape["event_pair_required_arity"] == 2
    assert shape["event_pair_required_ordered_element_types"] == ["string", "object"]
    assert shape["required_leading_string_pattern"] == "^0x[0-9a-f]{40}$"
    assert shape["minimum_valid_event_pair_count"] == 1

    retention = r8a["proposed_future_retention_boundary"]
    for key in (
        "wallet_address_retention_authorized", "leading_string_value_retention_authorized",
        "per_wallet_fill_count_retention_authorized", "unique_wallet_count_retention_authorized",
        "valid_event_pair_count_retention_authorized",
    ):
        assert retention[key] is True, key
    assert retention["normalization"] == "LOWERCASE_EXACT_0X40HEX"
    assert retention["retained_wallet_index_fields_only"] == ["wallet_address", "fill_count"]
    for key, value in retention.items():
        if key.endswith("_retention_authorized") and key not in {
            "wallet_address_retention_authorized",
            "leading_string_value_retention_authorized",
            "per_wallet_fill_count_retention_authorized",
            "unique_wallet_count_retention_authorized",
            "valid_event_pair_count_retention_authorized",
        }:
            assert value is False, key
    assert retention["payload_values_in_evidence_authorized"] is False
    assert retention["performance_field_values_retention_authorized"] is False

    output = r8a["deterministic_output_contract"]
    assert output["format"] == "UTF8_NDJSON"
    assert output["one_row_per_unique_wallet"] is True
    assert output["wallet_address_unique"] is True
    assert output["wallet_address_sort_order"] == "LEXICOGRAPHIC_ASCENDING"
    assert output["fill_count_positive_integer"] is True
    assert output["sum_fill_count_must_equal_valid_event_pair_count"] is True

    assert all(value is False for value in r8a["current_runtime_authority"].values())
    assert all(value is False for value in r8a["downstream_authorizations"].values())
    assert all(value is False for value in r8a["trading_authorizations"].values())
    assert r8a["human_approval_required_before_implementation"] is True
    assert r8a["implementation_required_before_execution_release"] is True
    assert r8a["separate_execution_release_required"] is True
    assert r8a["network_requests_executed_by_this_preregistration"] == 0
    assert r8a["wallet_addresses_retained_by_this_preregistration"] == 0
    assert r8a["empirical_result"] is None

    for required in (
        "APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001",
        "reviewed_commit=<CANONICAL_R8_STATIC_DESIGN_MERGE_COMMIT>",
        "maximum_one_time_budget_eur=0.10",
        f"object_key={MODERN_KEY}",
        "wallet_address_retention_authorized=true",
        "retained_wallet_index_fields_only=wallet_address,fill_count",
        "performance_field_values_retention_authorized=false",
        "historical_multi_hour_ingestion_authorized=false",
        "wallet_ranking_authorized=false",
        "pnl_or_alpha_analysis_authorized=false",
        "live_authorized=false",
    ):
        assert required in template, required

    assert "STATIC_PERFORMANCE_COPYABILITY_DATA_DESIGN_COMPLETE_MODERN_BRIDGE_REQUIRED" in report
    assert "HUMAN APPROVAL REQUIRED" in status

    forbidden_paths = [
        R8 / "collector.py",
        R8 / "R8A_IMPLEMENTATION_CONTRACT.json",
        R8 / "R8A_EXECUTION_RELEASE.json",
        R8 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.txt",
        ROOT / ".github/workflows/hyperliquid-archive-modern-wallet-index-r8a.yml",
    ]
    for path in forbidden_paths:
        assert not path.exists(), path

    print("R8_STATIC_DESIGN_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
