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
APPROVAL = R8 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.json"
IMPLEMENTATION = R8 / "R8A_IMPLEMENTATION_CONTRACT.json"
R4_EVIDENCE = ROOT / "research/archive_inventory/r4/evidence/run-31313913525/r4-body-result.json"
R7_RESULT = ROOT / "research/archive_inventory/r7/evidence/run-31330248235/r7-result.json"
R7_INDEX = ROOT / "research/archive_inventory/r7/evidence/run-31330248235/r7-wallet-index.ndjson"

R7_EVIDENCE_MERGE = "7802d741f193671e50356c6001dcae149e0fc88a"
R4_EVIDENCE_MERGE = "fe06874aeeb958d375a27100378f89bd25b4741b"
R8_MERGE = "526f92cf3666c8bb616ecb61b6f9881387c1d7ed"
APPROVAL_MERGE = "6c011cb604dec1f169d42b02de4ae67f3f8f8395"
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

    assert design["study_id"] == "HL-WALLET-PERFORMANCE-COPYABILITY-DATA-DESIGN-R8-001"
    assert design["status"] == "STATIC_DESIGN_PREREGISTERED_NO_EXECUTION"
    assert design["parent_r7_evidence_commit"] == R7_EVIDENCE_MERGE
    assert design["parent_r7_run_id"] == 31330248235
    assert design["parent_r7_unique_wallet_count"] == 4637
    assert design["parent_r7_sum_fill_count"] == 162815
    assert design["network_requests_executed_by_r8"] == 0
    assert design["wallets_ranked_by_r8"] == 0
    assert design["empirical_result"] is None
    assert all(value is False for value in design["current_authority"].values())
    assert all(value is False for value in design["trading_authorizations"].values())

    semantic = design["semantic_boundaries"]
    assert semantic["closed_pnl_sum_is_exact_account_return"] is False
    assert semantic["fee_must_not_be_blindly_subtracted_from_closed_pnl_without_formula_proof"] is True
    assert semantic["crossed_maker_taker_semantics_proven"] is False
    assert semantic["one_wallet_address_equals_one_human_or_economic_entity"] is False
    assert semantic["portfolio_graphs_are_precise_accounting"] is False
    assert [row["stage"] for row in design["proposed_research_pipeline"]] == [
        "A_GLOBAL_ARCHIVE_SCREEN",
        "B_CANDIDATE_REDUCTION",
        "C_SHORTLIST_PUBLIC_API_ENRICHMENT",
        "D_COPYABILITY_EXECUTION_RESEARCH",
    ]
    assert design["api_scaling_constraint"]["per_address_user_fills_is_not_primary_population_scan"] is True
    assert design["api_scaling_constraint"]["shortlist_first_required"] is True

    # Immutable R8A preregistration remains non-self-authorizing after later approval/implementation.
    assert bridge["pilot_id"] == "HL-ARCHIVE-MODERN-WALLET-INDEX-BRIDGE-R8A-001"
    assert bridge["status"] == "PREREGISTERED_NO_EXECUTION"
    assert bridge["parent_r7_evidence_commit"] == R7_EVIDENCE_MERGE
    assert bridge["parent_r4_evidence_commit"] == R4_EVIDENCE_MERGE
    assert bridge["parent_r4_run_id"] == 31313913525
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
    assert envelope["maximum_retries_per_request"] == 0
    assert envelope["http_redirect_following_authorized"] is False
    assert envelope["head_object_authorized"] is False
    assert envelope["range_get_authorized"] is False
    assert envelope["list_objects_v2_authorized"] is False

    shape = bridge["required_modern_block_shape"]
    assert shape["top_level_record_type"] == "object"
    assert shape["required_fields"] == {"local_time":"string","block_time":"string","block_number":"integer","events":"array"}
    assert shape["expected_top_level_block_record_count"] == 4345
    assert shape["event_pair_required_type"] == "array"
    assert shape["event_pair_required_arity"] == 2
    assert shape["event_pair_required_ordered_element_types"] == ["string", "object"]
    assert shape["required_leading_string_pattern"] == "^0x[0-9a-f]{40}$"

    retention = bridge["proposed_future_retention_boundary"]
    assert retention["wallet_address_retention_authorized"] is True
    assert retention["leading_string_value_retention_authorized"] is True
    assert retention["per_wallet_fill_count_retention_authorized"] is True
    assert retention["unique_wallet_count_retention_authorized"] is True
    assert retention["valid_event_pair_count_retention_authorized"] is True
    assert retention["retained_wallet_index_fields_only"] == ["wallet_address", "fill_count"]
    for key, value in retention.items():
        if key.endswith("_retention_authorized") and key not in {
            "wallet_address_retention_authorized", "leading_string_value_retention_authorized",
            "per_wallet_fill_count_retention_authorized", "unique_wallet_count_retention_authorized",
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
    assert derivation["parent_commit"] == R7_EVIDENCE_MERGE
    assert derivation["parent_run_id"] == 31330248235
    assert derivation["facts_carried_forward"]["unique_wallet_count"] == 4637
    assert derivation["facts_carried_forward"]["sum_fill_count"] == 162815
    assert sources["study_id"] == design["study_id"]

    report = REPORT.read_text(encoding="utf-8")
    status = STATUS.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    assert "STATIC_PERFORMANCE_COPYABILITY_DATA_DESIGN_COMPLETE_MODERN_BRIDGE_REQUIRED" in report
    assert "HUMAN APPROVED" in status
    assert "APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001" in template
    assert "retained_wallet_index_fields_only=wallet_address,fill_count" in template
    assert "historical_multi_hour_ingestion_authorized=false" in template
    assert "wallet_ranking_authorized=false" in template
    assert "pnl_or_alpha_analysis_authorized=false" in template

    # Later-stage snapshots may exist only if they stay inert; release/activation still must not exist here.
    if APPROVAL.exists():
        approval = load(APPROVAL)
        assert approval["reviewed_commit"] == R8_MERGE
        assert all(value is False for value in approval["current_runtime_authority"].values())
    if IMPLEMENTATION.exists():
        impl = load(IMPLEMENTATION)
        assert APPROVAL.exists()
        assert impl["approval_merge_commit"] == APPROVAL_MERGE
        assert impl["status"] == "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION"
        assert all(value is False for value in impl["current_runtime_authority"].values())
        assert impl["s3_requests_executed"] == 0
        assert impl["wallet_addresses_retained"] == 0
        assert impl["empirical_result"] is None
    release_path = R8 / "R8A_EXECUTION_RELEASE.json"
    if release_path.exists():
        release = load(release_path)
        assert release["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
        assert release["execution_ready"] is False
        assert release["single_workflow_dispatch_authorized"] is False
        assert release["s3_requests_executed"] == 0
        assert release["wallet_addresses_retained"] == 0
        assert release["empirical_result"] is None
    activation_path = R8 / "R8A_EXECUTION_RELEASE_CANONICALIZATION.json"
    if activation_path.exists():
        activation = load(activation_path)
        assert activation["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R8A_RUN"
        assert activation["single_workflow_dispatch_authorized"] is True
        assert activation["rerun_authorized"] is False
        assert activation["release_consumed"] is False
        assert activation["s3_requests_executed"] == 0
        assert activation["wallet_addresses_retained"] == 0
        assert activation["empirical_result"] is None

    print("R8_STATIC_DESIGN_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
