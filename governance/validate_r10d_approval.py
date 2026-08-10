from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREREG = BASE / "r10d/R10D_RECORD_ANCHORED_BOUNDARY_REPAIR_PREREGISTRATION.json"
DIR = BASE / "r10d_approval"
TEXT = DIR / "APPROVE_HL_ARCHIVE_R10D_RECORD_ANCHORED_MULTI_HOUR_FEATURE_REPAIR_001.txt"
RECEIPT = DIR / "APPROVE_HL_ARCHIVE_R10D_RECORD_ANCHORED_MULTI_HOUR_FEATURE_REPAIR_001.json"

EXPECTED_SHA = "d8d1466a5da40c4fe32523ba81bfa165e0b88221cc70534f0f0a118870c1275f"
REVIEWED = "b8e8d1080be27ff9db3fb639804b4040fdc7c2a0"
PILOT = "HL-ARCHIVE-R10D-RECORD-ANCHORED-MULTI-HOUR-FEATURE-REPAIR-001"
ROLE = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
SELECTED = ["coin", "side", "time", "px", "sz", "closedPnl", "tid", "crossed", "liquidation"]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    p = load(PREREG)
    a = load(RECEIPT)
    raw = TEXT.read_bytes()

    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SHA
    assert raw.endswith(b"\n")
    assert a["approval_id"] == "APPROVE_HL_ARCHIVE_R10D_RECORD_ANCHORED_MULTI_HOUR_FEATURE_REPAIR_001"
    assert a["pilot_id"] == p["pilot_id"] == PILOT
    assert a["status"] == "OWNER_APPROVED_IMPLEMENTATION_NO_EXECUTION"
    assert a["reviewed_commit"] == REVIEWED
    assert a["exact_approval_text_sha256"] == EXPECTED_SHA
    assert a["approval_source"] == "EXPLICIT_CHAT_APPROVAL_EXACT_BLOCK"
    assert a["approval_source_user_text_first_line"] == a["approval_id"]
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
    assert scope["exact_target_set_inherited_from_reviewed_preregistration"] is True
    assert len(p["exact_future_network_targets"]) == 6

    transport = a["approved_future_transport"]
    assert transport["requester_pays"] is True
    assert transport["get_object"] is True
    for key in (
        "head_object", "range_get", "list_objects_v2", "list_object_versions", "list_all_my_buckets",
        "get_object_attributes", "get_object_version", "http_redirect_following",
    ):
        assert transport[key] is False, key
        assert env[f"{key}_authorized"] is False, key

    role = a["approved_role_reuse"]
    assert role["existing_dedicated_r10_role_reuse"] is True
    assert role["existing_dedicated_r10_role_mutation"] is False
    assert role["new_role_creation"] is False
    assert role["bound_existing_role_arn"] == ROLE

    approved_rule = a["approved_record_anchored_alignment_rule"]
    rule = p["record_anchored_alignment_rule"]
    mapping = {
        "metadata_timezone_parsing": "metadata_timezone_parsing_authorized",
        "metadata_timezone_inference": "metadata_timezone_inference_authorized",
        "metadata_datetime_conversion": "metadata_datetime_conversion_authorized",
        "local_time_raw_prefix_must_match_source_path_hour_for_every_record": "local_time_raw_prefix_must_match_source_path_hour_for_every_record",
        "block_time_raw_prefix_allowed_buckets": "block_time_raw_prefix_allowed_buckets",
        "block_time_next_or_other_prefix_is_fail_closed": "block_time_next_or_other_prefix_is_fail_closed",
        "fill_time_integer_milliseconds_processing": "fill_time_integer_milliseconds_processing_authorized",
        "numeric_tolerance_authorized": "numeric_tolerance_authorized",
        "path_block_record_allowed_fill_partitions": "path_block_record_allowed_fill_partitions",
        "previous_block_record_allowed_fill_partitions": "previous_block_record_allowed_fill_partitions",
        "previous_block_record_before_fill_must_be_within_immediately_previous_epoch_hour": "previous_block_record_before_fill_must_be_within_immediately_previous_epoch_hour",
        "after_path_hour_fill_count_required_for_success": "after_path_hour_fill_count_required_for_success",
    }
    for approved_key, prereg_key in mapping.items():
        assert approved_rule[approved_key] == rule[prereg_key], (approved_key, prereg_key)
    assert approved_rule["numeric_tolerance_authorized"] is False
    assert rule["fill_time_numeric_tolerance_milliseconds"] is None

    assert a["selected_fill_fields_for_transient_processing"] == SELECTED
    assert a["selected_fill_fields_for_transient_processing"] == p["selected_fill_fields_for_transient_processing"]
    assert a["wallet_feature_retention_authorized_for_future_separate_execution_release"] is True

    assert all(v is False for v in a["current_runtime_authority"].values())
    assert all(v is False for v in a["downstream_authorizations"].values())
    assert all(v is False for v in a["trading_authorizations"].values())
    assert p["status"] == "PREREGISTERED_NO_EXECUTION"
    assert all(v is False for v in p["current_runtime_authority"].values())
    assert p["network_requests_executed_by_preregistration"] == 0
    assert p["aws_iam_mutations_executed_by_preregistration"] == 0

    print("R10D_APPROVAL_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
