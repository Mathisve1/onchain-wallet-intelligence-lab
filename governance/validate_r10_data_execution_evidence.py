from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RUN = BASE / "r10_data_execution/evidence/run-31377732916"
ATTEST = BASE / "r10_data_execution/HL-ARCHIVE-POST-BOUNDARY-MULTI-HOUR-FEATURE-R10-001-ATTESTATION.json"
CONSUMPTION = BASE / "r10_data_execution/R10_EXECUTION_RELEASE_CONSUMPTION.json"
RELEASE = BASE / "r10_runtime/R10_EXECUTION_RELEASE_CANONICALIZATION.json"
R9 = BASE / "r9/evidence/HL-ARCHIVE-MODERN-WALLET-FEATURE-PILOT-R9-001-ATTESTATION.json"

ARTIFACT_SHA = "e6aebcbc0c73aecbea994fb4bd095c56f6c86b9ba5aa0dc152bee125b08f33bb"
LEDGER = {
    "r10-context.json": "292c8eb879611370c1d94d1d0eb640d2d785b0da2687c1bb4f2d53b98134e3a6",
    "r10-result.json": "21758e0fc3f6f39398afe9d0de10507ba0c9c96ed612c2423527c5842a973ff4",
    "r10-wallet-features.ndjson": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "r10.rc": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
}


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    context = load(RUN / "r10-context.json")
    result = load(RUN / "r10-result.json")
    verification = load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
    attest = load(ATTEST)
    consumption = load(CONSUMPTION)
    release = load(RELEASE)
    r9 = load(R9)

    observed = {}
    for line in (RUN / "R10_FILES.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        observed[name] = digest
    assert observed == LEDGER
    for name, digest in LEDGER.items():
        assert hashlib.sha256((RUN / name).read_bytes()).hexdigest() == digest
        assert verification["internal_ledger"][name] == digest

    assert (RUN / "r10.rc").read_text(encoding="utf-8") == "0\n"
    assert (RUN / "r10-wallet-features.ndjson").read_bytes() == b""
    assert context["workflow_run_id"] == 31377732916
    assert context["workflow_run_attempt"] == 1
    assert context["dispatch_sha"] == "64a04363e2c885f3a419f5cc4a789dd157fed229"
    assert context["dispatch_ref"] == "refs/heads/main"
    assert context["configure_aws_outcome"] == "success"

    assert result["terminal_status"] == "R10_MULTI_HOUR_FEATURE_STUDY_COMPLETE"
    assert result["technical_result"] == "MULTI_HOUR_FEATURE_PIPELINE_UNRESOLVED"
    assert result["research_conclusion"] == "MULTI_HOUR_FEATURE_PIPELINE_UNRESOLVED"
    assert result["failure_class"] == "fill time lies outside source path hour"
    assert result["request_attempt_count"] == 1
    assert result["successful_request_count"] == 1
    assert result["failed_request_count"] == 0
    assert result["s3_http_request_count"] == 1
    assert result["retries_used"] == 0
    assert result["http_redirects_followed"] is False
    assert result["total_compressed_bytes"] == 18147822
    assert result["completed_hour_count"] == 0
    assert result["wallet_feature_retained"] is False
    assert result["aggregate_wallet_feature_summary"] is None
    for key in (
        "raw_compressed_objects_retained", "raw_decompressed_payloads_retained",
        "raw_block_records_retained", "raw_event_pairs_retained", "raw_fill_objects_retained",
        "individual_selected_values_retained", "historical_window_beyond_six_hours_performed",
        "full_population_historical_ingestion_performed", "legacy_modern_merged_history_performed",
        "public_api_enrichment_performed", "entity_clustering_performed", "wallet_ranking_performed",
        "candidate_shortlisting_performed", "pnl_or_alpha_analysis_performed",
        "copyability_analysis_performed", "market_data_ingested", "strategy_inference_performed",
        "sum_closed_pnl_interpreted_as_exact_account_return",
        "sum_closed_pnl_used_as_wallet_ranking_score",
        "notional_proxy_interpreted_as_copyable_notional",
        "active_hour_count_interpreted_as_wallet_quality_score",
    ):
        assert result[key] is False, key

    assert verification["provider_sha256"] == ARTIFACT_SHA
    assert verification["independently_downloaded_zip_sha256"] == ARTIFACT_SHA
    assert verification["provider_digest_matches_independent_download"] is True
    assert verification["internal_ledger_matches_all_retained_files"] is True
    assert verification["job_conclusion"] == "success"
    assert verification["verification_result"] == "ALL_RETAINED_EVIDENCE_CHECKS_PASS_RESEARCH_UNRESOLVED"

    assert attest["status"] == "ATTESTED_RESEARCH_UNRESOLVED"
    assert attest["release_consumed"] is True
    assert attest["rerun_authorized"] is False
    assert attest["claims_proven"]["strict_fill_time_within_source_path_hour_rule_was_not_satisfied"] is True
    assert attest["claims_not_proven"]["direction_or_magnitude_of_path_hour_time_misalignment"] is False
    assert attest["claims_not_proven"]["multi_hour_wallet_feature_pipeline_complete"] is False
    assert attest["new_network_request_requires_new_preregistration_approval_and_release"] is True

    assert consumption["status"] == "CONSUMED_RESEARCH_UNRESOLVED"
    assert consumption["release_consumed"] is True
    assert consumption["future_r10_dispatch_authorized"] is False
    assert consumption["rerun_authorized"] is False
    assert consumption["remaining_get_object_budget_from_consumed_release"] == 5
    assert consumption["remaining_budget_is_not_reusable_without_new_release"] is True
    assert all(value is False for value in consumption["downstream_authorizations"].values())
    assert all(value is False for value in consumption["trading_authorizations"].values())

    # The original release is an immutable pre-run snapshot; consumption is separate.
    assert release["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10_RUN"
    assert release["release_consumed"] is False
    assert release["rerun_authorized"] is False

    # R9 is static context only and does not resolve R10's mismatch semantics.
    assert r9["execution_identity"]["workflow_run_id"] == 31336490854
    obs = r9["direct_aggregate_observations"]
    assert obs["global_first_fill_time_utc"] == "2025-07-27T08:50:10.273Z"
    assert obs["global_last_fill_time_utc"] == "2025-07-27T08:59:59.895Z"
    assert attest["static_context_from_prior_r9_evidence"]["r9_context_resolves_r10_misalignment"] is False

    print("R10_DATA_EXECUTION_EVIDENCE_VALID_UNRESOLVED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
