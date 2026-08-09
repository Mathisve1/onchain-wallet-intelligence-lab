from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R9 = ROOT / "research/archive_inventory/r9"
PREREG = R9 / "MODERN_WALLET_FEATURE_PILOT_R9_CONTRACT.json"
APPROVAL = R9 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001.json"
APPROVAL_TEXT = R9 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001.txt"
IMPLEMENTATION = R9 / "R9_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = R9 / "R9_AWS_ROLE_REUSE_ANALYSIS.json"
COLLECTOR = R9 / "collector.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-modern-wallet-feature-r9.yml"
RELEASE = R9 / "R9_EXECUTION_RELEASE.json"
ACTIVATION = R9 / "R9_EXECUTION_RELEASE_CANONICALIZATION.json"

PREREG_MERGE = "62ce0009c3c4aad70d2a91f242a690cd26ace355"
APPROVAL_MERGE = "332aa535b0de19a18befb8529450ae88acf35762"
APPROVAL_SHA = "1e4642ef2eef660f7971c2632864cf78894340e3408f15d15597e4eb12a04330"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
OBJECT_ARN = "arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/8.lz4"
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
    prereg = load(PREREG)
    approval = load(APPROVAL)
    impl = load(IMPLEMENTATION)
    reuse = load(ROLE_REUSE)
    workflow = WORKFLOW.read_text(encoding="utf-8")
    collector = COLLECTOR.read_text(encoding="utf-8")

    assert sha(APPROVAL_TEXT) == APPROVAL_SHA
    assert prereg["pilot_id"] == approval["pilot_id"] == impl["pilot_id"] == "HL-ARCHIVE-MODERN-WALLET-FEATURE-PILOT-R9-001"
    assert prereg["status"] == "PREREGISTERED_NO_EXECUTION"
    assert approval["reviewed_commit"] == PREREG_MERGE
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert approval["implementation_authorized"] is True
    assert approval["execution_authorized_by_this_record"] is False
    assert all(v is False for v in approval["current_runtime_authority"].values())

    assert impl["status"] == "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION"
    assert impl["r9_preregistration_merge_commit"] == PREREG_MERGE
    assert impl["approval_merge_commit"] == APPROVAL_MERGE
    assert impl["approval_text_sha256"] == APPROVAL_SHA
    assert impl["expected_canonical_implementation_commit"] == "PENDING_CANONICAL_IMPLEMENTATION_MERGE"
    assert impl["execution_release_present"] is False
    assert impl["canonical_activation_present"] is False
    assert impl["reused_dedicated_role_arn"] == ROLE_ARN
    assert impl["aws_iam_mutation_required"] is False
    assert impl["aws_iam_mutation_authorized"] is False
    assert impl["aws_iam_mutation_performed"] is False
    assert impl["session_s3_policy"] == "ALLOW_GETOBJECT_EXACT_R9_MODERN_FIXTURE_ONLY"
    assert impl["session_policy_strict_subset_of_persistent_role"] is True
    assert impl["object"] == {
        "key": "node_fills_by_block/hourly/20250727/8.lz4",
        "expected_size_bytes": 1517603,
        "expected_etag": '"60d4c1277f76651b5f04666bbe8d7594"',
        "expected_compressed_sha256": "928e1cd6bd7d69ad7243c263bacee48e53e4762ae9e99ef75f45007f6c0e6105",
        "expected_decompressed_byte_count": 7380378,
        "expected_top_level_block_record_count": 4345,
        "expected_valid_event_pair_count": 17516,
        "required_leading_string_regex": "^0x[0-9a-f]{40}$",
    }
    assert impl["selected_fill_fields_processed_transiently"] == ["coin", "side", "time", "px", "sz", "closedPnl", "tid", "crossed", "liquidation"]
    assert impl["wallet_feature_fields_only"] == FIELDS
    assert impl["wallet_address_normalization"] == "LOWERCASE_EXACT_0X40HEX"
    assert impl["decimal_output_encoding"] == "CANONICAL_BASE10_STRING_NO_EXPONENT"
    assert impl["selected_field_rules"]["exact_decimal_arithmetic_required"] is True
    assert impl["selected_field_rules"]["floating_point_aggregation_authorized"] is False
    assert impl["selected_field_rules"]["maximum_numeric_token_characters"] == 128
    assert all(v is True for v in impl["future_release_retention_authorizations"].values())
    assert all(v is False for v in impl["forbidden_retention_authorizations"].values())
    assert all(v is False for v in impl["semantic_boundaries"].values())
    assert all(v is False for v in impl["downstream_authorizations"].values())
    assert all(v is False for v in impl["current_runtime_authority"].values())
    assert all(v is False for v in impl["trading_authorizations"].values())
    assert impl["s3_requests_executed"] == 0
    assert impl["compressed_bytes_downloaded"] == 0
    assert impl["decompressed_bytes_processed"] == 0
    assert impl["wallet_feature_rows_created"] == 0
    assert impl["empirical_result"] is None

    assert reuse["reused_role_arn"] == ROLE_ARN
    assert reuse["workflow_name_required_for_reuse"] == "Hyperliquid Archive Hourly Body Schema Pilot R4"
    assert reuse["new_sts_preflight_required"] is False
    assert reuse["aws_iam_mutation_performed"] is False
    assert reuse["persistent_role_scope_expanded"] is False
    assert reuse["r9_session_scope"]["allowed_actions"] == ["s3:GetObject"]
    assert reuse["r9_session_scope"]["allowed_object_arns"] == [OBJECT_ARN]
    assert reuse["r9_session_scope"]["session_policy_strict_subset_of_persistent_role"] is True
    assert all(v is False for v in reuse["current_runtime_authority"].values())
    assert reuse["network_requests_executed"] == 0
    assert reuse["empirical_result"] is None

    assert "from research.archive_inventory.r8 import collector as r8a_transport" in collector
    assert "iter_lz4_frame" in collector
    assert "Decimal" in collector
    assert "floating" not in collector.lower() or "floating_point_aggregation_authorized" in collector
    assert "sum_closed_pnl_used_as_wallet_ranking_score" in collector
    assert "historical_multi_hour_ingestion_performed" in collector
    assert "candidate_shortlisting_performed" in collector

    assert WORKFLOW.is_file()
    assert "name: Hyperliquid Archive Hourly Body Schema Pilot R4" in workflow
    assert "run-name: R9 bounded modern wallet feature pilot" in workflow
    assert "workflow_dispatch:" in workflow
    assert "id-token: write" in workflow
    assert "persist-credentials: false" in workflow
    assert ROLE_ARN in workflow
    assert OBJECT_ARN in workflow
    assert '"Action":"s3:GetObject"' in workflow
    assert "R9_EXECUTION_RELEASE.json" in workflow
    assert "R9_EXECUTION_RELEASE_CANONICALIZATION.json" in workflow
    for filename in ("r9-context.json", "r9-result.json", "r9-wallet-features.ndjson", "r9.rc", "R9_FILES.sha256"):
        assert filename in workflow
    for forbidden in ("s3:ListBucket", "s3:GetObjectVersion", "s3:GetObjectAttributes", "s3:ListAllMyBuckets"):
        assert forbidden not in workflow
    assert workflow.index("Prove canonical R9 implementation and active release before AWS OIDC") < workflow.index("Assume unchanged dedicated AWS role with exact-one-object R9 session")
    assert workflow.index("Enforce R9 single-use release before AWS OIDC") < workflow.index("Assume unchanged dedicated AWS role with exact-one-object R9 session")

    if RELEASE.exists():
        release = load(RELEASE)
        assert release["release_id"] == "RELEASE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001"
        assert release["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
        assert release["execution_ready"] is False
        assert release["single_workflow_dispatch_authorized"] is False
        assert release["rerun_authorized"] is False
        assert release["s3_requests_executed"] == 0
        assert release["wallet_feature_rows_created"] == 0
        assert release["empirical_result"] is None
    assert not ACTIVATION.exists()

    print("R9_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
