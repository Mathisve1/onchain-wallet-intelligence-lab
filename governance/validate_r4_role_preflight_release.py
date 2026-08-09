from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4"
CONTRACT = BASE / "role_attestation/R4_ROLE_STS_PREFLIGHT_CONTRACT.json"
ATTESTATION = BASE / "role_attestation/R4_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
ANCHOR = BASE / "role_attestation/R4_ROLE_STS_PREFLIGHT_RELEASE_ANCHOR.json"
RELEASE = BASE / "role_attestation/R4_ROLE_STS_PREFLIGHT_RELEASE.json"
BODY_RELEASE = BASE / "R4_EXECUTION_RELEASE.json"
BODY_ACTIVATION = BASE / "R4_EXECUTION_RELEASE_CANONICALIZATION.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-hourly-body-schema-role-preflight-r4.yml"

IMPLEMENTATION = "3b0a1ae634288646f3757493d4e90258bae21421"
ATTESTATION_MERGE = "c45527941dea7d152e332327ebd0593dc2413bea"
ANCHOR_COMMIT = "1c01ee6275b4c3ca1afd89385c5c740e99cbc362"
ANCHOR_TIME = "2026-08-09T10:36:28Z"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    contract = load(CONTRACT)
    attestation = load(ATTESTATION)
    anchor = load(ANCHOR)
    release = load(RELEASE)
    body = load(BODY_RELEASE)

    assert contract["preflight_id"] == release["preflight_id"]
    assert contract["role_attestation_merge_commit"] == ATTESTATION_MERGE
    assert contract["preflight_release_required"] is True
    assert contract["preflight_execution_authorized"] is False
    assert attestation["operator_attested"] is True
    assert attestation["independently_verified"] is False
    assert attestation["sts_only_preflight_completed"] is False

    assert anchor["anchor_id"] == "HL-ARCHIVE-R4-ROLE-STS-PREFLIGHT-RELEASE-ANCHOR-001"
    assert anchor["preflight_implementation_merge_commit"] == IMPLEMENTATION
    assert anchor["role_attestation_merge_commit"] == ATTESTATION_MERGE
    assert anchor["execution_authorized_by_this_file"] is False
    assert anchor["single_workflow_dispatch_authorized"] is False
    assert anchor["sts_get_caller_identity_authorized"] is False
    assert anchor["s3_requests_authorized"] is False
    assert anchor["requests_executed"] == 0
    assert anchor["empirical_result"] is None

    assert release["preflight_release_id"] == "RELEASE_HL_ARCHIVE_R4_ROLE_STS_PREFLIGHT_001"
    assert release["status"] == "RELEASED_FOR_EXACTLY_ONE_CANONICAL_STS_PREFLIGHT"
    assert release["preflight_implementation_commit"] == IMPLEMENTATION
    assert release["role_attestation_merge_commit"] == ATTESTATION_MERGE
    assert release["release_candidate_merge_commit"] == "01521d1cad209263a217dbcca98ecd74ec16857c"
    assert release["operator_attestation_text_sha256"] == attestation["exact_attestation_text_sha256"]
    assert release["role_arn"] == ROLE_ARN
    assert release["expected_account_id"] == "630956766927"
    assert release["github_event_required"] == "workflow_dispatch"
    assert release["canonical_dispatch_ref_required"] == "refs/heads/main"
    assert release["workflow_path"] == ".github/workflows/hyperliquid-archive-hourly-body-schema-role-preflight-r4.yml"
    assert release["anchor_commit"] == ANCHOR_COMMIT
    assert release["single_use_window_start_utc"] == ANCHOR_TIME
    assert release["single_workflow_dispatch_authorized"] is True
    assert release["rerun_authorized"] is False
    assert release["role_session_name"] == "HLArchiveR4RolePreflight"
    assert release["role_duration_seconds"] == 900
    assert release["configure_aws_retry_max_attempts"] == 1
    assert release["configure_aws_action_timeout_seconds"] == 60
    assert release["inline_session_policy"] == "DENY_ALL_S3_ON_ALL_RESOURCES"
    assert release["sts_get_caller_identity_authorized"] is True
    assert release["maximum_explicit_aws_cli_calls"] == 1

    for key in (
        "s3_requests_authorized", "requester_pays_authorized", "get_object_authorized",
        "list_objects_authorized", "head_object_authorized", "range_get_authorized",
        "object_body_download_authorized", "decompression_authorized",
        "raw_oidc_token_retention_authorized", "aws_credentials_retention_authorized",
        "raw_caller_identity_retention_authorized", "body_release_consumed_by_preflight",
        "body_execution_activation_authorized", "wallet_reconstruction_authorized",
        "entity_clustering_authorized", "copyability_analysis_authorized",
        "pnl_or_alpha_analysis_authorized", "market_data_ingestion_authorized",
    ):
        assert release[key] is False, key
    assert all(value is False for value in release["trading_authorizations"].values())
    assert release["s3_requests_executed"] == 0
    assert release["object_bytes_downloaded"] == 0
    assert release["empirical_result"] is None

    assert body["single_workflow_dispatch_authorized"] is False
    assert body["get_object_authorized"] is False
    assert body["execution_ready"] is False
    assert not BODY_ACTIVATION.exists()

    text = WORKFLOW.read_text(encoding="utf-8")
    assert f"EXPECTED_PREFLIGHT_IMPLEMENTATION_COMMIT: {IMPLEMENTATION}" in text
    assert "DenyAllS3DuringR4RolePreflight" in text
    assert '"Action":"s3:*"' in text
    assert text.count("aws sts get-caller-identity --output json") == 1
    assert "aws s3" not in text
    assert "research/archive_inventory/r4/collector.py" not in text

    print("R4_ROLE_STS_PREFLIGHT_RELEASE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
