from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R10 = ROOT / "research/archive_inventory/r10"
CONTRACT = R10 / "POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_CONTRACT.json"
SELECTION = R10 / "R3_OBJECT_SELECTION.json"
DERIVATION = R10 / "R9_DERIVATION.json"
IAM = R10 / "R10_IAM_DESIGN.json"
COST = R10 / "R10_COST_ENVELOPE.json"
TEMPLATE = R10 / "HUMAN_APPROVAL_TEMPLATE_R10.md"
STATUS = R10 / "APPROVAL_STATUS.md"
README = R10 / "README.md"
R3_SUMMARY = ROOT / "research/archive_inventory/r3/evidence/run-31299905850/R3_COMPACT_INVENTORY_SUMMARY.json"
R4_POLICY = ROOT / "research/archive_inventory/r4/R4_IAM_POLICY_TEMPLATE.json"
R4_PRICING = ROOT / "research/archive_inventory/r4/R4_PRICING_EVIDENCE.json"
R9_ATTESTATION = ROOT / "research/archive_inventory/r9/evidence/HL-ARCHIVE-MODERN-WALLET-FEATURE-PILOT-R9-001-ATTESTATION.json"
R9_CONSUMPTION = ROOT / "research/archive_inventory/r9/R9_EXECUTION_RELEASE_CONSUMPTION.json"

