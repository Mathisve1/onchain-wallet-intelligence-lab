from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R5 = ROOT / "research/archive_inventory/r5"
CONTRACT = R5 / "LEGACY_FORMAT_FINGERPRINT_R5_CONTRACT.json"
DERIVATION = R5 / "R4_DERIVATION.json"
SOURCES = R5 / "OFFICIAL_SOURCE_EVIDENCE.json"
STATUS = R5 / "APPROVAL_STATUS.md"
TEMPLATE = R5 / "HUMAN_APPROVAL_TEMPLATE.md"
PARENT = ROOT / "research/archive_inventory/r4/evidence/run-31313913525/r4-body-result.json"

EXPECTED_PARENT_MERGE = "fe06874aeeb958d375a27100378f89bd25b4741b"
EXPECTED_KEY = "node_fills/hourly/20250727/8.lz4"
EXPECTED_ETAG = '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"'
EXPECTED_COMPRESSED_SHA = "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622"
EXPECTED_CLASSIFIERS = [
    "UTF8_NDJSON_PAIR_STRING_OBJECT",
    "UTF8_NDJSON_PAIR_OBJECT_STRING",
    "UTF8_NDJSON_ARRAY_OTHER",
    "UTF8_NDJSON_OBJECT_STREAM",
    "UTF8_NDJSON_MIXED_JSON_ROOTS",
    "UTF8_SINGLE_JSON_ARRAY_DOCUMENT",
    "UTF8_SINGLE_JSON_OBJECT_DOCUMENT",
    "UTF8_CONCATENATED_JSON_VALUES",
    "UTF8_NONJSON_OR_UNRESOLVED",
    "NON_UTF8_OR_UNRESOLVED",
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    contract = load(CONTRACT)
    derivation = load(DERIVATION)
    sources = load(SOURCES)
    parent = load(PARENT)

    assert contract["pilot_id"] == "HL-ARCHIVE-LEGACY-FORMAT-FINGERPRINT-R5-001"
    assert contract["status"] == "PREREGISTERED_STATIC_NO_EXECUTION"
    assert contract["parent_r4"]["evidence_merge_commit"] == EXPECTED_PARENT_MERGE
    assert contract["parent_r4"]["run_id"] == 31313913525
    assert contract["parent_r4"]["legacy_failure_class"] == "UTF8_NDJSON_OBJECT_SCHEMA_UNRESOLVED"
    assert contract["parent_r4"]["legacy_compressed_sha256"] == EXPECTED_COMPRESSED_SHA
    assert contract["parent_r4"]["legacy_decompressed_byte_count"] == 62169139

    target = contract["exact_future_network_target"]
    assert target == {
        "bucket": "hl-mainnet-node-data",
        "signing_region": "ap-northeast-1",
        "regional_virtual_hosted_endpoint": "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com",
        "key": EXPECTED_KEY,
        "expected_size_bytes": 12726384,
        "expected_etag": EXPECTED_ETAG,
        "expected_compressed_sha256": EXPECTED_COMPRESSED_SHA,
        "expected_decompressed_byte_count": 62169139,
    }

    envelope = contract["proposed_future_execution_envelope"]
    assert envelope["maximum_one_time_budget_eur"] == 0.1
    assert envelope["maximum_monthly_budget_eur"] == 0
    assert envelope["maximum_get_object_requests"] == 1
    assert envelope["maximum_requests_per_object"] == 1
    assert envelope["maximum_total_compressed_bytes"] == 12726384
    assert envelope["maximum_total_decompressed_bytes"] == 134217728
    assert envelope["maximum_runtime_seconds"] == 120
    assert envelope["maximum_retries_per_request"] == 0
    for key in (
        "requester_pays_required",
        "if_match_etag_required",
        "exact_content_length_required",
        "exact_compressed_sha256_required",
        "exact_decompressed_byte_count_required",
    ):
        assert envelope[key] is True, key
    for key in (
        "http_redirect_following_authorized",
        "head_object_authorized",
        "range_get_authorized",
        "list_objects_v2_authorized",
        "list_object_versions_authorized",
        "list_all_my_buckets_authorized",
    ):
        assert envelope[key] is False, key

    classifier = contract["proposed_format_classifier"]
    assert classifier["classifier_precedence"] == EXPECTED_CLASSIFIERS
    assert classifier["lz4_frame_stream_only"] is True
    assert classifier["alternate_decompressor_fallback_authorized"] is False
    assert classifier["strict_utf8_decode"] is True
    assert classifier["strict_json_duplicate_keys_rejected"] is True
    assert classifier["strict_json_nonfinite_constants_rejected"] is True
    assert classifier["maximum_record_bytes"] == 16777216
    assert classifier["maximum_records_parsed"] == 5000000
    assert classifier["maximum_schema_nesting_depth"] == 16
    assert classifier["maximum_unique_field_paths"] == 4096
    assert classifier["maximum_unique_structural_signatures"] == 256
    for key in (
        "payload_values_in_evidence_authorized",
        "string_values_in_evidence_authorized",
        "numeric_values_in_evidence_authorized",
        "wallet_address_retention_from_body_authorized",
        "record_payload_retention_authorized",
        "raw_compressed_object_retention_authorized",
        "raw_decompressed_payload_retention_authorized",
    ):
        assert classifier[key] is False, key

    semantic = contract["semantic_boundaries"]
    assert all(value is False for value in semantic.values())
    assert all(value is False for value in contract["trading_authorizations"].values())

    authority = contract["current_runtime_authority"]
    assert authority["s3_requests_executed"] == 0
    assert authority["compressed_bytes_downloaded"] == 0
    assert authority["decompressed_bytes_processed"] == 0
    assert authority["empirical_result"] is None
    for key, value in authority.items():
        if key.endswith("authorized") or key in {"human_approval_recorded", "implementation_authorized", "execution_release_present"}:
            assert value is False, key

    legacy = next(row for row in parent["observations"] if row["dataset_family_id"] == "node_fills")
    modern = next(row for row in parent["observations"] if row["dataset_family_id"] == "node_fills_by_block")
    assert legacy["key"] == EXPECTED_KEY
    assert legacy["compressed_object_sha256"] == EXPECTED_COMPRESSED_SHA
    assert legacy["decompressed_byte_count"] == 62169139
    assert legacy["decompression_status"] == "LZ4_FRAME_DECOMPRESSED"
    assert legacy["failure_class"] == "UTF8_NDJSON_OBJECT_SCHEMA_UNRESOLVED"
    assert legacy["record_count"] == 0
    assert modern["field_path_type_sets"]["/events/*"] == ["array"]
    assert set(modern["field_path_type_sets"]["/events/*/*"]) == {"object", "string"}

    assert derivation["parent_evidence_merge_commit"] == EXPECTED_PARENT_MERGE
    assert derivation["inference_status"] == "HYPOTHESIS_ONLY_NOT_EMPIRICALLY_PROVEN"
    assert derivation["modern_observation"]["event_container_type"] == "array"
    assert set(derivation["modern_observation"]["event_member_type_set"]) == {"object", "string"}

    urls = {row["url"] for row in sources["sources"]}
    assert "https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data" in urls
    assert "https://github.com/hyperliquid-dex/node" in urls
    assert "https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint" in urls
    assert sources["network_execution_authority"] is False
    assert sources["semantic_equivalence_authority"] is False
    assert sources["trading_authority"] is False

    status_text = STATUS.read_text(encoding="utf-8")
    template_text = TEMPLATE.read_text(encoding="utf-8")
    assert "PREREGISTERED_STATIC_NO_EXECUTION" in status_text
    assert "APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001" in template_text
    assert "reviewed_commit=<CANONICAL_R5_PREREGISTRATION_MERGE_COMMIT>" in template_text

    forbidden_paths = [
        ROOT / ".github/workflows/hyperliquid-archive-legacy-format-fingerprint-r5.yml",
        R5 / "collector.py",
        R5 / "R5_IMPLEMENTATION_CONTRACT.json",
        R5 / "R5_EXECUTION_RELEASE.json",
        R5 / "R5_EXECUTION_RELEASE_CANONICALIZATION.json",
        R5 / "approvals/APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001.txt",
        R5 / "approvals/APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001.json",
    ]
    for path in forbidden_paths:
        assert not path.exists(), path

    print("R5_PREREGISTRATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
