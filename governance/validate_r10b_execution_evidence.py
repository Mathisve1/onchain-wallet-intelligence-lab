from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RUN = BASE / "r10b_evidence/run-31395720147"
ATTEST = BASE / "r10b_evidence/HL-ARCHIVE-R10B-BATCH-METADATA-LEXICAL-DIAGNOSTIC-001-ATTESTATION.json"
CONSUMPTION = BASE / "r10b_runtime/R10B_EXECUTION_RELEASE_CONSUMPTION.json"
RELEASE = BASE / "r10b_runtime/R10B_EXECUTION_RELEASE.json"

ARTIFACT_SHA = "6fe553710846794176bc040c87937a719ab83c0cb10101892b3f23749cefc789"
LEDGER = {
    "r10b-context.json": "40d80eae46a2619346b60b3b7ccb2cba874a2deb33e73235a5e1a9a2718d3bb9",
    "r10b-result.json": "2cd8a282453481c567ae58996e6c8131b5bd485bf8e3c2678f1333a588dda7d9",
    "r10b.rc": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
}


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    context = load(RUN / "r10b-context.json")
    result = load(RUN / "r10b-result.json")
    verification = load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
    attest = load(ATTEST)
    consumption = load(CONSUMPTION)
    release = load(RELEASE)

    observed: dict[str, str] = {}
    for line in (RUN / "R10B_FILES.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        observed[name] = digest
    assert observed == LEDGER
    for name, digest in LEDGER.items():
        computed = hashlib.sha256((RUN / name).read_bytes()).hexdigest()
        assert computed == digest, (name, computed, digest)
        assert verification["internal_ledger"][name] == digest

    assert (RUN / "r10b.rc").read_text(encoding="utf-8") == "0\n"
    assert context["workflow_run_id"] == 31395720147
    assert context["workflow_run_attempt"] == 1
    assert context["dispatch_sha"] == "de5f6ff5aabcb40650fa8c1f9b94dd305e9ff556"
    assert context["checked_out_commit"] == context["dispatch_sha"]
    assert context["dispatch_ref"] == "refs/heads/main"
    assert context["configure_aws_outcome"] == "success"
    assert context["expected_account_id"] == "630956766927"
    assert context["maximum_get_object_requests"] == 1
    assert context["maximum_retries_per_request"] == 0
    assert context["metadata_lexical_processing_authorized"] is True
    assert context["aggregate_lexical_retention_authorized"] is True
    for key in (
        "timezone_parsing_authorized", "timezone_inference_authorized",
        "datetime_conversion_authorized", "event_array_contents_inspection_authorized",
        "wallet_address_retention_authorized", "economic_fill_field_processing_authorized",
    ):
        assert context[key] is False, key

    assert result["terminal_status"] == "R10B_BATCH_METADATA_LEXICAL_DIAGNOSTIC_COMPLETE"
    assert result["technical_result"] == "BATCH_METADATA_LEXICALLY_CROSSES_PATH_HOUR"
    assert result["research_conclusion"] == "BATCH_METADATA_LEXICALLY_CROSSES_PATH_HOUR"
    assert result["request_attempt_count"] == 1
    assert result["s3_http_request_count"] == 1
    assert result["successful_request_count"] == 1
    assert result["failed_request_count"] == 0
    assert result["retries_used"] == 0
    assert result["http_redirects_followed"] is False
    assert result["total_compressed_bytes"] == 18147822
    assert result["total_decompressed_bytes"] == 90089570

    summary = result["diagnostic_summary"]
    assert summary["lexical_diagnostic_classification"] == "BATCH_METADATA_LEXICALLY_CROSSES_PATH_HOUR"
    assert summary["compressed_sha256"] == "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339"
    assert summary["block_record_count"] == 36029
    assert summary["local_time_lexical_class_counts"] == {
        "DECIMAL_INTEGER_STRING": 0,
        "ISO8601_NAIVE_FRACTION": 36029,
        "ISO8601_NAIVE_SECONDS": 0,
        "ISO8601_OFFSET_FRACTION": 0,
        "ISO8601_OFFSET_SECONDS": 0,
        "ISO8601_Z_FRACTION": 0,
        "ISO8601_Z_SECONDS": 0,
        "OTHER": 0,
    }
    assert summary["block_time_lexical_class_counts"] == summary["local_time_lexical_class_counts"]
    assert summary["local_time_prefix_bucket_counts"] == {
        "MATCHES_NEXT_DATE_HOUR_PREFIX": 0,
        "MATCHES_PATH_DATE_HOUR_PREFIX": 36029,
        "MATCHES_PREVIOUS_DATE_HOUR_PREFIX": 0,
        "OTHER_PREFIX": 0,
    }
    assert summary["block_time_prefix_bucket_counts"] == {
        "MATCHES_NEXT_DATE_HOUR_PREFIX": 0,
        "MATCHES_PATH_DATE_HOUR_PREFIX": 36028,
        "MATCHES_PREVIOUS_DATE_HOUR_PREFIX": 1,
        "OTHER_PREFIX": 0,
    }
    assert summary["local_time_equals_block_time_count"] == 0
    assert summary["local_time_differs_from_block_time_count"] == 36029
    assert summary["metadata_string_length_min_local_time"] == 26
    assert summary["metadata_string_length_max_local_time"] == 29
    assert summary["metadata_string_length_min_block_time"] == 26
    assert summary["metadata_string_length_max_block_time"] == 29

    for key in (
        "raw_object_retained", "raw_block_event_fill_retained", "individual_metadata_value_retained",
        "event_array_contents_inspected", "event_pair_count_retained", "block_number_value_retained",
        "wallet_address_retained", "wallet_aggregation_performed", "economic_fill_field_processing_performed",
        "individual_fill_time_processing_performed", "timezone_parsing_performed", "timezone_inference_performed",
        "datetime_conversion_of_metadata_performed", "r10_rule_amendment_performed", "r10_rerun_performed",
        "six_hour_execution_performed", "wallet_ranking_performed", "candidate_shortlisting_performed",
        "pnl_or_alpha_analysis_performed", "copyability_analysis_performed", "market_data_ingested",
        "strategy_inference_performed",
    ):
        assert result[key] is False, key

    assert verification["provider_zip_sha256"] == ARTIFACT_SHA
    assert verification["independently_downloaded_zip_sha256"] == ARTIFACT_SHA
    assert verification["provider_digest"] == f"sha256:{ARTIFACT_SHA}"
    assert verification["provider_digest_matches_independent_download"] is True
    assert verification["internal_ledger_matches_all_retained_files"] is True
    assert verification["job_conclusion"] == "success"
    assert verification["artifact_id"] == 9065535303
    assert verification["artifact_size_bytes"] == 2459
    assert verification["verification_result"] == "ALL_RETAINED_EVIDENCE_CHECKS_PASS_BATCH_METADATA_LEXICALLY_CROSSES_PATH_HOUR"

    assert attest["status"] == "ATTESTED_COMPLETE_BATCH_METADATA_LEXICALLY_CROSSES_PATH_HOUR"
    assert attest["workflow_run_id"] == 31395720147
    assert attest["workflow_job_id"] == 93478017396
    assert attest["artifact_id"] == 9065535303
    assert attest["artifact_zip_sha256"] == ARTIFACT_SHA
    assert attest["release_consumed"] is True
    assert attest["rerun_authorized"] is False
    assert attest["claims_proven"]["all_local_time_values_match_path_date_hour_prefix"] is True
    assert attest["claims_proven"]["exactly_one_block_time_value_matches_previous_date_hour_prefix"] is True
    assert attest["claims_proven"]["local_time_and_block_time_strings_differ_on_all_36029_records"] is True
    assert attest["claims_not_proven"]["local_time_timezone_semantics"] is False
    assert attest["claims_not_proven"]["block_time_timezone_semantics"] is False
    assert attest["claims_not_proven"]["previous_hour_block_time_is_the_record_containing_either_pre_hour_fill"] is False
    assert attest["claims_not_proven"]["a_51ms_fill_time_tolerance_is_safe_for_general_history"] is False
    assert attest["claims_not_proven"]["r10_rule_should_be_amended"] is False
    assert attest["r10_rule_amendment_authorized"] is False
    assert attest["six_hour_execution_authorized"] is False

    assert consumption["status"] == "CONSUMED_SUCCESS_BATCH_METADATA_LEXICALLY_CROSSES_PATH_HOUR"
    assert consumption["release_consumed"] is True
    assert consumption["future_r10b_dispatch_authorized"] is False
    assert consumption["rerun_authorized"] is False
    assert consumption["remaining_get_object_budget_from_consumed_release"] == 0
    assert consumption["new_network_request_requires_new_preregistration_approval_and_release"] is True
    assert all(value is False for value in consumption["downstream_authorizations"].values())
    assert all(value is False for value in consumption["trading_authorizations"].values())

    # The canonical release remains an immutable pre-run snapshot. Consumption is separate.
    assert release["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10B_RUN"
    assert release["release_consumed"] is False
    assert release["rerun_authorized"] is False

    print("R10B_EXECUTION_EVIDENCE_VALID_BATCH_METADATA_LEXICALLY_CROSSES_PATH_HOUR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
