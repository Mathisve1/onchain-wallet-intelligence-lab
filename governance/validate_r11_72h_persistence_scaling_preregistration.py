from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
R11 = BASE / "r11"
SELECTION = R11 / "R11_72H_SELECTION.json"
DERIVATION = R11 / "R11_SELECTION_DERIVATION.json"
PREREG = R11 / "R11_72H_PERSISTENCE_SCALING_PREREGISTRATION.json"
STATUS = R11 / "APPROVAL_STATUS.md"
TEMPLATE = R11 / "HUMAN_APPROVAL_TEMPLATE_R11.md"
R10D = BASE / "r10d_evidence/HL-ARCHIVE-R10D-RECORD-ANCHORED-MULTI-HOUR-FEATURE-REPAIR-001-ATTESTATION.json"
R3 = BASE / "r3/evidence/run-31299905850/R3_COMPACT_INVENTORY_SUMMARY.json"

PILOT = "HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001"
SELECTION_ID = "HL-ARCHIVE-R11-72H-MODERN-PERSISTENCE-SELECTION-001"
PARENT = "0b13a80235ecd43bcd220985383f79f8ccbfb6ca"
SELECTION_SHA = "7c134f4b62f547904126a5f810c177484dceeffa246d53c5c35944367d563eb2"
R3_ARTIFACT_SHA = "1049509ef12f1ef2a312f6ded1d443b434e2ed860503a264f103a73c2a70cf88"
R3_RAW_SHA = "94c3e77a05de2363b95abdce718dfd61f1b440f3d9c3972a0d03ce28a9edc479"
KEY_RE = re.compile(r"^node_fills_by_block/hourly/(\d{8})/(\d{1,2})\.lz4$")


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def parse_key_hour(key: str) -> datetime:
    match = KEY_RE.fullmatch(key)
    assert match, key
    hour = int(match.group(2))
    assert 0 <= hour <= 23
    return datetime.strptime(match.group(1) + f"{hour:02d}", "%Y%m%d%H").replace(tzinfo=timezone.utc)


