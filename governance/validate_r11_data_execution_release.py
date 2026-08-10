from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RELEASE = BASE / "r11_runtime/R11_EXECUTION_RELEASE.json"
CANDIDATE = BASE / "r11_data_execution/R11_EXECUTION_RELEASE_CANDIDATE.json"
IMPLEMENTATION = BASE / "r11_data_execution/R11_DATA_WORKFLOW_IMPLEMENTATION_CONTRACT.json"
APPROVAL = BASE / "r11_approval/APPROVE_HL_ARCHIVE_R11_72H_PERSISTENCE_SCALING_001.json"
SELECTION = BASE / "r11/R11_72H_SELECTION.json"
PERMISSION = BASE / "r11_implementation/R11_PERMISSION_POLICY.json"
STS = BASE / "r11_role_preflight/HL-ARCHIVE-R11-DEDICATED-ROLE-STS-PREFLIGHT-001-ATTESTATION.json"
STS_CONSUMPTION = BASE / "r11_runtime/R11_STS_PREFLIGHT_RELEASE_CONSUMPTION.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11-72h-persistence.yml"

CANDIDATE_MERGE = "0cf741d7bf853598e293936648d2fdc9a27975a1"
DATA_IMPL_MERGE = "932b39d45acccc83cc7bf55d3dc29cb8b51a12cd"
WORKFLOW_BLOB_SHA = "3b9d8c723d1bbf675def790027afbf91f814754e"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-scaling-r11"
WINDOW_START = "2026-08-10T21:57:00Z"
PREFIX_ARNS = [
    "arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250728/*",
    "arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250729/*",
    "arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250730/*",
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def main() -> int:
    r = load(RELEASE)
    c = load(CANDIDATE)
    impl = load(IMPLEMENTATION)
    approval = load(APPROVAL)
    selection = load(SELECTION)
    permission = load(PERMISSION)
    sts = load(STS)
    consumption = load(STS_CONSUMPTION)

    assert r["execution_release_id"] == "RELEASE_HL_ARCHIVE_R11_72H_PERSISTENCE_001"
    assert r["pilot_id"] == "HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001"
    assert r["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R11_RUN"
    assert r["release_candidate_merge_commit"] == CANDIDATE_MERGE
    assert r["data_workflow_implementation_merge_commit"] == DATA_IMPL_MERGE
    assert r["r11_preregistration_merge_commit"] == "dc63f2846652e50755369aa95d0f01ec2e174b02"
    assert r["r11_approval_merge_commit"] == "86333a6759a492e5452bc565802fefce55a9fd6f"
    assert r["r11_implementation_merge_commit"] == "9568424524a2a9f78e75bf0f68b4de6146f6f2b7"
    assert r["r11_role_attestation_merge_commit"] == "38156c94a15aaef277a9bd8cf31c3a4808be1147"
    assert r["r11_sts_preflight_evidence_merge_commit"] == "db935f6c44639ba2a2fa66d8c1b4d0d1d26b254a"
    assert r["approval_text_sha256"] == "1c3ec861d5df30dbdeef4dece7422bc05fab50d59aa58aa36cf3b7f8fea0d3ca"
    assert r["selection_sha256"] == "7c134f4b62f547904126a5f810c177484dceeffa246d53c5c35944367d563eb2"
    assert r["selection_path"] == "research/archive_inventory/r11/R11_72H_SELECTION.json"
    assert r["selected_object_count"] == 72
    assert r["data_workflow_git_blob_sha"] == WORKFLOW_BLOB_SHA
    assert r["role_arn"] == ROLE_ARN
    assert r["workflow_name"] == "Hyperliquid Archive 72H Persistence Scaling R11"
    assert r["workflow_path"] == ".github/workflows/hyperliquid-archive-r11-72h-persistence.yml"
    assert r["canonical_activation_present"] is True
    assert r["activation_base_commit"] == CANDIDATE_MERGE
    assert r["single_use_window_start_utc"] == WINDOW_START
    parsed = datetime.fromisoformat(WINDOW_START.replace("Z", "+00:00")).astimezone(timezone.utc)
    assert parsed.isoformat() == "2026-08-10T21:57:00+00:00"
    assert r["single_workflow_dispatch_authorized"] is True
    assert r["rerun_authorized"] is False
    assert r["release_consumed"] is False

    for key in (
        "aws_oidc_authorized", "requester_pays_authorized", "get_object_authorized",
        "object_body_download_authorized", "decompression_authorized",
        "selected_fill_field_processing_authorized", "wallet_feature_retention_authorized",
    ):
        assert r[key] is True, key
    for key in (
        "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
        "list_object_versions_authorized", "list_all_my_buckets_authorized",
        "get_object_attributes_authorized", "get_object_version_authorized",
        "http_redirect_following_authorized",
    ):
        assert r[key] is False, key
    assert all(v is False for v in r["semantic_boundaries"].values())
    assert all(v is False for v in r["downstream_authorizations"].values())
    assert all(v is False for v in r["trading_authorizations"].values())
    assert r["network_requests_executed_by_activation"] == 0
    assert r["s3_requests_executed_by_activation"] == 0
    assert r["object_bytes_downloaded_by_activation"] == 0
    assert r["wallet_feature_rows_created_by_activation"] == 0
    assert r["empirical_result"] is None

    assert r["maximum_one_time_budget_eur"] == 0.50
    assert r["maximum_monthly_budget_eur"] == 0
    assert r["maximum_get_object_requests"] == 72
    assert r["maximum_requests_per_object"] == 1
    assert r["maximum_retries_per_request"] == 0
    assert r["maximum_total_compressed_bytes"] == 2107738436
    assert r["maximum_individual_compressed_bytes"] == 76616104
    assert r["maximum_total_decompressed_bytes"] == 17179869184
    assert r["maximum_individual_decompressed_bytes"] == 536870912
    assert r["maximum_runtime_seconds"] == 5400
    assert r["request_order"] == "PATH_HOUR_ASCENDING"
    assert r["stop_after_first_failed_or_mismatched_object"] is True
    assert r["target_bucket"] == "hl-mainnet-node-data"
    assert r["signing_region"] == "ap-northeast-1"
    assert r["window_start_utc"] == "2025-07-28T00:00:00Z"
    assert r["window_end_exclusive_utc"] == "2025-07-31T00:00:00Z"
    assert r["record_anchored_rule_id"] == "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1"
    assert r["numeric_tolerance_authorized"] is False
    scope = r["session_scope"]
    assert scope["allowed_s3_actions_only"] == ["s3:GetObject"]
    assert scope["persistent_exact_object_count"] == 72
    assert scope["persistent_permission_must_equal_exact_selection"] is True
    assert scope["session_intersection_resource_arns"] == PREFIX_ARNS

    targets = selection["exact_targets"]
    assert selection["selected_hour_count"] == 72
    assert selection["complete_utc_day_count"] == 3
    assert selection["aggregate_expected_compressed_bytes"] == 2107738436
    assert len(targets) == 72
    assert len({row["key"] for row in targets}) == 72
    assert sum(row["expected_size_bytes"] for row in targets) == 2107738436
    assert max(row["expected_size_bytes"] for row in targets) == 76616104
    assert targets[0]["path_hour_utc"] == "2025-07-28T00:00:00Z"
    assert targets[-1]["path_hour_utc"] == "2025-07-30T23:00:00Z"
    exact_arns = [f"arn:aws:s3:::hl-mainnet-node-data/{row['key']}" for row in targets]
    allow = permission["Statement"][0]
    assert allow["Action"] == "s3:GetObject"
    assert allow["Resource"] == exact_arns
    assert len(exact_arns) == len(set(exact_arns)) == 72

    # Earlier governance snapshots stay immutable and non-self-authorizing.
    assert c["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert c["canonical_activation_present"] is False
    assert c["single_workflow_dispatch_authorized"] is False
    assert c["aws_oidc_authorized"] is False
    assert c["get_object_authorized"] is False
    assert c["wallet_feature_retention_authorized"] is False
    assert impl["status"] == "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE"
    assert impl["single_workflow_dispatch_authorized"] is False
    assert impl["aws_oidc_authorized_now"] is False
    assert impl["get_object_authorized_now"] is False
    assert approval["execution_authorized_by_this_approval"] is False
    assert approval["separate_execution_release_required"] is True
    assert approval["separate_canonical_activation_required"] is True
    assert sts["terminal_status"] == "R11_STS_PREFLIGHT_PASS"
    assert sts["technical_result"] == "DEDICATED_R11_ROLE_ASSUMEABLE_FROM_CANONICAL_MAIN"
    assert sts["operator_attestation_independently_verified_by_preflight"] is True
    assert sts["s3_http_request_count"] == 0
    assert consumption["status"] == "CONSUMED_SUCCESS"
    assert consumption["preflight_release_consumed"] is True
    assert consumption["rerun_authorized"] is False
    assert consumption["s3_requests_executed"] == 0
    assert git_blob_sha(WORKFLOW) == WORKFLOW_BLOB_SHA

    print("R11_DATA_EXECUTION_RELEASE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
