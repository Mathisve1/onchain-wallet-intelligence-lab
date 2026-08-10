from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CONTRACT = BASE / "r10d/R10D_RECORD_ANCHORED_BOUNDARY_REPAIR_PREREGISTRATION.json"
STATUS = BASE / "r10d/APPROVAL_STATUS.md"
TEMPLATE = BASE / "r10d/HUMAN_APPROVAL_TEMPLATE_R10D.md"
README = BASE / "r10d/README.md"
R10 = BASE / "r10/POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_CONTRACT.json"
R10_CONSUMPTION = BASE / "r10_data_execution/R10_EXECUTION_RELEASE_CONSUMPTION.json"
R10C_ATTEST = BASE / "r10c_evidence/HL-ARCHIVE-R10C-BOUNDARY-RECORD-CORRELATION-001-ATTESTATION.json"
R10C_CONSUMPTION = BASE / "r10c_runtime/R10C_EXECUTION_RELEASE_CONSUMPTION.json"

PILOT = "HL-ARCHIVE-R10D-RECORD-ANCHORED-MULTI-HOUR-FEATURE-REPAIR-001"
R10C_MERGE = "83842a3947e8eec518fa4a05ca71a2b81079976b"
R10C_RESULT = "EXACT_TWO_PRE_HOUR_FILLS_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD"
EXPECTED_KEYS = [
    "node_fills_by_block/hourly/20250727/9.lz4",
    "node_fills_by_block/hourly/20250727/10.lz4",
    "node_fills_by_block/hourly/20250727/11.lz4",
    "node_fills_by_block/hourly/20250727/12.lz4",
    "node_fills_by_block/hourly/20250727/13.lz4",
    "node_fills_by_block/hourly/20250727/14.lz4",
]
FEATURE_FIELDS = [
    "wallet_address", "fill_count", "active_hour_count", "first_fill_time", "last_fill_time",
    "distinct_coin_count", "side_a_count", "side_b_count", "crossed_true_count",
    "liquidation_associated_fill_count", "duplicate_tid_count",
    "sum_abs_px_times_sz_notional_proxy", "sum_closed_pnl_fill_statistic",
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    c = load(CONTRACT)
    r10 = load(R10)
    r10x = load(R10_CONSUMPTION)
    r10c = load(R10C_ATTEST)
    r10cc = load(R10C_CONSUMPTION)

    assert c["pilot_id"] == PILOT
    assert c["status"] == "PREREGISTERED_NO_EXECUTION"
    assert c["parent_r10_pilot_id"] == r10["pilot_id"] == "HL-ARCHIVE-POST-BOUNDARY-MULTI-HOUR-FEATURE-R10-001"
    assert c["parent_r10_run_id"] == r10x["workflow_run_id"] == 31377732916
    assert c["parent_r10_result"] == r10x["technical_result"] == "MULTI_HOUR_FEATURE_PIPELINE_UNRESOLVED"
    assert c["parent_r10_failure_class"] == r10x["failure_class"] == "fill time lies outside source path hour"
    assert c["parent_r10_release_consumed"] is True and r10x["release_consumed"] is True
    assert c["parent_r10_rerun_authorized"] is False and r10x["rerun_authorized"] is False

    assert c["parent_r10c_evidence_merge_commit"] == R10C_MERGE
    assert c["parent_r10c_run_id"] == r10c["workflow_run_id"] == 31410638224
    assert c["parent_r10c_job_id"] == r10c["workflow_job_id"] == 93527564608
    assert c["parent_r10c_artifact_id"] == r10c["artifact_id"] == 9071422220
    assert c["parent_r10c_artifact_sha256"] == r10c["artifact_zip_sha256"] == "60602f1e5b4e5456504af9bbd65b64826cdf2b86a47bc1b2e690507dbf0a0f48"
    assert c["parent_r10c_result"] == r10c["technical_result"] == R10C_RESULT
    assert r10c["claims_proven"]["both_pre_hour_fills_colocate_in_that_single_cross_prefix_record"] is True
    assert r10c["claims_not_proven"]["a_51ms_fill_time_tolerance_is_safe_for_general_history"] is False
    assert r10cc["release_consumed"] is True and r10cc["rerun_authorized"] is False
    assert r10cc["remaining_get_object_budget_from_consumed_release"] == 0

    targets = c["exact_future_network_targets"]
    assert [row["key"] for row in targets] == EXPECTED_KEYS
    assert [row["key"] for row in r10["exact_future_network_targets"]] == EXPECTED_KEYS
    for got, old in zip(targets, r10["exact_future_network_targets"]):
        assert got["path_hour_utc"] == old["path_hour_utc"]
        assert got["key"] == old["key"]
        assert got["expected_size_bytes"] == old["expected_size_bytes"]
        assert got["expected_etag"] == old["expected_etag"]
    assert targets[0]["known_compressed_sha256"] == "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339"
    assert all(row["known_compressed_sha256"] is None for row in targets[1:])

    env = c["proposed_request_envelope"]
    assert env["maximum_one_time_budget_eur"] == 0.10 and env["maximum_monthly_budget_eur"] == 0
    assert env["maximum_get_object_requests"] == 6 and env["maximum_requests_per_object"] == 1
    assert env["maximum_retries_per_request"] == 0
    assert env["maximum_total_compressed_bytes"] == 120999698
    assert env["maximum_individual_compressed_bytes"] == 21672141
    assert env["maximum_total_decompressed_bytes"] == 1073741824
    assert env["maximum_individual_decompressed_bytes"] == 268435456
    assert env["maximum_runtime_seconds"] == 300
    assert env["request_order"] == "PATH_HOUR_ASCENDING"
    assert env["stop_after_first_failed_or_mismatched_object"] is True
    for key in ("requester_pays_required","if_match_etag_required","exact_content_length_required","exact_response_etag_required","compressed_sha256_computed_and_retained_per_object","hour9_preknown_compressed_sha256_required"):
        assert env[key] is True, key
    for key in ("head_object_authorized","range_get_authorized","list_objects_v2_authorized","list_object_versions_authorized","list_all_my_buckets_authorized","get_object_attributes_authorized","get_object_version_authorized","http_redirect_following_authorized"):
        assert env[key] is False, key

    rule = c["record_anchored_alignment_rule"]
    assert rule["rule_id"] == "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1"
    assert rule["metadata_timezone_parsing_authorized"] is False
    assert rule["metadata_timezone_inference_authorized"] is False
    assert rule["metadata_datetime_conversion_authorized"] is False
    assert rule["local_time_raw_prefix_must_match_source_path_hour_for_every_record"] is True
    assert rule["block_time_raw_prefix_allowed_buckets"] == ["MATCHES_PATH_DATE_HOUR_PREFIX","MATCHES_PREVIOUS_DATE_HOUR_PREFIX"]
    assert rule["block_time_next_or_other_prefix_is_fail_closed"] is True
    assert rule["fill_time_integer_milliseconds_processing_authorized"] is True
    assert rule["fill_time_numeric_tolerance_milliseconds"] is None
    assert rule["numeric_tolerance_authorized"] is False
    assert rule["path_block_record_allowed_fill_partitions"] == ["INSIDE_PATH_HOUR"]
    assert rule["previous_block_record_allowed_fill_partitions"] == ["BEFORE_PATH_HOUR"]
    assert rule["previous_block_record_before_fill_must_be_within_immediately_previous_epoch_hour"] is True
    assert rule["after_path_hour_fill_count_required_for_success"] == 0
    assert rule["any_fill_partition_or_prefix_rule_violation_causes_research_unresolved_and_stops_before_next_object"] is True
    assert rule["hour9_parent_fixture_required"] == {
        "block_record_count":36029,"fill_time_count":223950,"fill_time_before_path_hour_count":2,
        "fill_time_inside_path_hour_count":223948,"fill_time_after_path_hour_count":0,
        "local_path_block_path_record_count":36028,"local_path_block_previous_record_count":1,
        "before_fills_in_local_path_block_previous_records":2,
    }
    assert rule["hours10_to14_boundary_pattern_predeclared"] is False
    assert rule["rule_is_operational_validation_not_partition_semantics_claim"] is True

    unchanged = c["unchanged_r10_feature_contract"]
    assert unchanged["selected_fill_field_processing_unchanged_from_r10"] is True
    assert unchanged["cross_object_aggregation_rules_unchanged_from_r10_except_alignment_rule"] is True
    assert unchanged["proposed_per_wallet_output_fields_only"] == FEATURE_FIELDS
    assert c["selected_fill_fields_for_transient_processing"] == r10["selected_fill_fields_for_transient_processing"]

    assert all(v is False for v in c["semantic_boundaries"].values())
    assert all(v is False for v in c["raw_or_disallowed_retention"].values())
    assert all(v is False for v in c["downstream_authorizations"].values())
    assert all(v is False for v in c["current_runtime_authority"].values())
    assert all(v is False for v in c["trading_authorizations"].values())
    assert c["human_approval_required_before_implementation"] is True
    assert c["separate_execution_release_required"] is True
    assert c["separate_canonical_activation_required"] is True
    assert c["network_requests_executed_by_preregistration"] == 0
    assert c["aws_iam_mutations_executed_by_preregistration"] == 0
    assert c["wallet_feature_rows_created_by_preregistration"] == 0
    assert c["empirical_result"] is None

    status = STATUS.read_text()
    template = TEMPLATE.read_text()
    readme = README.read_text()
    assert "AWAITING_SEPARATE_HUMAN_APPROVAL" in status
    assert "No numeric millisecond tolerance is authorized" in status
    assert "APPROVE_HL_ARCHIVE_R10D_RECORD_ANCHORED_MULTI_HOUR_FEATURE_REPAIR_001" in template
    assert "numeric_tolerance_authorized=false" in template
    assert "execution_authorized_by_this_approval=false" in template
    assert "Nothing executes in this stage" in readme

    print("R10D_RECORD_ANCHORED_BOUNDARY_REPAIR_PREREGISTRATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