def main() -> int:
    selection = load(SELECTION)
    derivation = load(DERIVATION)
    prereg = load(PREREG)
    r10d = load(R10D)
    r3 = load(R3)

    assert hashlib.sha256(SELECTION.read_bytes()).hexdigest() == SELECTION_SHA
    assert selection["selection_id"] == SELECTION_ID
    assert selection["status"] == "STATIC_SELECTION_FROM_CANONICAL_R3_METADATA_NO_OBJECT_READS"
    assert selection["source_r3_run_id"] == 31299905850
    assert selection["source_r3_artifact_id"] == 9034170863
    assert selection["source_r3_artifact_sha256"] == R3_ARTIFACT_SHA
    assert selection["source_r3_raw_result_sha256"] == R3_RAW_SHA
    assert selection["dataset_family"] == "node_fills_by_block"
    assert selection["window_start_utc"] == "2025-07-28T00:00:00Z"
    assert selection["window_end_exclusive_utc"] == "2025-07-31T00:00:00Z"
    assert selection["complete_utc_day_count"] == 3
    assert selection["selected_hour_count"] == 72
    assert selection["all_selected_hours_post_censored_boundary"] is True
    assert selection["selected_hours_contiguous_in_complete_r3_inventory"] is True
    targets = selection["exact_targets"]
    assert len(targets) == 72
    observed_hours = [parse_key_hour(row["key"]) for row in targets]
    start = datetime(2025, 7, 28, tzinfo=timezone.utc)
    expected_hours = [start + timedelta(hours=index) for index in range(72)]
    assert observed_hours == expected_hours
    assert [row["path_hour_utc"] for row in targets] == [value.isoformat().replace("+00:00", "Z") for value in expected_hours]
    assert len({row["key"] for row in targets}) == 72
    assert all(row["storage_class"] == "STANDARD" for row in targets)
    sizes = [row["expected_size_bytes"] for row in targets]
    assert all(isinstance(value, int) and value > 0 for value in sizes)
    assert sum(sizes) == selection["aggregate_expected_compressed_bytes"] == 2107738436
    assert max(sizes) == selection["maximum_individual_expected_compressed_bytes"] == 76616104
    assert min(sizes) == selection["minimum_individual_expected_compressed_bytes"] == 15886307
    assert all(re.fullmatch(r'"[0-9a-f]{32}-\d+"', row["expected_etag"]) for row in targets)
    assert selection["network_requests_executed_by_selection"] == 0
    assert selection["object_body_reads_executed_by_selection"] == 0
    assert selection["empirical_result"] is None

    assert derivation["source_r3_run_id"] == 31299905850
    assert derivation["source_r3_artifact_id"] == 9034170863
    assert derivation["provider_artifact_digest"] == f"sha256:{R3_ARTIFACT_SHA}"
    assert derivation["independently_downloaded_artifact_sha256"] == R3_ARTIFACT_SHA
    assert derivation["provider_digest_matches_independent_download"] is True
    assert derivation["source_raw_result_sha256"] == R3_RAW_SHA
    assert derivation["source_raw_result_bytes"] == 3667237
    assert derivation["selection_sha256"] == SELECTION_SHA
    assert derivation["selection_entry_count"] == 72
    assert derivation["object_bodies_read_during_derivation"] is False
    assert derivation["network_requests_to_aws_during_derivation"] == 0

    modern = next(row for row in r3["family_summaries"] if row["dataset_family_id"] == "node_fills_by_block")
    assert modern["family_status"] == "COMPLETE"
    assert modern["missing_internal_hour_count"] == 0
    assert modern["earliest_path_hour_utc"] == "2025-07-27T08:00:00Z"
    assert modern["latest_path_hour_utc"] == "2026-08-09T05:00:00Z"
    assert r3["artifact_id"] == 9034170863
    assert r3["artifact_sha256"] == R3_ARTIFACT_SHA
    assert r3["result_raw_sha256"] == R3_RAW_SHA

    assert r10d["status"] == "ATTESTED_COMPLETE_R10D_MULTI_HOUR_FEATURE_PIPELINE"
    assert r10d["research_conclusion"] == "R10D_MULTI_HOUR_FEATURE_PIPELINE_COMPLETE"
    assert r10d["record_anchored_rule_id"] == "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1"
    assert r10d["numeric_tolerance_authorized"] is False
    assert r10d["release_consumed"] is True
    assert r10d["rerun_authorized"] is False

    assert prereg["pilot_id"] == PILOT
    assert prereg["status"] == "PREREGISTERED_NO_EXECUTION"
    assert prereg["parent_r10d_evidence_merge_commit"] == PARENT
    assert prereg["parent_r10d_run_id"] == 31420197671
    assert prereg["parent_r10d_terminal_result"] == "R10D_MULTI_HOUR_FEATURE_PIPELINE_COMPLETE"
    assert prereg["selection_id"] == SELECTION_ID
    assert prereg["selection_sha256"] == SELECTION_SHA
    window = prereg["historical_window_role"]
    assert window["complete_utc_day_count"] == 3
    assert window["selected_hour_count"] == 72
    assert window["window_is_sufficient_wallet_performance_history"] is False
    assert window["window_supports_wallet_quality_ranking"] is False

    envelope = prereg["proposed_request_envelope"]
    assert envelope["maximum_one_time_budget_eur"] == 0.50
    assert envelope["maximum_monthly_budget_eur"] == 0
    assert envelope["maximum_get_object_requests"] == 72
    assert envelope["maximum_requests_per_object"] == 1
    assert envelope["maximum_retries_per_request"] == 0
    assert envelope["maximum_total_compressed_bytes"] == 2107738436
    assert envelope["maximum_individual_compressed_bytes"] == 76616104
    assert envelope["maximum_total_decompressed_bytes"] == 17179869184
    assert envelope["maximum_individual_decompressed_bytes"] == 536870912
    assert envelope["maximum_runtime_seconds"] == 5400
    assert envelope["request_order"] == "PATH_HOUR_ASCENDING"
    assert envelope["stop_after_first_failed_or_mismatched_object"] is True
    for key in ("requester_pays_required", "if_match_etag_required", "exact_content_length_required", "exact_response_etag_required", "compressed_sha256_computed_and_retained_per_object"):
        assert envelope[key] is True, key
    for key in ("preknown_compressed_sha256_required", "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized", "get_object_attributes_authorized", "get_object_version_authorized", "http_redirect_following_authorized"):
        assert envelope[key] is False, key

    alignment = prereg["record_anchored_alignment_contract"]
    assert alignment["rule_id"] == "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1"
    assert alignment["numeric_tolerance_authorized"] is False
    assert alignment["metadata_timezone_parsing_authorized"] is False
    assert alignment["metadata_timezone_inference_authorized"] is False
    assert alignment["metadata_datetime_conversion_authorized"] is False
    assert alignment["local_time_raw_prefix_must_match_source_path_hour_for_every_record"] is True
    assert alignment["block_time_raw_prefix_allowed_buckets"] == ["MATCHES_PATH_DATE_HOUR_PREFIX", "MATCHES_PREVIOUS_DATE_HOUR_PREFIX"]
    assert alignment["path_block_record_allowed_fill_partitions"] == ["INSIDE_PATH_HOUR"]
    assert alignment["previous_block_record_allowed_fill_partitions"] == ["BEFORE_PATH_HOUR"]
    assert alignment["after_path_hour_fill_count_required_for_success"] == 0

    output = prereg["proposed_per_wallet_output"]
    assert output["fields_only"] == [
        "wallet_address", "fill_count", "active_hour_count", "active_day_count", "first_fill_time", "last_fill_time",
        "distinct_coin_count", "side_a_count", "side_b_count", "crossed_true_count", "liquidation_associated_fill_count",
        "duplicate_tid_count", "sum_abs_px_times_sz_notional_proxy", "sum_closed_pnl_fill_statistic",
    ]
    assert output["active_hour_count_maximum"] == 72
    assert output["active_day_count_maximum"] == 3
    assert prereg["cross_object_aggregation_rules"]["active_day_count_incremented_at_most_once_per_wallet_per_utc_date"] is True

    iam = prereg["iam_boundary"]
    assert iam["existing_r10_role_reuse_authorized"] is False
    assert iam["existing_r10_role_mutation_authorized"] is False
    assert iam["new_dedicated_r11_role_required"] is True
    assert iam["new_dedicated_r11_role_creation_authorized_now"] is False
    assert iam["proposed_persistent_permission_resource_count"] == 72
    assert iam["persistent_permission_resources_are_exact_selection_objects"] is True
    assert iam["future_session_policy_uses_three_date_prefix_arns_only_as_intersection_with_exact_persistent_allowlist"] is True
    assert iam["future_session_prefixes"] == [
        "node_fills_by_block/hourly/20250728/*",
        "node_fills_by_block/hourly/20250729/*",
        "node_fills_by_block/hourly/20250730/*",
    ]
    assert iam["proposed_role_max_session_duration_seconds"] == 7200
    assert iam["future_workflow_role_duration_seconds"] == 7200
    assert iam["s3_access_authorized_during_sts_preflight"] is False

    assert all(value is False for value in prereg["semantic_boundaries"].values())
    assert all(value is False for value in prereg["downstream_authorizations"].values())
    assert all(value is False for value in prereg["current_runtime_authority"].values())
    assert all(value is False for value in prereg["trading_authorizations"].values())
    assert prereg["human_approval_required_before_implementation"] is True
    assert prereg["separate_iam_role_operator_gate_required"] is True
    assert prereg["separate_sts_preflight_release_required"] is True
    assert prereg["separate_execution_release_required"] is True
    assert prereg["separate_canonical_activation_required"] is True
    assert prereg["network_requests_executed_by_r11_preregistration"] == 0
    assert prereg["aws_iam_mutations_executed_by_r11_preregistration"] == 0
    assert prereg["wallet_feature_rows_created_by_r11_preregistration"] == 0
    assert prereg["empirical_result"] is None

    status = STATUS.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    assert "AWAITING_SEPARATE_HUMAN_APPROVAL" in status
    assert "APPROVE_HL_ARCHIVE_R11_72H_PERSISTENCE_SCALING_001" in template
    assert "reviewed_commit=<CANONICAL_R11_PREREGISTRATION_MERGE_COMMIT>" in template
    assert "execution_authorized_by_this_approval=false" in template
    print("R11_72H_PERSISTENCE_SCALING_PREREGISTRATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
