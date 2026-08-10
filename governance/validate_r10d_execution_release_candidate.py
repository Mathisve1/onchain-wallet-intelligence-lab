from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CANDIDATE = BASE / "r10d_runtime/R10D_EXECUTION_RELEASE_CANDIDATE.json"
IMPLEMENTATION = BASE / "r10d_implementation/R10D_IMPLEMENTATION_CONTRACT.json"
APPROVAL = BASE / "r10d_approval/APPROVE_HL_ARCHIVE_R10D_RECORD_ANCHORED_MULTI_HOUR_FEATURE_REPAIR_001.json"
PREREG = BASE / "r10d/R10D_RECORD_ANCHORED_BOUNDARY_REPAIR_PREREGISTRATION.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r10d-record-anchored-multihour-feature.yml"
FROZEN = BASE / "r10d_implementation/workflows/hyperliquid-archive-r10d-record-anchored-multihour-feature.yml"

PREREG_MERGE = "b8e8d1080be27ff9db3fb639804b4040fdc7c2a0"
APPROVAL_MERGE = "95bc1a8c2f929e9266f0ae8c43e7cc2b38b40f11"
IMPLEMENTATION_MERGE = "641e36ffdaab96865f475103cc1fc1b389fba613"
APPROVAL_SHA = "d8d1466a5da40c4fe32523ba81bfa165e0b88221cc70534f0f0a118870c1275f"
WORKFLOW_BLOB_SHA = "8b63ac4f00e05e0533793cd91c6b0d13cad26213"
ROLE = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
RULE = "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1"


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

    assert c["release_candidate_id"] == "CANDIDATE_RELEASE_HL_ARCHIVE_R10D_RECORD_ANCHORED_MULTI_HOUR_FEATURE_001"
    assert c["pilot_id"] == i["pilot_id"] == a["pilot_id"] == p["pilot_id"] == "HL-ARCHIVE-R10D-RECORD-ANCHORED-MULTI-HOUR-FEATURE-REPAIR-001"
    assert c["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert c["r10d_preregistration_merge_commit"] == PREREG_MERGE
    assert c["r10d_approval_merge_commit"] == APPROVAL_MERGE
    assert c["r10d_implementation_merge_commit"] == IMPLEMENTATION_MERGE
    assert c["parent_r10c_evidence_merge_commit"] == "83842a3947e8eec518fa4a05ca71a2b81079976b"
    assert c["approval_text_sha256"] == APPROVAL_SHA

    assert c["workflow_path"] == ".github/workflows/hyperliquid-archive-r10d-record-anchored-multihour-feature.yml"
    assert c["workflow_candidate_path"] == "research/archive_inventory/r10d_implementation/workflows/hyperliquid-archive-r10d-record-anchored-multihour-feature.yml"
    assert c["workflow_name"] == "Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10"
    assert c["workflow_run_name"] == "R10D record-anchored multi-hour feature repair"
    assert c["workflow_git_blob_sha"] == WORKFLOW_BLOB_SHA
    assert git_blob_sha(WORKFLOW.read_bytes()) == WORKFLOW_BLOB_SHA
    assert WORKFLOW.read_bytes() == FROZEN.read_bytes()

    assert c["role_arn"] == ROLE and c["role_reuse_without_mutation"] is True
    assert c["exact_network_targets"] == i["exact_network_targets"] == p["exact_future_network_targets"]
    e = c["execution_envelope"]
    assert e == i["execution_envelope"] == p["proposed_request_envelope"]
    assert e["maximum_one_time_budget_eur"] == 0.10 and e["maximum_monthly_budget_eur"] == 0
    assert e["maximum_get_object_requests"] == 6 and e["maximum_requests_per_object"] == 1
    assert e["maximum_retries_per_request"] == 0
    assert e["maximum_total_compressed_bytes"] == 120999698
    assert e["maximum_total_decompressed_bytes"] == 1073741824
    assert e["maximum_runtime_seconds"] == 300
    assert e["request_order"] == "PATH_HOUR_ASCENDING"
    assert e["stop_after_first_failed_or_mismatched_object"] is True

    future = c["future_processing_authority_if_separately_activated"]
    for key in ("decompression", "metadata_raw_prefix_processing", "event_pair_shape_processing", "selected_fill_field_processing", "fill_time_integer_milliseconds_processing", "wallet_feature_retention"):
        assert future[key] is True, key
    assert future["record_anchored_rule_id"] == RULE
    assert future["numeric_tolerance_authorized"] is False
    for key in ("metadata_timezone_parsing", "metadata_timezone_inference", "metadata_datetime_conversion", "raw_object_retention", "raw_block_record_retention", "raw_event_pair_retention", "raw_fill_object_retention"):
        assert future[key] is False, key

    assert c["canonical_activation_required"] is True
    assert c["canonical_activation_present"] is False
    assert c["single_use_window_start_utc"] is None
    for key in (
        "single_workflow_dispatch_authorized", "aws_oidc_authorized", "requester_pays_authorized",
        "get_object_authorized", "object_body_download_authorized", "decompression_authorized",
        "metadata_prefix_processing_authorized", "selected_fill_field_processing_authorized",
        "wallet_feature_retention_authorized", "release_consumed", "rerun_authorized",
    ):
        assert c[key] is False, key
    assert c["network_requests_executed"] == 0
    assert c["aws_iam_mutations_executed"] == 0
    assert c["wallet_feature_rows_created"] == 0
    assert c["empirical_result"] is None
    assert all(v is False for v in c["semantic_boundaries"].values())
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

    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.startswith("name: Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10\nrun-name: R10D record-anchored multi-hour feature repair\n")
    assert "workflow_dispatch:" in text and "schedule:" not in text and "push:" not in text
    assert "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10D_RUN" in text
    assert text.index("Prove exact single-use R10D release before OIDC") < text.index("Assume exact existing R10 role with exact-six session scope")
    assert f"role-to-assume: {ROLE}" in text
    assert text.count("arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/") == 6
    assert '"Action":"s3:GetObject"' in text
    assert RULE in text

    print("R10D_EXECUTION_RELEASE_CANDIDATE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
