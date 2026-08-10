from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREREG = BASE / "r10d/R10D_RECORD_ANCHORED_BOUNDARY_REPAIR_PREREGISTRATION.json"
APPROVAL = BASE / "r10d_approval/APPROVE_HL_ARCHIVE_R10D_RECORD_ANCHORED_MULTI_HOUR_FEATURE_REPAIR_001.json"
APPROVAL_TEXT = BASE / "r10d_approval/APPROVE_HL_ARCHIVE_R10D_RECORD_ANCHORED_MULTI_HOUR_FEATURE_REPAIR_001.txt"
IMPLEMENTATION = BASE / "r10d_implementation/R10D_IMPLEMENTATION_CONTRACT.json"
COLLECTOR = BASE / "r10d_implementation/collector.py"
WORKFLOW = BASE / "r10d_implementation/workflows/hyperliquid-archive-r10d-record-anchored-multihour-feature.yml"
INSTALLED = ROOT / ".github/workflows/hyperliquid-archive-r10d-record-anchored-multihour-feature.yml"
ROLE_ATTESTATION = BASE / "r10_role_attestation/R10_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
STS_ATTESTATION = BASE / "r10_role_preflight/HL-ARCHIVE-R10-DEDICATED-ROLE-STS-PREFLIGHT-001-ATTESTATION.json"

