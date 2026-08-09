from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R7 = ROOT / "research/archive_inventory/r7"
CANDIDATE = R7 / "R7_EXECUTION_RELEASE.json"
ACTIVATION = R7 / "R7_EXECUTION_RELEASE_CANONICALIZATION.json"
APPROVAL = R7 / "approvals/APPROVE_HL_ARCHIVE_WALLET_INDEX_RECONSTRUCTION_R7_001.json"
APPROVAL_TEXT = R7 / "approvals/APPROVE_HL_ARCHIVE_WALLET_INDEX_RECONSTRUCTION_R7_001.txt"
IMPLEMENTATION = R7 / "R7_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = R7 / "R7_AWS_ROLE_REUSE_ANALYSIS.json"
COLLECTOR = R7 / "collector.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-wallet-index-r7.yml"
IMPLEMENTATION_VALIDATOR = ROOT / "governance/validate_r7_implementation.py"

PREREG_MERGE = "795281b2992466785ba48314d59feb61ac0b3aef"
APPROVAL_MERGE = "65a7b53796231b3aaea4c1dc1b41aa847b4ea3ba"
APPROVAL_SHA = "43f32634859eb39e4b1e464276f9721ed4ef8bcc30161f1f301f82e0312042a6"
IMPLEMENTATION_MERGE = "0a7d9821d6844439d95c7a79cf09673a0ed05329"
RELEASE_CANDIDATE_MERGE = "5f640cac2a8d1d9a6559bb6f69805489b5822d74"
CANDIDATE_SHA = "6d238406d738b90d3f03bef63b830c01857562821518210541d666b163abdff9"
PRE_ACTIVATION_RELEASE_VALIDATOR_SHA = "d45373852c90cd0e1c12fb864aa2c3b5715d502fd59f8824c792db0589f3796e"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    candidate = load(CANDIDATE)
    activation = load(ACTIVATION)
    approval = load(APPROVAL)
    impl = load(IMPLEMENTATION)
    reuse = load(ROLE_REUSE)

    assert sha(APPROVAL_TEXT) == APPROVAL_SHA
    assert approval["reviewed_commit"] == PREREG_MERGE
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert all(value is False for value in approval["current_runtime_authority"].values())

    assert sha(CANDIDATE) == CANDIDATE_SHA
    assert candidate["release_id"] == "RELEASE_HL_ARCHIVE_WALLET_INDEX_RECONSTRUCTION_R7_001"
    assert candidate["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert candidate["execution_ready"] is False
    assert candidate["single_workflow_dispatch_authorized"] is False
    assert candidate["rerun_authorized"] is False
    assert candidate["s3_requests_executed"] == 0
    assert candidate["wallet_addresses_retained"] == 0
    assert candidate["empirical_result"] is None

    assert activation["release_id"] == candidate["release_id"]
    assert activation["pilot_id"] == candidate["pilot_id"] == "HL-ARCHIVE-WALLET-INDEX-RECONSTRUCTION-R7-001"
    assert activation["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R7_RUN"
    assert activation["activation_model"] == "CANONICAL_PR_AND_BYTE_EXACT_TREE_BINDING"
    assert activation["preregistration_commit"] == candidate["preregistration_commit"] == PREREG_MERGE
    assert activation["approval_merge_commit"] == candidate["approval_merge_commit"] == APPROVAL_MERGE
    assert activation["approval_id"] == candidate["approval_id"] == approval["approval_id"]
    assert activation["approval_text_sha256"] == candidate["approval_text_sha256"] == APPROVAL_SHA
    assert activation["canonical_implementation_merge_commit"] == candidate["canonical_implementation_merge_commit"] == IMPLEMENTATION_MERGE
    assert activation["release_candidate_merge_commit"] == RELEASE_CANDIDATE_MERGE
    assert activation["candidate_sha256"] == CANDIDATE_SHA

    bindings = activation["implementation_byte_binding"]
    assert bindings["implementation_contract_sha256"] == sha(IMPLEMENTATION) == "0bcbaf78522ebc5914d096d15d74816001e1bcb50481c7232436166dd255f731"
    assert bindings["role_reuse_analysis_sha256"] == sha(ROLE_REUSE) == "d429ce6e0ec68232093d932e02fa5d639aabd2f5ee09114e422ebcf51ffffbe3"
    assert bindings["collector_sha256"] == sha(COLLECTOR) == "d374dbb2f581b641ecd115338760e496d440add3c1e5166d2c047f69a733e96a"
    assert bindings["workflow_sha256"] == sha(WORKFLOW) == "0718f6c2fca85baa1112819efb0ab98e440536cb01aef867c5f1eed0a8784e80"
    assert bindings["implementation_validator_sha256"] == sha(IMPLEMENTATION_VALIDATOR) == "c924e2d6105295f59ab00971501e79e4dc2caabc58655229727ea89e6a9503bc"
    assert bindings["release_validator_sha256"] == PRE_ACTIVATION_RELEASE_VALIDATOR_SHA

    assert impl["status"] == "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION"
    assert all(value is False for value in impl["current_runtime_authority"].values())
    assert reuse["aws_iam_mutation_performed"] is False
    assert reuse["new_sts_preflight_required"] is False

    assert activation["github_event_required"] == "workflow_dispatch"
    assert activation["canonical_dispatch_ref_required"] == "refs/heads/main"
    assert activation["canonical_dispatch_sha_source"] == "github.sha"
    start = datetime.fromisoformat(activation["single_use_window_start_utc"].replace("Z", "+00:00")).astimezone(timezone.utc)
    assert start == datetime(2026, 8, 9, 18, 48, tzinfo=timezone.utc)
    assert activation["single_workflow_dispatch_authorized"] is True
    assert activation["rerun_authorized"] is False
    assert activation["release_consumed"] is False

    for value in (candidate, activation):
        assert value["dedicated_role_arn"] == "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
        assert value["aws_role_mutation_required"] is False
        assert value["aws_role_mutation_authorized"] is False
        assert value["aws_role_mutation_performed"] is False
        assert value["session_s3_policy"] == "ALLOW_GETOBJECT_EXACT_R5_BOUND_LEGACY_OBJECT_ONLY"
        assert value["session_policy_strict_subset_of_persistent_role"] is True
        assert value["target_bucket"] == "hl-mainnet-node-data"
        assert value["signing_region"] == "ap-northeast-1"
        assert value["object_key"] == "node_fills/hourly/20250727/8.lz4"
        assert value["object_size_bytes"] == 12726384
        assert value["object_etag"] == '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"'
        assert value["expected_compressed_sha256"] == "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622"
        assert value["expected_decompressed_byte_count"] == 62169139
        assert value["expected_nonempty_record_count"] == 162815
        assert value["maximum_one_time_budget_eur"] == 0.10
        assert value["maximum_monthly_budget_eur"] == 0
        assert value["maximum_get_object_requests"] == 1
        assert value["maximum_requests_per_object"] == 1
        assert value["maximum_total_compressed_bytes"] == 12726384
        assert value["maximum_total_decompressed_bytes"] == 134217728
        assert value["maximum_runtime_seconds"] == 120
        assert value["maximum_retries_per_request"] == 0
        assert value["head_object_authorized"] is False
        assert value["range_get_authorized"] is False
        assert value["list_objects_v2_authorized"] is False
        assert value["list_object_versions_authorized"] is False
        assert value["list_all_my_buckets_authorized"] is False
        assert value["http_redirect_following_authorized"] is False
        assert value["wallet_address_retention_authorized"] is True
        assert value["leading_string_value_retention_authorized"] is True
        assert value["per_wallet_fill_count_retention_authorized"] is True
        assert value["unique_wallet_count_retention_authorized"] is True
        assert value["wallet_address_normalization"] == "LOWERCASE_EXACT_0X40HEX"
        assert value["wallet_index_entry_cap"] == 162815
        assert value["wallet_index_output_byte_cap"] == 16777216
        assert value["retained_wallet_index_fields_only"] == ["wallet_address", "fill_count"]
        for key in (
            "raw_compressed_object_retention_authorized", "raw_decompressed_payload_retention_authorized",
            "record_payload_retention_authorized", "fill_object_retention_authorized",
            "payload_values_in_evidence_authorized", "coin_value_retention_authorized",
            "price_value_retention_authorized", "size_value_retention_authorized",
            "side_value_retention_authorized", "time_value_retention_authorized",
            "closed_pnl_value_retention_authorized", "fee_value_retention_authorized",
            "transaction_hash_retention_authorized", "order_id_retention_authorized",
            "trade_id_retention_authorized", "client_order_id_retention_authorized",
        ):
            assert value[key] is False, key
        assert all(flag is False for flag in value["downstream_authorizations"].values())
        assert all(flag is False for flag in value["trading_authorizations"].values())
        assert value["s3_requests_executed"] == 0
        assert value["compressed_bytes_downloaded"] == 0
        assert value["decompressed_bytes_processed"] == 0
        assert value["wallet_addresses_retained"] == 0
        assert value["empirical_result"] is None

    assert activation["requester_pays_authorized"] is True
    assert activation["get_object_authorized"] is True
    assert activation["object_body_download_authorized"] is True
    assert activation["decompression_authorized"] is True
    assert activation["wallet_index_reconstruction_authorized"] is True

    print("R7_ACTIVATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
