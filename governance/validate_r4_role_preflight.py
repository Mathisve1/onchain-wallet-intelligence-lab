from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4"
CONTRACT = BASE / "role_attestation/R4_ROLE_STS_PREFLIGHT_CONTRACT.json"
ATTESTATION = BASE / "role_attestation/R4_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
RELEASE_CANDIDATE = BASE / "R4_EXECUTION_RELEASE.json"
BODY_ACTIVATION = BASE / "R4_EXECUTION_RELEASE_CANONICALIZATION.json"
PREFLIGHT_RELEASE = BASE / "role_attestation/R4_ROLE_STS_PREFLIGHT_RELEASE.json"
BODY_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-hourly-body-schema-pilot-r4.yml"
PREFLIGHT_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-hourly-body-schema-role-preflight-r4.yml"

ROLE_ATTESTATION_MERGE = "c45527941dea7d152e332327ebd0593dc2413bea"
BODY_WORKFLOW_SHA256 = "2499424483179f05472d951c3f9def2c791f156cd7cf36d465e93d4ab9d19677"
WORKFLOW_NAME = "Hyperliquid Archive Hourly Body Schema Pilot R4"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    contract = load(CONTRACT)
    attestation = load(ATTESTATION)
    body_release = load(RELEASE_CANDIDATE)

    assert contract["preflight_id"] == "HL-ARCHIVE-R4-DEDICATED-ROLE-STS-PREFLIGHT-001"
    assert contract["status"] == "IMPLEMENTED_AWAITING_SEPARATE_PREFLIGHT_RELEASE"
    assert contract["role_attestation_merge_commit"] == ROLE_ATTESTATION_MERGE
    assert contract["release_candidate_merge_commit"] == "01521d1cad209263a217dbcca98ecd74ec16857c"
    assert contract["r4_implementation_commit"] == "180c89ead78f9a6f4560a1ec12575658e62586ee"
    assert contract["operator_attestation_text_sha256"] == attestation["exact_attestation_text_sha256"]
    assert contract["role_arn"] == ROLE_ARN
    assert contract["expected_account_id"] == "630956766927"
    assert contract["workflow_name"] == WORKFLOW_NAME
    assert contract["github_event_required"] == "workflow_dispatch"
    assert contract["canonical_dispatch_ref_required"] == "refs/heads/main"
    assert contract["role_session_name"] == "HLArchiveR4RolePreflight"
    assert contract["role_duration_seconds"] == 900
    assert contract["configure_aws_retry_max_attempts"] == 1
    assert contract["configure_aws_action_timeout_seconds"] == 60
    assert contract["inline_session_policy"] == "DENY_ALL_S3_ON_ALL_RESOURCES"
    assert contract["explicit_aws_cli_commands"] == ["aws sts get-caller-identity --output json"]
    assert contract["maximum_explicit_aws_cli_calls"] == 1
    assert contract["preflight_release_required"] is True
    assert contract["preflight_release_present"] is False
    assert contract["preflight_execution_authorized"] is False

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
        "r4_body_release_consumed_by_preflight",
        "r4_body_execution_activation_authorized",
        "wallet_reconstruction_authorized",
        "entity_clustering_authorized",
        "copyability_analysis_authorized",
        "pnl_or_alpha_analysis_authorized",
        "market_data_ingestion_authorized",
    ):
        assert contract[key] is False, key
    assert all(value is False for value in contract["trading_authorizations"].values())
    assert contract["s3_requests_executed"] == 0
    assert contract["object_bytes_downloaded"] == 0
    assert contract["empirical_result"] is None

    assert attestation["operator_attested"] is True
    assert attestation["independently_verified"] is False
    assert attestation["sts_only_preflight_completed"] is False
    assert attestation["r4_execution_ready"] is False

    assert body_release["status"] == "RELEASE_CANDIDATE_AWAITING_DEDICATED_R4_ROLE_ATTESTATION"
    assert body_release["single_workflow_dispatch_authorized"] is False
    assert body_release["get_object_authorized"] is False
    assert body_release["execution_ready"] is False
    assert not BODY_ACTIVATION.exists()

    if PREFLIGHT_RELEASE.exists():
        later = load(PREFLIGHT_RELEASE)
        assert later["preflight_release_id"] == "RELEASE_HL_ARCHIVE_R4_ROLE_STS_PREFLIGHT_001"
        assert later["role_attestation_merge_commit"] == ROLE_ATTESTATION_MERGE
        assert later["role_arn"] == ROLE_ARN
        assert later["s3_requests_authorized"] is False
        assert later["object_body_download_authorized"] is False
        assert later["body_release_consumed_by_preflight"] is False
        assert later["body_execution_activation_authorized"] is False

    assert hashlib.sha256(BODY_WORKFLOW.read_bytes()).hexdigest() == BODY_WORKFLOW_SHA256
    text = PREFLIGHT_WORKFLOW.read_text(encoding="utf-8")
    assert text.startswith(f"name: {WORKFLOW_NAME}\n")
    assert "run-name: R4 dedicated role STS-only preflight" in text
    assert "DenyAllS3DuringR4RolePreflight" in text
    assert '"Action":"s3:*"' in text
    assert '"Effect":"Deny"' in text
    assert text.count("aws sts get-caller-identity --output json") == 1
    assert "aws s3" not in text
    assert "research/archive_inventory/r4/collector.py" not in text
    assert "node_fills/hourly/20250727/8.lz4" not in text
    assert "node_fills_by_block/hourly/20250727/8.lz4" not in text

    print("R4_ROLE_STS_PREFLIGHT_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
