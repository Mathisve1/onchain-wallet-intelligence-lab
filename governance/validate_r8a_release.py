from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "research/archive_inventory/r8"
RELEASE = R8 / "R8A_EXECUTION_RELEASE.json"
APPROVAL = R8 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.json"
APPROVAL_TEXT = R8 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.txt"
IMPLEMENTATION = R8 / "R8A_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = R8 / "R8A_AWS_ROLE_REUSE_ANALYSIS.json"
COLLECTOR = R8 / "collector.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-modern-wallet-index-r8a.yml"
ACTIVATION = R8 / "R8A_EXECUTION_RELEASE_CANONICALIZATION.json"

APPROVAL_SHA = "cb39246e2e5f345b14f87c15ac2c4d6aa993bcc9fbd28076f5f57eff94420e64"
IMPLEMENTATION_MERGE = "cb4f0e3272917aa27f53c85432107b21d2d242b9"
CANONICAL_IMPLEMENTATION_HASHES = {
    "implementation_contract_sha256": "f858e9888892205fdbd27a54205900b281585e0d683af586e3c6238109a6bff3",
    "role_reuse_analysis_sha256": "327aea34b666178189a06220322a2b95e63d66dfc204a5b57f53a95d818cd4dc",
    "collector_sha256": "0d5742807a92095b2bb7711c670cefe044e005a7dfbb440f60077c1d8a80a1d4",
    "workflow_sha256": "3e4ef561e42034f9dcf7233b80ca14d3282ef9601caed49e32a15bd9c5059c65",
    "implementation_validator_sha256": "0b5575bb28db71a306a950f662fd933d70a592cdc554ff746042080433de6962",
}


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    release = load(RELEASE)
    approval = load(APPROVAL)
    impl = load(IMPLEMENTATION)
    reuse = load(ROLE_REUSE)

    assert sha(APPROVAL_TEXT) == APPROVAL_SHA
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert release["release_id"] == "RELEASE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001"
    assert release["pilot_id"] == "HL-ARCHIVE-MODERN-WALLET-INDEX-BRIDGE-R8A-001"
    assert release["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert release["execution_ready"] is False
    assert release["single_workflow_dispatch_authorized"] is False
    assert release["rerun_authorized"] is False
    assert release["r8_static_design_commit"] == "526f92cf3666c8bb616ecb61b6f9881387c1d7ed"
    assert release["approval_merge_commit"] == "6c011cb604dec1f169d42b02de4ae67f3f8f8395"
    assert release["approval_id"] == approval["approval_id"]
    assert release["approval_text_sha256"] == APPROVAL_SHA
    assert release["canonical_implementation_merge_commit"] == IMPLEMENTATION_MERGE
    assert release["implementation_pull_request_number"] == 80
    assert release["canonical_implementation_byte_binding"] == CANONICAL_IMPLEMENTATION_HASHES

    assert sha(IMPLEMENTATION) == CANONICAL_IMPLEMENTATION_HASHES["implementation_contract_sha256"]
    assert sha(ROLE_REUSE) == CANONICAL_IMPLEMENTATION_HASHES["role_reuse_analysis_sha256"]
    assert sha(COLLECTOR) == CANONICAL_IMPLEMENTATION_HASHES["collector_sha256"]
    assert sha(WORKFLOW) == CANONICAL_IMPLEMENTATION_HASHES["workflow_sha256"]
    assert impl["status"] == "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION"
    assert all(value is False for value in impl["current_runtime_authority"].values())
    assert reuse["aws_iam_mutation_performed"] is False

    for key, expected in {
        "target_bucket": "hl-mainnet-node-data",
        "signing_region": "ap-northeast-1",
        "object_key": "node_fills_by_block/hourly/20250727/8.lz4",
        "object_size_bytes": 1517603,
        "object_etag": '"60d4c1277f76651b5f04666bbe8d7594"',
        "expected_compressed_sha256": "928e1cd6bd7d69ad7243c263bacee48e53e4762ae9e99ef75f45007f6c0e6105",
        "expected_decompressed_byte_count": 7380378,
        "expected_top_level_block_record_count": 4345,
        "maximum_one_time_budget_eur": 0.10,
        "maximum_monthly_budget_eur": 0,
        "maximum_get_object_requests": 1,
        "maximum_requests_per_object": 1,
        "maximum_total_compressed_bytes": 1517603,
        "maximum_total_decompressed_bytes": 16777216,
        "maximum_runtime_seconds": 120,
        "maximum_retries_per_request": 0,
        "wallet_index_entry_cap": 1000000,
        "wallet_index_output_byte_cap": 16777216,
    }.items():
        assert release[key] == expected, key

    assert release["dedicated_role_arn"] == "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
    assert release["aws_role_mutation_required"] is False
    assert release["aws_role_mutation_authorized"] is False
    assert release["aws_role_mutation_performed"] is False
    assert release["session_s3_policy"] == "ALLOW_GETOBJECT_EXACT_R8A_MODERN_BOUNDARY_OBJECT_ONLY"
    assert release["session_policy_strict_subset_of_persistent_role"] is True

    for key in (
        "requester_pays_authorized_for_later_activation",
        "get_object_authorized_for_later_activation",
        "object_body_download_authorized_for_later_activation",
        "decompression_authorized_for_later_activation",
        "modern_wallet_index_reconstruction_authorized_for_later_activation",
        "wallet_address_retention_authorized",
        "leading_string_value_retention_authorized",
        "per_wallet_fill_count_retention_authorized",
        "unique_wallet_count_retention_authorized",
        "valid_event_pair_count_retention_authorized",
    ):
        assert release[key] is True, key
    for key in (
        "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
        "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "http_redirect_following_authorized", "block_number_retention_authorized",
        "local_time_retention_authorized", "block_time_retention_authorized",
        "raw_compressed_object_retention_authorized", "raw_decompressed_payload_retention_authorized",
        "record_payload_retention_authorized", "fill_object_retention_authorized",
        "payload_values_in_evidence_authorized", "performance_field_values_retention_authorized",
        "coin_value_retention_authorized", "price_value_retention_authorized", "size_value_retention_authorized",
        "side_value_retention_authorized", "time_value_retention_authorized", "dir_value_retention_authorized",
        "closed_pnl_value_retention_authorized", "fee_value_retention_authorized",
        "fee_token_value_retention_authorized", "start_position_value_retention_authorized",
        "crossed_value_retention_authorized", "liquidation_value_retention_authorized",
        "transaction_hash_retention_authorized", "order_id_retention_authorized",
        "trade_id_retention_authorized", "client_order_id_retention_authorized",
    ):
        assert release[key] is False, key
    assert release["wallet_address_normalization"] == "LOWERCASE_EXACT_0X40HEX"
    assert release["retained_wallet_index_fields_only"] == ["wallet_address", "fill_count"]
    assert all(value is False for value in release["downstream_authorizations"].values())
    assert all(value is False for value in release["trading_authorizations"].values())
    assert release["s3_requests_executed"] == 0
    assert release["compressed_bytes_downloaded"] == 0
    assert release["decompressed_bytes_processed"] == 0
    assert release["wallet_addresses_retained"] == 0
    assert release["empirical_result"] is None

    if ACTIVATION.exists():
        activation = load(ACTIVATION)
        assert activation["release_id"] == release["release_id"]
        assert activation["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R8A_RUN"
        assert activation["candidate_sha256"] == sha(RELEASE)
        assert activation["single_workflow_dispatch_authorized"] is True
        assert activation["rerun_authorized"] is False
        assert activation["release_consumed"] is False
        assert activation["s3_requests_executed"] == 0
        assert activation["wallet_addresses_retained"] == 0
        assert activation["empirical_result"] is None
    print("R8A_RELEASE_CANDIDATE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
