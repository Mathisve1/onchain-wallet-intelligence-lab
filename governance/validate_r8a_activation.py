from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "research/archive_inventory/r8"
CANDIDATE = R8 / "R8A_EXECUTION_RELEASE.json"
ACTIVATION = R8 / "R8A_EXECUTION_RELEASE_CANONICALIZATION.json"
APPROVAL = R8 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.json"
APPROVAL_TEXT = R8 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.txt"
IMPLEMENTATION = R8 / "R8A_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = R8 / "R8A_AWS_ROLE_REUSE_ANALYSIS.json"
COLLECTOR = R8 / "collector.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-modern-wallet-index-r8a.yml"

R8_MERGE = "526f92cf3666c8bb616ecb61b6f9881387c1d7ed"
APPROVAL_MERGE = "6c011cb604dec1f169d42b02de4ae67f3f8f8395"
APPROVAL_SHA = "cb39246e2e5f345b14f87c15ac2c4d6aa993bcc9fbd28076f5f57eff94420e64"
IMPLEMENTATION_MERGE = "cb4f0e3272917aa27f53c85432107b21d2d242b9"
RELEASE_CANDIDATE_MERGE = "e98f7218682eaafbce1563d0bde3869b044d4476"
CANDIDATE_SHA = "e50a798bf46fdf5fdb7b808d87cb2f548b07eafda2fddbbec1f81d088805b935"


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
    assert approval["reviewed_commit"] == R8_MERGE
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert all(value is False for value in approval["current_runtime_authority"].values())

    assert sha(CANDIDATE) == CANDIDATE_SHA
    assert candidate["release_id"] == "RELEASE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001"
    assert candidate["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert candidate["execution_ready"] is False
    assert candidate["single_workflow_dispatch_authorized"] is False
    assert candidate["rerun_authorized"] is False
    assert candidate["s3_requests_executed"] == 0
    assert candidate["wallet_addresses_retained"] == 0
    assert candidate["empirical_result"] is None

    assert activation["release_id"] == candidate["release_id"]
    assert activation["pilot_id"] == candidate["pilot_id"] == "HL-ARCHIVE-MODERN-WALLET-INDEX-BRIDGE-R8A-001"
    assert activation["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R8A_RUN"
    assert activation["activation_model"] == "CANONICAL_PR_AND_BYTE_EXACT_TREE_BINDING"
    assert activation["r8_static_design_commit"] == candidate["r8_static_design_commit"] == R8_MERGE
    assert activation["approval_merge_commit"] == candidate["approval_merge_commit"] == APPROVAL_MERGE
    assert activation["approval_id"] == candidate["approval_id"] == approval["approval_id"]
    assert activation["approval_text_sha256"] == candidate["approval_text_sha256"] == APPROVAL_SHA
    assert activation["canonical_implementation_merge_commit"] == candidate["canonical_implementation_merge_commit"] == IMPLEMENTATION_MERGE
    assert activation["release_candidate_merge_commit"] == RELEASE_CANDIDATE_MERGE
    assert activation["candidate_sha256"] == CANDIDATE_SHA

    bindings = activation["implementation_byte_binding"]
    assert bindings["implementation_contract_sha256"] == sha(IMPLEMENTATION) == "f858e9888892205fdbd27a54205900b281585e0d683af586e3c6238109a6bff3"
    assert bindings["role_reuse_analysis_sha256"] == sha(ROLE_REUSE) == "327aea34b666178189a06220322a2b95e63d66dfc204a5b57f53a95d818cd4dc"
    assert bindings["collector_sha256"] == sha(COLLECTOR) == "0d5742807a92095b2bb7711c670cefe044e005a7dfbb440f60077c1d8a80a1d4"
    assert bindings["workflow_sha256"] == sha(WORKFLOW) == "3e4ef561e42034f9dcf7233b80ca14d3282ef9601caed49e32a15bd9c5059c65"
    assert bindings["pre_activation_implementation_validator_sha256"] == "ae7e09a6214b6b7d800edd9d9bbf71b812b10cf30c91a2c7cc61ebed6b56df7b"
    assert bindings["pre_activation_release_validator_sha256"] == "c8e36ff59a9c21527819b899dd4ea773ea23d6d59858624308798750fba451a7"

    assert impl["status"] == "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION"
    assert all(value is False for value in impl["current_runtime_authority"].values())
    assert reuse["aws_iam_mutation_performed"] is False
    assert reuse["new_sts_preflight_required"] is False

    assert activation["github_event_required"] == "workflow_dispatch"
    assert activation["canonical_dispatch_ref_required"] == "refs/heads/main"
    assert activation["canonical_dispatch_sha_source"] == "github.sha"
    start = datetime.fromisoformat(activation["single_use_window_start_utc"].replace("Z", "+00:00")).astimezone(timezone.utc)
    assert start == datetime(2026, 8, 9, 19, 46, tzinfo=timezone.utc)
    assert activation["single_workflow_dispatch_authorized"] is True
    assert activation["rerun_authorized"] is False
    assert activation["release_consumed"] is False

    for value in (candidate, activation):
        assert value["dedicated_role_arn"] == "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
        assert value["aws_role_mutation_required"] is False
        assert value["aws_role_mutation_authorized"] is False
        assert value["aws_role_mutation_performed"] is False
        assert value["session_s3_policy"] == "ALLOW_GETOBJECT_EXACT_R8A_MODERN_BOUNDARY_OBJECT_ONLY"
        assert value["session_policy_strict_subset_of_persistent_role"] is True
        assert value["target_bucket"] == "hl-mainnet-node-data"
        assert value["signing_region"] == "ap-northeast-1"
        assert value["object_key"] == "node_fills_by_block/hourly/20250727/8.lz4"
        assert value["object_size_bytes"] == 1517603
        assert value["object_etag"] == '"60d4c1277f76651b5f04666bbe8d7594"'
        assert value["expected_compressed_sha256"] == "928e1cd6bd7d69ad7243c263bacee48e53e4762ae9e99ef75f45007f6c0e6105"
        assert value["expected_decompressed_byte_count"] == 7380378
        assert value["expected_top_level_block_record_count"] == 4345
        assert value["maximum_one_time_budget_eur"] == 0.10
        assert value["maximum_monthly_budget_eur"] == 0
        assert value["maximum_get_object_requests"] == 1
        assert value["maximum_retries_per_request"] == 0
        assert value["wallet_address_retention_authorized"] is True
        assert value["per_wallet_fill_count_retention_authorized"] is True
        assert value["unique_wallet_count_retention_authorized"] is True
        assert value["valid_event_pair_count_retention_authorized"] is True
        assert value["retained_wallet_index_fields_only"] == ["wallet_address", "fill_count"]
        assert value["raw_compressed_object_retention_authorized"] is False
        assert value["raw_decompressed_payload_retention_authorized"] is False
        assert value["record_payload_retention_authorized"] is False
        assert value["fill_object_retention_authorized"] is False
        assert value["performance_field_values_retention_authorized"] is False
        assert all(flag is False for flag in value["downstream_authorizations"].values())
        assert all(flag is False for flag in value["trading_authorizations"].values())
        assert value["s3_requests_executed"] == 0
        assert value["compressed_bytes_downloaded"] == 0
        assert value["decompressed_bytes_processed"] == 0
        assert value["wallet_addresses_retained"] == 0
        assert value["empirical_result"] is None

    print("R8A_ACTIVATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
