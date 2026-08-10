from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
ATTEST_DIR = BASE / "r10_role_attestation"
IMPL_DIR = BASE / "r10_implementation"
PREFLIGHT_DIR = BASE / "r10_role_preflight"
RUNTIME = BASE / "r10_runtime"
TEXT = ATTEST_DIR / "R10_DEDICATED_ROLE_OPERATOR_ATTESTATION.txt"
ATTESTATION = ATTEST_DIR / "R10_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
EVIDENCE = ATTEST_DIR / "R10_ROLE_CREATION_EVIDENCE_MINIMIZED.json"
TRUST = IMPL_DIR / "R10_OIDC_TRUST_POLICY.json"
PERMISSION = IMPL_DIR / "R10_PERMISSION_POLICY.json"
IMPLEMENTATION = IMPL_DIR / "R10_IMPLEMENTATION_CONTRACT.json"
PREFLIGHT_CONTRACT = PREFLIGHT_DIR / "R10_STS_PREFLIGHT_CONTRACT.json"
PREFLIGHT_RELEASE = RUNTIME / "R10_STS_PREFLIGHT_RELEASE.json"

EXPECTED_TEXT_SHA = "aa6547983d197941b7ffe90811a77665a7924a8a29fb89955d2f31456cd9c8cd"
EXPECTED_TRUST_SHA = "2709fe66f6361d6498e07bdd2f292576c73485772af6d3cabb89a211e46bdcb9"
EXPECTED_PERMISSION_SHA = "caab807fb0fbc2f1d2132921a99692f5d3533db8449d9a55e4da0714147177fe"
EXPECTED_ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"
EXPECTED_POLICY = "HLArchivePostBoundaryMultiHourR10ExactSixOnly"


class R10RoleAttestationTests(unittest.TestCase):
    @staticmethod
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_operator_text_and_canonical_policies_are_hash_bound(self) -> None:
        a = self.load(ATTESTATION)
        self.assertEqual(hashlib.sha256(TEXT.read_bytes()).hexdigest(), EXPECTED_TEXT_SHA)
        self.assertEqual(a["exact_attestation_text_sha256"], EXPECTED_TEXT_SHA)
        self.assertEqual(hashlib.sha256(TRUST.read_bytes()).hexdigest(), EXPECTED_TRUST_SHA)
        self.assertEqual(hashlib.sha256(PERMISSION.read_bytes()).hexdigest(), EXPECTED_PERMISSION_SHA)

    def test_minimized_operator_readback_binds_exact_role_and_policy_shape(self) -> None:
        a = self.load(ATTESTATION)
        e = self.load(EVIDENCE)
        self.assertEqual(a["role_arn"], EXPECTED_ROLE_ARN)
        self.assertEqual(a["inline_policy_name"], EXPECTED_POLICY)
        self.assertEqual(a["role_max_session_duration_seconds"], 3600)
        self.assertEqual(a["future_workflow_role_duration_seconds"], 900)
        self.assertTrue(a["installed_trust_policy_matches_canonical"])
        self.assertTrue(a["installed_permission_policy_matches_canonical"])
        self.assertEqual(e["inline_policy_names_observed"], [EXPECTED_POLICY])
        self.assertEqual(e["managed_policies_observed"], [])
        self.assertEqual(e["additional_inline_policies_observed"], [])
        self.assertFalse(e["raw_cli_transcript_retained"])
        self.assertFalse(e["aws_credentials_or_session_tokens_retained"])

    def test_attestation_remains_inert_while_separate_preflight_release_exists(self) -> None:
        a = self.load(ATTESTATION)
        impl = self.load(IMPLEMENTATION)
        preflight = self.load(PREFLIGHT_CONTRACT)
        release = self.load(PREFLIGHT_RELEASE)
        self.assertTrue(a["operator_attested"])
        self.assertFalse(a["independently_verified_via_r10_sts_preflight"])
        self.assertTrue(a["sts_only_preflight_required"])
        self.assertFalse(a["sts_only_preflight_completed"])
        self.assertEqual(a["s3_requests_executed_by_role_creation_step"], 0)
        self.assertFalse(a["execution_release_present"])
        self.assertFalse(a["canonical_activation_present"])
        self.assertTrue(all(v is False for v in impl["current_runtime_authority"].values()))
        self.assertTrue(all(v is False for v in impl["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in impl["trading_authorizations"].values()))
        self.assertEqual(preflight["status"], "IMPLEMENTED_AWAITING_SEPARATE_PREFLIGHT_RELEASE")
        self.assertFalse(preflight["preflight_release_present"])
        self.assertFalse(preflight["preflight_execution_authorized"])
        self.assertFalse(preflight["sts_get_caller_identity_authorized"])
        self.assertEqual(preflight["s3_requests_executed"], 0)
        self.assertEqual(release["status"], "RELEASED_FOR_EXACTLY_ONE_R10_STS_ONLY_PREFLIGHT")
        self.assertTrue(release["single_workflow_dispatch_authorized"])
        self.assertFalse(release["rerun_authorized"])
        self.assertFalse(release["release_consumed"])
        self.assertTrue(release["sts_get_caller_identity_authorized"])
        self.assertFalse(release["s3_access_authorized_during_preflight"])
        self.assertEqual(release["aws_sts_requests_executed"], 0)
        self.assertEqual(release["s3_requests_executed"], 0)
        self.assertTrue((ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-role-preflight-r10.yml").is_file())
        self.assertFalse((ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml").exists())
        self.assertEqual(sorted(path.name for path in RUNTIME.iterdir() if path.is_file()), ["R10_STS_PREFLIGHT_RELEASE.json", "R10_STS_PREFLIGHT_RELEASE_CONSUMPTION.json"])

    def test_governance_validator_accepts_exact_snapshot(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10_role_attestation.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("R10_ROLE_OPERATOR_ATTESTATION_VALID", result.stdout)


if __name__ == "__main__":
    unittest.main()
