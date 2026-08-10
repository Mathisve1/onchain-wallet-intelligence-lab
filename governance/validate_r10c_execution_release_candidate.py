from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CANDIDATE = BASE / "r10c_runtime/R10C_EXECUTION_RELEASE_CANDIDATE.json"
IMPLEMENTATION = BASE / "r10c_implementation/R10C_IMPLEMENTATION_CONTRACT.json"
APPROVAL = BASE / "r10c_approval/APPROVE_HL_ARCHIVE_R10C_BOUNDARY_RECORD_CORRELATION_001.json"
PREREG = BASE / "r10c/R10C_BOUNDARY_RECORD_CORRELATION_PREREGISTRATION.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r10c-boundary-record-correlation.yml"
FROZEN_WORKFLOW = BASE / "r10c_implementation/workflows/hyperliquid-archive-r10c-boundary-record-correlation.yml"

PREREG_MERGE = "a812f7d5b67203c801f856c85b046af8e136c8f3"
APPROVAL_MERGE = "00dbe69b5c17df8ef42a9b573589add290e559d8"
IMPLEMENTATION_MERGE = "69fcb9365c3c3bb703ab1b8667acf89b1402fcdc"
APPROVAL_SHA = "3bea842b40837f791f1c2799822382adbab4f256185a59287b2f635cbaa4bdbe"
WORKFLOW_BLOB_SHA = "1cdc522dc0b827cc0173089b2082c6cb9a0896dd"
ROLE = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
OBJECT_KEY = "node_fills_by_block/hourly/20250727/9.lz4"
OBJECT_SHA = "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339"

