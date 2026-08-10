from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RUN = BASE / "r10c_evidence/run-31410638224"
ATTEST = BASE / "r10c_evidence/HL-ARCHIVE-R10C-BOUNDARY-RECORD-CORRELATION-001-ATTESTATION.json"
CONSUMPTION = BASE / "r10c_runtime/R10C_EXECUTION_RELEASE_CONSUMPTION.json"
RELEASE = BASE / "r10c_runtime/R10C_EXECUTION_RELEASE.json"

ARTIFACT_SHA = "60602f1e5b4e5456504af9bbd65b64826cdf2b86a47bc1b2e690507dbf0a0f48"
LEDGER = {
    "r10c-context.json": "b4f0b96aedafa92ecd188ec06fc5c93be6006b84b76bd8a893ae4d32e7bedc42",
    "r10c-result.json": "c86f606c18f26274b3fed1ba985c53ce7e88681cabf052c101574f7c776973fe",
    "r10c.rc": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
}
RESULT = "EXACT_TWO_PRE_HOUR_FILLS_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    context = load(RUN / "r10c-context.json")
    result = load(RUN / "r10c-result.json")
    verification = load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
    attest = load(ATTEST)
    consumption = load(CONSUMPTION)
    release = load(RELEASE)

    observed = {}
    for line in (RUN / "R10C_FILES.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        observed[name] = digest
    assert observed == LEDGER
    for name, digest in LEDGER.items():
        assert hashlib.sha256((RUN / name).read_bytes()).hexdigest() == digest
        assert verification["internal_ledger"][name] == digest

    assert (RUN / "r10c.rc").read_text(encoding="utf-8") == "0\n"
    assert context["workflow_run_id"] == 31410638224
    assert context["workflow_run_attempt"] == 1
    assert context["dispatch_sha"] == "07f988af8db67addf5d551b5b402186c0abafadb"
    assert context["checked_out_commit"] == context["dispatch_sha"]
    assert context["dispatch_ref"] == "refs/heads/main"
    assert context["configure_aws_outcome"] == "success"
    assert context["maximum_get_object_requests"] == 1
    assert context["maximum_retries_per_request"] == 0
    assert context["metadata_prefix_processing_authorized"] is True
    assert context["event_array_contents_inspection_scope"] == "PAIR_SHAPE_AND_FILL_TIME_ONLY"
    assert context["fill_object_field_allowlist"] == ["time"]
    assert context["aggregate_boundary_correlation_retention_authorized"] is True
    assert context["metadata_timezone_parsing_authorized"] is False
    assert context["metadata_timezone_inference_authorized"] is False
    assert context["wallet_address_retention_authorized"] is False
    assert context["economic_fill_field_processing_authorized"] is False

    assert result["terminal_status"] == "R10C_BOUNDARY_RECORD_CORRELATION_COMPLETE"
    assert result["technical_result"] == result["research_conclusion"] == RESULT
    assert result["request_attempt_count"] == result["s3_http_request_count"] == 1
    assert result["successful_request_count"] == 1 and result["failed_request_count"] == 0
    assert result["retries_used"] == 0 and result["http_redirects_followed"] is False
    assert result["total_compressed_bytes"] == 18147822
    assert result["total_decompressed_bytes"] == 90089570
    assert result["aggregate_boundary_correlation_retained"] is True
    assert result["event_array_contents_inspected"] is True
    assert result["event_pair_shape_inspection_performed"] is True
    assert result["fill_time_processing_performed"] is True
    assert result["metadata_prefix_processing_performed"] is True

    s = result["diagnostic_summary"]
    assert s["boundary_record_correlation_classification"] == RESULT
    assert s["compressed_sha256"] == "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339"
    assert s["block_record_count"] == 36029
    assert s["event_pair_count"] == s["fill_time_count"] == 223950
    assert s["fill_time_before_path_hour_count"] == 2
    assert s["fill_time_inside_path_hour_count"] == 223948
    assert s["fill_time_after_path_hour_count"] == 0
    assert s["block_record_count_with_any_before_fill"] == 1
    cross = "MATCHES_PATH_DATE_HOUR_PREFIX|MATCHES_PREVIOUS_DATE_HOUR_PREFIX"
    path = "MATCHES_PATH_DATE_HOUR_PREFIX|MATCHES_PATH_DATE_HOUR_PREFIX"
    assert s["block_record_counts_by_local_prefix_and_block_prefix"][cross] == 1
    assert s["block_record_counts_by_local_prefix_and_block_prefix"][path] == 36028
    assert s["block_records_with_before_fill_by_local_prefix_and_block_prefix"][cross] == 1
    assert s["fill_counts_by_local_prefix_block_prefix_and_fill_partition"][cross + "|BEFORE_PATH_HOUR"] == 2
    assert s["fill_counts_by_local_prefix_block_prefix_and_fill_partition"][path + "|BEFORE_PATH_HOUR"] == 0
    assert s["fill_counts_by_local_prefix_block_prefix_and_fill_partition"][path + "|INSIDE_PATH_HOUR"] == 223948

    for key in (
        "metadata_timezone_parsing_performed", "metadata_timezone_inference_performed",
        "metadata_datetime_conversion_performed", "individual_metadata_value_retained",
        "individual_fill_time_retained", "leading_event_string_value_retained",
        "leading_event_string_wallet_semantics_performed", "wallet_address_retained",
        "wallet_aggregation_performed", "economic_fill_field_processing_performed",
        "block_number_value_retained", "per_block_identity_retained",
        "raw_compressed_object_retained", "raw_decompressed_object_retained",
        "raw_block_record_retained", "raw_event_pair_retained", "r10_rule_amendment_performed",
        "r10_rerun_performed", "six_hour_execution_performed", "wallet_ranking_performed",
        "candidate_shortlisting_performed", "pnl_or_alpha_analysis_performed",
        "copyability_analysis_performed", "market_data_ingested", "strategy_inference_performed",
    ):
        assert result[key] is False, key

    assert verification["provider_zip_sha256"] == ARTIFACT_SHA
    assert verification["independently_downloaded_zip_sha256"] == ARTIFACT_SHA
    assert verification["provider_digest"] == f"sha256:{ARTIFACT_SHA}"
    assert verification["provider_digest_matches_independent_download"] is True
    assert verification["internal_ledger_matches_all_retained_files"] is True
    assert verification["job_conclusion"] == "success"
    assert verification["workflow_job_id"] == 93527564608
    assert verification["artifact_id"] == 9071422220
    assert verification["artifact_size_bytes"] == 2912

    assert attest["status"] == "ATTESTED_COMPLETE_" + RESULT
    assert attest["workflow_run_id"] == 31410638224
    assert attest["workflow_job_id"] == 93527564608
    assert attest["artifact_id"] == 9071422220
    assert attest["artifact_zip_sha256"] == ARTIFACT_SHA
    assert attest["release_consumed"] is True and attest["rerun_authorized"] is False
    assert attest["claims_proven"]["both_pre_hour_fills_colocate_in_that_single_cross_prefix_record"] is True
    assert attest["claims_not_proven"]["cross_prefix_pattern_generalizes_to_other_hours_or_dates"] is False
    assert attest["claims_not_proven"]["a_51ms_fill_time_tolerance_is_safe_for_general_history"] is False
    assert attest["claims_not_proven"]["r10_rule_should_be_amended_without_further_preregistration"] is False
    assert attest["r10_rule_amendment_authorized"] is False
    assert attest["six_hour_execution_authorized"] is False

    assert consumption["status"] == "CONSUMED_SUCCESS_" + RESULT
    assert consumption["release_consumed"] is True
    assert consumption["future_r10c_dispatch_authorized"] is False
    assert consumption["rerun_authorized"] is False
    assert consumption["remaining_get_object_budget_from_consumed_release"] == 0
    assert consumption["new_network_request_requires_new_preregistration_approval_and_release"] is True
    assert all(v is False for v in consumption["downstream_authorizations"].values())
    assert all(v is False for v in consumption["trading_authorizations"].values())

    assert release["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10C_RUN"
    assert release["release_consumed"] is False
    assert release["rerun_authorized"] is False

    print("R10C_EXECUTION_EVIDENCE_VALID_" + RESULT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