PILOT_ID = "HL-ARCHIVE-POST-BOUNDARY-MULTI-HOUR-FEATURE-R10-001"
R9_EVIDENCE_MERGE = "bdbcb94305670beda4cf5629951ee8c9e41c7495"
R8B_CUTOVER_MERGE = "b77debdf57cbe07bfa190fd40946f2fe897e3a33"
R3_ARTIFACT_SHA = "1049509ef12f1ef2a312f6ded1d443b434e2ed860503a264f103a73c2a70cf88"
R3_RAW_SHA = "94c3e77a05de2363b95abdce718dfd61f1b440f3d9c3972a0d03ce28a9edc479"
ROLE = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
EXPECTED = [
    ("2025-07-27T09:00:00Z", "node_fills_by_block/hourly/20250727/9.lz4", 18147822, '"5a9941a240118a57f77a4c3ee95b8430-3"'),
    ("2025-07-27T10:00:00Z", "node_fills_by_block/hourly/20250727/10.lz4", 21349239, '"cb25fba5dc3be80fd8c46dde03144655-3"'),
    ("2025-07-27T11:00:00Z", "node_fills_by_block/hourly/20250727/11.lz4", 17582600, '"758da733bb2d3913d0fdd8088b6fb63d-3"'),
    ("2025-07-27T12:00:00Z", "node_fills_by_block/hourly/20250727/12.lz4", 21672141, '"d6ee46b1bdfad4026e21d4285ed0cbc5-3"'),
    ("2025-07-27T13:00:00Z", "node_fills_by_block/hourly/20250727/13.lz4", 20840630, '"c3c9db0101ff278b5ced13ab278a2b85-3"'),
    ("2025-07-27T14:00:00Z", "node_fills_by_block/hourly/20250727/14.lz4", 21407266, '"3c6ab944be1ed8bd12932eb390267a21-3"'),
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


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def main() -> int:
    c = load(CONTRACT)
    s = load(SELECTION)
    d = load(DERIVATION)
    iam = load(IAM)
    cost = load(COST)
    r3 = load(R3_SUMMARY)
    r4_policy = load(R4_POLICY)
    r4_pricing = load(R4_PRICING)
    r9 = load(R9_ATTESTATION)
    r9_consumption = load(R9_CONSUMPTION)
    template = TEMPLATE.read_text(encoding="utf-8")
    status = STATUS.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")

    assert c["pilot_id"] == PILOT_ID
    assert c["status"] == "PREREGISTERED_NO_EXECUTION"
    assert c["parent_r9_evidence_commit"] == R9_EVIDENCE_MERGE
    assert c["parent_r8b_cutover_commit"] == R8B_CUTOVER_MERGE
    assert c["source_r3_run_id"] == 31299905850
    assert c["source_r3_artifact_id"] == 9034170863
    assert c["source_r3_artifact_sha256"] == R3_ARTIFACT_SHA
    assert c["source_r3_raw_result_sha256"] == R3_RAW_SHA

    assert r9["status"] == "ATTESTED_COMPLETE"
    assert r9["technical_result"] == "MODERN_WALLET_FEATURE_PIPELINE_COMPLETE"
    assert r9["retained_feature_result"]["row_count"] == 887
    assert r9["retained_feature_result"]["sum_fill_count"] == 17516
    assert r9["claims_not_proven"]["wallet_ranking_is_authorized"] is False
    assert r9_consumption["release_consumed"] is True
    assert r9_consumption["future_r9_dispatch_authorized"] is False
    assert r9_consumption["rerun_authorized"] is False
    assert d["parent_r9_evidence_commit"] == R9_EVIDENCE_MERGE
    assert d["parent_r9_run_id"] == 31336490854
    assert d["parent_r9_terminal_result"] == "MODERN_WALLET_FEATURE_PIPELINE_COMPLETE"
    assert d["parent_r9_release_consumed"] is True
    assert d["parent_r9_rerun_authorized"] is False
    assert all(d[k] is False for k in (
        "new_network_authority_created_by_derivation",
        "new_retention_authority_created_by_derivation",
        "new_ranking_authority_created_by_derivation",
        "new_trading_authority_created_by_derivation",
    ))

    modern = next(row for row in r3["family_summaries"] if row["dataset_family_id"] == "node_fills_by_block")
    assert modern["family_status"] == "COMPLETE"
    assert modern["entry_count"] == 9070
    assert modern["missing_internal_hour_count"] == 0
    assert modern["earliest_path_hour_utc"] == "2025-07-27T08:00:00Z"
    assert r3["artifact_sha256"] == R3_ARTIFACT_SHA
    assert r3["result_raw_sha256"] == R3_RAW_SHA
    assert s["source_r3_family_status"] == "COMPLETE"
    assert s["source_r3_modern_family_entry_count"] == 9070
    assert s["source_r3_modern_family_missing_internal_hour_count"] == 0
    assert s["selection_includes_censored_boundary_hour"] is False
    assert s["selection_derived_without_new_s3_request"] is True
    assert s["new_s3_requests_executed"] == 0

    objects = c["exact_future_network_targets"]
    selected = s["selected_objects"]
    assert len(objects) == len(selected) == len(EXPECTED) == 6
    for index, (hour, key, size, etag) in enumerate(EXPECTED):
        a = objects[index]
        b = selected[index]
        assert a["path_hour_utc"] == b["path_hour_utc"] == hour
        assert a["key"] == b["key"] == key
        assert a["expected_size_bytes"] == b["size_bytes"] == size
        assert a["expected_etag"] == b["etag"] == etag
        assert a["storage_class"] == b["storage_class"] == "STANDARD"
        if index:
            assert parse_utc(hour) - parse_utc(EXPECTED[index - 1][0]) == timedelta(hours=1)
    assert sum(row[2] for row in EXPECTED) == s["aggregate_selected_compressed_bytes"] == 120999698
    assert max(row[2] for row in EXPECTED) == s["maximum_selected_object_size_bytes"] == 21672141
    assert c["historical_window_role"]["window_start_utc"] == "2025-07-27T09:00:00Z"
    assert c["historical_window_role"]["window_end_exclusive_utc"] == "2025-07-27T15:00:00Z"
    assert c["historical_window_role"]["selected_hour_count"] == 6
    assert c["historical_window_role"]["censored_boundary_hour_included"] is False
    assert c["historical_window_role"]["six_hour_window_is_population_performance_representative"] is False
    assert c["historical_window_role"]["six_hour_window_supports_wallet_quality_ranking"] is False

    envelope = c["proposed_request_envelope"]
    assert envelope["maximum_one_time_budget_eur"] == 0.10
    assert envelope["maximum_monthly_budget_eur"] == 0
    assert envelope["maximum_get_object_requests"] == 6
    assert envelope["maximum_requests_per_object"] == 1
    assert envelope["maximum_total_compressed_bytes"] == 120999698
    assert envelope["maximum_individual_compressed_bytes"] == 21672141
    assert envelope["maximum_total_decompressed_bytes"] == 1073741824
    assert envelope["maximum_individual_decompressed_bytes"] == 268435456
    assert envelope["maximum_runtime_seconds"] == 300
    assert envelope["maximum_retries_per_request"] == 0
    assert envelope["request_order"] == "PATH_HOUR_ASCENDING"
    assert envelope["stop_after_first_failed_or_mismatched_object"] is True
    for key in (
        "requester_pays_required", "if_match_etag_required", "exact_content_length_required",
        "exact_response_etag_required", "compressed_sha256_computed_and_retained_per_object",
    ):
        assert envelope[key] is True, key
    assert envelope["preknown_compressed_sha256_required"] is False
    for key in (
        "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
        "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "get_object_attributes_authorized", "get_object_version_authorized", "http_redirect_following_authorized",
    ):
        assert envelope[key] is False, key

    parse_rules = c["decompression_and_parse_rules"]
    for key in (
        "decompression_authorized_for_future_separate_release", "lz4_frame_stream_only", "strict_utf8_decode",
        "strict_json_duplicate_keys_rejected", "strict_json_nonfinite_constants_rejected",
        "fill_time_must_fall_within_source_path_hour_utc", "path_hour_lower_bound_inclusive",
        "path_hour_upper_bound_exclusive",
    ):
        assert parse_rules[key] is True, key
    assert parse_rules["alternate_decompressor_fallback_authorized"] is False
    assert parse_rules["required_top_level_record_type"] == "object"
    assert parse_rules["required_block_fields"] == {"local_time":"string","block_time":"string","block_number":"integer","events":"array"}
    assert parse_rules["required_event_pair_arity"] == 2
    assert parse_rules["required_event_pair_ordered_element_types"] == ["string", "object"]
    assert parse_rules["required_leading_string_regex"] == "^0x[0-9a-f]{40}$"
    assert parse_rules["path_hour_alignment_violation_count_required_for_success"] == 0

    assert c["selected_fill_fields_for_transient_processing"] == ["coin","side","time","px","sz","closedPnl","tid","crossed","liquidation"]
    rules = c["selected_field_processing_rules"]
    assert rules["maximum_numeric_token_characters"] == 128
    assert rules["exact_decimal_arithmetic_required"] is True
    assert rules["floating_point_aggregation_authorized"] is False
    cross = c["cross_object_aggregation_rules"]
    assert cross["active_hour_count_incremented_at_most_once_per_wallet_per_selected_path_hour"] is True
    assert cross["duplicate_identity_key"] == "WALLET_ADDRESS_PLUS_TID"
    assert cross["duplicate_wallet_tid_count_required_for_clean_success"] == 0
    assert cross["blind_duplicate_deduplication_authorized"] is False
    assert cross["fill_count_conservation_required"] is True
    assert cross["side_count_conservation_required"] is True
    assert cross["per_hour_wallet_feature_rows_retention_authorized"] is False

    output = c["proposed_per_wallet_output"]
    assert output["fields_only"] == FEATURE_FIELDS
    assert output["format"] == "UTF8_NDJSON"
    assert output["sort_order"] == "WALLET_ADDRESS_LEXICOGRAPHIC_ASCENDING"
    assert output["decimal_output_encoding"] == "CANONICAL_BASE10_STRING_NO_EXPONENT"
    assert output["active_hour_count_minimum"] == 1
    assert output["active_hour_count_maximum"] == 6
    assert output["wallet_feature_output_byte_cap"] == 67108864
    assert output["first_time_lte_last_time_required"] is True
    assert output["nonnegative_notional_proxy_required"] is True

    assert all(value is False for value in c["raw_or_disallowed_retention"].values())
    assert all(value is False for value in c["semantic_boundaries"].values())
    assert all(value is False for value in c["downstream_authorizations"].values())
    assert all(value is False for value in c["current_runtime_authority"].values())
    assert all(value is False for value in c["trading_authorizations"].values())

    statements = r4_policy["Statement"]
    allow = next(row for row in statements if row["Sid"] == "AllowExactTwoBoundaryObjectsOnly")
    deny = next(row for row in statements if row["Sid"] == "DenyGetObjectOutsideExactTwo")
    assert allow["Resource"] == [
        "arn:aws:s3:::hl-mainnet-node-data/node_fills/hourly/20250727/8.lz4",
        "arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/8.lz4",
    ]
    assert deny["Effect"] == "Deny"
    assert iam["existing_r4_role_reuse_possible"] is False
    assert iam["existing_r4_role_reuse_authorized"] is False
    assert iam["existing_role_mutation_authorized"] is False
    assert iam["new_dedicated_role_required_for_future_execution"] is True
    assert iam["proposed_role_arn"] == ROLE
    assert iam["proposed_permission_boundary"]["allowed_actions_only"] == ["s3:GetObject"]
    assert len(iam["proposed_permission_boundary"]["allowed_object_arns_only"]) == 6
    assert iam["iam_role_creation_authorized_now"] is False
    assert iam["aws_iam_mutation_performed"] is False
    assert iam["aws_sts_request_executed"] is False
    assert iam["s3_request_executed"] is False
    assert all(value is False for value in iam["trading_authorizations"].values())

    assert cost["status"] == "PROPOSED_NOT_AUTHORIZED"
    assert cost["selected_object_count"] == 6
    assert cost["selected_compressed_bytes"] == 120999698
    assert cost["maximum_get_object_requests"] == 6
    assert cost["maximum_retries_per_request"] == 0
    assert cost["maximum_one_time_budget_eur"] == 0.10
    assert cost["maximum_monthly_budget_eur"] == 0
    assert cost["budget_is_not_cost_prediction"] is True
    assert cost["execution_authorized_by_this_file"] is False
    assert r4_pricing["release_budget_decision"] == "RETAIN_USER_APPROVED_EUR_0_10_ONE_TIME_CEILING_WITH_EXACT_REQUEST_AND_BYTE_CAPS"

    assert c["human_approval_required_before_implementation"] is True
    assert c["separate_iam_role_operator_gate_required"] is True
    assert c["separate_sts_preflight_release_required"] is True
    assert c["implementation_required_before_execution_release"] is True
    assert c["separate_execution_release_required"] is True
    assert c["separate_canonical_activation_required"] is True
    assert c["network_requests_executed_by_r10_preregistration"] == 0
    assert c["aws_iam_mutations_executed_by_r10_preregistration"] == 0
    assert c["wallet_feature_rows_created_by_r10_preregistration"] == 0
    assert c["empirical_result"] is None

    assert "APPROVE_HL_ARCHIVE_POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_001" in template
    assert "reviewed_commit=<CANONICAL_R10_PREREGISTRATION_MERGE_COMMIT>" in template
    assert "maximum_get_object_requests=6" in template
    assert "maximum_total_compressed_bytes=120999698" in template
    assert "new_dedicated_r10_role_creation_authorized=true" in template
    assert "existing_r4_role_mutation_authorized=false" in template
    assert "wallet_ranking_authorized=false" in template
    assert "candidate_shortlisting_authorized=false" in template
    assert "sum_closed_pnl_is_exact_account_return=false" in template
    assert "AWAITING_SEPARATE_HUMAN_APPROVAL" in status
    assert "zero new S3 requests" in readme
    assert "not a wallet-performance study" in readme

    assert not (R10 / "approvals").exists()
    assert not (R10 / "collector.py").exists()
    assert not (R10 / "R10_IMPLEMENTATION_CONTRACT.json").exists()
    assert not (R10 / "R10_TRUST_POLICY.json").exists()
    assert not (R10 / "R10_PERMISSION_POLICY.json").exists()
    assert not (R10 / "R10_EXECUTION_RELEASE.json").exists()
    assert not (R10 / "R10_EXECUTION_RELEASE_CANONICALIZATION.json").exists()
    assert not (ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml").exists()

    print("R10_PREREGISTRATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
