from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
REPORT = BASE / "r10d_evidence/R10D_BACKWARD_CONSISTENCY.json"
RESULT = BASE / "r10d_evidence/run-31420197671/r10d-result.json"
DIAGNOSTICS = BASE / "r10d_evidence/R10D_AGGREGATE_DIAGNOSTICS.json"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def validate_report(report: dict, result: dict, diagnostics: dict) -> None:
    assert report["schema_version"] == "1.0"
    assert report["report_id"] == "R10D-BACKWARD-CONSISTENCY-AFTER-R11-IDENTITY-AUDIT-001"
    assert report["status"] == "OFFLINE_REVIEW_COMPLETE_R10D_CANONICAL_IDENTITY_UNRESOLVED"

    source = report["source_basis"]
    assert source["canonical_r10d_run_id"] == 31420197671
    assert source["canonical_r10d_job_id"] == 93558813495
    assert source["canonical_r10d_artifact_id"] == 9075129362
    assert source["canonical_r10d_dispatch_sha"] == "c3e893da2e25d993250258f9b4b81aa5ad332e77"
    assert source["canonical_r10d_evidence_merge_commit"] == "0b13a80235ecd43bcd220985383f79f8ccbfb6ca"
    assert source["artifact_zip_sha256"] == "4e63afc141f98ee05030ce19effc88f3bbd1eab59796c716a5d3c671eb2476ae"

    classification = report["backward_consistency_classification"]
    assert classification["classification"] == "C_R10D_UNCERTAIN_UNDER_CANONICAL_IDENTITY"
    assert classification["scope"] == "CANONICAL_UNIQUE_BLOCK_AND_WALLET_USER_FILL_SEMANTICS"
    assert classification["option_a_exact_reproduction_proven"] is False
    assert classification["option_b_demonstrable_correction_proven"] is False
    assert classification["option_c_r10d_uncertain"] is True

    assert result["terminal_status"] == "R10D_MULTI_HOUR_FEATURE_REPAIR_STUDY_COMPLETE"
    assert result["technical_result"] == result["research_conclusion"] == "R10D_MULTI_HOUR_FEATURE_PIPELINE_COMPLETE"
    assert result["completed_hour_count"] == 6
    assert result["request_attempt_count"] == result["s3_http_request_count"] == result["successful_request_count"] == 6
    assert result["failed_request_count"] == result["retries_used"] == 0
    assert result["http_redirects_followed"] is False
    assert result["record_anchored_rule_id"] == "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1"
    assert result["numeric_tolerance_authorized"] is False

    hours = result["per_hour_summaries"]
    assert len(hours) == 6
    assert all(row["record_anchored_alignment_violation_count"] == 0 for row in hours)
    assert all(row["fill_time_after_path_hour_count"] == 0 for row in hours)
    assert all(
        row["local_path_block_path_record_count"] + row["local_path_block_previous_record_count"]
        == row["block_record_count"]
        for row in hours
    )
    assert all(
        row["fill_time_before_path_hour_count"]
        + row["fill_time_inside_path_hour_count"]
        + row["fill_time_after_path_hour_count"]
        == row["event_pair_count"]
        for row in hours
    )

    observed = {
        "terminal_status": result["terminal_status"],
        "technical_result": result["technical_result"],
        "completed_hour_count": result["completed_hour_count"],
        "request_attempt_count": result["request_attempt_count"],
        "successful_request_count": result["successful_request_count"],
        "failed_request_count": result["failed_request_count"],
        "retries_used": result["retries_used"],
        "http_redirects_followed": result["http_redirects_followed"],
        "total_compressed_bytes": result["total_compressed_bytes"],
        "total_decompressed_bytes": result["total_decompressed_bytes"],
        "block_record_observation_count": sum(row["block_record_count"] for row in hours),
        "path_block_record_observation_count": sum(row["local_path_block_path_record_count"] for row in hours),
        "previous_block_record_observation_count": sum(row["local_path_block_previous_record_count"] for row in hours),
        "event_pair_observation_count": sum(row["event_pair_count"] for row in hours),
        "before_path_hour_observation_count": sum(row["fill_time_before_path_hour_count"] for row in hours),
        "inside_path_hour_observation_count": sum(row["fill_time_inside_path_hour_count"] for row in hours),
        "after_path_hour_observation_count": sum(row["fill_time_after_path_hour_count"] for row in hours),
        "record_anchored_alignment_violation_count": sum(row["record_anchored_alignment_violation_count"] for row in hours),
        "record_anchored_rule_id": result["record_anchored_rule_id"],
        "numeric_tolerance_authorized": result["numeric_tolerance_authorized"],
    }
    assert report["retained_mechanics_result"] == observed

    summary = result["aggregate_wallet_feature_summary"]
    legacy = report["retained_legacy_wallet_aggregate"]
    assert summary["wallet_feature_row_count"] == diagnostics["wallet_feature_row_count"] == legacy["wallet_feature_row_count"] == 16410
    assert summary["sum_fill_count"] == diagnostics["sum_fill_count"] == legacy["sum_fill_count"] == 1486542
    assert summary["sum_side_count"] == diagnostics["sum_side_count"] == legacy["sum_side_count"] == 1486542
    assert summary["duplicate_wallet_tid_count"] == diagnostics["duplicate_tid_count_total"] == legacy["duplicate_wallet_typed_tid_repeat_count"] == 0
    assert summary["wallet_feature_bytes"] == diagnostics["wallet_feature_bytes"] == legacy["wallet_feature_bytes"] == 6557323
    assert summary["wallet_feature_sha256"] == diagnostics["wallet_feature_sha256"] == legacy["wallet_feature_sha256"]
    assert legacy["active_hour_count_distribution"] == diagnostics["active_hour_count_distribution"]
    assert legacy["crossed_true_count_total"] == diagnostics["crossed_true_count_total"]
    assert legacy["liquidation_associated_fill_count_total"] == diagnostics["liquidation_associated_fill_count_total"]
    assert legacy["sum_abs_px_times_sz_notional_proxy_total"] == diagnostics["sum_abs_px_times_sz_notional_proxy_total"]
    assert legacy["sum_closed_pnl_fill_statistic_total"] == diagnostics["sum_closed_pnl_fill_statistic_total"]
    assert legacy["semantic_status"] == "HISTORICAL_LEGACY_OBSERVATION_AGGREGATE_NOT_CANONICAL_UNIQUE_FILL_LEDGER"

    recomputed = report["offline_artifact_recomputation"]
    assert recomputed["status"] == "PROVEN_BYTE_EXACT_FOR_RETAINED_LEGACY_OUTPUT"
    assert recomputed["provider_zip_reconstructed_from_canonical_repository_parts"] is True
    assert recomputed["provider_zip_sha256_reproduced"] == source["artifact_zip_sha256"]
    assert recomputed["wallet_feature_file_sha256_reproduced"] == legacy["wallet_feature_sha256"]
    assert recomputed["unique_sorted_lowercase_wallet_rows_recomputed"] == legacy["wallet_feature_row_count"]
    assert recomputed["fill_count_sum_recomputed"] == recomputed["side_count_sum_recomputed"] == 1486542
    assert recomputed["legacy_duplicate_wallet_typed_tid_sum_recomputed"] == 0
    assert recomputed["active_hour_count_distribution_recomputed"] == legacy["active_hour_count_distribution"]
    assert recomputed["notional_proxy_total_recomputed_exact_decimal"] == legacy["sum_abs_px_times_sz_notional_proxy_total"]
    assert recomputed["closed_pnl_fill_statistic_total_recomputed_exact_decimal"] == legacy["sum_closed_pnl_fill_statistic_total"]
    assert recomputed["meaning"] == "EXACT_REPRODUCTION_OF_RETAINED_LEGACY_REDUCER_OUTPUT_NOT_RECOMPUTATION_FROM_RAW_OBJECTS_UNDER_NEW_IDENTITY"

    assumption = report["legacy_identity_assumption"]
    assert assumption["key"] == ["wallet_address", "normalized_typed_tid"]
    assert assumption["empirical_r10d_repeat_result"] == "ZERO_REPEATS_IN_EXACT_SIX_HOUR_RUN"
    assert assumption["canonical_identity_status"] == "SUPERSEDED_AS_SEMANTIC_EVENT_IDENTITY"

    assert report["canonical_identity_model_under_review"] == {
        "raw_observation_key": [
            "object_key",
            "verified_compressed_sha256",
            "record_ordinal",
            "event_ordinal",
        ],
        "archive_block_locator": "block_number",
        "archive_block_equality_invariants": [
            "exact_block_time",
            "ordered_event_fingerprint",
        ],
        "protocol_matched_trade_key": [
            "exact_block_time",
            "canonical_coin",
            "validated_integer_tid",
        ],
        "wallet_user_fill_key": [
            "canonical_lowercase_wallet",
            "exact_block_time",
            "canonical_coin",
            "validated_integer_tid",
        ],
    }

    matrix = report["evidence_matrix"]
    assert matrix["legacy_wallet_typed_tid_repeat_count_zero"] == "PROVEN_FOR_R10D_RUN"
    assert matrix["wallet_plus_tid_is_semantically_valid_identity"] == "DISPROVEN"
    for key in (
        "canonical_unique_block_count_equals_block_record_observation_count",
        "canonical_unique_wallet_fill_count_equals_1486542",
        "r10d_contains_cross_object_exact_block_replay",
        "new_identity_model_exactly_reproduces_r10d_wallet_rows",
        "new_identity_model_demonstrably_corrects_r10d_wallet_rows",
        "source_path_active_hour_counts_equal_event_time_active_hour_counts",
        "all_r10d_tids_are_json_integer_uint50",
    ):
        assert matrix[key] == "UNKNOWN", key

    consequences = report["scientific_consequences"]
    assert consequences["historical_r10d_evidence_must_not_be_rewritten"] is True
    assert consequences["r10d_transport_and_alignment_evidence_remains_valid"] is True
    assert consequences["r10d_counts_must_be_labelled_source_observations"] is True
    assert consequences["r10d_wallet_aggregate_must_be_labelled_legacy_weak_identity"] is True
    assert consequences["economic_or_global_uniqueness_interpretation_authorized"] is False
    assert consequences["backward_recomputation_requires_occurrence_level_identity_and_block_provenance"] is True
    assert consequences["r11a_exact_72_object_diagnostic_does_not_include_r10d_six_objects"] is True
    assert consequences["full_r10d_identity_backcompat_requires_separate_same_six_object_preregistration_approval_and_release"] is True
    assert consequences["next_permitted_empirical_source"] == "SEPARATELY_APPROVED_SAME_SIX_OBJECT_R10D_IDENTITY_BACKCOMPAT_DIAGNOSTIC"

    assert all(value is False for value in report["execution_and_downstream_boundaries"].values())
    assert all(value is False for value in diagnostics["interpretation_boundaries"].values())
    assert all(value is False for value in diagnostics["downstream_actions_performed"].values())


def main() -> int:
    validate_report(load(REPORT), load(RESULT), load(DIAGNOSTICS))
    print("R10D_BACKWARD_CONSISTENCY_VALID_C_UNCERTAIN_UNDER_CANONICAL_IDENTITY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
