from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r5"
CONTRACT = BASE / "LEGACY_FORMAT_FINGERPRINT_R5_CONTRACT.json"
APPROVAL_TEXT = BASE / "approvals/APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001.txt"
APPROVAL = BASE / "approvals/APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001.json"
STATUS = BASE / "APPROVAL_STATUS.md"
IMPLEMENTATION = BASE / "R5_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = BASE / "R5_AWS_ROLE_REUSE_ANALYSIS.json"
COLLECTOR = BASE / "collector.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-legacy-format-fingerprint-r5.yml"
RELEASE = BASE / "R5_EXECUTION_RELEASE.json"
ACTIVATION = BASE / "R5_EXECUTION_RELEASE_CANONICALIZATION.json"

PREREG_MERGE = "58f724d7f0208a43f7462abd80e1e69d995acff9"
APPROVAL_MERGE = "c22e28074ba2e95e1fe88912c364124e01eb0ff7"
APPROVAL_SHA = "667f94a66ea07296162ae0627a9cf7fc5b439b3f8312c8617ece923159f5ddc8"
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
    text_bytes = APPROVAL_TEXT.read_bytes()
    status = STATUS.read_text(encoding="utf-8")

    assert hashlib.sha256(text_bytes).hexdigest() == APPROVAL_SHA
    assert approval["approval_id"] == "APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001"
    assert approval["reviewed_commit"] == PREREG_MERGE
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert approval["approval_scope"] == "IMPLEMENTATION_AND_LATER_SEPARATE_RELEASE_PATH_ONLY"
    assert approval["execution_authorized_by_this_record"] is False
    assert approval["request_authorized_by_this_record"] is False
    assert approval["aws_role_mutation_authorized"] is False

    assert contract["pilot_id"] == "HL-ARCHIVE-LEGACY-FORMAT-FINGERPRINT-R5-001"
    assert contract["parent_r4"]["evidence_merge_commit"] == "fe06874aeeb958d375a27100378f89bd25b4741b"
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
        "maximum_one_time_budget_eur": 0.10, "maximum_monthly_budget_eur": 0,
        "maximum_get_object_requests": 1, "maximum_requests_per_object": 1,
        "maximum_total_compressed_bytes": 12726384, "maximum_total_decompressed_bytes": 134217728,
        "maximum_runtime_seconds": 120, "maximum_retries_per_request": 0,
    }.items():
        assert approval[key] == envelope[key] == expected, key

    classifier = contract["proposed_format_classifier"]
    for key, expected in {
        "maximum_record_bytes": 16777216, "maximum_records_parsed": 5000000,
        "maximum_schema_nesting_depth": 16, "maximum_unique_field_paths": 4096,
        "maximum_unique_structural_signatures": 256,
    }.items():
        assert approval[key] == classifier[key] == expected, key

    assert approval["requester_pays_authorized_for_later_release"] is True
    assert approval["get_object_authorized_for_later_release"] is True
    assert approval["decompression_authorized_for_later_release"] is True
    assert approval["format_classification_authorized_for_later_release"] is True
    assert envelope["requester_pays_required"] is True
    for key in ("if_match_etag_required", "exact_content_length_required", "exact_compressed_sha256_required", "exact_decompressed_byte_count_required"):
        assert approval[key] is True and envelope[key] is True, key
    for key in ("lz4_frame_stream_only", "strict_utf8_decode", "strict_json_duplicate_keys_rejected", "strict_json_nonfinite_constants_rejected"):
        assert approval[key] is True and classifier[key] is True, key
    assert approval["alternate_decompressor_fallback_authorized"] is False
    assert classifier["alternate_decompressor_fallback_authorized"] is False
    for key in ("head_object_authorized", "range_get_authorized", "list_objects_v2_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized", "http_redirect_following_authorized"):
        assert approval[key] is False and envelope[key] is False, key

    assert all(value is False for value in approval["retention_authorizations"].values())
    assert all(value is False for value in approval["inference_authorizations"].values())
    assert all(value is False for value in approval["trading_authorizations"].values())
    assert all(value is False for value in approval["current_runtime_authority"].values())
    assert approval["s3_requests_executed_under_r5"] == 0
    assert approval["compressed_bytes_downloaded_under_r5"] == 0
    assert approval["decompressed_bytes_processed_under_r5"] == 0
    assert approval["empirical_result"] is None
    assert approval["approval_reason_code"] == "ONE_EXACT_R4_BOUND_LEGACY_OBJECT_FOR_CONTAINER_FORMAT_FINGERPRINT_ONLY"

    # Immutable preregistration remains non-self-authorizing after approval and implementation.
    authority = contract["current_runtime_authority"]
    assert authority["human_approval_recorded"] is False
    assert authority["implementation_authorized"] is False
    assert authority["execution_authorized"] is False
    assert authority["get_object_authorized"] is False
    assert authority["decompression_authorized"] is False
    assert authority["format_classification_authorized"] is False
    assert authority["s3_requests_executed"] == 0
    assert "HUMAN_APPROVED_IMPLEMENTATION_LANE_ONLY_NO_RUNTIME" in status
    assert APPROVAL_SHA in status

    # A later separately reviewed implementation may exist; approval snapshot itself remains inert.
    implementation_paths = (IMPLEMENTATION, ROLE_REUSE, COLLECTOR, WORKFLOW)
    if any(path.exists() for path in implementation_paths):
        assert all(path.exists() for path in implementation_paths)
        impl = load(IMPLEMENTATION)
        reuse = load(ROLE_REUSE)
        assert impl["status"] == "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION"
        assert impl["preregistration_commit"] == PREREG_MERGE
        assert impl["approval_merge_commit"] == APPROVAL_MERGE
        assert impl["approval_text_sha256"] == APPROVAL_SHA
        assert impl["execution_release_present"] is False
        assert impl["execution_authorized"] is False
        assert impl["expected_canonical_implementation_commit"] == "PENDING_CANONICAL_IMPLEMENTATION_MERGE"
        assert impl["s3_requests_executed"] == 0
        assert impl["empirical_result"] is None
        assert reuse["aws_iam_mutation_performed"] is False
        assert reuse["current_r5_network_authority"] is False

    if RELEASE.exists():
        release = load(RELEASE)
        assert release["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
        assert release["preregistration_commit"] == PREREG_MERGE
        assert release["approval_merge_commit"] == APPROVAL_MERGE
        assert release["approval_text_sha256"] == APPROVAL_SHA
        assert release["execution_ready"] is False
        assert release["single_workflow_dispatch_authorized"] is False
        assert release["requester_pays_authorized_by_candidate"] is False
        assert release["get_object_authorized_by_candidate"] is False
        assert release["s3_requests_executed"] == 0
        assert release["empirical_result"] is None
    assert not ACTIVATION.exists(), ACTIVATION

    print("R5_APPROVAL_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
