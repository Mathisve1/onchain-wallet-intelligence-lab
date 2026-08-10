from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
R10C = BASE / "r10c"
CONTRACT = R10C / "R10C_BOUNDARY_RECORD_CORRELATION_PREREGISTRATION.json"
STATUS = R10C / "APPROVAL_STATUS.md"
TEMPLATE = R10C / "HUMAN_APPROVAL_TEMPLATE_R10C.md"
ASSESSMENT = R10C / "STATIC_PRIMARY_SOURCE_ASSESSMENT.md"
R10B_ATTEST = BASE / "r10b_evidence/HL-ARCHIVE-R10B-BATCH-METADATA-LEXICAL-DIAGNOSTIC-001-ATTESTATION.json"
R10B_CONSUMPTION = BASE / "r10b_runtime/R10B_EXECUTION_RELEASE_CONSUMPTION.json"
R10A_ATTEST = BASE / "r10a_evidence/HL-ARCHIVE-R10A-TIMESTAMP-PARTITION-DIAGNOSTIC-001-ATTESTATION.json"
R10A_CONSUMPTION = BASE / "r10a_runtime/R10A_EXECUTION_RELEASE_CONSUMPTION.json"

R10B_EVIDENCE_MERGE = "f7acce982681f7016cf16993ab506da89643ecfd"
R10A_EVIDENCE_MERGE = "93e47e23b50068b24bcc0aa3aa1cc9d99891b8e6"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
OBJECT_KEY = "node_fills_by_block/hourly/20250727/9.lz4"
OBJECT_ARN = f"arn:aws:s3:::hl-mainnet-node-data/{OBJECT_KEY}"
OBJECT_ETAG = '"5a9941a240118a57f77a4c3ee95b8430-3"'
OBJECT_SHA = "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339"
R10B_ARTIFACT_SHA = "6fe553710846794176bc040c87937a719ab83c0cb10101892b3f23749cefc789"
R10A_ARTIFACT_SHA = "c52344b911b439db08a9a369f9016bde87f2925091ce83b97c0ee00744fb1e68"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    c = load(CONTRACT)
    b = load(R10B_ATTEST)
    bc = load(R10B_CONSUMPTION)
    a = load(R10A_ATTEST)
    ac = load(R10A_CONSUMPTION)

    assert c["diagnostic_id"] == "HL-ARCHIVE-R10C-BOUNDARY-RECORD-CORRELATION-001"
    assert c["status"] == "PREREGISTERED_NO_EXECUTION"
    assert c["purpose"] == "CORRELATE_THE_R10A_PRE_HOUR_FILL_TIME_ANOMALY_WITH_R10B_LOCAL_TIME_AND_BLOCK_TIME_RAW_PREFIX_BUCKETS_ON_THE_SAME_IMMUTABLE_OBJECT_WITHOUT_RETAINING_INDIVIDUAL_VALUES"

    assert c["parent_r10b_evidence_merge_commit"] == R10B_EVIDENCE_MERGE
    assert c["parent_r10b_run_id"] == b["workflow_run_id"] == 31395720147
    assert c["parent_r10b_job_id"] == b["workflow_job_id"] == 93478017396
    assert c["parent_r10b_artifact_id"] == b["artifact_id"] == 9065535303
    assert c["parent_r10b_artifact_sha256"] == b["artifact_zip_sha256"] == R10B_ARTIFACT_SHA
    assert c["parent_r10b_research_conclusion"] == b["research_conclusion"] == "BATCH_METADATA_LEXICALLY_CROSSES_PATH_HOUR"
    obs = b["exact_network_observation"]
    assert c["parent_r10b_block_record_count"] == obs["block_record_count"] == 36029
    assert c["parent_r10b_local_time_path_prefix_count"] == obs["local_time_prefix_bucket_counts"]["MATCHES_PATH_DATE_HOUR_PREFIX"] == 36029
    assert c["parent_r10b_block_time_path_prefix_count"] == obs["block_time_prefix_bucket_counts"]["MATCHES_PATH_DATE_HOUR_PREFIX"] == 36028
    assert c["parent_r10b_block_time_previous_prefix_count"] == obs["block_time_prefix_bucket_counts"]["MATCHES_PREVIOUS_DATE_HOUR_PREFIX"] == 1
    assert c["parent_r10b_local_time_equals_block_time_count"] == obs["local_time_equals_block_time_count"] == 0
    assert c["parent_r10b_release_consumed"] is True
    assert c["parent_r10b_rerun_authorized"] is False
    assert b["release_consumed"] is True and b["rerun_authorized"] is False
    assert bc["status"] == "CONSUMED_SUCCESS_BATCH_METADATA_LEXICALLY_CROSSES_PATH_HOUR"
    assert bc["release_consumed"] is True
    assert bc["future_r10b_dispatch_authorized"] is False
    assert bc["rerun_authorized"] is False
    assert bc["remaining_get_object_budget_from_consumed_release"] == 0
    assert bc["new_network_request_requires_new_preregistration_approval_and_release"] is True

    assert c["parent_r10a_evidence_merge_commit"] == R10A_EVIDENCE_MERGE
    assert c["parent_r10a_run_id"] == a["workflow_run_id"] == 31386230522
    assert c["parent_r10a_artifact_sha256"] == a["artifact_zip_sha256"] == R10A_ARTIFACT_SHA
    aobs = a["exact_network_observation"]
    assert c["parent_r10a_fill_time_count"] == aobs["fill_time_count"] == 223950
    assert c["parent_r10a_fill_time_before_path_hour_count"] == aobs["fill_time_before_path_hour_count"] == 2
    assert c["parent_r10a_fill_time_inside_path_hour_count"] == aobs["fill_time_inside_path_hour_count"] == 223948
    assert c["parent_r10a_fill_time_after_path_hour_count"] == aobs["fill_time_after_path_hour_count"] == 0
    assert c["parent_r10a_earliest_boundary_offset_ms"] == aobs["fill_time_earliest_boundary_offset_ms"] == -51
    assert ac["release_consumed"] is True and ac["rerun_authorized"] is False
    assert a["claims_not_proven"]["a_51ms_tolerance_is_safe_for_general_history"] is False
    assert a["claims_not_proven"]["r10_rule_should_be_amended"] is False

    sources = c["primary_source_assessment"]
    assert sources["assessment_path"] == "research/archive_inventory/r10c/STATIC_PRIMARY_SOURCE_ASSESSMENT.md"
    assert sources["official_historical_data_url"] == "https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data"
    assert sources["official_node_repository_url"] == "https://github.com/hyperliquid-dex/node"
    assert sources["node_fills_by_block_is_write_fills_plus_batch_by_block_supported"] is True
    assert sources["batch_schema_local_time_block_time_block_number_events_supported"] is True
    assert sources["batch_by_block_waits_until_end_of_block_supported"] is True
    assert sources["local_time_timezone_semantics_defined_by_sources"] is False
    assert sources["block_time_timezone_semantics_defined_by_sources"] is False
    assert sources["s3_path_hour_partition_field_defined_by_sources"] is False
    assert sources["safe_fill_time_tolerance_defined_by_sources"] is False

    target = c["exact_future_network_target"]
    assert target == {
        "bucket": "hl-mainnet-node-data",
        "region": "ap-northeast-1",
        "key": OBJECT_KEY,
        "path_hour_utc_label": "2025-07-27T09:00:00Z",
        "path_hour_start_ms": 1753606800000,
        "path_hour_end_ms_exclusive": 1753610400000,
        "path_date_hour_prefix": "2025-07-27T09:",
        "previous_path_date_hour_prefix": "2025-07-27T08:",
        "next_path_date_hour_prefix": "2025-07-27T10:",
        "expected_size_bytes": 18147822,
        "expected_etag": OBJECT_ETAG,
        "expected_compressed_sha256": OBJECT_SHA,
        "storage_class": "STANDARD",
    }

    env = c["proposed_request_envelope"]
    assert env["maximum_one_time_budget_eur"] == 0.1
    assert env["maximum_monthly_budget_eur"] == 0
    assert env["maximum_get_object_requests"] == 1
    assert env["maximum_requests_per_object"] == 1
    assert env["maximum_retries_per_request"] == 0
    assert env["maximum_total_compressed_bytes"] == env["maximum_individual_compressed_bytes"] == 18147822
    assert env["maximum_total_decompressed_bytes"] == env["maximum_individual_decompressed_bytes"] == 268435456
    assert env["maximum_runtime_seconds"] == 120
    for key in ("requester_pays_required", "if_match_etag_required", "exact_content_length_required", "exact_response_etag_required", "compressed_sha256_must_match_parent_evidence"):
        assert env[key] is True, key
    for key in ("http_redirect_following_authorized", "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized", "get_object_attributes_authorized", "get_object_version_authorized"):
        assert env[key] is False, key

    iam = c["iam_boundary"]
    assert iam["existing_dedicated_r10_role_reuse_proposed"] is True
    assert iam["existing_dedicated_r10_role_reuse_authorized_now"] is False
    assert iam["existing_dedicated_r10_role_mutation_authorized"] is False
    assert iam["new_role_creation_authorized"] is False
    assert iam["role_arn"] == ROLE_ARN
    assert iam["future_session_policy_allowed_actions_only"] == ["s3:GetObject"]
    assert iam["future_session_policy_allowed_object_count"] == 1
    assert iam["future_session_policy_exact_object_arn"] == OBJECT_ARN
    assert iam["workflow_oidc_name_required"] == "Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10"
    assert iam["future_role_duration_seconds"] == 900

    rules = c["decompression_and_record_rules"]
    assert rules["lz4_frame_stream_only"] is True
    assert rules["alternate_decompressor_fallback_authorized"] is False
    assert rules["strict_utf8_decode"] is True
    assert rules["strict_json_duplicate_keys_rejected"] is True
    assert rules["strict_json_nonfinite_constants_rejected"] is True
    assert rules["required_top_level_record_type"] == "object"
    assert rules["required_block_fields"] == {"local_time":"string","block_time":"string","block_number":"integer","events":"array"}
    assert rules["maximum_record_bytes"] == 16777216
    assert rules["maximum_total_block_records"] == 500000
    assert rules["maximum_total_event_pairs"] == 2000000
    assert rules["maximum_metadata_string_bytes"] == 128

    corr = c["correlation_processing_rules"]
    assert corr["metadata_timezone_parsing_authorized"] is False
    assert corr["metadata_timezone_inference_authorized"] is False
    assert corr["metadata_datetime_conversion_authorized"] is False
    assert corr["individual_metadata_value_retention_authorized"] is False
    assert corr["metadata_prefix_comparison_is_raw_string_only"] is True
    assert corr["event_array_contents_inspection_authorized"] is True
    assert corr["event_pair_shape_inspection_authorized"] is True
    assert corr["leading_event_string_value_retention_authorized"] is False
    assert corr["leading_event_string_wallet_semantics_authorized"] is False
    assert corr["fill_object_field_allowlist"] == ["time"]
    assert corr["economic_fill_field_processing_authorized"] is False
    assert corr["fill_time_integer_milliseconds_processing_authorized"] is True
    assert corr["individual_fill_time_retention_authorized"] is False
    assert corr["fill_time_partition_buckets"] == ["BEFORE_PATH_HOUR", "INSIDE_PATH_HOUR", "AFTER_PATH_HOUR"]
    assert corr["fill_time_partition_uses_only_frozen_epoch_bounds"] is True
    assert corr["block_number_value_retention_authorized"] is False
    assert corr["per_block_identity_retention_authorized"] is False
    assert corr["per_wallet_processing_authorized"] is False
    assert corr["wallet_address_retention_authorized"] is False

    retained = set(c["retained_aggregate_fields_only"])
    assert retained == {
        "object_key", "expected_etag", "observed_etag", "compressed_bytes", "compressed_sha256",
        "decompressed_bytes", "block_record_count", "event_pair_count", "fill_time_count",
        "fill_time_before_path_hour_count", "fill_time_inside_path_hour_count", "fill_time_after_path_hour_count",
        "block_record_counts_by_local_prefix_and_block_prefix",
        "fill_counts_by_local_prefix_block_prefix_and_fill_partition",
        "block_records_with_before_fill_by_local_prefix_and_block_prefix",
        "block_record_count_with_any_before_fill", "boundary_record_correlation_classification",
    }

    pre = c["correlation_success_preconditions"]
    assert pre == {
        "exact_parent_block_record_count_required": 36029,
        "exact_parent_fill_time_count_required": 223950,
        "exact_parent_before_fill_count_required": 2,
        "exact_parent_inside_fill_count_required": 223948,
        "exact_parent_after_fill_count_required": 0,
        "exact_parent_local_time_path_prefix_count_required": 36029,
        "exact_parent_block_time_path_prefix_count_required": 36028,
        "exact_parent_block_time_previous_prefix_count_required": 1,
        "all_aggregate_conservation_checks_required": True,
    }
    assert c["allowed_boundary_record_correlation_classifications"] == [
        "EXACT_TWO_PRE_HOUR_FILLS_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD",
        "PRE_HOUR_FILLS_DO_NOT_EXACTLY_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD",
        "BOUNDARY_RECORD_CORRELATION_UNRESOLVED",
    ]

    assert all(value is False for value in c["interpretation_boundaries"].values())
    assert all(value is False for value in c["raw_or_disallowed_retention"].values())
    assert all(value is False for value in c["current_runtime_authority"].values())
    assert all(value is False for value in c["downstream_authorizations"].values())
    assert all(value is False for value in c["trading_authorizations"].values())
    assert c["human_approval_required_before_implementation"] is True
    assert c["separate_execution_release_required"] is True
    assert c["separate_canonical_activation_required"] is True
    assert c["network_requests_executed_by_preregistration"] == 0
    assert c["aws_iam_mutations_executed_by_preregistration"] == 0
    assert c["empirical_result"] is None

    assessment = ASSESSMENT.read_text(encoding="utf-8")
    assert "--write-fills" in assessment and "--batch-by-block" in assessment
    assert "waits until the end of the block" in assessment
    assert "do **not** define the timezone semantics" in assessment
    assert "do **not** state that the S3 hourly path partition" in assessment
    assert "do **not** define a safe timestamp tolerance" in assessment
    assert "does not justify a 51 ms tolerance" in assessment

    template = TEMPLATE.read_text(encoding="utf-8")
    assert "APPROVE_HL_ARCHIVE_R10C_BOUNDARY_RECORD_CORRELATION_001" in template
    assert "maximum_get_object_requests=1" in template
    assert "event_array_contents_inspection_authorized=true" in template
    assert "event_array_contents_inspection_scope=PAIR_SHAPE_AND_FILL_TIME_ONLY" in template
    assert "fill_object_field_allowlist=time" in template
    assert "metadata_timezone_inference_authorized=false" in template
    assert "economic_fill_field_processing_authorized=false" in template
    assert "wallet_address_retention_authorized=false" in template
    assert "execution_authorized_by_this_approval=false" in template
    assert "separate_execution_release_required=true" in template

    # APPROVAL_STATUS.md is a mutable lifecycle overlay. The preregistration
    # validator intentionally does not bind it to a pre-approval state; the
    # immutable preregistration contract above must remain valid after later,
    # separately reviewed approval, implementation, release and activation.
    assert STATUS.exists()

    print("R10C_BOUNDARY_RECORD_CORRELATION_PREREGISTRATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
