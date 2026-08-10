from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
R10A = BASE / "r10a"
CONTRACT = R10A / "R10A_TIMESTAMP_PARTITION_PREREGISTRATION.json"
STATUS = R10A / "APPROVAL_STATUS.md"
TEMPLATE = R10A / "HUMAN_APPROVAL_TEMPLATE_R10A.md"
R10_ATTEST = BASE / "r10_data_execution/HL-ARCHIVE-POST-BOUNDARY-MULTI-HOUR-FEATURE-R10-001-ATTESTATION.json"
R10_CONSUMPTION = BASE / "r10_data_execution/R10_EXECUTION_RELEASE_CONSUMPTION.json"
R9_ATTEST = BASE / "r9/evidence/HL-ARCHIVE-MODERN-WALLET-FEATURE-PILOT-R9-001-ATTESTATION.json"

PARENT_MERGE = "18dbd816bbc33979261247825a5133ee48874d51"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
OBJECT_KEY = "node_fills_by_block/hourly/20250727/9.lz4"
OBJECT_ARN = f"arn:aws:s3:::hl-mainnet-node-data/{OBJECT_KEY}"
OBJECT_SIZE = 18147822
OBJECT_ETAG = '"5a9941a240118a57f77a4c3ee95b8430-3"'


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    c = load(CONTRACT)
    r10 = load(R10_ATTEST)
    consumption = load(R10_CONSUMPTION)
    r9 = load(R9_ATTEST)

    assert c["diagnostic_id"] == "HL-ARCHIVE-R10A-TIMESTAMP-PARTITION-DIAGNOSTIC-001"
    assert c["status"] == "PREREGISTERED_NO_EXECUTION"
    assert c["research_question"] == "HOW_DOES_NODE_FILLS_BY_BLOCK_PATH_HOUR_RELATE_TO_FILL_TIME_BLOCK_TIME_AND_LOCAL_TIME"
    assert c["parent_r10_unresolved_evidence_merge_commit"] == PARENT_MERGE
    assert c["parent_r10_run_id"] == 31377732916
    assert c["parent_r10_job_id"] == 93420701174
    assert c["parent_r10_artifact_id"] == 9058595361
    assert c["parent_r10_artifact_sha256"] == "e6aebcbc0c73aecbea994fb4bd095c56f6c86b9ba5aa0dc152bee125b08f33bb"
    assert c["parent_r10_research_conclusion"] == "MULTI_HOUR_FEATURE_PIPELINE_UNRESOLVED"
    assert c["parent_r10_failure_class"] == "fill time lies outside source path hour"
    assert c["parent_r10_release_consumed"] is True
    assert c["parent_r10_rerun_authorized"] is False
    assert c["parent_r10_wallet_feature_rows_retained"] == 0

    assert r10["status"] == "ATTESTED_RESEARCH_UNRESOLVED"
    assert r10["release_consumed"] is True
    assert r10["rerun_authorized"] is False
    assert r10["claims_proven"]["strict_fill_time_within_source_path_hour_rule_was_not_satisfied"] is True
    assert r10["claims_not_proven"]["direction_or_magnitude_of_path_hour_time_misalignment"] is False
    assert consumption["status"] == "CONSUMED_RESEARCH_UNRESOLVED"
    assert consumption["release_consumed"] is True
    assert consumption["future_r10_dispatch_authorized"] is False
    assert consumption["remaining_budget_is_not_reusable_without_new_release"] is True

    static = c["static_r9_context"]
    assert static["run_id"] == 31336490854
    assert static["global_first_fill_time_utc"] == "2025-07-27T08:50:10.273Z"
    assert static["global_last_fill_time_utc"] == "2025-07-27T08:59:59.895Z"
    assert static["resolves_r10_mismatch_semantics"] is False
    assert r9["execution_identity"]["workflow_run_id"] == 31336490854

    target = c["exact_future_network_target"]
    assert target == {
        "bucket": "hl-mainnet-node-data",
        "region": "ap-northeast-1",
        "key": OBJECT_KEY,
        "path_hour_utc": "2025-07-27T09:00:00Z",
        "expected_size_bytes": OBJECT_SIZE,
        "expected_etag": OBJECT_ETAG,
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
    for key in ("requester_pays_required", "if_match_etag_required", "exact_content_length_required", "exact_response_etag_required", "compressed_sha256_computed_and_retained"):
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

    parse = c["decompression_and_parse_rules"]
    assert parse["lz4_frame_stream_only"] is True
    assert parse["alternate_decompressor_fallback_authorized"] is False
    assert parse["strict_utf8_decode"] is True
    assert parse["strict_json_duplicate_keys_rejected"] is True
    assert parse["strict_json_nonfinite_constants_rejected"] is True
    assert parse["required_block_fields"] == {"local_time":"string","block_time":"string","block_number":"integer","events":"array"}
    assert parse["required_event_pair_ordered_element_types"] == ["string", "object"]
    assert parse["required_leading_string_regex"] == "^0x[0-9a-f]{40}$"

    ts = c["timestamp_processing_rules"]
    assert ts["fill_time_field"] == "time"
    assert ts["fill_time_required_type"] == "integer_milliseconds_since_unix_epoch"
    assert ts["block_time_processing"] == "PARSE_ONLY_IF_ISO8601_HAS_EXPLICIT_Z_OR_NUMERIC_OFFSET"
    assert ts["local_time_processing"] == "PARSE_ONLY_IF_ISO8601_HAS_EXPLICIT_Z_OR_NUMERIC_OFFSET"
    assert ts["timezone_inference_for_local_time_authorized"] is False
    assert ts["individual_timestamp_retention_authorized"] is False
    assert ts["individual_wallet_address_retention_authorized"] is False
    assert ts["economic_fill_field_processing_authorized"] is False
    assert ts["wallet_aggregation_authorized"] is False

    retained = set(c["retained_aggregate_fields_only"])
    for required in (
        "fill_time_before_path_hour_count", "fill_time_inside_path_hour_count", "fill_time_after_path_hour_count",
        "fill_time_path_hour_offset_histogram", "block_time_parseable_count", "block_time_unparseable_count",
        "block_time_path_hour_offset_histogram", "local_time_not_explicitly_zoned_count",
        "fill_minus_block_time_delta_histogram", "alignment_classification",
    ):
        assert required in retained
    assert "wallet_address" not in retained
    assert "coin" not in retained
    assert "closedPnl" not in retained

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

    template = TEMPLATE.read_text(encoding="utf-8")
    status = STATUS.read_text(encoding="utf-8")
    assert "APPROVE_HL_ARCHIVE_R10A_TIMESTAMP_PARTITION_DIAGNOSTIC_001" in template
    assert "maximum_get_object_requests=1" in template
    assert "existing_dedicated_r10_role_reuse_authorized=true" in template
    assert "existing_dedicated_r10_role_mutation_authorized=false" in template
    assert "wallet_address_retention_authorized=false" in template
    assert "execution_authorized_by_this_approval=false" in template
    assert "AWAITING_SEPARATE_HUMAN_APPROVAL" in status

    assert not (R10A / "collector.py").exists()
    assert not (R10A / "APPROVAL_RECEIPT.json").exists()
    assert not (R10A / "EXECUTION_RELEASE.json").exists()
    assert not (ROOT / ".github/workflows/hyperliquid-archive-r10a-timestamp-partition-diagnostic.yml").exists()

    print("R10A_TIMESTAMP_PARTITION_PREREGISTRATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
