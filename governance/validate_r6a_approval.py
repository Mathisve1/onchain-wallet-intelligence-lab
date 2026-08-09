from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r6a"
CONTRACT = BASE / "LEGACY_USER_KEY_LEXICAL_R6A_CONTRACT.json"
APPROVAL_TEXT = BASE / "approvals/APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001.txt"
APPROVAL = BASE / "approvals/APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001.json"
STATUS = BASE / "APPROVAL_STATUS.md"

PREREG_MERGE = "870fdf3e10a761d6c4589d43def8e436f3a129b5"
APPROVAL_SHA = "b24c67f527a320e533408fd821d10b5e2ea01d020c837e87ae5e5bbd386c94ed"
OBJECT_KEY = "node_fills/hourly/20250727/8.lz4"
OBJECT_ETAG = '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"'
OBJECT_SHA = "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    contract = load(CONTRACT)
    approval = load(APPROVAL)
    status = STATUS.read_text(encoding="utf-8")

    assert hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA
    assert approval["approval_id"] == "APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001"
    assert approval["reviewed_commit"] == PREREG_MERGE
    assert approval["approval_received_at_utc"] == "2026-08-09T16:36:00Z"
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert approval["approval_scope"] == "IMPLEMENTATION_AND_LATER_SEPARATE_RELEASE_PATH_ONLY"
    assert approval["execution_authorized_by_this_record"] is False
    assert approval["request_authorized_by_this_record"] is False
    assert approval["aws_role_mutation_authorized"] is False

    assert contract["pilot_id"] == "HL-ARCHIVE-LEGACY-USER-KEY-LEXICAL-R6A-001"
    assert contract["parent_r6"]["canonical_commit"] == "17a907923f63476c983b8c2dc131d34c491af913"
    assert contract["parent_r5"]["canonical_evidence_commit"] == "4400963aa972ed878650116202cc72880e667849"

    target = contract["exact_future_network_target"]
    assert approval["target_bucket"] == target["bucket"] == "hl-mainnet-node-data"
    assert approval["signing_region"] == target["signing_region"] == "ap-northeast-1"
    assert approval["object_key"] == target["key"] == OBJECT_KEY
    assert approval["object_size_bytes"] == target["expected_size_bytes"] == 12726384
    assert approval["object_etag"] == target["expected_etag"] == OBJECT_ETAG
    assert approval["expected_compressed_sha256"] == target["expected_compressed_sha256"] == OBJECT_SHA
    assert approval["expected_decompressed_byte_count"] == target["expected_decompressed_byte_count"] == 62169139

    envelope = contract["proposed_future_execution_envelope"]
    for key, expected in {
        "maximum_one_time_budget_eur": 0.10,
        "maximum_monthly_budget_eur": 0,
        "maximum_get_object_requests": 1,
        "maximum_requests_per_object": 1,
        "maximum_total_compressed_bytes": 12726384,
        "maximum_total_decompressed_bytes": 134217728,
        "maximum_runtime_seconds": 120,
        "maximum_retries_per_request": 0,
    }.items():
        assert approval[key] == envelope[key] == expected, key

    for key in (
        "if_match_etag_required",
        "exact_content_length_required",
        "exact_compressed_sha256_required",
        "exact_decompressed_byte_count_required",
    ):
        assert approval[key] is True and envelope[key] is True, key
    for key in (
        "head_object_authorized",
        "range_get_authorized",
        "list_objects_v2_authorized",
        "list_object_versions_authorized",
        "list_all_my_buckets_authorized",
        "http_redirect_following_authorized",
    ):
        assert approval[key] is False and envelope[key] is False, key

    classifier = contract["proposed_streaming_lexical_classifier"]
    assert approval["requester_pays_authorized_for_later_release"] is True
    assert approval["get_object_authorized_for_later_release"] is True
    assert approval["decompression_authorized_for_later_release"] is True
    assert approval["lexical_classification_authorized_for_later_release"] is True
    assert envelope["requester_pays_required"] is True
    for key in (
        "lz4_frame_stream_only",
        "strict_utf8_decode",
        "strict_json_duplicate_keys_rejected",
        "strict_json_nonfinite_constants_rejected",
    ):
        assert approval[key] is True and classifier[key] is True, key
    assert approval["alternate_decompressor_fallback_authorized"] is False
    assert classifier["alternate_decompressor_fallback_authorized"] is False
    assert approval["required_top_level_record_type"] == classifier["required_top_level_record_type"] == "array"
    assert approval["required_array_arity"] == classifier["required_array_arity"] == 2
    assert approval["required_ordered_element_types"] == classifier["required_ordered_element_types"] == ["string", "object"]
    assert approval["maximum_record_bytes"] == classifier["maximum_record_bytes"] == 16777216
    assert approval["maximum_records_parsed"] == classifier["maximum_records_parsed"] == 5000000
    assert approval["expected_nonempty_record_count"] == classifier["expected_nonempty_record_count"] == 162815

    counts = approval["lexical_count_authorizations"]
    assert all(value is True for value in counts.values())
    proposed_counts = classifier["leading_string_tests"]
    assert proposed_counts["count_all_leading_strings"] is True
    assert proposed_counts["count_length_42"] is True
    assert proposed_counts["count_regex_0x_40_hex_case_insensitive"] is True
    assert proposed_counts["count_regex_0x_40_hex_lowercase"] is True
    assert proposed_counts["count_nonmatching_0x_40_hex"] is True
    assert proposed_counts["retain_any_leading_string"] is False
    assert proposed_counts["retain_any_address"] is False
    assert proposed_counts["retain_any_hash_of_leading_string"] is False
    assert proposed_counts["retain_distinct_address_set"] is False

    assert all(value is False for value in approval["retention_authorizations"].values())
    assert all(value is False for value in approval["downstream_authorizations"].values())
    assert all(value is False for value in approval["trading_authorizations"].values())
    assert all(value is False for value in approval["current_runtime_authority"].values())
    assert approval["s3_requests_executed_under_r6a"] == 0
    assert approval["compressed_bytes_downloaded_under_r6a"] == 0
    assert approval["decompressed_bytes_processed_under_r6a"] == 0
    assert approval["empirical_result"] is None
    assert approval["approval_reason_code"] == "ONE_EXACT_R5_BOUND_LEGACY_OBJECT_FOR_USER_KEY_LEXICAL_COUNTS_ONLY"

    authority = contract["current_runtime_authority"]
    assert authority["human_approval_recorded"] is False
    assert authority["implementation_authorized"] is False
    assert authority["execution_authorized"] is False
    assert authority["paid_request_authorized"] is False
    assert authority["requester_pays_authorized"] is False
    assert authority["get_object_authorized"] is False
    assert authority["object_body_download_authorized"] is False
    assert authority["decompression_authorized"] is False
    assert authority["lexical_classification_authorized"] is False
    assert authority["s3_requests_executed"] == 0
    assert authority["empirical_result"] is None

    assert "HUMAN_APPROVED_IMPLEMENTATION_LANE_ONLY_NO_RUNTIME" in status
    assert PREREG_MERGE in status
    assert APPROVAL_SHA in status

    print("R6A_APPROVAL_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
