from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R9 = ROOT / "research/archive_inventory/r9"
CANDIDATE = R9 / "R9_EXECUTION_RELEASE.json"
ACTIVATION = R9 / "R9_EXECUTION_RELEASE_CANONICALIZATION.json"
APPROVAL_TEXT = R9 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001.txt"
IMPLEMENTATION = R9 / "R9_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = R9 / "R9_AWS_ROLE_REUSE_ANALYSIS.json"
COLLECTOR = R9 / "collector.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-modern-wallet-feature-r9.yml"

PREREG_MERGE = "62ce0009c3c4aad70d2a91f242a690cd26ace355"
APPROVAL_MERGE = "332aa535b0de19a18befb8529450ae88acf35762"
APPROVAL_SHA = "1e4642ef2eef660f7971c2632864cf78894340e3408f15d15597e4eb12a04330"
IMPLEMENTATION_MERGE = "35afca156a99cc71360b338968cb842f9f31ab3b"
RELEASE_MERGE = "2ce37ca972907e55de30a4f1aed41ae3cd5b805b"
CANDIDATE_SHA = "80c66a1ea5637032c61aa47e3299def5e6b590529e25c21250bb4028f62548bc"
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
    candidate = load(CANDIDATE)
    activation = load(ACTIVATION)
    impl = load(IMPLEMENTATION)
    reuse = load(ROLE_REUSE)

    assert sha(APPROVAL_TEXT) == APPROVAL_SHA
    assert sha(CANDIDATE) == CANDIDATE_SHA
    assert candidate["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert candidate["execution_ready"] is False
    assert candidate["single_workflow_dispatch_authorized"] is False
    assert candidate["rerun_authorized"] is False
    assert candidate["release_consumed"] is False
    assert candidate["s3_requests_executed"] == 0
    assert candidate["wallet_feature_rows_created"] == 0
    assert candidate["empirical_result"] is None

    assert activation["release_id"] == candidate["release_id"] == "RELEASE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001"
    assert activation["pilot_id"] == candidate["pilot_id"] == "HL-ARCHIVE-MODERN-WALLET-FEATURE-PILOT-R9-001"
    assert activation["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R9_RUN"
    assert activation["activation_model"] == "CANONICAL_PR_AND_BYTE_EXACT_TREE_BINDING"
    assert activation["r9_preregistration_merge_commit"] == candidate["r9_preregistration_merge_commit"] == PREREG_MERGE
    assert activation["approval_merge_commit"] == candidate["approval_merge_commit"] == APPROVAL_MERGE
    assert activation["approval_id"] == candidate["approval_id"] == "APPROVE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001"
    assert activation["approval_text_sha256"] == candidate["approval_text_sha256"] == APPROVAL_SHA
    assert activation["canonical_implementation_merge_commit"] == candidate["canonical_implementation_merge_commit"] == IMPLEMENTATION_MERGE
    assert activation["release_candidate_merge_commit"] == RELEASE_MERGE
    assert activation["candidate_sha256"] == CANDIDATE_SHA

    bindings = activation["implementation_byte_binding"]
    assert bindings["implementation_contract_sha256"] == sha(IMPLEMENTATION) == "d721b8f03f07890ad0c0071e922cdcb3b2c5d815a30ed3ba397029acfa540688"
    assert bindings["role_reuse_analysis_sha256"] == sha(ROLE_REUSE) == "603fb301f11483e83f13d00aa05d409eb1d9b2554e2d2a2ea04a626bbe23c0a6"
    assert bindings["collector_sha256"] == sha(COLLECTOR) == "b1abe0d84de9230bb65cbfe9244534329c34085e8c82f118b880905e306d6ce7"
    assert bindings["workflow_sha256"] == sha(WORKFLOW) == "f70cb36fc7e097838a57f47c67d3bda39aa0028b60cfafac2e1635fb863e09c9"
    assert bindings["pre_activation_implementation_validator_sha256"] == "aa459c8f427372488d4fc91c0a933f43388eca9e1e58beba3f9828b99ecd0d6c"
    assert bindings["pre_activation_release_validator_sha256"] == "074bf959fb460c8505d186e2b8fd4555523acef77b1841bc6d2ddd5085961b77"

    assert activation["github_event_required"] == "workflow_dispatch"
    assert activation["canonical_dispatch_ref_required"] == "refs/heads/main"
    assert activation["canonical_dispatch_sha_source"] == "github.sha"
    start = datetime.fromisoformat(activation["single_use_window_start_utc"].replace("Z", "+00:00")).astimezone(timezone.utc)
    assert start == datetime(2026, 8, 9, 21, 12, tzinfo=timezone.utc)
    assert activation["single_workflow_dispatch_authorized"] is True
    assert activation["rerun_authorized"] is False
    assert activation["release_consumed"] is False

    for value in (candidate, activation):
        assert value["dedicated_role_arn"] == "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
        assert value["aws_role_mutation_required"] is False
        assert value["aws_role_mutation_authorized"] is False
        assert value["aws_role_mutation_performed"] is False
        assert value["session_s3_policy"] == "ALLOW_GETOBJECT_EXACT_R9_MODERN_FIXTURE_ONLY"
        assert value["session_policy_strict_subset_of_persistent_role"] is True
        assert value["target_bucket"] == "hl-mainnet-node-data"
        assert value["signing_region"] == "ap-northeast-1"
        assert value["object_key"] == "node_fills_by_block/hourly/20250727/8.lz4"
        assert value["object_size_bytes"] == 1517603
        assert value["object_etag"] == '"60d4c1277f76651b5f04666bbe8d7594"'
        assert value["expected_compressed_sha256"] == "928e1cd6bd7d69ad7243c263bacee48e53e4762ae9e99ef75f45007f6c0e6105"
        assert value["expected_decompressed_byte_count"] == 7380378
        assert value["expected_top_level_block_record_count"] == 4345
        assert value["expected_valid_event_pair_count"] == 17516
        assert value["maximum_one_time_budget_eur"] == 0.10
        assert value["maximum_monthly_budget_eur"] == 0
        assert value["maximum_get_object_requests"] == 1
        assert value["maximum_retries_per_request"] == 0
        assert value["boundary_fixture_role"] == "SERIALIZER_AND_FEATURE_PIPELINE_FIXTURE_ONLY"
        assert value["boundary_fixture_historical_representativeness_authorized"] is False
        assert value["canonical_cross_format_history_use_authorized"] is False
        assert value["selected_fill_fields_processed"] == ["coin", "side", "time", "px", "sz", "closedPnl", "tid", "crossed", "liquidation"]
        assert value["retained_wallet_feature_fields_only"] == FIELDS
        assert value["exact_decimal_arithmetic_required"] is True
        assert value["floating_point_aggregation_authorized"] is False
        assert value["sum_closed_pnl_is_exact_account_return"] is False
        assert value["sum_closed_pnl_is_wallet_ranking_score"] is False
        assert value["notional_proxy_is_copyable_notional"] is False
        assert all(flag is False for flag in value["downstream_authorizations"].values())
        assert all(flag is False for flag in value["trading_authorizations"].values())
        assert value["s3_requests_executed"] == 0
        assert value["compressed_bytes_downloaded"] == 0
        assert value["decompressed_bytes_processed"] == 0
        assert value["wallet_feature_rows_created"] == 0
        assert value["empirical_result"] is None

    assert impl["status"] == "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION"
    assert all(flag is False for flag in impl["current_runtime_authority"].values())
    assert reuse["aws_iam_mutation_performed"] is False

    print("R9_ACTIVATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
