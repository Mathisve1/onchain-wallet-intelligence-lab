from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREREG = BASE / "r10c/R10C_BOUNDARY_RECORD_CORRELATION_PREREGISTRATION.json"
DIR = BASE / "r10c_approval"
TEXT = DIR / "APPROVE_HL_ARCHIVE_R10C_BOUNDARY_RECORD_CORRELATION_001.txt"
RECEIPT = DIR / "APPROVE_HL_ARCHIVE_R10C_BOUNDARY_RECORD_CORRELATION_001.json"

EXPECTED_SHA = "3bea842b40837f791f1c2799822382adbab4f256185a59287b2f635cbaa4bdbe"
REVIEWED = "a812f7d5b67203c801f856c85b046af8e136c8f3"
ROLE = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
KEY = "node_fills_by_block/hourly/20250727/9.lz4"
ETAG = '"5a9941a240118a57f77a4c3ee95b8430-3"'
OBJECT_SHA = "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339"


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
    assert a["approval_id"] == "APPROVE_HL_ARCHIVE_R10C_BOUNDARY_RECORD_CORRELATION_001"
    assert a["diagnostic_id"] == p["diagnostic_id"] == "HL-ARCHIVE-R10C-BOUNDARY-RECORD-CORRELATION-001"
    assert a["status"] == "OWNER_APPROVED_IMPLEMENTATION_NO_EXECUTION"
    assert a["reviewed_commit"] == REVIEWED
    assert a["exact_approval_text_sha256"] == EXPECTED_SHA
    assert a["approval_source"] == "EXPLICIT_CHAT_APPROVAL_EXACT_BLOCK"
    assert a["execution_authorized_by_this_approval"] is False
    assert a["separate_execution_release_required"] is True
    assert a["separate_canonical_activation_required"] is True

    scope = a["approved_future_scope"]
    target = p["exact_future_network_target"]
    assert scope["maximum_one_time_budget_eur"] == 0.10
    assert scope["maximum_monthly_budget_eur"] == 0
    assert scope["maximum_get_object_requests"] == 1
    assert scope["maximum_requests_per_object"] == 1
    assert scope["maximum_retries_per_request"] == 0
    assert scope["maximum_total_compressed_bytes"] == scope["maximum_individual_compressed_bytes"] == target["expected_size_bytes"] == 18147822
    assert scope["maximum_total_decompressed_bytes"] == scope["maximum_individual_decompressed_bytes"] == 268435456
    assert scope["maximum_runtime_seconds"] == 120
    assert scope["target_bucket"] == target["bucket"] == "hl-mainnet-node-data"
    assert scope["signing_region"] == target["region"] == "ap-northeast-1"
    assert scope["object_key"] == target["key"] == KEY
    assert scope["object_expected_size_bytes"] == target["expected_size_bytes"] == 18147822
    assert scope["object_expected_etag"] == target["expected_etag"] == ETAG
    assert scope["object_expected_compressed_sha256"] == target["expected_compressed_sha256"] == OBJECT_SHA

    transport = a["approved_future_transport"]
    assert transport["requester_pays"] is True
    assert transport["get_object"] is True
    for key in (
        "head_object", "range_get", "list_objects_v2", "list_object_versions",
        "list_all_my_buckets", "get_object_attributes", "get_object_version",
        "http_redirect_following",
    ):
        assert transport[key] is False, key

    role = a["approved_role_reuse"]
    assert role["existing_dedicated_r10_role_reuse"] is True
    assert role["existing_dedicated_r10_role_mutation"] is False
    assert role["new_role_creation"] is False
    assert role["role_arn"] == ROLE
    assert role["future_session_policy_allowed_s3_actions_only"] == ["s3:GetObject"]
    assert role["future_session_policy_allowed_object_count"] == 1
    assert role["future_session_policy_exact_object_arn"] == f"arn:aws:s3:::hl-mainnet-node-data/{KEY}"
    assert role["future_role_duration_seconds"] == 900

    processing = a["approved_future_processing"]
    for key in (
        "decompression", "metadata_prefix_processing", "event_array_contents_inspection",
        "event_pair_shape_inspection", "fill_time_integer_milliseconds_processing",
        "aggregate_boundary_correlation_retention",
    ):
        assert processing[key] is True, key
    assert processing["event_array_contents_inspection_scope"] == "PAIR_SHAPE_AND_FILL_TIME_ONLY"
    assert processing["fill_object_field_allowlist"] == ["time"]
    for key in (
        "metadata_timezone_parsing", "metadata_timezone_inference", "metadata_datetime_conversion",
        "individual_metadata_value_retention", "leading_event_string_value_retention",
        "leading_event_string_wallet_semantics", "individual_fill_time_retention",
        "economic_fill_field_processing", "block_number_value_retention",
        "per_block_identity_retention", "per_wallet_processing", "wallet_address_retention",
        "raw_compressed_object_retention", "raw_decompressed_object_retention",
        "raw_block_record_retention", "raw_event_pair_retention",
    ):
        assert processing[key] is False, key

    assert all(v is False for v in a["current_runtime_authority"].values())
    assert all(v is False for v in a["downstream_authorizations"].values())
    assert all(v is False for v in a["trading_authorizations"].values())

    print("R10C_APPROVAL_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
