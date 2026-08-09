from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R9 = ROOT / "research/archive_inventory/r9"
RELEASE = R9 / "R9_EXECUTION_RELEASE.json"
IMPLEMENTATION = R9 / "R9_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = R9 / "R9_AWS_ROLE_REUSE_ANALYSIS.json"
COLLECTOR = R9 / "collector.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-modern-wallet-feature-r9.yml"
ACTIVATION = R9 / "R9_EXECUTION_RELEASE_CANONICALIZATION.json"

IMPL_MERGE = "35afca156a99cc71360b338968cb842f9f31ab3b"
FIELDS = [
    "wallet_address", "fill_count", "first_fill_time", "last_fill_time", "distinct_coin_count",
    "side_a_count", "side_b_count", "crossed_true_count", "liquidation_associated_fill_count",
    "duplicate_tid_count", "sum_abs_px_times_sz_notional_proxy", "sum_closed_pnl_fill_statistic",
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    release = load(RELEASE)
    impl = load(IMPLEMENTATION)
    reuse = load(ROLE_REUSE)

    assert release["release_id"] == "RELEASE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001"
    assert release["pilot_id"] == "HL-ARCHIVE-MODERN-WALLET-FEATURE-PILOT-R9-001"
    assert release["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert release["execution_ready"] is False
    assert release["single_workflow_dispatch_authorized"] is False
    assert release["rerun_authorized"] is False
    assert release["release_consumed"] is False
    assert release["r9_preregistration_merge_commit"] == "62ce0009c3c4aad70d2a91f242a690cd26ace355"
    assert release["approval_merge_commit"] == "332aa535b0de19a18befb8529450ae88acf35762"
    assert release["approval_id"] == "APPROVE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001"
    assert release["approval_text_sha256"] == "1e4642ef2eef660f7971c2632864cf78894340e3408f15d15597e4eb12a04330"
    assert release["canonical_implementation_merge_commit"] == IMPL_MERGE
    assert release["implementation_pull_request_number"] == 87

    bindings = release["canonical_implementation_byte_binding"]
    assert bindings["implementation_contract_sha256"] == sha(IMPLEMENTATION) == "d721b8f03f07890ad0c0071e922cdcb3b2c5d815a30ed3ba397029acfa540688"
    assert bindings["role_reuse_analysis_sha256"] == sha(ROLE_REUSE) == "603fb301f11483e83f13d00aa05d409eb1d9b2554e2d2a2ea04a626bbe23c0a6"
    assert bindings["collector_sha256"] == sha(COLLECTOR) == "b1abe0d84de9230bb65cbfe9244534329c34085e8c82f118b880905e306d6ce7"
    assert bindings["workflow_sha256"] == sha(WORKFLOW) == "f70cb36fc7e097838a57f47c67d3bda39aa0028b60cfafac2e1635fb863e09c9"
    assert bindings["implementation_validator_sha256"] == "aa459c8f427372488d4fc91c0a933f43388eca9e1e58beba3f9828b99ecd0d6c"

    assert release["github_event_required_for_later_activation"] == "workflow_dispatch"
    assert release["canonical_dispatch_ref_required_for_later_activation"] == "refs/heads/main"
    assert release["dedicated_role_arn"] == "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
    assert release["aws_role_mutation_required"] is False
    assert release["aws_role_mutation_authorized"] is False
    assert release["aws_role_mutation_performed"] is False
    assert release["session_s3_policy"] == "ALLOW_GETOBJECT_EXACT_R9_MODERN_FIXTURE_ONLY"
    assert release["session_policy_strict_subset_of_persistent_role"] is True
    assert release["target_bucket"] == "hl-mainnet-node-data"
    assert release["signing_region"] == "ap-northeast-1"
    assert release["object_key"] == "node_fills_by_block/hourly/20250727/8.lz4"
    assert release["object_size_bytes"] == 1517603
    assert release["object_etag"] == '"60d4c1277f76651b5f04666bbe8d7594"'
    assert release["expected_compressed_sha256"] == "928e1cd6bd7d69ad7243c263bacee48e53e4762ae9e99ef75f45007f6c0e6105"
    assert release["expected_decompressed_byte_count"] == 7380378
    assert release["expected_top_level_block_record_count"] == 4345
    assert release["expected_valid_event_pair_count"] == 17516
    assert release["maximum_one_time_budget_eur"] == 0.10
    assert release["maximum_monthly_budget_eur"] == 0
    assert release["maximum_get_object_requests"] == 1
    assert release["maximum_requests_per_object"] == 1
    assert release["maximum_total_compressed_bytes"] == 1517603
    assert release["maximum_total_decompressed_bytes"] == 16777216
    assert release["maximum_runtime_seconds"] == 120
    assert release["maximum_retries_per_request"] == 0

    for key in (
        "requester_pays_authorized_for_later_activation", "get_object_authorized_for_later_activation",
        "object_body_download_authorized_for_later_activation", "decompression_authorized_for_later_activation",
        "selected_fill_field_processing_authorized_for_later_activation", "wallet_feature_retention_authorized_for_later_activation",
        "exact_decimal_arithmetic_required", "fill_count_conservation_required", "side_count_conservation_required",
        "first_time_lte_last_time_required", "nonnegative_notional_proxy_required",
    ):
        assert release[key] is True, key
    for key in (
        "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
        "list_object_versions_authorized", "list_all_my_buckets_authorized", "http_redirect_following_authorized",
        "boundary_fixture_historical_representativeness_authorized", "canonical_cross_format_history_use_authorized",
        "floating_point_aggregation_authorized", "raw_compressed_object_retention_authorized",
        "raw_decompressed_payload_retention_authorized", "raw_block_record_retention_authorized",
        "raw_event_pair_retention_authorized", "raw_fill_object_retention_authorized", "coin_value_retention_authorized",
        "side_value_retention_authorized", "individual_time_value_retention_authorized",
        "individual_price_value_retention_authorized", "individual_size_value_retention_authorized",
        "individual_closed_pnl_value_retention_authorized", "trade_id_value_retention_authorized",
        "crossed_value_retention_authorized", "liquidation_payload_value_retention_authorized",
        "fee_value_processing_authorized", "fee_token_value_processing_authorized", "dir_value_processing_authorized",
        "start_position_value_processing_authorized", "transaction_hash_processing_authorized",
        "order_id_processing_authorized", "client_order_id_processing_authorized",
        "sum_closed_pnl_is_exact_account_return", "sum_closed_pnl_is_wallet_ranking_score",
        "notional_proxy_is_copyable_notional",
    ):
        assert release[key] is False, key
    assert release["boundary_fixture_role"] == "SERIALIZER_AND_FEATURE_PIPELINE_FIXTURE_ONLY"
    assert release["selected_fill_fields_processed"] == ["coin", "side", "time", "px", "sz", "closedPnl", "tid", "crossed", "liquidation"]
    assert release["maximum_numeric_token_characters"] == 128
    assert release["wallet_address_normalization"] == "LOWERCASE_EXACT_0X40HEX"
    assert release["decimal_output_encoding"] == "CANONICAL_BASE10_STRING_NO_EXPONENT"
    assert release["wallet_feature_entry_cap"] == 1000000
    assert release["wallet_feature_output_byte_cap"] == 33554432
    assert release["retained_wallet_feature_fields_only"] == FIELDS
    assert all(v is False for v in release["downstream_authorizations"].values())
    assert all(v is False for v in release["trading_authorizations"].values())
    assert release["s3_requests_executed"] == 0
    assert release["compressed_bytes_downloaded"] == 0
    assert release["decompressed_bytes_processed"] == 0
    assert release["wallet_feature_rows_created"] == 0
    assert release["empirical_result"] is None

    assert impl["status"] == "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION"
    assert all(v is False for v in impl["current_runtime_authority"].values())
    assert reuse["aws_iam_mutation_performed"] is False
    if ACTIVATION.exists():
        activation = load(ACTIVATION)
        assert activation["release_id"] == release["release_id"]
        assert activation["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R9_RUN"
        assert activation["candidate_sha256"] == sha(RELEASE)
        assert activation["single_workflow_dispatch_authorized"] is True
        assert activation["rerun_authorized"] is False
        assert activation["release_consumed"] is False
        assert activation["s3_requests_executed"] == 0
        assert activation["wallet_feature_rows_created"] == 0
        assert activation["empirical_result"] is None

    print("R9_RELEASE_CANDIDATE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
