from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREREG = BASE / "r10c/R10C_BOUNDARY_RECORD_CORRELATION_PREREGISTRATION.json"
APPROVAL = BASE / "r10c_approval/APPROVE_HL_ARCHIVE_R10C_BOUNDARY_RECORD_CORRELATION_001.json"
APPROVAL_TEXT = BASE / "r10c_approval/APPROVE_HL_ARCHIVE_R10C_BOUNDARY_RECORD_CORRELATION_001.txt"
IMPLEMENTATION = BASE / "r10c_implementation/R10C_IMPLEMENTATION_CONTRACT.json"
COLLECTOR = BASE / "r10c_implementation/collector.py"
WORKFLOW = BASE / "r10c_implementation/workflows/hyperliquid-archive-r10c-boundary-record-correlation.yml"
INSTALLED_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r10c-boundary-record-correlation.yml"

PREREG_MERGE = "a812f7d5b67203c801f856c85b046af8e136c8f3"
APPROVAL_MERGE = "00dbe69b5c17df8ef42a9b573589add290e559d8"
APPROVAL_SHA = "3bea842b40837f791f1c2799822382adbab4f256185a59287b2f635cbaa4bdbe"
ROLE = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
KEY = "node_fills_by_block/hourly/20250727/9.lz4"
OBJECT_SHA = "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    prereg = load(PREREG)
    approval = load(APPROVAL)
    impl = load(IMPLEMENTATION)

    assert hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest() == APPROVAL_SHA
    assert prereg["diagnostic_id"] == approval["diagnostic_id"] == impl["diagnostic_id"] == "HL-ARCHIVE-R10C-BOUNDARY-RECORD-CORRELATION-001"
    assert prereg["status"] == "PREREGISTERED_NO_EXECUTION"
    assert approval["status"] == "OWNER_APPROVED_IMPLEMENTATION_NO_EXECUTION"
    assert approval["reviewed_commit"] == PREREG_MERGE
    assert approval["exact_approval_text_sha256"] == APPROVAL_SHA
    assert approval["execution_authorized_by_this_approval"] is False

    assert impl["status"] == "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE"
    assert impl["r10c_preregistration_merge_commit"] == PREREG_MERGE
    assert impl["r10c_approval_merge_commit"] == APPROVAL_MERGE
    assert impl["approval_text_sha256"] == APPROVAL_SHA
    assert impl["role_arn"] == ROLE
    assert impl["role_reused_without_mutation"] is True
    assert impl["new_role_created"] is False
    assert impl["workflow_name"] == "Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10"
    assert impl["workflow_run_name"] == "R10C boundary record correlation"
    assert impl["workflow_candidate_path"] == "research/archive_inventory/r10c_implementation/workflows/hyperliquid-archive-r10c-boundary-record-correlation.yml"

    target = impl["exact_network_target"]
    assert target["bucket"] == "hl-mainnet-node-data"
    assert target["region"] == "ap-northeast-1"
    assert target["key"] == KEY
    assert target["expected_size_bytes"] == 18147822
    assert target["expected_etag"] == '"5a9941a240118a57f77a4c3ee95b8430-3"'
    assert target["expected_compressed_sha256"] == OBJECT_SHA
    assert target["path_hour_start_ms"] == 1753606800000
    assert target["path_hour_end_ms_exclusive"] == 1753610400000
    assert target["path_date_hour_prefix"] == "2025-07-27T09:"
    assert target["previous_path_date_hour_prefix"] == "2025-07-27T08:"
    assert target["next_path_date_hour_prefix"] == "2025-07-27T10:"

    env = impl["execution_envelope"]
    assert env["maximum_one_time_budget_eur"] == 0.10
    assert env["maximum_monthly_budget_eur"] == 0
    assert env["maximum_get_object_requests"] == 1
    assert env["maximum_requests_per_object"] == 1
    assert env["maximum_retries_per_request"] == 0
    assert env["maximum_total_compressed_bytes"] == env["maximum_individual_compressed_bytes"] == 18147822
    assert env["maximum_total_decompressed_bytes"] == env["maximum_individual_decompressed_bytes"] == 268435456
    assert env["maximum_runtime_seconds"] == 120
    assert env["requester_pays_required"] is True
    assert env["if_match_etag_required"] is True
    assert env["exact_content_length_required"] is True
    assert env["exact_response_etag_required"] is True
    assert env["compressed_sha256_required"] is True
    for key in ("http_redirect_following_authorized", "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized", "get_object_attributes_authorized", "get_object_version_authorized"):
        assert env[key] is False, key

    p = impl["processing_contract"]
    for key in ("decompression", "metadata_prefix_processing", "event_array_contents_inspection", "event_pair_shape_inspection", "fill_time_integer_milliseconds_processing", "aggregate_boundary_correlation_retention"):
        assert p[key] is True, key
    assert p["event_array_contents_inspection_scope"] == "PAIR_SHAPE_AND_FILL_TIME_ONLY"
    assert p["fill_object_field_allowlist"] == ["time"]
    for key in ("metadata_timezone_parsing", "metadata_timezone_inference", "metadata_datetime_conversion", "individual_metadata_value_retention", "leading_event_string_value_retention", "leading_event_string_wallet_semantics", "individual_fill_time_retention", "economic_fill_field_processing", "block_number_value_retention", "per_block_identity_retention", "per_wallet_processing", "wallet_address_retention", "raw_compressed_object_retention", "raw_decompressed_object_retention", "raw_block_record_retention", "raw_event_pair_retention"):
        assert p[key] is False, key

    assert impl["parent_aggregate_preconditions"] == {
        "block_record_count": 36029,
        "fill_time_count": 223950,
        "fill_time_before_path_hour_count": 2,
        "fill_time_inside_path_hour_count": 223948,
        "fill_time_after_path_hour_count": 0,
        "local_time_path_prefix_count": 36029,
        "block_time_path_prefix_count": 36028,
        "block_time_previous_prefix_count": 1,
    }
    assert impl["allowed_boundary_record_correlation_classifications"] == [
        "EXACT_TWO_PRE_HOUR_FILLS_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD",
        "PRE_HOUR_FILLS_DO_NOT_EXACTLY_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD",
        "BOUNDARY_RECORD_CORRELATION_UNRESOLVED",
    ]

    for key in ("execution_release_present", "canonical_activation_present", "single_workflow_dispatch_authorized", "aws_oidc_authorized_now", "requester_pays_authorized_now", "get_object_authorized_now", "object_body_download_authorized_now", "decompression_authorized_now", "metadata_prefix_processing_authorized_now", "event_time_processing_authorized_now", "aggregate_boundary_correlation_retention_authorized_now"):
        assert impl[key] is False, key
    assert impl["execution_release_required"] is True
    assert impl["network_requests_executed"] == 0
    assert impl["aws_iam_mutations_executed"] == 0
    assert impl["empirical_result"] is None
    assert all(v is False for v in impl["interpretation_boundaries"].values())
    assert all(v is False for v in impl["downstream_authorizations"].values())
    assert all(v is False for v in impl["trading_authorizations"].values())

    collector = COLLECTOR.read_text(encoding="utf-8")
    assert "fill.get(\"time\")" in collector
    assert "ADDRESS_RE" not in collector
    for forbidden in ("closedPnl", "feeToken", "startPosition", "transaction_hash"):
        assert forbidden not in collector
    assert "datetime.fromisoformat" not in collector
    assert "block_number" in collector
    assert "per_block_identity_retained" in collector

    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "name: Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10" in workflow
    assert "run-name: R10C boundary record correlation" in workflow
    assert "research/archive_inventory/r10c_runtime/R10C_EXECUTION_RELEASE.json" in workflow
    assert "s3:GetObject" in workflow
    assert "PAIR_SHAPE_AND_FILL_TIME_ONLY" in workflow
    assert "BOUNDARY_RECORD_CORRELATION_UNRESOLVED" in workflow
    assert ".github/workflows/hyperliquid-archive-r10c-boundary-record-correlation.yml" not in impl["workflow_candidate_path"]

    # The immutable implementation snapshot remains inert even if a later,
    # separately reviewed release-candidate stage installs the frozen workflow.
    # If that later stage is present, it may only install byte-identical bytes.
    if INSTALLED_WORKFLOW.exists():
        assert INSTALLED_WORKFLOW.read_bytes() == WORKFLOW.read_bytes()

    # Prior preregistration and approval snapshots never gain runtime authority
    # merely because a later lifecycle overlay exists.
    assert all(v is False for v in prereg["current_runtime_authority"].values())
    assert all(v is False for v in approval["current_runtime_authority"].values())
    assert approval["execution_authorized_by_this_approval"] is False

    print("R10C_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
