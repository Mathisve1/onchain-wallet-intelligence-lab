from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
DATA = BASE / "r11_data_execution"
CONTRACT = DATA / "R11_DATA_WORKFLOW_IMPLEMENTATION_CONTRACT.json"
APPROVAL = BASE / "r11_approval/APPROVE_HL_ARCHIVE_R11_72H_PERSISTENCE_SCALING_001.json"
SELECTION = BASE / "r11/R11_72H_SELECTION.json"
ROLE = BASE / "r11_role_attestation/R11_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
STS = BASE / "r11_role_preflight/HL-ARCHIVE-R11-DEDICATED-ROLE-STS-PREFLIGHT-001-ATTESTATION.json"
STS_CONSUMPTION = BASE / "r11_runtime/R11_STS_PREFLIGHT_RELEASE_CONSUMPTION.json"
PERMISSION = BASE / "r11_implementation/R11_PERMISSION_POLICY.json"
SOURCE = BASE / "r11_implementation/workflows/hyperliquid-archive-r11-72h-persistence.yml"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11-72h-persistence.yml"
PREFLIGHT_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11-role-preflight.yml"
RELEASE_CANDIDATE = DATA / "R11_EXECUTION_RELEASE_CANDIDATE.json"
RUNTIME_RELEASE = BASE / "r11_runtime/R11_EXECUTION_RELEASE.json"

ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-scaling-r11"
WORKFLOW_NAME = "Hyperliquid Archive 72H Persistence Scaling R11"
WORKFLOW_BLOB_SHA = "3b9d8c723d1bbf675def790027afbf91f814754e"
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
    c = load(CONTRACT)
    approval = load(APPROVAL)
    selection = load(SELECTION)
    role = load(ROLE)
    sts = load(STS)
    consumption = load(STS_CONSUMPTION)
    permission = load(PERMISSION)

    assert c["stage_id"] == "HL-ARCHIVE-R11-DATA-WORKFLOW-IMPLEMENTATION-001"
    assert c["pilot_id"] == "HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001"
    assert c["status"] == "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE"
    assert c["r11_preregistration_merge_commit"] == "dc63f2846652e50755369aa95d0f01ec2e174b02"
    assert c["r11_approval_merge_commit"] == "86333a6759a492e5452bc565802fefce55a9fd6f"
    assert c["r11_implementation_merge_commit"] == "9568424524a2a9f78e75bf0f68b4de6146f6f2b7"
    assert c["r11_role_attestation_merge_commit"] == "38156c94a15aaef277a9bd8cf31c3a4808be1147"
    assert c["r11_sts_preflight_release_merge_commit"] == "efad3f278e458a5c35fbfcc11de2b97bbe7cb388"
    assert c["r11_sts_preflight_evidence_merge_commit"] == "db935f6c44639ba2a2fa66d8c1b4d0d1d26b254a"
    assert c["approval_text_sha256"] == "1c3ec861d5df30dbdeef4dece7422bc05fab50d59aa58aa36cf3b7f8fea0d3ca"
    assert c["selection_sha256"] == "7c134f4b62f547904126a5f810c177484dceeffa246d53c5c35944367d563eb2"
    assert c["source_frozen_data_workflow_git_blob_sha"] == WORKFLOW_BLOB_SHA
    assert c["installed_data_workflow_git_blob_sha"] == WORKFLOW_BLOB_SHA
    assert c["installed_workflow_path"] == ".github/workflows/hyperliquid-archive-r11-72h-persistence.yml"
    assert c["source_frozen_workflow_path"] == "research/archive_inventory/r11_implementation/workflows/hyperliquid-archive-r11-72h-persistence.yml"
    assert c["workflow_name"] == WORKFLOW_NAME
    assert c["run_name"] == "R11 72h persistence scaling"
    assert c["expected_account_id"] == "630956766927"
    assert c["dedicated_role_arn"] == ROLE_ARN
    assert c["role_duration_seconds"] == 7200
    assert c["configure_aws_retry_max_attempts"] == 1
    assert c["configure_aws_action_timeout_seconds"] == 60
    assert c["preflight_evidence_path"] == "research/archive_inventory/r11_role_preflight/HL-ARCHIVE-R11-DEDICATED-ROLE-STS-PREFLIGHT-001-ATTESTATION.json"
    assert c["preflight_consumption_path"] == "research/archive_inventory/r11_runtime/R11_STS_PREFLIGHT_RELEASE_CONSUMPTION.json"
    assert c["preflight_release_consumed"] is True
    assert c["consumed_preflight_workflow_retained_fail_closed"] is True
    assert c["execution_release_required"] is True
    assert c["execution_release_candidate_present"] is False
    assert c["canonical_activation_required"] is True
    assert c["canonical_activation_present"] is False
    assert c["single_workflow_dispatch_authorized"] is False
    assert c["rerun_authorized"] is False
    for key in (
        "aws_oidc_authorized_now",
        "requester_pays_authorized_now",
        "get_object_authorized_now",
        "object_body_download_authorized_now",
        "decompression_authorized_now",
        "selected_fill_field_processing_authorized_now",
        "wallet_feature_retention_authorized_now",
    ):
        assert c[key] is False, key
    assert c["s3_requests_executed_by_this_stage"] == 0
    assert c["object_bytes_downloaded_by_this_stage"] == 0
    assert c["wallet_feature_rows_created_by_this_stage"] == 0
    assert all(v is False for v in c["downstream_authorizations"].values())
    assert all(v is False for v in c["trading_authorizations"].values())
    assert c["empirical_result"] is None

    env = c["execution_envelope"]
    assert env == {
        "maximum_one_time_budget_eur": 0.50,
        "maximum_monthly_budget_eur": 0,
        "maximum_get_object_requests": 72,
        "maximum_requests_per_object": 1,
        "maximum_retries_per_request": 0,
        "maximum_total_compressed_bytes": 2107738436,
        "maximum_individual_compressed_bytes": 76616104,
        "maximum_total_decompressed_bytes": 17179869184,
        "maximum_individual_decompressed_bytes": 536870912,
        "maximum_runtime_seconds": 5400,
        "request_order": "PATH_HOUR_ASCENDING",
        "stop_after_first_failed_or_mismatched_object": True,
        "selected_hour_count": 72,
        "window_start_utc": "2025-07-28T00:00:00Z",
        "window_end_exclusive_utc": "2025-07-31T00:00:00Z",
        "target_bucket": "hl-mainnet-node-data",
        "signing_region": "ap-northeast-1",
    }
    scope = c["session_scope"]
    assert scope["allowed_s3_actions_only"] == ["s3:GetObject"]
    assert scope["persistent_exact_object_count"] == 72
    assert scope["persistent_permission_must_equal_exact_selection"] is True
    assert scope["session_intersection_resource_arns"] == PREFIX_ARNS
    assert c["record_anchored_rule_id"] == "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1"
    assert c["numeric_tolerance_authorized"] is False

    assert approval["execution_authorized_by_this_approval"] is False
    assert approval["separate_execution_release_required"] is True
    assert approval["separate_canonical_activation_required"] is True
    approved = approval["approved_future_scope"]
    assert approved["maximum_get_object_requests"] == 72
    assert approved["maximum_retries_per_request"] == 0
    assert approved["maximum_total_compressed_bytes"] == 2107738436
    assert approved["maximum_total_decompressed_bytes"] == 17179869184
    assert approved["maximum_runtime_seconds"] == 5400
    assert approval["approved_future_transport"]["requester_pays"] is True
    assert approval["approved_future_transport"]["get_object"] is True
    for key in ("head_object","range_get","list_objects_v2","list_object_versions","list_all_my_buckets","get_object_attributes","get_object_version","http_redirect_following"):
        assert approval["approved_future_transport"][key] is False, key

    assert role["role_arn"] == ROLE_ARN
    assert role["role_created_and_policies_applied"] is True
    assert role["installed_trust_policy_matches_canonical"] is True
    assert role["installed_permission_policy_matches_canonical"] is True
    assert role["persistent_permission_resource_count"] == 72
    assert role["persistent_permission_resources_match_exact_selection_objects"] is True
    assert role["additional_managed_policies_attached"] is False
    assert role["additional_inline_policies_attached"] is False
    assert role["existing_r10_role_modified"] is False

    assert sts["terminal_status"] == "R11_STS_PREFLIGHT_PASS"
    assert sts["technical_result"] == "DEDICATED_R11_ROLE_ASSUMEABLE_FROM_CANONICAL_MAIN"
    assert sts["expected_account_id"] == sts["observed_account_id"] == "630956766927"
    assert sts["expected_role_arn"] == ROLE_ARN
    assert sts["operator_attestation_independently_verified_by_preflight"] is True
    assert sts["preflight_release_consumed"] is True
    assert sts["rerun_authorized"] is False
    assert sts["s3_http_request_count"] == 0
    assert sts["object_bytes_downloaded"] == 0
    assert consumption["status"] == "CONSUMED_SUCCESS"
    assert consumption["preflight_release_consumed"] is True
    assert consumption["rerun_authorized"] is False
    assert consumption["s3_requests_executed"] == 0
    assert consumption["object_bytes_downloaded"] == 0

    exact_targets = selection["exact_targets"]
    exact_arns = [f"arn:aws:s3:::hl-mainnet-node-data/{row['key']}" for row in exact_targets]
    allow = permission["Statement"][0]
    assert allow["Action"] == "s3:GetObject"
    assert allow["Resource"] == exact_arns
    assert len(exact_arns) == len(set(exact_arns)) == 72
    assert all("*" not in arn for arn in exact_arns)

    assert SOURCE.is_file() and WORKFLOW.is_file()
    assert SOURCE.read_bytes() == WORKFLOW.read_bytes()
    assert git_blob_sha(SOURCE) == WORKFLOW_BLOB_SHA
    assert git_blob_sha(WORKFLOW) == WORKFLOW_BLOB_SHA
    assert PREFLIGHT_WORKFLOW.is_file()
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.startswith(f"name: {WORKFLOW_NAME}\n")
    assert "run-name: R11 72h persistence scaling" in text
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text and "push:" not in text
    assert "id-token: write" in text and "actions: read" in text
    assert "persist-credentials: false" in text
    assert f"role-to-assume: {ROLE_ARN}" in text
    assert "role-duration-seconds: 7200" in text
    assert "retry-max-attempts: 1" in text and "action-timeout-s: 60" in text
    assert "R11_STS_PREFLIGHT_RELEASE_CONSUMPTION.json" not in text
    assert "HL-ARCHIVE-R11-DEDICATED-ROLE-STS-PREFLIGHT-001-ATTESTATION.json" in text
    assert "R11_EXECUTION_RELEASE.json" in text
    assert "research.archive_inventory.r11_implementation.collector" in text
    assert "r11-wallet-features.ndjson" in text
    assert text.count('"Action":"s3:GetObject"') == 1
    for arn in PREFIX_ARNS:
        assert arn in text
    assert "aws s3 " not in text.lower() and "aws s3api " not in text.lower()
    for token in (
        "wallet_ranking_performed",
        "candidate_shortlisting_performed",
        "pnl_or_alpha_analysis_performed",
        "copyability_analysis_performed",
        "active_day_count_interpreted_as_wallet_quality_score",
    ):
        assert token in text

    # Later stages may add an inert release candidate and then a single-use runtime release.
    if RELEASE_CANDIDATE.exists():
        later = load(RELEASE_CANDIDATE)
        assert later["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
        assert later["single_workflow_dispatch_authorized"] is False
        assert later["requester_pays_authorized"] is False
        assert later["get_object_authorized"] is False
        assert later["rerun_authorized"] is False
    if RUNTIME_RELEASE.exists():
        later = load(RUNTIME_RELEASE)
        assert later["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R11_RUN"
        assert later["single_workflow_dispatch_authorized"] is True
        assert later["rerun_authorized"] is False
        assert later["release_consumed"] is False
        assert later["maximum_get_object_requests"] == 72
        assert later["maximum_retries_per_request"] == 0
        assert later["maximum_total_compressed_bytes"] == 2107738436
        assert later["record_anchored_rule_id"] == "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1"
        assert later["numeric_tolerance_authorized"] is False
        assert all(v is False for v in later["downstream_authorizations"].values())
        assert all(v is False for v in later["trading_authorizations"].values())

    print("R11_DATA_WORKFLOW_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
