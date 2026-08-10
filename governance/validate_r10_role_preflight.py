from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CONTRACT = BASE / "r10_role_preflight/R10_STS_PREFLIGHT_CONTRACT.json"
RELEASE_CANDIDATE = BASE / "r10_role_preflight/R10_STS_PREFLIGHT_RELEASE_CANDIDATE.json"
ATTESTATION = BASE / "r10_role_attestation/R10_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
ATTESTATION_TEXT = BASE / "r10_role_attestation/R10_DEDICATED_ROLE_OPERATOR_ATTESTATION.txt"
TRUST = BASE / "r10_implementation/R10_OIDC_TRUST_POLICY.json"
CANDIDATE = BASE / "r10_implementation/workflows/hyperliquid-archive-post-boundary-multihour-role-preflight-r10.yml"
PREFLIGHT_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-role-preflight-r10.yml"
DATA_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml"
RUNTIME = BASE / "r10_runtime"
RUNTIME_RELEASE = RUNTIME / "R10_STS_PREFLIGHT_RELEASE.json"

ROLE_ATTESTATION_MERGE = "ba7835c8e8ecb1cdc6a1c44c9b679d8f43e7a40e"
R10_IMPLEMENTATION_MERGE = "820d0cbbb0f49f800f36025da27a06754d3fc08d"
SESSION_REPAIR_MERGE = "c2e4e262d74bcf9feebb531d507590d5f9e62c85"
RELEASE_CANDIDATE_MERGE = "fdefa27955202f4592c9441665f3c40336c501d1"
ATTESTATION_TEXT_SHA = "aa6547983d197941b7ffe90811a77665a7924a8a29fb89955d2f31456cd9c8cd"
TRUST_SHA = "2709fe66f6361d6498e07bdd2f292576c73485772af6d3cabb89a211e46bdcb9"
PERMISSION_SHA = "caab807fb0fbc2f1d2132921a99692f5d3533db8449d9a55e4da0714147177fe"
WORKFLOW_SHA = "fefef8a7bb40e965c9ed77e9892057ac8e0a64dcfa60d7f3e7dba8f1651b5f4d"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
WORKFLOW_NAME = "Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    contract = load(CONTRACT)
    attestation = load(ATTESTATION)
    trust = load(TRUST)

    assert contract["preflight_id"] == "HL-ARCHIVE-R10-DEDICATED-ROLE-STS-PREFLIGHT-001"
    assert contract["status"] == "IMPLEMENTED_AWAITING_SEPARATE_PREFLIGHT_RELEASE"
    assert contract["role_attestation_merge_commit"] == ROLE_ATTESTATION_MERGE
    assert contract["r10_implementation_merge_commit"] == R10_IMPLEMENTATION_MERGE
    assert contract["session_duration_repair_merge_commit"] == SESSION_REPAIR_MERGE
    assert contract["operator_attestation_text_sha256"] == ATTESTATION_TEXT_SHA
    assert contract["trust_policy_sha256"] == TRUST_SHA
    assert contract["permission_policy_sha256"] == PERMISSION_SHA
    assert contract["role_arn"] == ROLE_ARN
    assert contract["expected_account_id"] == "630956766927"
    assert contract["workflow_name"] == WORKFLOW_NAME
    assert contract["workflow_path"] == ".github/workflows/hyperliquid-archive-post-boundary-multihour-role-preflight-r10.yml"
    assert contract["frozen_workflow_candidate_sha256"] == WORKFLOW_SHA
    assert contract["installed_workflow_sha256"] == WORKFLOW_SHA
    assert contract["github_event_required"] == "workflow_dispatch"
    assert contract["canonical_dispatch_ref_required"] == "refs/heads/main"
    assert contract["canonical_dispatch_sha_source"] == "github.sha"
    assert contract["role_session_name"] == "HLArchiveR10STSPreflight"
    assert contract["role_duration_seconds"] == 900
    assert contract["configure_aws_retry_max_attempts"] == 1
    assert contract["configure_aws_action_timeout_seconds"] == 60
    assert contract["inline_session_policy"] == "DENY_ALL_S3_ON_ALL_RESOURCES"
    assert contract["explicit_aws_cli_commands"] == ["aws sts get-caller-identity --output json"]
    assert contract["maximum_explicit_aws_cli_calls"] == 1
    assert contract["preflight_release_required"] is True
    assert contract["preflight_release_present"] is False
    assert contract["preflight_execution_authorized"] is False
    assert contract["sts_get_caller_identity_authorized"] is False
    assert contract["single_workflow_dispatch_authorized"] is False
    assert contract["rerun_authorized"] is False

    for key in (
        "preflight_s3_requests_authorized",
        "preflight_requester_pays_authorized",
        "preflight_get_object_authorized",
        "preflight_list_objects_authorized",
        "preflight_head_object_authorized",
        "preflight_range_get_authorized",
        "preflight_object_body_download_authorized",
        "preflight_decompression_authorized",
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
        assert contract[key] is False, key
    assert all(value is False for value in contract["trading_authorizations"].values())
    assert contract["aws_sts_requests_executed"] == 0
    assert contract["s3_requests_executed"] == 0
    assert contract["object_bytes_downloaded"] == 0
    assert contract["empirical_result"] is None

    assert sha256(ATTESTATION_TEXT) == ATTESTATION_TEXT_SHA
    assert attestation["role_arn"] == ROLE_ARN
    assert attestation["operator_attested"] is True
    assert attestation["sts_only_preflight_required"] is True
    assert attestation["sts_only_preflight_completed"] is False
    assert attestation["execution_release_present"] is False
    assert attestation["canonical_activation_present"] is False

    assert sha256(TRUST) == TRUST_SHA
    conditions = trust["Statement"][0]["Condition"]["StringEquals"]
    assert conditions["token.actions.githubusercontent.com:workflow"] == WORKFLOW_NAME
    assert conditions["token.actions.githubusercontent.com:ref"] == "refs/heads/main"

    assert CANDIDATE.is_file()
    assert PREFLIGHT_WORKFLOW.is_file()
    assert sha256(CANDIDATE) == WORKFLOW_SHA
    assert sha256(PREFLIGHT_WORKFLOW) == WORKFLOW_SHA
    assert CANDIDATE.read_bytes() == PREFLIGHT_WORKFLOW.read_bytes()
    text = PREFLIGHT_WORKFLOW.read_text(encoding="utf-8")
    assert text.startswith(f"name: {WORKFLOW_NAME}\n")
    assert "run-name: R10 dedicated role STS-only preflight" in text
    assert "workflow_dispatch:" in text
    assert "id-token: write" in text
    assert "actions: read" in text
    assert "persist-credentials: false" in text
    assert "role-duration-seconds: 900" in text
    assert "retry-max-attempts: 1" in text
    assert "action-timeout-s: 60" in text
    assert "DenyAllS3DuringR10Preflight" in text
    assert '"Effect":"Deny","Action":"s3:*","Resource":"*"' in text
    assert text.count("aws sts get-caller-identity --output json") == 1
    assert "aws s3" not in text
    assert "aws s3api" not in text
    assert "collector.py" not in text
    assert "R10_STS_PREFLIGHT_RELEASE.json" in text
    assert text.index("test -f") < text.index("aws-actions/configure-aws-credentials")

    assert not DATA_WORKFLOW.exists()
    if RUNTIME.exists():
        assert RELEASE_CANDIDATE.is_file()
        release_candidate = load(RELEASE_CANDIDATE)
        release = load(RUNTIME_RELEASE)
        assert release_candidate["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
        assert release_candidate["canonical_activation_present"] is False
        assert release_candidate["single_workflow_dispatch_authorized"] is False
        assert release["status"] == "RELEASED_FOR_EXACTLY_ONE_R10_STS_ONLY_PREFLIGHT"
        assert release["release_candidate_merge_commit"] == RELEASE_CANDIDATE_MERGE
        assert release["role_arn"] == ROLE_ARN
        assert release["single_workflow_dispatch_authorized"] is True
        assert release["rerun_authorized"] is False
        assert release["release_consumed"] is False
        assert release["sts_get_caller_identity_authorized"] is True
        assert release["s3_access_authorized_during_preflight"] is False
        assert release["aws_sts_requests_executed"] == 0
        assert release["s3_requests_executed"] == 0
        assert sorted(path.name for path in RUNTIME.iterdir() if path.is_file()) == ["R10_STS_PREFLIGHT_RELEASE.json"]

    print("R10_ROLE_STS_PREFLIGHT_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
