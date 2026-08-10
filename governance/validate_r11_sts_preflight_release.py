from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RELEASE = BASE / "r11_runtime/R11_STS_PREFLIGHT_RELEASE.json"
CANDIDATE = BASE / "r11_role_preflight/R11_STS_PREFLIGHT_RELEASE_CANDIDATE.json"
CONTRACT = BASE / "r11_role_preflight/R11_STS_PREFLIGHT_CONTRACT.json"
ATTESTATION = BASE / "r11_role_attestation/R11_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11-role-preflight.yml"
DATA_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11-72h-persistence.yml"
FROZEN_DATA_WORKFLOW = BASE / "r11_implementation/workflows/hyperliquid-archive-r11-72h-persistence.yml"
DATA_CONTRACT = BASE / "r11_data_execution/R11_DATA_WORKFLOW_IMPLEMENTATION_CONTRACT.json"

RELEASE_CANDIDATE_MERGE = "3d41425c5c1663b1730fb960948e4971b9c1be8a"
PREFLIGHT_IMPLEMENTATION_MERGE = "910efc2045cb5f8231c16d4d879a8baf00a08952"
ROLE_ATTESTATION_MERGE = "38156c94a15aaef277a9bd8cf31c3a4808be1147"
R11_IMPLEMENTATION_MERGE = "9568424524a2a9f78e75bf0f68b4de6146f6f2b7"
R11_APPROVAL_MERGE = "86333a6759a492e5452bc565802fefce55a9fd6f"
ATTESTATION_TEXT_SHA = "b064e73e0368e4159bb08591893c8bb37340f662e0cdaad778d8684acb977810"
TRUST_SHA = "2df95bdfe662596334c46c641cc6e973b4fb4ef9361f122e53c23f129669b4ae"
PERMISSION_SHA = "2b64ad33c6ed6348af110117a24c0c834fe8b08b26aecba6e32384b09628abee"
WORKFLOW_BLOB_SHA = "eca98a08e3008d68c7c19845b1af1acb89fd3932"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-scaling-r11"
WINDOW_START = "2026-08-10T21:08:00Z"


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
    contract = load(CONTRACT)
    att = load(ATTESTATION)

    assert r["preflight_release_id"] == "RELEASE_HL_ARCHIVE_R11_ROLE_STS_PREFLIGHT_001"
    assert r["preflight_id"] == "HL-ARCHIVE-R11-DEDICATED-ROLE-STS-PREFLIGHT-001"
    assert r["pilot_id"] == "HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001"
    assert r["status"] == "RELEASED_FOR_EXACTLY_ONE_R11_STS_ONLY_PREFLIGHT"
    assert r["release_candidate_merge_commit"] == RELEASE_CANDIDATE_MERGE
    assert r["preflight_implementation_merge_commit"] == PREFLIGHT_IMPLEMENTATION_MERGE
    assert r["role_attestation_merge_commit"] == ROLE_ATTESTATION_MERGE
    assert r["r11_implementation_merge_commit"] == R11_IMPLEMENTATION_MERGE
    assert r["r11_approval_merge_commit"] == R11_APPROVAL_MERGE
    assert r["operator_attestation_text_sha256"] == ATTESTATION_TEXT_SHA
    assert r["trust_policy_sha256"] == TRUST_SHA
    assert r["permission_policy_sha256"] == PERMISSION_SHA
    assert r["workflow_git_blob_sha"] == WORKFLOW_BLOB_SHA
    assert r["role_arn"] == ROLE_ARN
    assert r["expected_account_id"] == "630956766927"
    assert r["workflow_name"] == "Hyperliquid Archive 72H Persistence Scaling R11"
    assert r["workflow_path"] == ".github/workflows/hyperliquid-archive-r11-role-preflight.yml"
    assert r["activation_base_commit"] == RELEASE_CANDIDATE_MERGE
    assert r["single_use_window_start_utc"] == WINDOW_START
    parsed = datetime.fromisoformat(WINDOW_START.replace("Z", "+00:00")).astimezone(timezone.utc)
    assert parsed.isoformat() == "2026-08-10T21:08:00+00:00"
    assert r["single_workflow_dispatch_authorized"] is True
    assert r["rerun_authorized"] is False
    assert r["release_consumed"] is False
    assert r["operator_attestation_reviewed"] is True
    assert r["sts_get_caller_identity_authorized"] is True
    assert r["maximum_explicit_aws_cli_calls"] == 1
    assert r["role_session_name"] == "HLArchiveR11STSPreflight"
    assert r["role_duration_seconds"] == 7200
    assert r["configure_aws_retry_max_attempts"] == 1
    assert r["configure_aws_action_timeout_seconds"] == 60
    assert r["inline_session_policy"] == "DENY_ALL_S3_ON_ALL_RESOURCES"

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
        assert r[key] is False, key
    assert all(v is False for v in r["trading_authorizations"].values())
    assert r["aws_sts_requests_executed"] == 0
    assert r["s3_requests_executed"] == 0
    assert r["object_bytes_downloaded"] == 0
    assert r["empirical_result"] is None

    assert c["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
    assert c["canonical_activation_present"] is False
    assert c["single_workflow_dispatch_authorized"] is False
    assert c["sts_get_caller_identity_authorized"] is False
    assert c["s3_access_authorized_during_preflight"] is False
    assert c["release_consumed"] is False
    assert c["aws_sts_requests_executed"] == 0 and c["s3_requests_executed"] == 0
    assert contract["status"] == "IMPLEMENTED_AWAITING_SEPARATE_PREFLIGHT_RELEASE"
    assert contract["preflight_release_present"] is False
    assert contract["preflight_execution_authorized"] is False
    assert contract["sts_get_caller_identity_authorized"] is False
    assert contract["aws_sts_requests_executed"] == 0 and contract["s3_requests_executed"] == 0
    assert att["operator_attested"] is True
    assert att["sts_only_preflight_completed"] is False

    assert git_blob_sha(WORKFLOW) == WORKFLOW_BLOB_SHA
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count("aws sts get-caller-identity --output json") == 1
    assert '"Effect":"Deny","Action":"s3:*","Resource":"*"' in text
    assert "aws s3 " not in text.lower() and "aws s3api " not in text.lower()

    # This immutable STS release never authorizes data. A later separately governed
    # post-preflight implementation may install the frozen data route while remaining inert.
    if DATA_CONTRACT.exists():
        data_contract = load(DATA_CONTRACT)
        assert data_contract["status"] == "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE"
        assert data_contract["r11_sts_preflight_evidence_merge_commit"] == "db935f6c44639ba2a2fa66d8c1b4d0d1d26b254a"
        assert data_contract["preflight_release_consumed"] is True
        assert data_contract["single_workflow_dispatch_authorized"] is False
        assert data_contract["aws_oidc_authorized_now"] is False
        assert data_contract["get_object_authorized_now"] is False
        assert DATA_WORKFLOW.is_file()
        assert FROZEN_DATA_WORKFLOW.is_file()
        assert DATA_WORKFLOW.read_bytes() == FROZEN_DATA_WORKFLOW.read_bytes()
    else:
        assert not DATA_WORKFLOW.exists()

    print("R11_STS_PREFLIGHT_RELEASE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
