from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREREG = BASE / "r11/R11_72H_PERSISTENCE_SCALING_PREREGISTRATION.json"
SELECTION = BASE / "r11/R11_72H_SELECTION.json"
DIR = BASE / "r11_approval"
TEXT = DIR / "APPROVE_HL_ARCHIVE_R11_72H_PERSISTENCE_SCALING_001.txt"
RECEIPT = DIR / "APPROVE_HL_ARCHIVE_R11_72H_PERSISTENCE_SCALING_001.json"

EXPECTED_SHA = "1c3ec861d5df30dbdeef4dece7422bc05fab50d59aa58aa36cf3b7f8fea0d3ca"
REVIEWED = "dc63f2846652e50755369aa95d0f01ec2e174b02"
PILOT = "HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001"
SELECTED = ["coin", "side", "time", "px", "sz", "closedPnl", "tid", "crossed", "liquidation"]
PREFIXES = [
    "node_fills_by_block/hourly/20250728/*",
    "node_fills_by_block/hourly/20250729/*",
    "node_fills_by_block/hourly/20250730/*",
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    p = load(PREREG)
    s = load(SELECTION)
    a = load(RECEIPT)
    raw = TEXT.read_bytes()

    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SHA
    assert raw.endswith(b"\n")
    assert a["approval_id"] == "APPROVE_HL_ARCHIVE_R11_72H_PERSISTENCE_SCALING_001"
    assert a["pilot_id"] == p["pilot_id"] == PILOT
    assert a["status"] == "OWNER_APPROVED_IMPLEMENTATION_AND_DEDICATED_ROLE_CREATION_NO_DATA_EXECUTION"
    assert a["reviewed_commit"] == REVIEWED
    assert a["exact_approval_text_sha256"] == EXPECTED_SHA
    assert a["approval_source"] == "EXPLICIT_CHAT_APPROVAL_MARKDOWN_ESCAPES_CANONICALLY_NORMALIZED"
    assert a["execution_authorized_by_this_approval"] is False
    assert a["separate_execution_release_required"] is True
    assert a["separate_canonical_activation_required"] is True

    scope = a["approved_future_scope"]
    env = p["proposed_request_envelope"]
    for key in (
        "maximum_one_time_budget_eur", "maximum_monthly_budget_eur", "maximum_get_object_requests",
        "maximum_requests_per_object", "maximum_retries_per_request", "maximum_total_compressed_bytes",
        "maximum_individual_compressed_bytes", "maximum_total_decompressed_bytes",
        "maximum_individual_decompressed_bytes", "maximum_runtime_seconds", "request_order",
        "stop_after_first_failed_or_mismatched_object",
    ):
        assert scope[key] == env[key], (key, scope[key], env[key])
    assert scope["window_start_utc"] == p["historical_window_role"]["window_start_utc"]
    assert scope["window_end_exclusive_utc"] == p["historical_window_role"]["window_end_exclusive_utc"]
    assert scope["selected_hour_count"] == p["historical_window_role"]["selected_hour_count"] == 72
    assert scope["exact_target_set_inherited_from_reviewed_preregistration"] is True
    assert s["selected_hour_count"] == 72

    transport = a["approved_future_transport"]
    assert transport["target_bucket"] == "hl-mainnet-node-data"
    assert transport["signing_region"] == "ap-northeast-1"
    assert transport["requester_pays"] is True and transport["get_object"] is True
    for key in (
        "head_object", "range_get", "list_objects_v2", "list_object_versions", "list_all_my_buckets",
        "get_object_attributes", "get_object_version", "http_redirect_following",
    ):
        assert transport[key] is False, key
        assert env[f"{key}_authorized"] is False, key

    role = a["approved_dedicated_role_creation"]
    iam = p["iam_boundary"]
    assert role["existing_r10_role_reuse"] is False
    assert role["existing_r10_role_mutation"] is False
    assert role["new_dedicated_r11_role_creation"] is True
    assert role["role_name"] == iam["proposed_role_name"] == "onchain-wallet-intelligence-hl-archive-scaling-r11"
    assert role["persistent_permission_resource_count"] == iam["proposed_persistent_permission_resource_count"] == 72
    assert role["persistent_permission_resources_must_equal_exact_selection_objects"] is True
    assert role["future_session_policy_date_prefixes"] == iam["future_session_prefixes"] == PREFIXES
    assert role["role_max_session_duration_seconds"] == iam["proposed_role_max_session_duration_seconds"] == 7200
    assert role["future_workflow_role_duration_seconds"] == iam["future_workflow_role_duration_seconds"] == 7200
    assert role["separate_operator_attestation_required"] is True
    assert role["separate_sts_only_preflight_required"] is True
    assert role["s3_access_during_sts_preflight_authorized"] is False

    rule = a["approved_record_anchored_alignment_rule"]
    prereg_rule = p["record_anchored_alignment_contract"]
    assert rule["rule_id"] == prereg_rule["rule_id"] == "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1"
    assert rule["numeric_tolerance_authorized"] is False
    assert rule["metadata_timezone_parsing"] is False
    assert rule["metadata_timezone_inference"] is False
    assert rule["metadata_datetime_conversion"] is False

    assert a["selected_fill_fields_for_transient_processing"] == SELECTED == p["selected_fill_fields_for_transient_processing"]
    assert a["wallet_feature_retention_authorized_for_future_separate_execution_release"] is True
    assert a["active_day_count_processing_authorized_for_future_separate_execution_release"] is True
    assert p["cross_object_aggregation_rules"]["active_day_count_incremented_at_most_once_per_wallet_per_utc_date"] is True

    assert all(v is False for v in a["current_runtime_authority"].values())
    assert all(v is False for v in a["downstream_authorizations"].values())
    assert all(v is False for v in a["trading_authorizations"].values())
    assert p["status"] == "PREREGISTERED_NO_EXECUTION"
    assert all(v is False for v in p["current_runtime_authority"].values())
    assert p["network_requests_executed_by_r11_preregistration"] == 0
    assert p["aws_iam_mutations_executed_by_r11_preregistration"] == 0

    print("R11_APPROVAL_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
