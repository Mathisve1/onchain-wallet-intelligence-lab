from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREFLIGHT = BASE / "r11_role_preflight"
CANDIDATE = PREFLIGHT / "R11_STS_PREFLIGHT_RELEASE_CANDIDATE.json"
CONTRACT = PREFLIGHT / "R11_STS_PREFLIGHT_CONTRACT.json"
ATTESTATION = BASE / "r11_role_attestation/R11_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11-role-preflight.yml"
DATA_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11-72h-persistence.yml"
RUNTIME_RELEASE = BASE / "r11_runtime/R11_STS_PREFLIGHT_RELEASE.json"

PREFLIGHT_IMPLEMENTATION_MERGE = "910efc2045cb5f8231c16d4d879a8baf00a08952"
ROLE_ATTESTATION_MERGE = "38156c94a15aaef277a9bd8cf31c3a4808be1147"
R11_IMPLEMENTATION_MERGE = "9568424524a2a9f78e75bf0f68b4de6146f6f2b7"
R11_APPROVAL_MERGE = "86333a6759a492e5452bc565802fefce55a9fd6f"
ATTESTATION_TEXT_SHA = "b064e73e0368e4159bb08591893c8bb37340f662e0cdaad778d8684acb977810"
TRUST_SHA = "2df95bdfe662596334c46c641cc6e973b4fb4ef9361f122e53c23f129669b4ae"
PERMISSION_SHA = "2b64ad33c6ed6348af110117a24c0c834fe8b08b26aecba6e32384b09628abee"
WORKFLOW_BLOB_SHA = "eca98a08e3008d68c7c19845b1af1acb89fd3932"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-scaling-r11"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def main() -> int:
    c = load(CANDIDATE)
    contract = load(CONTRACT)
    att = load(ATTESTATION)

    assert c["preflight_release_candidate_id"] == "CANDIDATE_RELEASE_HL_ARCHIVE_R11_ROLE_STS_PREFLIGHT_001"
    assert c["preflight_id"] == "HL-ARCHIVE-R11-DEDICATED-ROLE-STS-PREFLIGHT-001"
    assert c["pilot_id"] == "HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001"
    assert c["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert c["preflight_implementation_merge_commit"] == PREFLIGHT_IMPLEMENTATION_MERGE
    assert c["role_attestation_merge_commit"] == ROLE_ATTESTATION_MERGE
    assert c["r11_implementation_merge_commit"] == R11_IMPLEMENTATION_MERGE
    assert c["r11_approval_merge_commit"] == R11_APPROVAL_MERGE
    assert c["operator_attestation_text_sha256"] == ATTESTATION_TEXT_SHA
    assert c["trust_policy_sha256"] == TRUST_SHA
    assert c["permission_policy_sha256"] == PERMISSION_SHA
    assert c["workflow_git_blob_sha"] == WORKFLOW_BLOB_SHA
    assert c["role_arn"] == ROLE_ARN
    assert c["expected_account_id"] == "630956766927"
    assert c["workflow_name"] == "Hyperliquid Archive 72H Persistence Scaling R11"
    assert c["workflow_path"] == ".github/workflows/hyperliquid-archive-r11-role-preflight.yml"
    assert c["future_runtime_release_path"] == "research/archive_inventory/r11_runtime/R11_STS_PREFLIGHT_RELEASE.json"
    assert c["github_event_required"] == "workflow_dispatch"
    assert c["canonical_dispatch_ref_required"] == "refs/heads/main"
    assert c["role_session_name"] == "HLArchiveR11STSPreflight"
    assert c["role_duration_seconds"] == 7200
    assert c["configure_aws_retry_max_attempts"] == 1
    assert c["configure_aws_action_timeout_seconds"] == 60
    assert c["inline_session_policy"] == "DENY_ALL_S3_ON_ALL_RESOURCES"
    assert c["future_explicit_aws_cli_commands"] == ["aws sts get-caller-identity --output json"]
    assert c["future_maximum_explicit_aws_cli_calls"] == 1
    assert c["canonical_activation_required"] is True
    assert c["canonical_activation_present"] is False
    assert c["single_use_window_start_utc"] is None and c["anchor_commit"] is None
    assert c["single_workflow_dispatch_authorized"] is False
    assert c["rerun_authorized"] is False
    assert c["sts_get_caller_identity_authorized"] is False
    assert c["release_consumed"] is False
    assert c["operator_attestation_reviewed"] is True

    for key in (
        "s3_access_authorized_during_preflight", "requester_pays_authorized", "get_object_authorized",
        "list_objects_authorized", "head_object_authorized", "range_get_authorized",
        "object_body_download_authorized", "decompression_authorized", "raw_oidc_token_retention_authorized",
        "aws_credentials_retention_authorized", "raw_caller_identity_retention_authorized",
        "data_workflow_installation_authorized", "historical_window_beyond_three_days_authorized",
        "full_population_historical_ingestion_authorized", "public_api_enrichment_authorized",
        "entity_clustering_authorized", "wallet_ranking_authorized", "candidate_shortlisting_authorized",
        "pnl_or_alpha_analysis_authorized", "copyability_analysis_authorized", "market_data_ingestion_authorized",
        "strategy_inference_authorized",
    ):
        assert c[key] is False, key
    assert all(v is False for v in c["trading_authorizations"].values())
    assert c["aws_sts_requests_executed"] == 0
    assert c["s3_requests_executed"] == 0
    assert c["object_bytes_downloaded"] == 0
    assert c["empirical_result"] is None

    assert contract["status"] == "IMPLEMENTED_AWAITING_SEPARATE_PREFLIGHT_RELEASE"
    assert contract["preflight_release_present"] is False
    assert contract["preflight_execution_authorized"] is False
    assert contract["sts_get_caller_identity_authorized"] is False
    assert contract["s3_requests_executed"] == 0
    assert att["operator_attested"] is True
    assert att["sts_only_preflight_completed"] is False
    assert att["execution_release_present"] is False

    assert WORKFLOW.is_file()
    assert git_blob_sha(WORKFLOW) == WORKFLOW_BLOB_SHA
    text = WORKFLOW.read_text(encoding="utf-8")
    assert '"Effect":"Deny","Action":"s3:*","Resource":"*"' in text
    assert text.count("aws sts get-caller-identity --output json") == 1
    assert not DATA_WORKFLOW.exists()
    assert not RUNTIME_RELEASE.exists()

    print("R11_STS_PREFLIGHT_RELEASE_CANDIDATE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
