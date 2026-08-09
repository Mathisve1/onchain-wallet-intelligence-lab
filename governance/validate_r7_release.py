from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R7 = ROOT / "research/archive_inventory/r7"
RELEASE = R7 / "R7_EXECUTION_RELEASE.json"
APPROVAL = R7 / "approvals/APPROVE_HL_ARCHIVE_WALLET_INDEX_RECONSTRUCTION_R7_001.json"
APPROVAL_TEXT = R7 / "approvals/APPROVE_HL_ARCHIVE_WALLET_INDEX_RECONSTRUCTION_R7_001.txt"
IMPLEMENTATION = R7 / "R7_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = R7 / "R7_AWS_ROLE_REUSE_ANALYSIS.json"
COLLECTOR = R7 / "collector.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-wallet-index-r7.yml"
ACTIVATION = R7 / "R7_EXECUTION_RELEASE_CANONICALIZATION.json"

APPROVAL_SHA = "43f32634859eb39e4b1e464276f9721ed4ef8bcc30161f1f301f82e0312042a6"
IMPLEMENTATION_MERGE = "0a7d9821d6844439d95c7a79cf09673a0ed05329"
CANONICAL_IMPLEMENTATION_HASHES = {
    "implementation_contract_sha256": "0bcbaf78522ebc5914d096d15d74816001e1bcb50481c7232436166dd255f731",
    "role_reuse_analysis_sha256": "d429ce6e0ec68232093d932e02fa5d639aabd2f5ee09114e422ebcf51ffffbe3",
    "collector_sha256": "d374dbb2f581b641ecd115338760e496d440add3c1e5166d2c047f69a733e96a",
    "workflow_sha256": "0718f6c2fca85baa1112819efb0ab98e440536cb01aef867c5f1eed0a8784e80",
    "implementation_validator_sha256": "7185240bd2a9c85c613b2bbbfb8c57a1b1ded672b3a4bb0f01ccde348735d11c",
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
    assert release["release_id"] == "RELEASE_HL_ARCHIVE_WALLET_INDEX_RECONSTRUCTION_R7_001"
    assert release["pilot_id"] == "HL-ARCHIVE-WALLET-INDEX-RECONSTRUCTION-R7-001"
    assert release["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert release["execution_ready"] is False
    assert release["single_workflow_dispatch_authorized"] is False
    assert release["rerun_authorized"] is False
    assert release["preregistration_commit"] == "795281b2992466785ba48314d59feb61ac0b3aef"
    assert release["approval_merge_commit"] == "65a7b53796231b3aaea4c1dc1b41aa847b4ea3ba"
    assert release["approval_id"] == approval["approval_id"]
    assert release["approval_text_sha256"] == APPROVAL_SHA
    assert release["canonical_implementation_merge_commit"] == IMPLEMENTATION_MERGE
    assert release["implementation_pull_request_number"] == 74
    assert release["canonical_implementation_byte_binding"] == CANONICAL_IMPLEMENTATION_HASHES

    # The implementation contract, role analysis, collector and runtime workflow
    # remain byte-identical to their canonical implementation merge. The
    # implementation validator itself is allowed to become later-stage-aware.
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
        "object_key": "node_fills/hourly/20250727/8.lz4",
        "object_size_bytes": 12726384,
        "object_etag": '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"',
        "expected_compressed_sha256": "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622",
        "expected_decompressed_byte_count": 62169139,
        "expected_nonempty_record_count": 162815,
        "maximum_one_time_budget_eur": 0.10,
        "maximum_monthly_budget_eur": 0,
        "maximum_get_object_requests": 1,
        "maximum_requests_per_object": 1,
        "maximum_total_compressed_bytes": 12726384,
        "maximum_total_decompressed_bytes": 134217728,
        "maximum_runtime_seconds": 120,
        "maximum_retries_per_request": 0,
        "wallet_index_entry_cap": 162815,
        "wallet_index_output_byte_cap": 16777216,
    }.items():
        assert release[key] == expected, key

    assert release["dedicated_role_arn"] == "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
    assert release["aws_role_mutation_required"] is False
    assert release["aws_role_mutation_authorized"] is False
    assert release["aws_role_mutation_performed"] is False
    assert release["session_s3_policy"] == "ALLOW_GETOBJECT_EXACT_R5_BOUND_LEGACY_OBJECT_ONLY"
    assert release["session_policy_strict_subset_of_persistent_role"] is True

    for key in (
        "requester_pays_authorized_for_later_activation",
        "get_object_authorized_for_later_activation",
        "object_body_download_authorized_for_later_activation",
        "decompression_authorized_for_later_activation",
        "wallet_index_reconstruction_authorized_for_later_activation",
        "wallet_address_retention_authorized",
        "leading_string_value_retention_authorized",
        "per_wallet_fill_count_retention_authorized",
        "unique_wallet_count_retention_authorized",
    ):
        assert release[key] is True, key
    for key in (
        "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
        "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "http_redirect_following_authorized", "raw_compressed_object_retention_authorized",
        "raw_decompressed_payload_retention_authorized", "record_payload_retention_authorized",
        "fill_object_retention_authorized", "payload_values_in_evidence_authorized",
        "coin_value_retention_authorized", "price_value_retention_authorized",
        "size_value_retention_authorized", "side_value_retention_authorized",
        "time_value_retention_authorized", "closed_pnl_value_retention_authorized",
        "fee_value_retention_authorized", "transaction_hash_retention_authorized",
        "order_id_retention_authorized", "trade_id_retention_authorized",
        "client_order_id_retention_authorized",
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

    assert not ACTIVATION.exists()
    print("R7_RELEASE_CANDIDATE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