PARENT = {
    "block_record_count": 36029,
    "fill_time_count": 223950,
    "fill_time_before_path_hour_count": 2,
    "fill_time_inside_path_hour_count": 223948,
    "fill_time_after_path_hour_count": 0,
    "local_time_path_prefix_count": 36029,
    "block_time_path_prefix_count": 36028,
    "block_time_previous_prefix_count": 1,
}
CLASSES = [
    "EXACT_TWO_PRE_HOUR_FILLS_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD",
    "PRE_HOUR_FILLS_DO_NOT_EXACTLY_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD",
    "BOUNDARY_RECORD_CORRELATION_UNRESOLVED",
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def main() -> int:
    c = load(CANDIDATE)
    i = load(IMPLEMENTATION)
    a = load(APPROVAL)
    p = load(PREREG)

    assert c["release_candidate_id"] == "CANDIDATE_RELEASE_HL_ARCHIVE_R10C_BOUNDARY_RECORD_CORRELATION_001"
    assert c["diagnostic_id"] == i["diagnostic_id"] == a["diagnostic_id"] == p["diagnostic_id"] == "HL-ARCHIVE-R10C-BOUNDARY-RECORD-CORRELATION-001"
    assert c["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert c["r10c_preregistration_merge_commit"] == PREREG_MERGE
    assert c["r10c_approval_merge_commit"] == APPROVAL_MERGE
    assert c["r10c_implementation_merge_commit"] == IMPLEMENTATION_MERGE
    assert c["approval_text_sha256"] == APPROVAL_SHA

    assert c["workflow_path"] == ".github/workflows/hyperliquid-archive-r10c-boundary-record-correlation.yml"
    assert c["workflow_candidate_path"] == "research/archive_inventory/r10c_implementation/workflows/hyperliquid-archive-r10c-boundary-record-correlation.yml"
    assert c["workflow_name"] == "Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10"
    assert c["workflow_run_name"] == "R10C boundary record correlation"
    assert c["workflow_git_blob_sha"] == WORKFLOW_BLOB_SHA
    assert git_blob_sha(WORKFLOW.read_bytes()) == WORKFLOW_BLOB_SHA
    assert WORKFLOW.read_bytes() == FROZEN_WORKFLOW.read_bytes()

    assert c["role_arn"] == ROLE
    assert c["role_reuse_without_mutation"] is True
    target = c["exact_network_target"]
    assert target == {
        "bucket": "hl-mainnet-node-data",
        "region": "ap-northeast-1",
        "key": OBJECT_KEY,
        "expected_size_bytes": 18147822,
        "expected_etag": '"5a9941a240118a57f77a4c3ee95b8430-3"',
        "expected_compressed_sha256": OBJECT_SHA,
        "path_hour_start_ms": 1753606800000,
        "path_hour_end_ms_exclusive": 1753610400000,
        "path_date_hour_prefix": "2025-07-27T09:",
        "previous_path_date_hour_prefix": "2025-07-27T08:",
        "next_path_date_hour_prefix": "2025-07-27T10:",
        "storage_class": "STANDARD",
    }

    e = c["execution_envelope"]
    assert e["maximum_one_time_budget_eur"] == 0.10
    assert e["maximum_monthly_budget_eur"] == 0
    assert e["maximum_get_object_requests"] == 1
    assert e["maximum_requests_per_object"] == 1
    assert e["maximum_retries_per_request"] == 0
    assert e["maximum_total_compressed_bytes"] == e["maximum_individual_compressed_bytes"] == 18147822
    assert e["maximum_total_decompressed_bytes"] == e["maximum_individual_decompressed_bytes"] == 268435456
    assert e["maximum_runtime_seconds"] == 120
    for key in (
        "requester_pays_required",
        "if_match_etag_required",
        "exact_content_length_required",
        "exact_response_etag_required",
        "exact_compressed_sha256_required",
    ):
        assert e[key] is True, key
    for key in (
        "http_redirect_following_authorized",
        "head_object_authorized",
        "range_get_authorized",
        "list_objects_v2_authorized",
        "list_object_versions_authorized",
        "list_all_my_buckets_authorized",
        "get_object_attributes_authorized",
        "get_object_version_authorized",
    ):
        assert e[key] is False, key

    future = c["future_processing_authority_if_separately_activated"]
    for key in (
        "decompression",
        "metadata_prefix_processing",
        "event_array_contents_inspection",
        "event_pair_shape_inspection",
        "fill_time_integer_milliseconds_processing",
        "aggregate_boundary_correlation_retention",
    ):
        assert future[key] is True, key
    assert future["event_array_contents_inspection_scope"] == "PAIR_SHAPE_AND_FILL_TIME_ONLY"
    assert future["fill_object_field_allowlist"] == ["time"]
    for key in (
        "metadata_timezone_parsing",
        "metadata_timezone_inference",
        "metadata_datetime_conversion",
        "individual_metadata_value_retention",
        "leading_event_string_value_retention",
        "leading_event_string_wallet_semantics",
        "individual_fill_time_retention",
        "economic_fill_field_processing",
        "block_number_value_retention",
        "per_block_identity_retention",
        "per_wallet_processing",
        "wallet_address_retention",
        "raw_compressed_object_retention",
        "raw_decompressed_object_retention",
        "raw_block_record_retention",
        "raw_event_pair_retention",
    ):
        assert future[key] is False, key

    assert c["parent_aggregate_preconditions"] == PARENT
    assert c["allowed_boundary_record_correlation_classifications"] == CLASSES
    assert c["canonical_activation_required"] is True
    assert c["canonical_activation_present"] is False
    assert c["single_use_window_start_utc"] is None
    for key in (
        "single_workflow_dispatch_authorized",
        "aws_oidc_authorized",
        "requester_pays_authorized",
        "get_object_authorized",
        "object_body_download_authorized",
        "decompression_authorized",
        "metadata_prefix_processing_authorized",
        "event_time_processing_authorized",
        "aggregate_boundary_correlation_retention_authorized",
        "release_consumed",
        "rerun_authorized",
    ):
        assert c[key] is False, key
    assert c["network_requests_executed"] == 0
    assert c["aws_iam_mutations_executed"] == 0
    assert c["empirical_result"] is None
    assert all(v is False for v in c["interpretation_boundaries"].values())
    assert all(v is False for v in c["downstream_authorizations"].values())
    assert all(v is False for v in c["trading_authorizations"].values())

    assert p["status"] == "PREREGISTERED_NO_EXECUTION"
    assert all(v is False for v in p["current_runtime_authority"].values())
    assert a["status"] == "OWNER_APPROVED_IMPLEMENTATION_NO_EXECUTION"
    assert a["execution_authorized_by_this_approval"] is False
    assert all(v is False for v in a["current_runtime_authority"].values())
    assert i["status"] == "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE"
    assert i["execution_release_present"] is False
    assert i["canonical_activation_present"] is False
    assert i["single_workflow_dispatch_authorized"] is False
    assert i["network_requests_executed"] == 0
    assert i["aws_iam_mutations_executed"] == 0

    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.startswith(
        "name: Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10\n"
        "run-name: R10C boundary record correlation\n"
    )
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10C_RUN" in text
    assert text.index("Prove exact single-use R10C release before OIDC") < text.index(
        "Assume existing R10 role with exact one-object session scope"
    )
    assert f"role-to-assume: {ROLE}" in text
    assert "role-duration-seconds: 900" in text
    assert "retry-max-attempts: 1" in text
    assert '"Action":"s3:GetObject"' in text
    assert f"arn:aws:s3:::hl-mainnet-node-data/{OBJECT_KEY}" in text
    assert OBJECT_SHA in text
    assert "research.archive_inventory.r10c_implementation.collector" in text
    assert "PAIR_SHAPE_AND_FILL_TIME_ONLY" in text
    assert "fill_object_field_allowlist" in text

    print("R10C_EXECUTION_RELEASE_CANDIDATE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
