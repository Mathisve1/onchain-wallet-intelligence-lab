from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RUN = BASE / "r10a_evidence/run-31386230522"
ATTEST = BASE / "r10a_evidence/HL-ARCHIVE-R10A-TIMESTAMP-PARTITION-DIAGNOSTIC-001-ATTESTATION.json"
CONSUMPTION = BASE / "r10a_runtime/R10A_EXECUTION_RELEASE_CONSUMPTION.json"
RELEASE = BASE / "r10a_runtime/R10A_EXECUTION_RELEASE.json"

ARTIFACT_SHA = "c52344b911b439db08a9a369f9016bde87f2925091ce83b97c0ee00744fb1e68"
LEDGER = {
    "r10a-context.json": "d6eab95f9771ed043a098be35e1f4db50aa567168870e0e2a04e3572b3c2d9d3",
    "r10a-result.json": "e1ca787e6b9225db4c69a0b541bccbb518f6d61a1e41bd3439d77e35656edf90",
    "r10a.rc": "9a271f2a916b0b3206ef074578be55d9bc94f6f3fe3ab86aa",
}


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    context = load(RUN / "r10a-context.json")
    result = load(RUN / "r10a-result.json")
    verification = load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
    attest = load(ATTEST)
    consumption = load(CONSUMPTION)
    release = load(RELEASE)

    observed = {}
    for line in (RUN / "R10A_FILES.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        observed[name] = digest
    assert observed == LEDGER
    for name, digest in LEDGER.items():
        assert hashlib.sha256((RUN / name).read_bytes()).hexdigest() == digest
        assert verification["internal_ledger"][name] == digest

    assert (RUN / "r10a.rc").read_text(encoding="utf-8") == "0\n"
    assert context["workflow_run_id"] == 31386230522
    assert context["workflow_run_attempt"] == 1
    assert context["dispatch_sha"] == "429fe209b03e00516759995c50c6461ec901714b"
    assert context["dispatch_ref"] == "refs/heads/main"
    assert context["configure_aws_outcome"] == "success"
    assert context["maximum_get_object_requests"] == 1
    assert context["maximum_retries_per_request"] == 0
    assert context["wallet_address_retention_authorized"] is False
    assert context["economic_fill_field_processing_authorized"] is False

    assert result["terminal_status"] == "R10A_TIMESTAMP_PARTITION_DIAGNOSTIC_COMPLETE"
    assert result["technical_result"] == "FILL_TIME_SPILLS_OUTSIDE_PATH_HOUR"
    assert result["research_conclusion"] == "FILL_TIME_SPILLS_OUTSIDE_PATH_HOUR"
    assert result["request_attempt_count"] == 1
    assert result["s3_http_request_count"] == 1
    assert result["successful_request_count"] == 1
    assert result["failed_request_count"] == 0
    assert result["retries_used"] == 0
    assert result["http_redirects_followed"] is False
    assert result["total_compressed_bytes"] == 18147822
    assert result["total_decompressed_bytes"] == 90089570

    s = result["diagnostic_summary"]
    assert s["alignment_classification"] == "FILL_TIME_SPILLS_OUTSIDE_PATH_HOUR"
    assert s["compressed_sha256"] == "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339"
    assert s["block_record_count"] == 36029
    assert s["event_pair_count"] == 223950
    assert s["fill_time_count"] == 223950
    assert s["fill_time_before_path_hour_count"] == 2
    assert s["fill_time_inside_path_hour_count"] == 223948
    assert s["fill_time_after_path_hour_count"] == 0
    assert s["fill_time_min_ms"] == 1753606799949
    assert s["fill_time_min_utc"] == "2025-07-27T08:59:59.949Z"
    assert s["fill_time_max_ms"] == 1753610399594
    assert s["fill_time_max_utc"] == "2025-07-27T09:59:59.594Z"
    assert s["fill_time_path_hour_offset_histogram"]["-1"] == 2
    assert s["fill_time_path_hour_offset_histogram"]["0"] == 223948
    assert sum(s["fill_time_path_hour_offset_histogram"].values()) == 223950
    assert s["block_time_parseable_count"] == 0
    assert s["block_time_unparseable_count"] == 36029
    assert s["local_time_parseable_with_explicit_timezone_count"] == 0
    assert s["local_time_not_explicitly_zoned_count"] == 36029
    assert s["fill_minus_block_time_delta_histogram"]["UNAVAILABLE"] == 223950

    for key in (
        "raw_object_retained", "raw_block_event_fill_retained", "individual_timestamp_retained",
        "wallet_address_retained", "wallet_aggregation_performed", "economic_fill_field_processing_performed",
        "timezone_inference_for_local_time_performed", "r10_rule_amendment_performed", "r10_rerun_performed",
        "six_hour_execution_performed", "wallet_ranking_performed", "candidate_shortlisting_performed",
        "pnl_or_alpha_analysis_performed", "copyability_analysis_performed", "market_data_ingested",
        "strategy_inference_performed",
    ):
        assert result[key] is False, key

    assert verification["provider_zip_sha256"] == ARTIFACT_SHA
    assert verification["independently_downloaded_zip_sha256"] == ARTIFACT_SHA
    assert verification["provider_digest_matches_independent_download"] is True
    assert verification["internal_ledger_matches_all_retained_files"] is True
    assert verification["job_conclusion"] == "success"
    assert verification["verification_result"] == "ALL_RETAINED_EVIDENCE_CHECKS_PASS_FILL_TIME_SPILL_OBSERVED"

    assert attest["status"] == "ATTESTED_COMPLETE_FILL_TIME_SPILL_OBSERVED"
    assert attest["release_consumed"] is True
    assert attest["rerun_authorized"] is False
    assert attest["exact_network_observation"]["fill_time_earliest_boundary_offset_ms"] == -51
    assert attest["claims_proven"]["exactly_two_fill_times_precede_path_hour_lower_bound"] is True
    assert attest["claims_proven"]["no_fill_time_exceeds_path_hour_upper_bound_in_this_object"] is True
    assert attest["claims_not_proven"]["a_51ms_tolerance_is_safe_for_general_history"] is False
    assert attest["claims_not_proven"]["r10_rule_should_be_amended"] is False
    assert attest["r10_rule_amendment_authorized"] is False
    assert attest["six_hour_execution_authorized"] is False

    assert consumption["status"] == "CONSUMED_SUCCESS_FILL_TIME_SPILL_OBSERVED"
    assert consumption["release_consumed"] is True
    assert consumption["future_r10a_dispatch_authorized"] is False
    assert consumption["rerun_authorized"] is False
    assert consumption["remaining_get_object_budget_from_consumed_release"] == 0
    assert consumption["new_network_request_requires_new_preregistration_approval_and_release"] is True
    assert all(value is False for value in consumption["downstream_authorizations"].values())
    assert all(value is False for value in consumption["trading_authorizations"].values())

    # The canonical release remains an immutable pre-run snapshot.
    assert release["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10A_RUN"
    assert release["release_consumed"] is False
    assert release["rerun_authorized"] is False

    print("R10A_EXECUTION_EVIDENCE_VALID_FILL_TIME_SPILL_OBSERVED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
