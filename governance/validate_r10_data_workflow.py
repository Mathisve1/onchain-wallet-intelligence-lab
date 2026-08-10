from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
DATA = BASE / "r10_data_execution"
IMPL = BASE / "r10_implementation"
ROLE = BASE / "r10_role_attestation/R10_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
STS = BASE / "r10_role_preflight/HL-ARCHIVE-R10-DEDICATED-ROLE-STS-PREFLIGHT-001-ATTESTATION.json"
STS_CONSUMPTION = BASE / "r10_runtime/R10_STS_PREFLIGHT_RELEASE_CONSUMPTION.json"
APPROVAL = BASE / "r10_approval/APPROVE_HL_ARCHIVE_POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_001.json"
CONTRACT = DATA / "R10_DATA_WORKFLOW_IMPLEMENTATION_CONTRACT.json"
SOURCE_CANDIDATE = IMPL / "workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml"
PREFLIGHT_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-role-preflight-r10.yml"
RELEASE_CANDIDATE = DATA / "R10_EXECUTION_RELEASE_CANDIDATE.json"
RUNTIME_RELEASE = BASE / "r10_runtime/R10_EXECUTION_RELEASE_CANONICALIZATION.json"

SOURCE_CANDIDATE_SHA = "89d44c623cb2352d691bccbed1932107050f4a66606e9a23146c492bbf65e0f6"
INSTALLED_WORKFLOW_SHA = "4d3b85c01a5f529e16e8516a47e83931521438e978a17fdabdf8397b0f0c275e"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
WORKFLOW_NAME = "Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10"
OBJECT_ARNS = [f"arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/{hour}.lz4" for hour in range(9, 15)]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    c = load(CONTRACT)
    role = load(ROLE)
    sts = load(STS)
    consumption = load(STS_CONSUMPTION)
    approval = load(APPROVAL)

    assert c["stage_id"] == "HL-ARCHIVE-R10-DATA-WORKFLOW-IMPLEMENTATION-001"
    assert c["status"] == "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE"
    assert c["r10_approval_merge_commit"] == "92761986d8dc6bf818eebf7dc0411d24649a27df"
    assert c["r10_implementation_merge_commit"] == "820d0cbbb0f49f800f36025da27a06754d3fc08d"
    assert c["r10_role_attestation_merge_commit"] == "ba7835c8e8ecb1cdc6a1c44c9b679d8f43e7a40e"
    assert c["r10_sts_preflight_release_merge_commit"] == "8316f05f8fdfd444073e69e292cb89766ac89d7b"
    assert c["r10_sts_preflight_evidence_merge_commit"] == "5e54d346653f2153c21a50c3d25c755b596a651b"
    assert c["source_frozen_data_workflow_candidate_sha256"] == SOURCE_CANDIDATE_SHA
    assert c["installed_data_workflow_sha256"] == INSTALLED_WORKFLOW_SHA
    assert c["dedicated_role_arn"] == ROLE_ARN
    assert c["workflow_name"] == WORKFLOW_NAME
    assert c["consumed_preflight_workflow_retired"] is False
    assert c["consumed_preflight_workflow_retained_fail_closed"] is True
    assert c["candidate_binding_adjustment"]["required"] is True
    assert c["candidate_binding_adjustment"]["scope_expanding"] is False
    assert c["candidate_binding_adjustment"]["source_candidate_immutable"] is True
    assert c["execution_release_required"] is True
    assert c["execution_release_candidate_present"] is False
    assert c["canonical_activation_required"] is True
    assert c["canonical_activation_present"] is False
    assert c["single_workflow_dispatch_authorized"] is False
    assert c["rerun_authorized"] is False
    assert c["aws_oidc_authorized_now"] is False
    assert c["get_object_authorized_now"] is False
    assert c["s3_requests_executed_by_this_stage"] == 0
    assert c["object_bytes_downloaded_by_this_stage"] == 0
    assert c["wallet_feature_rows_created_by_this_stage"] == 0
    assert all(value is False for value in c["downstream_authorizations"].values())
    assert all(value is False for value in c["trading_authorizations"].values())
    assert c["empirical_result"] is None

    env = c["execution_envelope"]
    assert env["maximum_one_time_budget_eur"] == 0.1
    assert env["maximum_monthly_budget_eur"] == 0
    assert env["maximum_get_object_requests"] == 6
    assert env["maximum_requests_per_object"] == 1
    assert env["maximum_total_compressed_bytes"] == 120999698
    assert env["maximum_individual_compressed_bytes"] == 21672141
    assert env["maximum_total_decompressed_bytes"] == 1073741824
    assert env["maximum_individual_decompressed_bytes"] == 268435456
    assert env["maximum_runtime_seconds"] == 300
    assert env["maximum_retries_per_request"] == 0
    assert env["selected_hour_count"] == 6
    assert env["window_start_utc"] == "2025-07-27T09:00:00Z"
    assert env["window_end_exclusive_utc"] == "2025-07-27T15:00:00Z"
    assert c["session_scope"]["allowed_s3_actions_only"] == ["s3:GetObject"]
    assert c["session_scope"]["allowed_object_count"] == 6
    assert c["session_scope"]["exact_object_arns"] == OBJECT_ARNS

    assert approval["execution_authorized_by_this_approval"] is False
    assert approval["separate_execution_release_required"] is True
    assert approval["separate_canonical_activation_required"] is True
    assert approval["approved_future_scope"]["maximum_get_object_requests"] == 6
    assert approval["approved_future_scope"]["maximum_total_compressed_bytes"] == 120999698
    assert approval["approved_future_scope"]["maximum_total_decompressed_bytes"] == 1073741824

    assert role["attestation_id"] == "R10_DEDICATED_ROLE_OPERATOR_ATTESTATION"
    assert role["role_arn"] == ROLE_ARN
    assert role["role_created_and_policies_applied"] is True
    assert role["installed_trust_policy_matches_canonical"] is True
    assert role["installed_permission_policy_matches_canonical"] is True
    assert role["additional_managed_policies_attached"] is False
    assert role["additional_inline_policies_attached"] is False
    assert role["existing_r4_role_modified"] is False
    assert role["s3_requests_executed_by_role_creation_step"] == 0

    assert sts["terminal_status"] == "R10_STS_PREFLIGHT_PASS"
    assert sts["technical_result"] == "DEDICATED_R10_ROLE_ASSUMEABLE_FROM_CANONICAL_MAIN"
    assert sts["observed_account_id"] == "630956766927"
    assert sts["expected_role_arn"] == ROLE_ARN
    assert sts["operator_attestation_independently_verified_by_preflight"] is True
    assert sts["preflight_release_consumed"] is True
    assert sts["rerun_authorized"] is False
    assert sts["s3_http_request_count"] == 0
    assert consumption["status"] == "CONSUMED_SUCCESS"
    assert consumption["preflight_release_consumed"] is True
    assert consumption["rerun_authorized"] is False
    assert consumption["s3_requests_executed"] == 0

    assert sha256(SOURCE_CANDIDATE) == SOURCE_CANDIDATE_SHA
    assert sha256(WORKFLOW) == INSTALLED_WORKFLOW_SHA
    assert PREFLIGHT_WORKFLOW.is_file()
    assert sha256(PREFLIGHT_WORKFLOW) == "fefef8a7bb40e965c9ed77e9892057ac8e0a64dcfa60d7f3e7dba8f1651b5f4d"
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.startswith(f"name: {WORKFLOW_NAME}\n")
    assert "run-name: R10 bounded six-hour multi-wallet feature pilot" in text
    assert "workflow_dispatch:" in text
    assert "id-token: write" in text
    assert "persist-credentials: false" in text
    assert "role-duration-seconds: 900" in text
    assert "retry-max-attempts: 1" in text
    assert "action-timeout-s: 60" in text
    assert "R10_STS_PREFLIGHT_RELEASE_CONSUMPTION.json" in text
    assert "HL-ARCHIVE-R10-DEDICATED-ROLE-STS-PREFLIGHT-001-ATTESTATION.json" in text
    assert "R10_EXECUTION_RELEASE_CANONICALIZATION.json" in text
    assert "python governance/validate_r10_role_preflight_evidence.py" in text
    assert "python research/archive_inventory/r10_implementation/collector.py" in text
    assert text.count("s3:GetObject") == 1
    for arn in OBJECT_ARNS:
        assert arn in text
    assert "aws s3" not in text
    assert "aws s3api" not in text
    assert "wallet_ranking_authorized':False" in text
    assert "pnl_or_alpha_analysis_authorized':False" in text
    assert "copyability_analysis_authorized':False" in text

    # Later stages may add an inert release candidate and then a canonical single-use
    # runtime release. This implementation snapshot itself remains unchanged.
    if RELEASE_CANDIDATE.exists():
        later = load(RELEASE_CANDIDATE)
        assert later["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
        assert later["single_workflow_dispatch_authorized"] is False
        assert later["get_object_authorized"] is False
        assert later["rerun_authorized"] is False
    if RUNTIME_RELEASE.exists():
        later = load(RUNTIME_RELEASE)
        assert later["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10_RUN"
        assert later["single_workflow_dispatch_authorized"] is True
        assert later["rerun_authorized"] is False
        assert later["release_consumed"] is False
        assert later["maximum_get_object_requests"] == 6
        assert later["maximum_total_compressed_bytes"] == 120999698
        assert all(value is False for value in later["downstream_authorizations"].values())
        assert all(value is False for value in later["trading_authorizations"].values())

    print("R10_DATA_WORKFLOW_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
