from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "research/archive_inventory/r8"
DESIGN = R8 / "PERFORMANCE_COPYABILITY_DATA_DESIGN_R8_CONTRACT.json"
BRIDGE = R8 / "MODERN_WALLET_INDEX_BRIDGE_R8A_CONTRACT.json"
SOURCES = R8 / "OFFICIAL_SOURCE_EVIDENCE.json"
DERIVATION = R8 / "R7_DERIVATION.json"
REPORT = R8 / "DESIGN_REPORT.md"
STATUS = R8 / "APPROVAL_STATUS.md"
TEMPLATE = R8 / "HUMAN_APPROVAL_TEMPLATE_R8A.md"
R4_EVIDENCE = ROOT / "research/archive_inventory/r4/evidence/run-31313913525/r4-body-result.json"
R7_RESULT = ROOT / "research/archive_inventory/r7/evidence/run-31330248235/r7-result.json"
R7_INDEX = ROOT / "research/archive_inventory/r7/evidence/run-31330248235/r7-wallet-index.ndjson"

R7_EVIDENCE_MERGE = "7802d741f193671e50356c6001dcae149e0fc88a"
R4_EVIDENCE_MERGE = "fe06874aeeb958d375a27100378f89bd25b4741b"
R4_RUN = 31313913525
R7_RUN = 31330248235
MODERN_KEY = "node_fills_by_block/hourly/20250727/8.lz4"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    design = load(DESIGN)
    bridge = load(BRIDGE)
    sources = load(SOURCES)
    derivation = load(DERIVATION)
    r4 = load(R4_EVIDENCE)
    r7 = load(R7_RESULT)
    report = REPORT.read_text(encoding="utf-8")
    status = STATUS.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")

    assert design["study_id"] == "HL-WALLET-PERFORMANCE-COPYABILITY-DATA-DESIGN-R8-001"
    assert design["status"] == "STATIC_DESIGN_PREREGISTERED_NO_EXECUTION"
    assert design["parent_r7_evidence_commit"] == R7_EVIDENCE_MERGE
    assert design["parent_r7_run_id"] == R7_RUN
    assert design["parent_r7_terminal_result"] == "WALLET_INDEX_RECONSTRUCTION_COMPLETE"
    assert design["parent_r7_unique_wallet_count"] == 4637
    assert design["parent_r7_sum_fill_count"] == 162815
    assert design["network_requests_executed_by_r8"] == 0
    assert design["wallets_ranked_by_r8"] == 0
    assert design["empirical_result"] is None
    assert all(value is False for value in design["current_authority"].values())
    assert all(value is False for value in design["trading_authorizations"].values())

    fields = design["minimum_archive_candidate_field_set"]
    assert fields["identity_and_time"] == ["wallet_address", "time"]
    assert fields["instrument_and_direction"] == ["coin", "side", "dir"]
    assert fields["economic_fill_values"] == ["px", "sz", "closedPnl", "fee", "feeToken"]
    assert fields["position_transition"] == ["startPosition"]
    assert fields["deduplication"] == ["tid"]
    assert fields["behavioral_or_risk_flags_with_limited_semantic_use"] == ["crossed", "liquidation_presence"]
    assert fields["explicitly_not_required_for_initial_candidate_screen"] == ["hash", "oid", "cloid", "builder", "builderFee"]

    semantic = design["semantic_boundaries"]
    assert semantic["closed_pnl_sum_is_exact_account_return"] is False
    assert semantic["closed_pnl_may_be_used_as_fill_derived_statistic"] is True
    assert semantic["fee_may_be_retained_for_cost_diagnostics"] is True
    assert semantic["fee_must_not_be_blindly_subtracted_from_closed_pnl_without_formula_proof"] is True
    assert semantic["crossed_maker_taker_semantics_proven"] is False
    assert semantic["crossed_may_be_retained_as_uninterpreted_boolean_until_separate_semantic_proof"] is True
    assert semantic["one_wallet_address_equals_one_human_or_economic_entity"] is False
    assert semantic["portfolio_graphs_are_precise_accounting"] is False
    assert semantic["portfolio_graphs_may_support_shortlisted_wallet_performance_context"] is True

    pipeline = design["proposed_research_pipeline"]
    assert [row["stage"] for row in pipeline] == [
        "A_GLOBAL_ARCHIVE_SCREEN",
        "B_CANDIDATE_REDUCTION",
        "C_SHORTLIST_PUBLIC_API_ENRICHMENT",
        "D_COPYABILITY_EXECUTION_RESEARCH",
    ]
    assert pipeline[0]["data_source"] == "node_fills and node_fills_by_block"
    assert pipeline[0]["per_wallet_api_calls"] is False
    assert pipeline[1]["ranking_authorized_by_r8"] is False
    assert pipeline[2]["network_authorized_by_r8"] is False
    assert pipeline[3]["network_authorized_by_r8"] is False
    assert design["api_scaling_constraint"]["per_address_user_fills_is_not_primary_population_scan"] is True
    assert design["api_scaling_constraint"]["shortlist_first_required"] is True

    assert bridge["pilot_id"] == "HL-ARCHIVE-MODERN-WALLET-INDEX-BRIDGE-R8A-001"
    assert bridge["status"] == "PREREGISTERED_NO_EXECUTION"
    assert bridge["parent_r8_study_id"] == design["study_id"]
    assert bridge["parent_r7_evidence_commit"] == R7_EVIDENCE_MERGE
    assert bridge["parent_r4_evidence_commit"] == R4_EVIDENCE_MERGE
    assert bridge["parent_r4_run_id"] == R4_RUN
    assert bridge["human_approval_required_before_implementation"] is True
    assert bridge["implementation_required_before_execution_release"] is True
    assert bridge["separate_execution_release_required"] is True
    assert bridge["network_requests_executed_by_this_preregistration"] == 0
    assert bridge["wallet_addresses_retained_by_this_preregistration"] == 0
    assert bridge["empirical_result"] is None
    assert all(value is False for value in bridge["current_runtime_authority"].values())
    assert all(value is False for value in bridge["downstream_authorizations"].values())
    assert all(value is False for value in bridge["trading_authorizations"].values())

    target = bridge["exact_future_network_target"]
    assert target == {
        "bucket": "hl-mainnet-node-data",
        "signing_region": "ap-northeast-1",
        "key": MODERN_KEY,
        "expected_size_bytes": 1517603,
        "expected_etag": '"60d4c1277f76651b5f04666bbe8d7594"',
        "expected_compressed_sha256": "928e1cd6bd7d69ad7243c263bacee48e53e4762ae9e99ef75f45007f6c0e6105",
        "expected_decompressed_byte_count": 7380378,
        "expected_top_level_block_record_count": 4345,
    }
    envelope = bridge["proposed_future_request_envelope"]
    assert envelope["maximum_one_time_budget_eur"] == 0.10
    assert envelope["maximum_monthly_budget_eur"] == 0
    assert envelope["maximum_get_object_requests"] == 1
    assert envelope["maximum_requests_per_object"] == 1
    assert envelope["maximum_total_compressed_bytes"] == 1517603
    assert envelope["maximum_total_decompressed_bytes"] == 16777216
    assert envelope["maximum_runtime_seconds"] == 120
    assert envelope["maximum_retries_per_request"] == 0
    assert envelope["requester_pays_required"] is True
    assert envelope["if_match_etag_required"] is True
    assert envelope["exact_content_length_required"] is True
    assert envelope["exact_response_etag_required"] is True
    assert envelope["exact_compressed_sha256_required"] is True
    assert envelope["exact_decompressed_byte_count_required"] is True
    assert envelope["http_redirect_following_authorized"] is False
    assert envelope["head_object_authorized"] is False
    assert envelope["range_get_authorized"] is False
    assert envelope["list_objects_v2_authorized"] is False
    assert envelope["list_object_versions_authorized"] is False
    assert envelope["list_all_my_buckets_authorized"] is False
    assert envelope["lz4_frame_stream_only"] is True
    assert envelope["alternate_decompressor_fallback_authorized"] is False
    assert envelope["strict_utf8_decode"] is True
    assert envelope["strict_json_duplicate_keys_rejected"] is True
    assert envelope["strict_json_nonfinite_constants_rejected"] is True
    assert envelope["maximum_record_bytes"] == 16777216
    assert envelope["maximum_block_records_parsed"] == 1000000
    assert envelope["maximum_event_pairs_parsed"] == 5000000

    shape = bridge["required_modern_block_shape"]
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

    retention = bridge["proposed_future_retention_boundary"]
    assert retention["wallet_address_retention_authorized"] is True
    assert retention["leading_string_value_retention_authorized"] is True
    assert retention["normalization"] == "LOWERCASE_EXACT_0X40HEX"
    assert retention["per_wallet_fill_count_retention_authorized"] is True
    assert retention["unique_wallet_count_retention_authorized"] is True
    assert retention["valid_event_pair_count_retention_authorized"] is True
    assert retention["wallet_index_entry_cap"] == 1000000
    assert retention["wallet_index_output_byte_cap"] == 16777216
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

    modern = next(row for row in r4["observations"] if row["dataset_family_id"] == "node_fills_by_block")
    assert modern["key"] == MODERN_KEY
    assert modern["compressed_object_size_bytes"] == target["expected_size_bytes"]
    assert modern["expected_etag"] == target["expected_etag"]
    assert modern["compressed_object_sha256"] == target["expected_compressed_sha256"]
    assert modern["decompressed_byte_count"] == target["expected_decompressed_byte_count"]
    assert modern["record_count"] == target["expected_top_level_block_record_count"]
    assert modern["schema_status"] == "FULL_SCHEMA_PARSED"

    assert r7["research_conclusion"] == "WALLET_INDEX_RECONSTRUCTION_COMPLETE"
    assert r7["wallet_index_summary"]["unique_wallet_count"] == 4637
    assert r7["wallet_index_summary"]["sum_fill_count"] == 162815
    assert hashlib.sha256(R7_INDEX.read_bytes()).hexdigest() == r7["wallet_index_summary"]["wallet_index_sha256"]
    assert derivation["parent_r7_evidence_commit"] == R7_EVIDENCE_MERGE
    assert derivation["parent_r7_run_id"] == R7_RUN
    assert derivation["parent_r7_unique_wallet_count"] == 4637
    assert derivation["parent_r7_sum_fill_count"] == 162815
    assert sources["study_id"] == design["study_id"]

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
    assert ("HUMAN APPROVAL REQUIRED" in status) or ("HUMAN APPROVED" in status)

    # R8 remains static and non-self-authorizing. A later approval record is allowed
    # to exist, but implementation/runtime artifacts are still forbidden until a
    # separately reviewed implementation stage is created.
    forbidden_paths = [
        R8 / "collector.py",
        R8 / "R8A_IMPLEMENTATION_CONTRACT.json",
        R8 / "R8A_EXECUTION_RELEASE.json",
        R8 / "R8A_EXECUTION_RELEASE_CANONICALIZATION.json",
        ROOT / ".github/workflows/hyperliquid-archive-modern-wallet-index-r8a.yml",
    ]
    for path in forbidden_paths:
        assert not path.exists(), path

    print("R8_STATIC_DESIGN_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
