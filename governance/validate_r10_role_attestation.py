from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
ATTEST_DIR = BASE / "r10_role_attestation"
IMPL_DIR = BASE / "r10_implementation"
PREFLIGHT_DIR = BASE / "r10_role_preflight"

TEXT = ATTEST_DIR / "R10_DEDICATED_ROLE_OPERATOR_ATTESTATION.txt"
ATTESTATION = ATTEST_DIR / "R10_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
EVIDENCE = ATTEST_DIR / "R10_ROLE_CREATION_EVIDENCE_MINIMIZED.json"
TRUST = IMPL_DIR / "R10_OIDC_TRUST_POLICY.json"
PERMISSION = IMPL_DIR / "R10_PERMISSION_POLICY.json"
IMPLEMENTATION = IMPL_DIR / "R10_IMPLEMENTATION_CONTRACT.json"
PREFLIGHT_CONTRACT = PREFLIGHT_DIR / "R10_STS_PREFLIGHT_CONTRACT.json"
PREFLIGHT_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-role-preflight-r10.yml"
DATA_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml"

EXPECTED_TEXT_SHA = "aa6547983d197941b7ffe90811a77665a7924a8a29fb89955d2f31456cd9c8cd"
EXPECTED_TRUST_SHA = "2709fe66f6361d6498e07bdd2f292576c73485772af6d3cabb89a211e46bdcb9"
EXPECTED_PERMISSION_SHA = "caab807fb0fbc2f1d2132921a99692f5d3533db8449d9a55e4da0714147177fe"
EXPECTED_ROLE_NAME = "onchain-wallet-intelligence-hl-archive-multihour-r10"
EXPECTED_ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
EXPECTED_INLINE_POLICY = "HLArchivePostBoundaryMultiHourR10ExactSixOnly"
ROLE_ATTESTATION_MERGE = "ba7835c8e8ecb1cdc6a1c44c9b679d8f43e7a40e"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    a = json.loads(ATTESTATION.read_text(encoding="utf-8"))
    e = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    impl = json.loads(IMPLEMENTATION.read_text(encoding="utf-8"))

    assert sha256(TEXT) == EXPECTED_TEXT_SHA
    assert sha256(TRUST) == EXPECTED_TRUST_SHA
    assert sha256(PERMISSION) == EXPECTED_PERMISSION_SHA

    assert a["attestation_id"] == "R10_DEDICATED_ROLE_OPERATOR_ATTESTATION"
    assert a["recorded_against_main_commit"] == "c2e4e262d74bcf9feebb531d507590d5f9e62c85"
    assert a["canonical_implementation_merge_commit"] == "820d0cbbb0f49f800f36025da27a06754d3fc08d"
    assert a["session_duration_repair_merge_commit"] == "c2e4e262d74bcf9feebb531d507590d5f9e62c85"
    assert a["exact_attestation_text_sha256"] == EXPECTED_TEXT_SHA
    assert a["role_name"] == EXPECTED_ROLE_NAME
    assert a["role_arn"] == EXPECTED_ROLE_ARN
    assert a["inline_policy_name"] == EXPECTED_INLINE_POLICY
    assert a["trust_policy_sha256"] == EXPECTED_TRUST_SHA
    assert a["permission_policy_sha256"] == EXPECTED_PERMISSION_SHA
    assert a["role_max_session_duration_seconds"] == 3600
    assert a["future_workflow_role_duration_seconds"] == 900
    assert a["role_created_and_policies_applied"] is True
    assert a["installed_trust_policy_matches_canonical"] is True
    assert a["installed_permission_policy_matches_canonical"] is True
    assert a["additional_managed_policies_attached"] is False
    assert a["additional_inline_policies_attached"] is False
    assert a["existing_r4_role_modified"] is False
    assert a["operator_attested"] is True
    assert a["independently_verified_via_r10_sts_preflight"] is False
    assert a["sts_only_preflight_required"] is True
    assert a["sts_only_preflight_completed"] is False
    assert a["s3_requests_executed_by_role_creation_step"] == 0
    assert a["execution_release_present"] is False
    assert a["canonical_activation_present"] is False
    for key in (
        "wallet_ranking_authorized",
        "pnl_or_alpha_analysis_authorized",
        "copyability_analysis_authorized",
        "integration_authorized",
        "paper_authorized",
        "shadow_authorized",
        "live_authorized",
        "leverage_authorized",
        "capital_allocation_authorized",
    ):
        assert a[key] is False
    assert a["empirical_result"] is None

    assert e["evidence_id"] == "R10_ROLE_CREATION_EVIDENCE_MINIMIZED"
    assert e["aws_account_id"] == "630956766927"
    assert e["role_absent_before_creation"] is True
    assert e["role_name"] == EXPECTED_ROLE_NAME
    assert e["role_arn"] == EXPECTED_ROLE_ARN
    assert e["role_max_session_duration_seconds"] == 3600
    assert e["trust_policy_sha256_verified_before_creation"] == EXPECTED_TRUST_SHA
    assert e["permission_policy_sha256_verified_before_application"] == EXPECTED_PERMISSION_SHA
    assert e["trust_policy_readback_semantically_matches_canonical"] is True
    assert e["permission_policy_readback_semantically_matches_canonical"] is True
    assert e["inline_policy_names_observed"] == [EXPECTED_INLINE_POLICY]
    assert e["managed_policies_observed"] == []
    assert e["additional_inline_policies_observed"] == []
    assert e["s3_requests_observed_during_role_creation"] == 0
    assert e["administrative_sts_identity_check_is_not_r10_preflight"] is True
    assert e["r10_sts_preflight_executed"] is False
    assert e["r10_execution_release_present"] is False
    assert e["r10_canonical_activation_present"] is False
    assert e["raw_cli_transcript_retained"] is False
    assert e["aws_credentials_or_session_tokens_retained"] is False

    # The immutable implementation snapshot keeps its original zero-runtime fields.
    assert impl["role_creation_performed"] is False
    assert impl["role_attestation_present"] is False
    assert impl["sts_preflight_release_present"] is False
    assert impl["sts_preflight_completed"] is False
    assert impl["execution_release_present"] is False
    assert impl["canonical_activation_present"] is False
    assert all(v is False for v in impl["current_runtime_authority"].values())
    assert all(v is False for v in impl["downstream_authorizations"].values())
    assert all(v is False for v in impl["trading_authorizations"].values())
    assert impl["s3_requests_executed"] == 0
    assert impl["aws_sts_requests_executed"] == 0
    assert impl["wallet_feature_rows_created"] == 0
    assert impl["empirical_result"] is None

    # A later, separately reviewed STS-only preflight implementation may install
    # only the preflight workflow. The attestation itself remains unchanged/inert.
    if PREFLIGHT_CONTRACT.exists():
        preflight = json.loads(PREFLIGHT_CONTRACT.read_text(encoding="utf-8"))
        assert preflight["status"] == "IMPLEMENTED_AWAITING_SEPARATE_PREFLIGHT_RELEASE"
        assert preflight["role_attestation_merge_commit"] == ROLE_ATTESTATION_MERGE
        assert preflight["role_arn"] == EXPECTED_ROLE_ARN
        assert preflight["preflight_release_present"] is False
        assert preflight["preflight_execution_authorized"] is False
        assert preflight["sts_get_caller_identity_authorized"] is False
        assert preflight["s3_requests_executed"] == 0
        assert PREFLIGHT_WORKFLOW.is_file()
    else:
        assert not PREFLIGHT_WORKFLOW.exists()
    assert DATA_WORKFLOW.is_file()

    print("R10_ROLE_OPERATOR_ATTESTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
