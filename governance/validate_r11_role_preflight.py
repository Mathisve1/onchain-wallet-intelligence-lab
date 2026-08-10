from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CONTRACT = BASE / "r11_role_preflight/R11_STS_PREFLIGHT_CONTRACT.json"
ATTESTATION = BASE / "r11_role_attestation/R11_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
ATTESTATION_TEXT = BASE / "r11_role_attestation/R11_DEDICATED_ROLE_OPERATOR_ATTESTATION.txt"
TRUST = BASE / "r11_implementation/R11_OIDC_TRUST_POLICY.json"
PERMISSION = BASE / "r11_implementation/R11_PERMISSION_POLICY.json"
CANDIDATE = BASE / "r11_implementation/workflows/hyperliquid-archive-r11-role-preflight.yml"
PREFLIGHT_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11-role-preflight.yml"
DATA_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11-72h-persistence.yml"
RUNTIME = BASE / "r11_runtime"
RUNTIME_RELEASE = RUNTIME / "R11_STS_PREFLIGHT_RELEASE.json"
RELEASE_CANDIDATE = BASE / "r11_role_preflight/R11_STS_PREFLIGHT_RELEASE_CANDIDATE.json"

ROLE_ATTESTATION_MERGE = "38156c94a15aaef277a9bd8cf31c3a4808be1147"
R11_IMPLEMENTATION_MERGE = "9568424524a2a9f78e75bf0f68b4de6146f6f2b7"
ATTESTATION_TEXT_SHA = "b064e73e0368e4159bb08591893c8bb37340f662e0cdaad778d8684acb977810"
TRUST_SHA = "2df95bdfe662596334c46c641cc6e973b4fb4ef9361f122e53c23f129669b4ae"
PERMISSION_SHA = "2b64ad33c6ed6348af110117a24c0c834fe8b08b26aecba6e32384b09628abee"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-scaling-r11"
WORKFLOW_NAME = "Hyperliquid Archive 72H Persistence Scaling R11"


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
    permission = load(PERMISSION)

    assert contract["preflight_id"] == "HL-ARCHIVE-R11-DEDICATED-ROLE-STS-PREFLIGHT-001"
    assert contract["pilot_id"] == "HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001"
    assert contract["status"] == "IMPLEMENTED_AWAITING_SEPARATE_PREFLIGHT_RELEASE"
    assert contract["role_attestation_merge_commit"] == ROLE_ATTESTATION_MERGE
    assert contract["r11_implementation_merge_commit"] == R11_IMPLEMENTATION_MERGE
    assert contract["operator_attestation_text_sha256"] == ATTESTATION_TEXT_SHA
    assert contract["trust_policy_sha256"] == TRUST_SHA
    assert contract["permission_policy_sha256"] == PERMISSION_SHA
    assert contract["role_arn"] == ROLE_ARN
    assert contract["expected_account_id"] == "630956766927"
    assert contract["workflow_name"] == WORKFLOW_NAME
    assert contract["workflow_path"] == ".github/workflows/hyperliquid-archive-r11-role-preflight.yml"
    assert contract["frozen_workflow_candidate_path"] == "research/archive_inventory/r11_implementation/workflows/hyperliquid-archive-r11-role-preflight.yml"
    assert contract["frozen_workflow_candidate_git_blob_sha"] == "eca98a08e3008d68c7c19845b1af1acb89fd3932"
    assert contract["installed_workflow_git_blob_sha"] == "eca98a08e3008d68c7c19845b1af1acb89fd3932"
    assert contract["github_event_required"] == "workflow_dispatch"
    assert contract["canonical_dispatch_ref_required"] == "refs/heads/main"
    assert contract["canonical_dispatch_sha_source"] == "github.sha"
    assert contract["role_session_name"] == "HLArchiveR11STSPreflight"
    assert contract["role_duration_seconds"] == 7200
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
        "preflight_s3_requests_authorized", "preflight_requester_pays_authorized", "preflight_get_object_authorized",
        "preflight_list_objects_authorized", "preflight_head_object_authorized", "preflight_range_get_authorized",
        "preflight_object_body_download_authorized", "preflight_decompression_authorized",
        "raw_oidc_token_retention_authorized", "aws_credentials_retention_authorized",
        "raw_caller_identity_retention_authorized", "data_workflow_installation_authorized",
        "historical_window_beyond_three_days_authorized", "full_population_historical_ingestion_authorized",
        "public_api_enrichment_authorized", "entity_clustering_authorized", "wallet_ranking_authorized",
        "candidate_shortlisting_authorized", "pnl_or_alpha_analysis_authorized", "copyability_analysis_authorized",
        "market_data_ingestion_authorized", "strategy_inference_authorized",
    ):
        assert contract[key] is False, key
    assert all(v is False for v in contract["trading_authorizations"].values())
    assert contract["aws_sts_requests_executed"] == 0
    assert contract["s3_requests_executed"] == 0
    assert contract["object_bytes_downloaded"] == 0
    assert contract["empirical_result"] is None

    assert sha256(ATTESTATION_TEXT) == ATTESTATION_TEXT_SHA
    assert attestation["canonical_implementation_merge_commit"] == R11_IMPLEMENTATION_MERGE
    assert attestation["role_arn"] == ROLE_ARN
    assert attestation["operator_attested"] is True
    assert attestation["persistent_permission_resource_count"] == 72
    assert attestation["additional_managed_policies_attached"] is False
    assert attestation["additional_inline_policies_attached"] is False
    assert attestation["sts_only_preflight_required"] is True
    assert attestation["sts_only_preflight_completed"] is False
    assert attestation["execution_release_present"] is False
    assert attestation["canonical_activation_present"] is False

    assert sha256(TRUST) == TRUST_SHA
    assert sha256(PERMISSION) == PERMISSION_SHA
    conditions = trust["Statement"][0]["Condition"]["StringEquals"]
    assert conditions["token.actions.githubusercontent.com:workflow"] == WORKFLOW_NAME
    assert conditions["token.actions.githubusercontent.com:ref"] == "refs/heads/main"
    resources = permission["Statement"][0]["Resource"]
    assert len(resources) == len(set(resources)) == 72
    assert all("*" not in arn for arn in resources)

    assert CANDIDATE.is_file() and PREFLIGHT_WORKFLOW.is_file()
    assert CANDIDATE.read_bytes() == PREFLIGHT_WORKFLOW.read_bytes()
    text = PREFLIGHT_WORKFLOW.read_text(encoding="utf-8")
    assert text.startswith(f"name: {WORKFLOW_NAME}\n")
    assert "run-name: R11 dedicated role STS-only preflight" in text
    assert "workflow_dispatch:" in text
    assert "id-token: write" in text and "actions: read" in text
    assert "persist-credentials: false" in text
    assert f"role-to-assume: {ROLE_ARN}" in text
    assert "role-duration-seconds: 7200" in text
    assert "retry-max-attempts: 1" in text and "action-timeout-s: 60" in text
    assert "DenyAllS3DuringR11Preflight" in text
    assert '"Effect":"Deny","Action":"s3:*","Resource":"*"' in text
    assert text.count("aws sts get-caller-identity --output json") == 1
    assert "aws s3 " not in text.lower() and "aws s3api " not in text.lower()
    assert "research.archive_inventory.r11_implementation.collector" not in text
    assert "R11_STS_PREFLIGHT_RELEASE.json" in text
    assert text.index("test -f") < text.index("aws-actions/configure-aws-credentials")

    assert not DATA_WORKFLOW.exists(), "R11 data workflow must remain uninstalled before successful STS preflight evidence"

    if RUNTIME_RELEASE.exists():
        release = load(RUNTIME_RELEASE)
        assert RELEASE_CANDIDATE.is_file()
        candidate = load(RELEASE_CANDIDATE)
        assert candidate["status"] == "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION"
        assert candidate["canonical_activation_present"] is False
        assert candidate["single_workflow_dispatch_authorized"] is False
        assert release["status"] == "RELEASED_FOR_EXACTLY_ONE_R11_STS_ONLY_PREFLIGHT"
        assert release["role_arn"] == ROLE_ARN
        assert release["single_workflow_dispatch_authorized"] is True
        assert release["rerun_authorized"] is False
        assert release["release_consumed"] is False
        assert release["sts_get_caller_identity_authorized"] is True
        assert release["s3_access_authorized_during_preflight"] is False
        assert release["aws_sts_requests_executed"] == 0
        assert release["s3_requests_executed"] == 0

    print("R11_ROLE_STS_PREFLIGHT_IMPLEMENTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
