from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r6a"
CONTRACT = BASE / "LEGACY_USER_KEY_LEXICAL_R6A_CONTRACT.json"
DERIVATION = BASE / "R6_DERIVATION.json"
TEMPLATE = BASE / "HUMAN_APPROVAL_TEMPLATE.md"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    contract = load(CONTRACT)
    derivation = load(DERIVATION)
    template = TEMPLATE.read_text(encoding="utf-8")

    assert contract["pilot_id"] == "HL-ARCHIVE-LEGACY-USER-KEY-LEXICAL-R6A-001"
    assert contract["status"] == "PREREGISTERED_STATIC_NO_EXECUTION"

    parent_r6 = contract["parent_r6"]
    assert parent_r6["canonical_commit"] == "17a907923f63476c983b8c2dc131d34c491af913"
    assert parent_r6["terminal_result"] == "LEADING_STRING_USER_ADDRESS_SEMANTICS_HIGH_CONFIDENCE_STATIC_INFERENCE"
    assert parent_r6["semantic_label"] == "HYPERLIQUID_USER_ADDRESS"
    assert parent_r6["semantic_label_status"] == "SUPPORTED_INFERENCE_NOT_DIRECT_SERIALIZER_PROOF"
    assert parent_r6["confidence_class"] == "HIGH"

    parent_r5 = contract["parent_r5"]
    assert parent_r5["canonical_evidence_commit"] == "4400963aa972ed878650116202cc72880e667849"
    assert parent_r5["run_id"] == 31321019885
    assert parent_r5["nonempty_record_count"] == 162815
    assert parent_r5["format_class"] == "UTF8_NDJSON_PAIR_STRING_OBJECT"

    target = contract["exact_future_network_target"]
    assert target == {
        "bucket": "hl-mainnet-node-data",
        "signing_region": "ap-northeast-1",
        "regional_virtual_hosted_endpoint": "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com",
        "key": "node_fills/hourly/20250727/8.lz4",
        "expected_size_bytes": 12726384,
        "expected_etag": '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"',
        "expected_compressed_sha256": "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622",
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
    assert envelope["requester_pays_required"] is True
    assert envelope["if_match_etag_required"] is True
    assert envelope["exact_content_length_required"] is True
    assert envelope["exact_compressed_sha256_required"] is True
    assert envelope["exact_decompressed_byte_count_required"] is True
    for key in (
        "http_redirect_following_authorized",
        "head_object_authorized",
        "range_get_authorized",
        "list_objects_v2_authorized",
        "list_object_versions_authorized",
        "list_all_my_buckets_authorized",
    ):
        assert envelope[key] is False, key

    classifier = contract["proposed_streaming_lexical_classifier"]
    assert classifier["required_top_level_record_type"] == "array"
    assert classifier["required_array_arity"] == 2
    assert classifier["required_ordered_element_types"] == ["string", "object"]
    assert classifier["expected_nonempty_record_count"] == 162815
    tests = classifier["leading_string_tests"]
    assert tests["count_all_leading_strings"] is True
    assert tests["count_length_42"] is True
    assert tests["count_regex_0x_40_hex_case_insensitive"] is True
    assert tests["count_regex_0x_40_hex_lowercase"] is True
    assert tests["count_nonmatching_0x_40_hex"] is True
    assert tests["retain_any_leading_string"] is False
    assert tests["retain_any_address"] is False
    assert tests["retain_any_hash_of_leading_string"] is False
    assert tests["retain_distinct_address_set"] is False

    assert classifier["retained_aggregates_only"] == [
        "nonempty_record_count",
        "pair_string_object_record_count",
        "leading_string_count",
        "leading_string_length_42_count",
        "leading_string_0x40hex_count",
        "leading_string_lowercase_0x40hex_count",
        "leading_string_non_0x40hex_count",
    ]
    for key in (
        "payload_values_in_evidence_authorized",
        "string_values_in_evidence_authorized",
        "numeric_values_in_evidence_authorized",
        "wallet_address_retention_authorized",
        "record_payload_retention_authorized",
        "raw_compressed_object_retention_authorized",
        "raw_decompressed_payload_retention_authorized",
    ):
        assert classifier[key] is False, key

    interpretation = contract["interpretation_boundary"]
    assert interpretation["lexical_match_may_strengthen_parent_r6_semantic_inference"] is True
    for key, value in interpretation.items():
        if key != "lexical_match_may_strengthen_parent_r6_semantic_inference":
            assert value is False, key

    assert all(value is False for value in contract["trading_authorizations"].values())

    authority = contract["current_runtime_authority"]
    for key in (
        "human_approval_recorded",
        "implementation_authorized",
        "execution_release_present",
        "execution_authorized",
        "paid_request_authorized",
        "requester_pays_authorized",
        "get_object_authorized",
        "object_body_download_authorized",
        "decompression_authorized",
        "lexical_classification_authorized",
    ):
        assert authority[key] is False, key
    assert authority["s3_requests_executed"] == 0
    assert authority["compressed_bytes_downloaded"] == 0
    assert authority["decompressed_bytes_processed"] == 0
    assert authority["empirical_result"] is None

    assert derivation["parent_canonical_commit"] == parent_r6["canonical_commit"]
    assert derivation["child_gate_id"] == contract["pilot_id"]
    assert derivation["current_network_authority"] is False
    assert derivation["current_paid_request_authority"] is False
    assert derivation["current_wallet_address_retention_authority"] is False
    assert derivation["current_wallet_reconstruction_authority"] is False
    assert derivation["current_trading_authority"] is False

    assert "APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001" in template
    assert "reviewed_commit=<CANONICAL_R6A_PREREGISTRATION_MERGE_COMMIT>" in template
    assert "maximum_one_time_budget_eur=0.10" in template
    assert "maximum_get_object_requests=1" in template
    assert "retain_any_leading_string=false" in template
    assert "retain_any_wallet_address=false" in template
    assert "wallet_reconstruction_authorized=false" in template
    assert "live_authorized=false" in template

    print("R6A_PREREGISTRATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