PREREG_MERGE = "b8e8d1080be27ff9db3fb639804b4040fdc7c2a0"
APPROVAL_MERGE = "95bc1a8c2f929e9266f0ae8c43e7cc2b38b40f11"
APPROVAL_SHA = "d8d1466a5da40c4fe32523ba81bfa165e0b88221cc70534f0f0a118870c1275f"
PILOT = "HL-ARCHIVE-R10D-RECORD-ANCHORED-MULTI-HOUR-FEATURE-REPAIR-001"
ROLE = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
RULE = "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1"
EXPECTED_KEYS = [f"node_fills_by_block/hourly/20250727/{hour}.lz4" for hour in range(9, 15)]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    p = load(PREREG)
    a = load(APPROVAL)
    i = load(IMPLEMENTATION)
    role = load(ROLE_ATTESTATION)
    sts = load(STS_ATTESTATION)

    assert hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA
    assert p["pilot_id"] == a["pilot_id"] == i["pilot_id"] == PILOT
    assert p["status"] == "PREREGISTERED_NO_EXECUTION"
    assert a["status"] == "OWNER_APPROVED_IMPLEMENTATION_NO_EXECUTION"
    assert a["reviewed_commit"] == PREREG_MERGE
    assert a["exact_approval_text_sha256"] == APPROVAL_SHA
    assert a["execution_authorized_by_this_approval"] is False
    assert i["status"] == "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE"
    assert i["r10d_preregistration_merge_commit"] == PREREG_MERGE
    assert i["r10d_approval_merge_commit"] == APPROVAL_MERGE
    assert i["approval_text_sha256"] == APPROVAL_SHA
    assert i["parent_r10c_evidence_merge_commit"] == "83842a3947e8eec518fa4a05ca71a2b81079976b"

    assert i["role_arn"] == ROLE
    assert i["role_reused_without_mutation"] is True
    assert i["new_role_created"] is False
    assert i["role_attestation_reused"] is True
    assert i["sts_preflight_evidence_reused"] is True
    # The operator attestation is an immutable pre-preflight snapshot. The
    # later STS attestation below supplies independent verification.
    assert role["attestation_id"] == "R10_DEDICATED_ROLE_OPERATOR_ATTESTATION"
    assert role["role_arn"] == ROLE
    assert role["role_created_and_policies_applied"] is True
    assert role["installed_trust_policy_matches_canonical"] is True
    assert role["installed_permission_policy_matches_canonical"] is True
    assert role["additional_managed_policies_attached"] is False
    assert role["additional_inline_policies_attached"] is False
    assert role["existing_r4_role_modified"] is False
    assert role["operator_attested"] is True
    assert role["independently_verified_via_r10_sts_preflight"] is False
    assert role["sts_only_preflight_completed"] is False
    assert sts["terminal_status"] == "R10_STS_PREFLIGHT_PASS"
    assert sts["technical_result"] == "DEDICATED_R10_ROLE_ASSUMEABLE_FROM_CANONICAL_MAIN"
    assert sts["expected_role_arn"] == ROLE
    assert sts["operator_attestation_independently_verified_by_preflight"] is True
    assert sts["preflight_release_consumed"] is True
    assert sts["rerun_authorized"] is False
    assert sts["s3_http_request_count"] == 0
    assert sts["object_bytes_downloaded"] == 0

    targets = i["exact_network_targets"]
    assert [row["key"] for row in targets] == EXPECTED_KEYS
    assert [row["key"] for row in p["exact_future_network_targets"]] == EXPECTED_KEYS
    for got, frozen in zip(targets, p["exact_future_network_targets"]):
        assert got["path_hour_utc"] == frozen["path_hour_utc"]
        assert got["key"] == frozen["key"]
        assert got["expected_size_bytes"] == frozen["expected_size_bytes"]
        assert got["expected_etag"] == frozen["expected_etag"]
        assert got["known_compressed_sha256"] == frozen["known_compressed_sha256"]
    assert targets[0]["known_compressed_sha256"] == "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339"
    assert all(row["known_compressed_sha256"] is None for row in targets[1:])

    env = i["execution_envelope"]
    penv = p["proposed_request_envelope"]
    assert env == penv
    assert env["maximum_get_object_requests"] == 6
    assert env["maximum_retries_per_request"] == 0
    assert env["maximum_total_compressed_bytes"] == 120999698
    assert env["maximum_total_decompressed_bytes"] == 1073741824
    assert env["request_order"] == "PATH_HOUR_ASCENDING"
    assert env["stop_after_first_failed_or_mismatched_object"] is True

    rule = i["record_anchored_alignment_rule"]
    assert rule == p["record_anchored_alignment_rule"]
    assert rule["rule_id"] == RULE
    assert rule["metadata_timezone_parsing_authorized"] is False
    assert rule["metadata_timezone_inference_authorized"] is False
    assert rule["metadata_datetime_conversion_authorized"] is False
    assert rule["local_time_raw_prefix_must_match_source_path_hour_for_every_record"] is True
    assert rule["block_time_raw_prefix_allowed_buckets"] == ["MATCHES_PATH_DATE_HOUR_PREFIX", "MATCHES_PREVIOUS_DATE_HOUR_PREFIX"]
    assert rule["fill_time_numeric_tolerance_milliseconds"] is None
    assert rule["numeric_tolerance_authorized"] is False
    assert rule["path_block_record_allowed_fill_partitions"] == ["INSIDE_PATH_HOUR"]
    assert rule["previous_block_record_allowed_fill_partitions"] == ["BEFORE_PATH_HOUR"]
    assert rule["previous_block_record_before_fill_must_be_within_immediately_previous_epoch_hour"] is True
    assert rule["after_path_hour_fill_count_required_for_success"] == 0
    assert rule["hours10_to14_boundary_pattern_predeclared"] is False

    parse = i["parse_and_aggregation"]
    assert parse["selected_fill_fields_processed_transiently"] == ["coin","side","time","px","sz","closedPnl","tid","crossed","liquidation"]
    assert parse["exact_decimal_arithmetic_required"] is True
    assert parse["floating_point_aggregation_authorized"] is False
    assert parse["duplicate_wallet_tid_count_required_for_clean_success"] == 0
    assert parse["blind_duplicate_deduplication_authorized"] is False
    assert parse["fill_count_conservation_required"] is True
    assert parse["side_count_conservation_required"] is True

    output = i["wallet_feature_output"]
    assert output["format"] == "UTF8_NDJSON"
    assert output["sort_order"] == "WALLET_ADDRESS_LEXICOGRAPHIC_ASCENDING"
    assert output["wallet_feature_entry_cap"] == 1000000
    assert output["wallet_feature_output_byte_cap"] == 67108864
    assert "wallet_address" in output["fields_only"] and "sum_closed_pnl_fill_statistic" in output["fields_only"]

    assert all(v is False for v in i["semantic_boundaries"].values())
    assert all(v is False for v in i["forbidden_retention_authorizations"].values())
    assert all(v is False for v in i["current_runtime_authority"].values())
    assert all(v is False for v in i["downstream_authorizations"].values())
    assert all(v is False for v in i["trading_authorizations"].values())
    assert i["execution_release_present"] is False
    assert i["canonical_activation_present"] is False
    assert i["single_workflow_dispatch_authorized"] is False
    assert i["network_requests_executed"] == 0
    assert i["aws_iam_mutations_executed"] == 0
    assert i["wallet_feature_rows_created"] == 0
    assert i["empirical_result"] is None

    collector = COLLECTOR.read_text(encoding="utf-8")
    assert "class RecordAnchoredAggregator" in collector
    assert "local_time.startswith(path_prefix)" in collector
    assert "block_time.startswith(previous_prefix)" in collector
    assert "fill_time < previous_start_ms" in collector
    assert "path-hour block record contains non-inside fill" in collector
    assert "previous-hour block record contains non-before fill" in collector
    assert "HOUR9_SHA" in collector
    assert "datetime.fromisoformat(block" not in collector
    assert "wallet_ranking_performed" in collector

    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert workflow.startswith("name: Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10\nrun-name: R10D record-anchored multi-hour feature repair\n")
    assert "workflow_dispatch:" in workflow and "schedule:" not in workflow and "push:" not in workflow
    for pin in (
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
        "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
        "aws-actions/configure-aws-credentials@e6de054238d6b7531b4efff3b6587d9aade6a06c",
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
    ):
        assert pin in workflow, pin
    assert workflow.count("arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/") == 6
    assert '"Action":"s3:GetObject"' in workflow
    assert "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1" in workflow
    assert "R10D_EXECUTION_RELEASE.json" in workflow
    assert "r10_role_preflight/HL-ARCHIVE-R10-DEDICATED-ROLE-STS-PREFLIGHT-001-ATTESTATION.json" in workflow
    assert workflow.index("Prove exact single-use R10D release before OIDC") < workflow.index("Assume exact existing R10 role with exact-six session scope")
    if INSTALLED.exists():
        assert INSTALLED.read_bytes() == WORKFLOW.read_bytes()

    print("R10D_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
