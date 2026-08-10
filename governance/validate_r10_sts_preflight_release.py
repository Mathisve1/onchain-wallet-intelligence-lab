from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RELEASE = BASE / "r10_runtime/R10_STS_PREFLIGHT_RELEASE.json"
CANDIDATE = BASE / "r10_role_preflight/R10_STS_PREFLIGHT_RELEASE_CANDIDATE.json"
CONTRACT = BASE / "r10_role_preflight/R10_STS_PREFLIGHT_CONTRACT.json"
ATTESTATION = BASE / "r10_role_attestation/R10_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-role-preflight-r10.yml"
DATA_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml"

RELEASE_CANDIDATE_MERGE = "fdefa27955202f4592c9441665f3c40336c501d1"
PREFLIGHT_IMPLEMENTATION_MERGE = "57583e70f0067d045dc8d51d9e8c67c27fa8b818"
ROLE_ATTESTATION_MERGE = "ba7835c8e8ecb1cdc6a1c44c9b679d8f43e7a40e"
R10_IMPLEMENTATION_MERGE = "820d0cbbb0f49f800f36025da27a06754d3fc08d"
ATTESTATION_TEXT_SHA = "aa6547983d197941b7ffe90811a77665a7924a8a29fb89955d2f31456cd9c8cd"
WORKFLOW_SHA = "fefef8a7bb40e965c9ed77e9892057ac8e0a64dcfa60d7f3e7dba8f1651b5f4d"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
WINDOW_START = "2026-08-10T08:43:00Z"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    release = load(RELEASE)
    candidate = load(CANDIDATE)
    contract = load(CONTRACT)
    attestation = load(ATTESTATION)

    assert release["preflight_release_id"] == "RELEASE_HL_ARCHIVE_R10_ROLE_STS_PREFLIGHT_001"
    assert release["preflight_id"] == "HL-ARCHIVE-R10-DEDICATED-ROLE-STS-PREFLIGHT-001"
    assert release["status"] == "RELEASED_FOR_EXACTLY_ONE_R10_STS_ONLY_PREFLIGHT"
    assert release["release_candidate_merge_commit"] == RELEASE_CANDIDATE_MERGE
    assert release["preflight_implementation_merge_commit"] == PREFLIGHT_IMPLEMENTATION_MERGE
    assert release["role_attestation_merge_commit"] == ROLE_ATTESTATION_MERGE
    assert release["r10_implementation_merge_commit"] == R10_IMPLEMENTATION_MERGE
    assert release["operator_attestation_text_sha256"] == ATTESTATION_TEXT_SHA
    assert release["workflow_sha256"] == WORKFLOW_SHA
    assert release["role_arn"] == ROLE_ARN
    assert release["expected_account_id"] == "630956766927"
    assert release["workflow_name"] == "Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10"
    assert release["workflow_path"] == ".github/workflows/hyperliquid-archive-post-boundary-multihour-role-preflight-r10.yml"
    assert release["activation_base_commit"] == RELEASE_CANDIDATE_MERGE
    assert release["single_use_window_start_utc"] == WINDOW_START
    parsed = datetime.fromisoformat(WINDOW_START.replace("Z", "+00:00")).astimezone(timezone.utc)
    assert parsed.isoformat() == "2026-08-10T08:43:00+00:00"
    assert release["single_workflow_dispatch_authorized"] is True
    assert release["rerun_authorized"] is False
    assert release["release_consumed"] is False
    assert release["operator_attestation_reviewed"] is True
    assert release["sts_get_caller_identity_authorized"] is True
    assert release["maximum_explicit_aws_cli_calls"] == 1
    assert release["role_session_name"] == "HLArchiveR10STSPreflight"
    assert release["role_duration_seconds"] == 900
    assert release["configure_aws_retry_max_attempts"] == 1
    assert release["configure_aws_action_timeout_seconds"] == 60
    assert release["inline_session_policy"] == "DENY_ALL_S3_ON_ALL_RESOURCES"

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
        assert release[key] is False, key
    assert all(value is False for value in release["trading_authorizations"].values())
    assert release["aws_sts_requests_executed"] == 0
    assert release["s3_requests_executed"] == 0
    assert release["object_bytes_downloaded"] == 0
    assert release["empirical_result"] is None

    # The candidate and implementation contract remain immutable and inert.
    assert candidate["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert candidate["canonical_activation_present"] is False
    assert candidate["single_workflow_dispatch_authorized"] is False
    assert candidate["sts_get_caller_identity_authorized"] is False
    assert candidate["s3_access_authorized_during_preflight"] is False
    assert candidate["aws_sts_requests_executed"] == 0
    assert candidate["s3_requests_executed"] == 0
    assert contract["status"] == "IMPLEMENTED_AWAITING_SEPARATE_PREFLIGHT_RELEASE"
    assert contract["preflight_release_present"] is False
    assert contract["preflight_execution_authorized"] is False
    assert contract["sts_get_caller_identity_authorized"] is False
    assert contract["aws_sts_requests_executed"] == 0
    assert contract["s3_requests_executed"] == 0
    assert attestation["operator_attested"] is True
    assert attestation["sts_only_preflight_completed"] is False

    assert hashlib.sha256(WORKFLOW.read_bytes()).hexdigest() == WORKFLOW_SHA
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count("aws sts get-caller-identity --output json") == 1
    assert '"Effect":"Deny","Action":"s3:*","Resource":"*"' in text
    assert "aws s3" not in text
    assert "aws s3api" not in text
    assert DATA_WORKFLOW.is_file()
    runtime_files = sorted(path.name for path in RELEASE.parent.iterdir() if path.is_file())
    assert runtime_files == ["R10_EXECUTION_RELEASE_CANONICALIZATION.json", "R10_STS_PREFLIGHT_RELEASE.json", "R10_STS_PREFLIGHT_RELEASE_CONSUMPTION.json"]

    print("R10_STS_PREFLIGHT_RELEASE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
