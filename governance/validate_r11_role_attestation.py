from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
ATTEST_DIR = BASE / "r11_role_attestation"
IMPL_DIR = BASE / "r11_implementation"

TEXT = ATTEST_DIR / "R11_DEDICATED_ROLE_OPERATOR_ATTESTATION.txt"
ATTESTATION = ATTEST_DIR / "R11_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
EVIDENCE = ATTEST_DIR / "R11_ROLE_CREATION_EVIDENCE_MINIMIZED.json"
TRUST = IMPL_DIR / "R11_OIDC_TRUST_POLICY.json"
PERMISSION = IMPL_DIR / "R11_PERMISSION_POLICY.json"
IMPLEMENTATION = IMPL_DIR / "R11_IMPLEMENTATION_CONTRACT.json"
SELECTION = BASE / "r11/R11_72H_SELECTION.json"

EXPECTED_TEXT_SHA = "b064e73e0368e4159bb08591893c8bb37340f662e0cdaad778d8684acb977810"
EXPECTED_TRUST_SHA = "2df95bdfe662596334c46c641cc6e973b4fb4ef9361f122e53c23f129669b4ae"
EXPECTED_PERMISSION_SHA = "2b64ad33c6ed6348af110117a24c0c834fe8b08b26aecba6e32384b09628abee"
EXPECTED_IMPL_MERGE = "9568424524a2a9f78e75bf0f68b4de6146f6f2b7"
EXPECTED_ROLE_NAME = "onchain-wallet-intelligence-hl-archive-scaling-r11"
EXPECTED_ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-scaling-r11"
EXPECTED_INLINE_POLICY = "HLArchiveR11Exact72Only"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def main() -> int:
    a = load(ATTESTATION)
    e = load(EVIDENCE)
    impl = load(IMPLEMENTATION)
    selection = load(SELECTION)
    permission = load(PERMISSION)

    assert sha256(TEXT) == EXPECTED_TEXT_SHA
    assert sha256(TRUST) == EXPECTED_TRUST_SHA
    assert sha256(PERMISSION) == EXPECTED_PERMISSION_SHA

    assert a["attestation_id"] == "R11_DEDICATED_ROLE_OPERATOR_ATTESTATION"
    assert a["recorded_against_main_commit"] == EXPECTED_IMPL_MERGE
    assert a["canonical_implementation_merge_commit"] == EXPECTED_IMPL_MERGE
    assert a["exact_attestation_text_sha256"] == EXPECTED_TEXT_SHA
    assert a["role_name"] == EXPECTED_ROLE_NAME
    assert a["role_arn"] == EXPECTED_ROLE_ARN
    assert a["inline_policy_name"] == EXPECTED_INLINE_POLICY
    assert a["trust_policy_sha256"] == EXPECTED_TRUST_SHA
    assert a["permission_policy_sha256"] == EXPECTED_PERMISSION_SHA
    assert a["role_max_session_duration_seconds"] == 7200
    assert a["future_workflow_role_duration_seconds"] == 7200
    assert a["persistent_permission_resource_count"] == 72
    assert a["persistent_permission_resources_match_exact_selection_objects"] is True
    assert a["role_created_and_policies_applied"] is True
    assert a["installed_trust_policy_matches_canonical"] is True
    assert a["installed_permission_policy_matches_canonical"] is True
    assert a["additional_managed_policies_attached"] is False
    assert a["additional_inline_policies_attached"] is False
    assert a["existing_r10_role_modified"] is False
    assert a["operator_attested"] is True
    assert a["independently_verified_via_r11_sts_preflight"] is False
    assert a["sts_only_preflight_required"] is True
    assert a["sts_only_preflight_completed"] is False
    assert a["s3_requests_executed_by_role_creation_step"] == 0
    assert a["object_bytes_downloaded_by_role_creation_step"] == 0
    assert a["execution_release_present"] is False
    assert a["canonical_activation_present"] is False
    assert all(v is False for v in a["downstream_authorizations"].values())
    assert all(v is False for v in a["trading_authorizations"].values())
    assert a["empirical_result"] is None

    assert e["evidence_id"] == "R11_ROLE_CREATION_EVIDENCE_MINIMIZED"
    assert e["recorded_against_main_commit"] == EXPECTED_IMPL_MERGE
    assert e["evidence_source"] == "operator-provided AWS CLI output"
    assert e["aws_account_id"] == "630956766927"
    assert e["role_absent_before_creation"] is True
    assert e["role_name"] == EXPECTED_ROLE_NAME
    assert e["role_arn"] == EXPECTED_ROLE_ARN
    assert e["role_id_observed"] == "AROAZFZ7UG3HWQRWO46IV"
    assert e["role_create_date_utc"] == "2026-08-10T20:20:01+00:00"
    assert e["role_max_session_duration_seconds"] == 7200
    assert e["future_workflow_role_duration_seconds"] == 7200
    assert e["trust_policy_sha256_verified_before_creation"] == EXPECTED_TRUST_SHA
    assert e["permission_policy_sha256_verified_before_application"] == EXPECTED_PERMISSION_SHA
    assert e["trust_policy_readback_semantically_matches_canonical"] is True
    assert e["permission_policy_readback_semantically_matches_canonical"] is True
    assert e["persistent_permission_resource_count_observed"] == 72
    assert e["persistent_permission_resources_match_exact_selection_objects"] is True
    assert e["inline_policy_names_observed"] == [EXPECTED_INLINE_POLICY]
    assert e["managed_policies_observed"] == []
    assert e["additional_inline_policies_observed"] == []
    assert e["existing_r10_role_modified"] is False
    assert e["s3_requests_observed_during_role_creation"] == 0
    assert e["object_bytes_downloaded_during_role_creation"] == 0
    assert e["r11_sts_preflight_executed"] is False
    assert e["r11_execution_release_present"] is False
    assert e["r11_canonical_activation_present"] is False
    assert e["raw_cli_transcript_retained"] is False
    assert e["aws_credentials_or_session_tokens_retained"] is False

    assert impl["status"] == "IMPLEMENTED_AWAITING_OPERATOR_ROLE_CREATION_AND_ATTESTATION"
    assert impl["r11_preregistration_merge_commit"] == "dc63f2846652e50755369aa95d0f01ec2e174b02"
    assert impl["r11_approval_merge_commit"] == "86333a6759a492e5452bc565802fefce55a9fd6f"
    assert all(v is False for v in impl["current_runtime_authority"].values())
    assert all(v is False for v in impl["downstream_authorizations"].values())
    assert all(v is False for v in impl["trading_authorizations"].values())

    resources = permission["Statement"][0]["Resource"]
    expected_resources = [f"arn:aws:s3:::hl-mainnet-node-data/{row['key']}" for row in selection["exact_targets"]]
    assert resources == expected_resources
    assert len(resources) == len(set(resources)) == 72

    print("R11_ROLE_OPERATOR_ATTESTATION_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
