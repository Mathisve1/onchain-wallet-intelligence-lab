from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREFLIGHT_DIR = BASE / "r10_role_preflight"
CANDIDATE = PREFLIGHT_DIR / "R10_STS_PREFLIGHT_RELEASE_CANDIDATE.json"
CONTRACT = PREFLIGHT_DIR / "R10_STS_PREFLIGHT_CONTRACT.json"
ATTESTATION = BASE / "r10_role_attestation/R10_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-role-preflight-r10.yml"
DATA_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml"
RUNTIME_DIR = BASE / "r10_runtime"
RUNTIME_RELEASE = RUNTIME_DIR / "R10_STS_PREFLIGHT_RELEASE.json"

PREFLIGHT_IMPLEMENTATION_MERGE = "57583e70f0067d045dc8d51d9e8c67c27fa8b818"
ROLE_ATTESTATION_MERGE = "ba7835c8e8ecb1cdc6a1c44c9b679d8f43e7a40e"
R10_IMPLEMENTATION_MERGE = "820d0cbbb0f49f800f36025da27a06754d3fc08d"
R10_APPROVAL_MERGE = "92761986d8dc6bf818eebf7dc0411d24649a27df"
RELEASE_CANDIDATE_MERGE = "fdefa27955202f4592c9441665f3c40336c501d1"
ATTESTATION_TEXT_SHA = "aa6547983d197941b7ffe90811a77665a7924a8a29fb89955d2f31456cd9c8cd"
WORKFLOW_SHA = "fefef8a7bb40e965c9ed77e9892057ac8e0a64dcfa60d7f3e7dba8f1651b5f4d"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    candidate = load(CANDIDATE)
    contract = load(CONTRACT)
    attestation = load(ATTESTATION)

    assert candidate["preflight_release_candidate_id"] == "CANDIDATE_RELEASE_HL_ARCHIVE_R10_ROLE_STS_PREFLIGHT_001"
    assert candidate["preflight_id"] == "HL-ARCHIVE-R10-DEDICATED-ROLE-STS-PREFLIGHT-001"
    assert candidate["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert candidate["preflight_implementation_merge_commit"] == PREFLIGHT_IMPLEMENTATION_MERGE
    assert candidate["role_attestation_merge_commit"] == ROLE_ATTESTATION_MERGE
    assert candidate["r10_implementation_merge_commit"] == R10_IMPLEMENTATION_MERGE
    assert candidate["r10_approval_merge_commit"] == R10_APPROVAL_MERGE
    assert candidate["operator_attestation_text_sha256"] == ATTESTATION_TEXT_SHA
    assert candidate["workflow_sha256"] == WORKFLOW_SHA
    assert candidate["role_arn"] == ROLE_ARN
    assert candidate["expected_account_id"] == "630956766927"
    assert candidate["workflow_name"] == "Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10"
    assert candidate["workflow_path"] == ".github/workflows/hyperliquid-archive-post-boundary-multihour-role-preflight-r10.yml"
    assert candidate["future_runtime_release_path"] == "research/archive_inventory/r10_runtime/R10_STS_PREFLIGHT_RELEASE.json"
    assert candidate["github_event_required"] == "workflow_dispatch"
    assert candidate["canonical_dispatch_ref_required"] == "refs/heads/main"
    assert candidate["role_session_name"] == "HLArchiveR10STSPreflight"
    assert candidate["role_duration_seconds"] == 900
    assert candidate["configure_aws_retry_max_attempts"] == 1
    assert candidate["configure_aws_action_timeout_seconds"] == 60
    assert candidate["inline_session_policy"] == "DENY_ALL_S3_ON_ALL_RESOURCES"
    assert candidate["future_explicit_aws_cli_commands"] == ["aws sts get-caller-identity --output json"]
    assert candidate["future_maximum_explicit_aws_cli_calls"] == 1
    assert candidate["canonical_activation_required"] is True
    assert candidate["canonical_activation_present"] is False
    assert candidate["single_use_window_start_utc"] is None
    assert candidate["anchor_commit"] is None
    assert candidate["single_workflow_dispatch_authorized"] is False
    assert candidate["rerun_authorized"] is False
    assert candidate["sts_get_caller_identity_authorized"] is False
    assert candidate["release_consumed"] is False
    assert candidate["operator_attestation_reviewed"] is True

    for key in (
        "s3_access_authorized_during_preflight",
        "requester_pays_authorized",
        "get_object_authorized",
        "list_objects_authorized",
        "head_object_authorized",
        "range_get_authorized",
        "object_body_download_authorized",
        "decompression_authorized",
        "raw_oidc_token_retention_authorized",
        "aws_credentials_retention_authorized",
        "raw_caller_identity_retention_authorized",
        "data_workflow_installation_authorized",
        "historical_window_expansion_authorized",
        "wallet_ranking_authorized",
        "shortlisting_authorized",
        "pnl_or_alpha_analysis_authorized",
        "copyability_analysis_authorized",
        "market_data_ingestion_authorized",
    ):
        assert candidate[key] is False, key
    assert all(value is False for value in candidate["trading_authorizations"].values())
    assert candidate["aws_sts_requests_executed"] == 0
    assert candidate["s3_requests_executed"] == 0
    assert candidate["object_bytes_downloaded"] == 0
    assert candidate["empirical_result"] is None

    assert contract["status"] == "IMPLEMENTED_AWAITING_SEPARATE_PREFLIGHT_RELEASE"
    assert contract["preflight_release_present"] is False
    assert contract["preflight_execution_authorized"] is False
    assert contract["sts_get_caller_identity_authorized"] is False
    assert contract["aws_sts_requests_executed"] == 0
    assert contract["s3_requests_executed"] == 0
    assert attestation["operator_attested"] is True
    assert attestation["sts_only_preflight_completed"] is False
    assert attestation["execution_release_present"] is False

    assert WORKFLOW.is_file()
    assert hashlib.sha256(WORKFLOW.read_bytes()).hexdigest() == WORKFLOW_SHA
    assert not DATA_WORKFLOW.exists()

    if RUNTIME_DIR.exists():
        assert RUNTIME_RELEASE.is_file()
        release = load(RUNTIME_RELEASE)
        assert release["status"] == "RELEASED_FOR_EXACTLY_ONE_R10_STS_ONLY_PREFLIGHT"
        assert release["release_candidate_merge_commit"] == RELEASE_CANDIDATE_MERGE
        assert release["role_arn"] == ROLE_ARN
        assert release["workflow_sha256"] == WORKFLOW_SHA
        assert release["single_workflow_dispatch_authorized"] is True
        assert release["rerun_authorized"] is False
        assert release["release_consumed"] is False
        assert release["sts_get_caller_identity_authorized"] is True
        assert release["s3_access_authorized_during_preflight"] is False
        assert release["data_workflow_installation_authorized"] is False
        assert release["aws_sts_requests_executed"] == 0
        assert release["s3_requests_executed"] == 0
        assert sorted(path.name for path in RUNTIME_DIR.iterdir() if path.is_file()) == ["R10_STS_PREFLIGHT_RELEASE.json", "R10_STS_PREFLIGHT_RELEASE_CONSUMPTION.json"]

    print("R10_STS_PREFLIGHT_RELEASE_CANDIDATE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
