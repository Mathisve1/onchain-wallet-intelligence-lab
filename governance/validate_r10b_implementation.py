from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREREG = BASE / "r10b/R10B_BATCH_METADATA_LEXICAL_PREREGISTRATION.json"
APPROVAL = BASE / "r10b_approval/APPROVE_HL_ARCHIVE_R10B_BATCH_METADATA_LEXICAL_DIAGNOSTIC_001.json"
APPROVAL_TEXT = BASE / "r10b_approval/APPROVE_HL_ARCHIVE_R10B_BATCH_METADATA_LEXICAL_DIAGNOSTIC_001.txt"
IMPLEMENTATION = BASE / "r10b_implementation/R10B_IMPLEMENTATION_CONTRACT.json"
COLLECTOR = BASE / "r10b_implementation/collector.py"
WORKFLOW = BASE / "r10b_implementation/workflows/hyperliquid-archive-r10b-batch-metadata-lexical-diagnostic.yml"

PREREG_MERGE = "8ba7b0928ac45c66dd6df756491928fddbe2a060"
APPROVAL_MERGE = "0ca8bc4da2dbb3cda073a41c45a72e5f051419cc"
APPROVAL_SHA = "981b9277b652117c2a3648fa3870015d3efe590a595e84bcba22cf0b3f8f8061"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
OBJECT_KEY = "node_fills_by_block/hourly/20250727/9.lz4"
OBJECT_ARN = f"arn:aws:s3:::hl-mainnet-node-data/{OBJECT_KEY}"
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
RETAINED = {
    "object_key", "expected_etag", "observed_etag", "compressed_bytes", "compressed_sha256",
    "decompressed_bytes", "block_record_count", "local_time_lexical_class_counts",
    "block_time_lexical_class_counts", "local_time_prefix_bucket_counts", "block_time_prefix_bucket_counts",
    "local_time_equals_block_time_count", "local_time_differs_from_block_time_count",
    "metadata_string_length_min_local_time", "metadata_string_length_max_local_time",
    "metadata_string_length_min_block_time", "metadata_string_length_max_block_time",
    "lexical_diagnostic_classification",
}
CLASSIFICATIONS = [
    "BATCH_METADATA_LEXICALLY_PATH_HOUR_CONSISTENT",
    "BATCH_METADATA_LEXICALLY_CROSSES_PATH_HOUR",
    "BATCH_METADATA_LEXICAL_FORMAT_UNRESOLVED",
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    p = load(PREREG)
    a = load(APPROVAL)
    i = load(IMPLEMENTATION)
    workflow = WORKFLOW.read_text(encoding="utf-8")
    collector = COLLECTOR.read_text(encoding="utf-8")

    assert hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA
    assert p["diagnostic_id"] == a["diagnostic_id"] == i["diagnostic_id"] == "HL-ARCHIVE-R10B-BATCH-METADATA-LEXICAL-DIAGNOSTIC-001"
    assert p["status"] == "PREREGISTERED_NO_EXECUTION"
    assert a["status"] == "OWNER_APPROVED_IMPLEMENTATION_NO_EXECUTION"
    assert a["reviewed_commit"] == PREREG_MERGE
    assert a["exact_approval_text_sha256"] == APPROVAL_SHA
    assert i["status"] == "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE"
    assert i["r10b_preregistration_merge_commit"] == PREREG_MERGE
    assert i["r10b_approval_merge_commit"] == APPROVAL_MERGE
    assert i["approval_id"] == a["approval_id"]
    assert i["approval_text_sha256"] == APPROVAL_SHA

    target = i["exact_network_target"]
    assert target == {
        "bucket": "hl-mainnet-node-data",
        "region": "ap-northeast-1",
        "key": OBJECT_KEY,
        "expected_size_bytes": 18147822,
        "expected_etag": OBJECT_ETAG,
        "expected_compressed_sha256": OBJECT_SHA,
        "storage_class": "STANDARD",
    }
    ptarget = p["exact_future_network_target"]
    assert ptarget["key"] == target["key"]
    assert ptarget["expected_size_bytes"] == target["expected_size_bytes"]
    assert ptarget["expected_etag"] == target["expected_etag"]
    assert ptarget["expected_compressed_sha256_from_r10a"] == target["expected_compressed_sha256"]

    env = i["request_envelope"]
    assert env["maximum_one_time_budget_eur"] == 0.10
    assert env["maximum_monthly_budget_eur"] == 0
    assert env["maximum_get_object_requests"] == 1
    assert env["maximum_requests_per_object"] == 1
    assert env["maximum_retries_per_request"] == 0
    assert env["maximum_total_compressed_bytes"] == 18147822
    assert env["maximum_total_decompressed_bytes"] == 268435456
    assert env["maximum_runtime_seconds"] == 120
    for key in ("requester_pays_required", "if_match_etag_required", "exact_content_length_required", "exact_response_etag_required", "exact_compressed_sha256_required"):
        assert env[key] is True, key
    for key in ("head_object_authorized", "range_get_authorized", "list_objects_v2_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized", "get_object_attributes_authorized", "get_object_version_authorized", "http_redirect_following_authorized"):
        assert env[key] is False, key

    assert i["role_arn"] == ROLE_ARN
    assert i["role_reused_without_mutation"] is True
    assert i["new_role_created"] is False
    session = i["future_session_scope"]
    assert session["allowed_s3_actions_only"] == ["s3:GetObject"]
    assert session["allowed_object_count"] == 1
    assert session["exact_object_arn"] == OBJECT_ARN
    assert session["role_duration_seconds"] == 900

    processing = i["processing_contract"]
    for key in ("lz4_frame_stream_only", "strict_utf8_decode", "strict_json_duplicate_keys_rejected", "strict_json_nonfinite_constants_rejected", "metadata_lexical_processing", "aggregate_lexical_retention"):
        assert processing[key] is True, key
    assert processing["alternate_decompressor_fallback_authorized"] is False
    assert processing["required_top_level_record_type"] == "object"
    assert processing["required_block_fields"] == {"local_time":"string","block_time":"string","block_number":"integer","events":"array"}
    assert processing["maximum_record_bytes"] == 16777216
    assert processing["maximum_total_block_records"] == 500000
    assert processing["maximum_metadata_string_bytes"] == 128
    for key in ("timezone_parsing", "timezone_inference", "datetime_conversion_of_metadata", "individual_metadata_value_retention", "event_array_contents_inspection", "event_pair_count_retention", "block_number_value_retention", "individual_fill_time_processing", "wallet_address_retention", "wallet_aggregation", "economic_fill_field_processing", "raw_object_retention", "raw_block_event_fill_retention"):
        assert processing[key] is False, key

    lexical = i["lexical_rules"]
    assert lexical["class_precedence"] == CLASSES
    assert lexical["prefix_buckets"] == PREFIXES
    assert lexical["path_date_hour_prefix"] == "2025-07-27T09:"
    assert lexical["previous_date_hour_prefix"] == "2025-07-27T08:"
    assert lexical["next_date_hour_prefix"] == "2025-07-27T10:"
    assert lexical["prefix_comparison_is_raw_string_only"] is True
    assert lexical["local_vs_block_exact_string_equality_count"] is True
    assert set(lexical["regexes"]) == set(CLASSES)
    assert lexical["regexes"]["OTHER"] == "CATCH_ALL"
    assert set(i["retained_aggregate_fields_only"]) == RETAINED
    assert i["allowed_lexical_diagnostic_classifications"] == CLASSIFICATIONS

    for key in ("execution_release_present", "canonical_activation_present", "single_workflow_dispatch_authorized", "aws_oidc_authorized_now", "requester_pays_authorized_now", "get_object_authorized_now", "object_body_download_authorized_now", "decompression_authorized_now", "metadata_lexical_processing_authorized_now", "aggregate_lexical_retention_authorized_now"):
        assert i[key] is False, key
    assert i["network_requests_executed"] == 0
    assert i["aws_iam_mutations_executed"] == 0
    assert i["empirical_result"] is None
    assert all(v is False for v in i["interpretation_boundaries"].values())
    assert all(v is False for v in i["downstream_authorizations"].values())
    assert all(v is False for v in i["trading_authorizations"].values())

    candidate = i["workflow_candidate"]
    assert candidate["path"] == "research/archive_inventory/r10b_implementation/workflows/hyperliquid-archive-r10b-batch-metadata-lexical-diagnostic.yml"
    assert candidate["installed_path"] == ".github/workflows/hyperliquid-archive-r10b-batch-metadata-lexical-diagnostic.yml"
    assert candidate["installed_now"] is False
    assert candidate["manual_only"] is True
    assert candidate["workflow_name"] == "Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10"
    assert candidate["run_name"] == "R10B batch metadata lexical diagnostic"

    assert workflow.startswith("name: Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10\nrun-name: R10B batch metadata lexical diagnostic\n")
    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow and "push:" not in workflow
    for pin in (
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
        "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
        "aws-actions/configure-aws-credentials@e6de054238d6b7531b4efff3b6587d9aade6a06c",
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
    ):
        assert pin in workflow, pin
    assert f"role-to-assume: {ROLE_ARN}" in workflow
    assert "role-duration-seconds: 900" in workflow
    assert "retry-max-attempts: 1" in workflow
    assert '"Action":"s3:GetObject"' in workflow
    assert OBJECT_ARN in workflow
    assert OBJECT_SHA in workflow
    assert "research.archive_inventory.r10b_implementation.collector" in workflow
    assert "r10b-context.json" in workflow and "r10b-result.json" in workflow and "r10b.rc" in workflow and "R10B_FILES.sha256" in workflow
    assert workflow.index("Prove exact single-use R10B release before OIDC") < workflow.index("Assume existing R10 role")
    for forbidden in ("aws s3 ", "aws s3api ", "head-object", "list-objects", "get-object-attributes", "get-object-version"):
        assert forbidden not in workflow.lower(), forbidden
    for flag in ("event_array_contents_inspected", "wallet_address_retained", "economic_fill_field_processing_performed", "timezone_parsing_performed", "timezone_inference_performed", "r10_rule_amendment_performed", "six_hour_execution_performed", "wallet_ranking_performed", "pnl_or_alpha_analysis_performed", "copyability_analysis_performed"):
        assert flag in workflow, flag

    assert "for pair in block[\"events\"]" not in collector
    assert "for pair in block['events']" not in collector
    assert "closedPnl" not in collector and "feeToken" not in collector and "startPosition" not in collector
    assert "datetime.fromisoformat(" not in collector
    assert "datetime.fromtimestamp(" not in collector
    assert "prefix_bucket(" in collector and "classify_lexical(" in collector

    # Prior snapshots stay inert even though a later implementation overlay exists.
    assert all(v is False for v in p["current_runtime_authority"].values())
    assert all(v is False for v in a["current_runtime_authority"].values())
    assert a["execution_authorized_by_this_approval"] is False
    print("R10B_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
