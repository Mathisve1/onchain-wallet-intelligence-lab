from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
R10B = BASE / "r10b"
CONTRACT = R10B / "R10B_BATCH_METADATA_LEXICAL_PREREGISTRATION.json"
STATUS = R10B / "APPROVAL_STATUS.md"
TEMPLATE = R10B / "HUMAN_APPROVAL_TEMPLATE_R10B.md"
ASSESSMENT = R10B / "STATIC_PRIMARY_SOURCE_ASSESSMENT.md"
R10A_ATTEST = BASE / "r10a_evidence/HL-ARCHIVE-R10A-TIMESTAMP-PARTITION-DIAGNOSTIC-001-ATTESTATION.json"
R10A_CONSUMPTION = BASE / "r10a_runtime/R10A_EXECUTION_RELEASE_CONSUMPTION.json"

PARENT_MERGE = "93e47e23b50068b24bcc0aa3aa1cc9d99891b8e6"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
OBJECT_KEY = "node_fills_by_block/hourly/20250727/9.lz4"
OBJECT_ARN = f"arn:aws:s3:::hl-mainnet-node-data/{OBJECT_KEY}"
OBJECT_SIZE = 18147822
OBJECT_ETAG = '"5a9941a240118a57f77a4c3ee95b8430-3"'
OBJECT_SHA = "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339"
CLASSES = [
    "ISO8601_Z_FRACTION",
    "ISO8601_Z_SECONDS",
    "ISO8601_OFFSET_FRACTION",
    "ISO8601_OFFSET_SECONDS",
    "ISO8601_NAIVE_FRACTION",
    "ISO8601_NAIVE_SECONDS",
    "DECIMAL_INTEGER_STRING",
    "OTHER",
]
PREFIXES = [
    "MATCHES_PATH_DATE_HOUR_PREFIX",
    "MATCHES_PREVIOUS_DATE_HOUR_PREFIX",
    "MATCHES_NEXT_DATE_HOUR_PREFIX",
    "OTHER_PREFIX",
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    c = load(CONTRACT)
    parent = load(R10A_ATTEST)
    consumption = load(R10A_CONSUMPTION)

    assert c["diagnostic_id"] == "HL-ARCHIVE-R10B-BATCH-METADATA-LEXICAL-DIAGNOSTIC-001"
    assert c["status"] == "PREREGISTERED_NO_EXECUTION"
    assert c["parent_r10a_evidence_merge_commit"] == PARENT_MERGE
    assert c["parent_r10a_run_id"] == 31386230522
    assert c["parent_r10a_job_id"] == 93447175508
    assert c["parent_r10a_artifact_id"] == 9061819935
    assert c["parent_r10a_artifact_sha256"] == "c52344b911b439db08a9a369f9016bde87f2925091ce83b97c0ee00744fb1e68"
    assert c["parent_r10a_research_conclusion"] == "FILL_TIME_SPILLS_OUTSIDE_PATH_HOUR"
    assert c["parent_r10a_fill_time_count"] == 223950
    assert c["parent_r10a_fill_time_before_path_hour_count"] == 2
    assert c["parent_r10a_fill_time_inside_path_hour_count"] == 223948
    assert c["parent_r10a_fill_time_after_path_hour_count"] == 0
    assert c["parent_r10a_earliest_boundary_offset_ms"] == -51
    assert c["parent_r10a_block_record_count"] == 36029
    assert c["parent_r10a_block_time_parseable_under_explicit_zone_rule"] == 0
    assert c["parent_r10a_local_time_explicitly_zoned_count"] == 0
    assert c["parent_r10a_release_consumed"] is True
    assert c["parent_r10a_rerun_authorized"] is False

    assert parent["status"] == "ATTESTED_COMPLETE_FILL_TIME_SPILL_OBSERVED"
    assert parent["workflow_run_id"] == 31386230522
    assert parent["claims_proven"]["exactly_two_fill_times_precede_path_hour_lower_bound"] is True
    assert parent["claims_not_proven"]["a_51ms_tolerance_is_safe_for_general_history"] is False
    assert parent["claims_not_proven"]["r10_rule_should_be_amended"] is False
    assert parent["r10_rule_amendment_authorized"] is False
    assert parent["six_hour_execution_authorized"] is False
    assert consumption["status"] == "CONSUMED_SUCCESS_FILL_TIME_SPILL_OBSERVED"
    assert consumption["release_consumed"] is True
    assert consumption["future_r10a_dispatch_authorized"] is False
    assert consumption["rerun_authorized"] is False

    sources = c["primary_source_assessment"]
    assert sources["assessment_path"] == "research/archive_inventory/r10b/STATIC_PRIMARY_SOURCE_ASSESSMENT.md"
    assert sources["official_historical_data_url"] == "https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data"
    assert sources["official_node_repository_url"] == "https://github.com/hyperliquid-dex/node"
    assert sources["official_l1_schema_url"] == "https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/nodes/l1-data-schemas"
    assert sources["node_fills_by_block_is_write_fills_plus_batch_by_block_supported"] is True
    assert sources["batch_schema_local_time_block_time_block_number_events_supported"] is True
    assert sources["path_hour_defined_by_fill_time_supported"] is False
    assert sources["batch_metadata_timezone_defined_by_sources"] is False
    assert sources["safe_fill_time_tolerance_defined_by_sources"] is False

    target = c["exact_future_network_target"]
    assert target == {
        "bucket": "hl-mainnet-node-data",
        "region": "ap-northeast-1",
        "key": OBJECT_KEY,
        "path_hour_utc_label": "2025-07-27T09:00:00Z",
        "path_date_hour_prefix": "2025-07-27T09:",
        "previous_path_date_hour_prefix": "2025-07-27T08:",
        "next_path_date_hour_prefix": "2025-07-27T10:",
        "expected_size_bytes": OBJECT_SIZE,
        "expected_etag": OBJECT_ETAG,
        "expected_compressed_sha256_from_r10a": OBJECT_SHA,
        "storage_class": "STANDARD",
    }

    env = c["proposed_request_envelope"]
    assert env["maximum_one_time_budget_eur"] == 0.10
    assert env["maximum_monthly_budget_eur"] == 0
    assert env["maximum_get_object_requests"] == 1
    assert env["maximum_requests_per_object"] == 1
    assert env["maximum_retries_per_request"] == 0
    assert env["maximum_total_compressed_bytes"] == OBJECT_SIZE
    assert env["maximum_individual_compressed_bytes"] == OBJECT_SIZE
    assert env["maximum_total_decompressed_bytes"] == 268435456
    assert env["maximum_individual_decompressed_bytes"] == 268435456
    assert env["maximum_runtime_seconds"] == 120
    for key in ("requester_pays_required", "if_match_etag_required", "exact_content_length_required", "exact_response_etag_required", "compressed_sha256_must_match_parent_r10a"):
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

    parse = c["decompression_and_record_rules"]
    assert parse["lz4_frame_stream_only"] is True
    assert parse["alternate_decompressor_fallback_authorized"] is False
    assert parse["strict_utf8_decode"] is True
    assert parse["strict_json_duplicate_keys_rejected"] is True
    assert parse["strict_json_nonfinite_constants_rejected"] is True
    assert parse["required_block_fields"] == {"local_time":"string","block_time":"string","block_number":"integer","events":"array"}
    assert parse["maximum_record_bytes"] == 16777216
    assert parse["maximum_total_block_records"] == 500000
    assert parse["maximum_metadata_string_bytes"] == 128
    assert parse["event_array_contents_inspection_authorized"] is False
    assert parse["event_pair_count_retention_authorized"] is False
    assert parse["block_number_value_retention_authorized"] is False

    lexical = c["lexical_classification_rules"]
    assert lexical["timezone_parsing_authorized"] is False
    assert lexical["timezone_inference_authorized"] is False
    assert lexical["datetime_conversion_authorized"] is False
    assert lexical["individual_metadata_value_retention_authorized"] is False
    assert lexical["class_precedence"] == CLASSES
    assert lexical["prefix_buckets"] == PREFIXES
    assert lexical["prefix_comparison_is_raw_string_only"] is True
    assert lexical["local_vs_block_exact_string_equality_count_authorized"] is True
    assert set(lexical["regexes"]) == set(CLASSES)
    assert lexical["regexes"]["OTHER"] == "CATCH_ALL"

    retained = set(c["retained_aggregate_fields_only"])
    required = {
        "object_key", "expected_etag", "observed_etag", "compressed_bytes", "compressed_sha256",
        "decompressed_bytes", "block_record_count", "local_time_lexical_class_counts",
        "block_time_lexical_class_counts", "local_time_prefix_bucket_counts", "block_time_prefix_bucket_counts",
        "local_time_equals_block_time_count", "local_time_differs_from_block_time_count",
        "metadata_string_length_min_local_time", "metadata_string_length_max_local_time",
        "metadata_string_length_min_block_time", "metadata_string_length_max_block_time",
        "lexical_diagnostic_classification",
    }
    assert retained == required
    assert all(value is False for value in c["raw_or_disallowed_retention"].values())
    assert all(value is False for value in c["interpretation_boundaries"].values())
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
    assert "does not justify a 51 ms tolerance" in assessment
    assert "--write-fills --batch-by-block" in assessment
    assert "do **not** state" in assessment
    template = TEMPLATE.read_text(encoding="utf-8")
    status = STATUS.read_text(encoding="utf-8")
    assert "APPROVE_HL_ARCHIVE_R10B_BATCH_METADATA_LEXICAL_DIAGNOSTIC_001" in template
    assert "maximum_get_object_requests=1" in template
    assert "timezone_inference_authorized=false" in template
    assert "event_array_contents_inspection_authorized=false" in template
    assert "economic_fill_field_processing_authorized=false" in template
    assert "execution_authorized_by_this_approval=false" in template
    assert "AWAITING_SEPARATE_HUMAN_APPROVAL" in status

    # This validator proves the immutable preregistration snapshot remains inert.
    # Later approval, implementation, release, or evidence must be separate overlays
    # and must never rewrite these preregistered zero-authority fields.
    assert c["status"] == "PREREGISTERED_NO_EXECUTION"
    assert all(value is False for value in c["current_runtime_authority"].values())
    assert c["network_requests_executed_by_preregistration"] == 0
    assert c["aws_iam_mutations_executed_by_preregistration"] == 0
    assert c["empirical_result"] is None

    print("R10B_BATCH_METADATA_LEXICAL_PREREGISTRATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
