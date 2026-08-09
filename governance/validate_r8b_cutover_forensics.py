from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8B = ROOT / "research/archive_inventory/r8b"
CONTRACT = R8B / "CUTOVER_FORENSICS_R8B_CONTRACT.json"
ANALYSIS = R8B / "METADATA_BOUNDARY_ANALYSIS.json"
SOURCES = R8B / "OFFICIAL_SOURCE_EVIDENCE.json"
REPORT = R8B / "LEGACY_MODERN_CUTOVER_FORENSICS_REPORT.md"

R3 = ROOT / "research/archive_inventory/r3/evidence/run-31299905850/R3_COMPACT_INVENTORY_SUMMARY.json"
R7 = ROOT / "research/archive_inventory/r7/evidence/run-31330248235/r7-result.json"
R8A = ROOT / "research/archive_inventory/r8/evidence/run-31333421763/r8a-result.json"
COMPARE = ROOT / "research/archive_inventory/r8/evidence/R8A_LEGACY_MODERN_BRIDGE_COMPARISON.json"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    c = load(CONTRACT)
    a = load(ANALYSIS)
    s = load(SOURCES)
    r3 = load(R3)
    r7 = load(R7)
    r8a = load(R8A)
    cmp = load(COMPARE)
    report = REPORT.read_text(encoding="utf-8")

    assert c["study_id"] == a["study_id"] == s["study_id"] == "HL-ARCHIVE-LEGACY-MODERN-CUTOVER-FORENSICS-R8B-001"
    assert c["status"] == "STATIC_FORENSICS_COMPLETE_NO_EXECUTION"
    assert c["parent_r8a_evidence_commit"] == "04c23127a553c53e9c3c9b80dabb4a9b7e61de61"
    assert c["parent_r7_evidence_commit"] == "7802d741f193671e50356c6001dcae149e0fc88a"
    assert c["parent_r3_evidence_commit"] == "98eca5b7b13b25aed3d11f006972acea2ee5c258"
    assert c["network_requests_executed"] == 0
    assert c["new_s3_requests_executed"] == 0
    assert c["new_requester_pays_cost_eur"] == 0

    families = {row["dataset_family_id"]: row for row in r3["family_summaries"]}
    assert families["node_fills"]["latest_path_hour_utc"] == "2025-07-27T08:00:00Z"
    assert families["node_fills_by_block"]["earliest_path_hour_utc"] == "2025-07-27T08:00:00Z"
    assert families["node_fills_by_block"]["minimum_object_size_bytes"] == 1517603
    assert families["node_fills_by_block"]["entry_count"] == 9070
    assert r3["transition_analysis"]["delta_hours_modern_start_minus_legacy_end"] == 0

    assert a["family_boundary"]["same_path_hour_boundary"] is True
    assert a["modern_boundary_object"]["size_bytes"] == 1517603
    assert a["modern_boundary_object"]["is_family_global_minimum"] is True
    assert a["modern_boundary_object"]["global_minimum_rank"] == 1
    assert a["modern_boundary_object"]["next_path_hour_size_bytes"] == 18147822
    assert abs(a["modern_boundary_object"]["boundary_to_next_hour_size_ratio"] - 0.083624525301) < 1e-12
    assert a["legacy_boundary_object"]["size_bytes"] == 12726384
    assert a["legacy_boundary_object"]["previous_path_hour_size_bytes"] == 13078775
    assert abs(a["legacy_boundary_object"]["boundary_to_previous_hour_size_ratio"] - 0.973056268649) < 1e-12

    assert r7["wallet_index_summary"]["sum_fill_count"] == a["boundary_body_counts"]["legacy_valid_fill_records"] == 162815
    assert r7["wallet_index_summary"]["unique_wallet_count"] == a["boundary_body_counts"]["legacy_unique_wallets"] == 4637
    assert r8a["wallet_index_summary"]["valid_event_pair_count"] == a["boundary_body_counts"]["modern_valid_event_pairs"] == 17516
    assert r8a["wallet_index_summary"]["unique_wallet_count"] == a["boundary_body_counts"]["modern_unique_wallets"] == 887

    assert cmp["overlapping_wallet_count"] == a["address_set_comparison"]["overlapping_wallet_count"] == 688
    assert cmp["modern_only_wallet_count"] == a["address_set_comparison"]["modern_only_wallet_count"] == 199
    assert cmp["legacy_only_wallet_count"] == a["address_set_comparison"]["legacy_only_wallet_count"] == 3949
    assert cmp["modern_address_set_subset_of_legacy"] is False
    assert a["address_set_comparison"]["modern_address_set_subset_of_legacy"] is False

    assert s["source_policy"] == "PRIMARY_OFFICIAL_SOURCES_ONLY"
    by_id = {row["source_id"]: row for row in s["sources"]}
    assert by_id["HL-NODE-WRITE-FILLS-COMMIT"]["commit"] == "c4933f2273e4dfca6915971229d22149712641e0"
    assert by_id["HL-NODE-WRITE-FILLS-COMMIT"]["commit_date_utc"] < "2025-07-27T00:00:00Z"
    assert by_id["HL-NODE-BATCH-BY-BLOCK-COMMIT"]["commit"] == "247aea04898c23f2cd8948ad0e70a5f47d8b43bc"
    assert by_id["HL-NODE-BATCH-BY-BLOCK-COMMIT"]["commit_date_utc"] < "2025-07-27T00:00:00Z"
    assert s["historical_predate_checks"]["write_fills_documentation_predates_boundary"] is True
    assert s["historical_predate_checks"]["batch_by_block_documentation_predates_boundary"] is True

    interp = c["interpretation"]
    assert interp["classification"] == "HIGH_CONFIDENCE_WITHIN_HOUR_FORMAT_CUTOVER_OR_SEPARATE_BOUNDARY_COVERAGE_INFERENCE"
    assert interp["direct_serializer_cutover_proven"] is False
    assert interp["exact_temporal_partition_proven"] is False
    assert interp["exact_fill_overlap_or_gap_proven"] is False

    rule = c["canonical_cross_format_rule"]
    assert rule["rule_id"] == "CUTOVER_CENSOR_HOUR_20250727_08"
    assert rule["boundary_hour_status"] == "INTENTIONALLY_CENSORED_FROM_CANONICAL_CROSS_FORMAT_HISTORY"
    assert rule["legacy_last_format_boundary_unambiguous_path_hour_utc"] == "2025-07-27T07:00:00Z"
    assert rule["modern_first_format_boundary_unambiguous_path_hour_utc"] == "2025-07-27T09:00:00Z"
    assert rule["include_legacy_boundary_hour"] is False
    assert rule["include_modern_boundary_hour"] is False
    assert rule["double_count_boundary_hour"] is False
    assert rule["claim_continuous_market_time_history"] is False

    assert c["next_research_implication"]["exact_transition_hour_temporal_fingerprint_required_now"] is False
    assert all(v is False for v in c["current_authority"].values())
    assert all(v is False for v in c["trading_authorizations"].values())
    assert "transition-censored" in report
    assert "do not need another paid request" in report
    print("R8B_CUTOVER_FORENSICS_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
