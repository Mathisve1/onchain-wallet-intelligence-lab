from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CONTRACT = BASE / "r10_role_preflight/R10_STS_PREFLIGHT_CONTRACT.json"
ATTESTATION = BASE / "r10_role_attestation/R10_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
CANDIDATE = BASE / "r10_implementation/workflows/hyperliquid-archive-post-boundary-multihour-role-preflight-r10.yml"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-role-preflight-r10.yml"
DATA_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml"
RUNTIME = BASE / "r10_runtime"
RELEASE = RUNTIME / "R10_STS_PREFLIGHT_RELEASE.json"

EXPECTED_WORKFLOW_SHA = "fefef8a7bb40e965c9ed77e9892057ac8e0a64dcfa60d7f3e7dba8f1651b5f4d"
EXPECTED_ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10"


class R10RolePreflightTests(unittest.TestCase):
    @staticmethod
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_contract_is_inert_and_role_attestation_bound(self) -> None:
        c = self.load(CONTRACT)
        a = self.load(ATTESTATION)
        self.assertEqual(c["status"], "IMPLEMENTED_AWAITING_SEPARATE_PREFLIGHT_RELEASE")
        self.assertEqual(c["role_attestation_merge_commit"], "ba7835c8e8ecb1cdc6a1c44c9b679d8f43e7a40e")
        self.assertEqual(c["r10_implementation_merge_commit"], "820d0cbbb0f49f800f36025da27a06754d3fc08d")
        self.assertEqual(c["role_arn"], EXPECTED_ROLE_ARN)
        self.assertEqual(a["role_arn"], EXPECTED_ROLE_ARN)
        self.assertTrue(a["operator_attested"])
        self.assertFalse(a["sts_only_preflight_completed"])
        self.assertTrue(c["preflight_release_required"])
        self.assertFalse(c["preflight_release_present"])
        self.assertFalse(c["preflight_execution_authorized"])
        self.assertFalse(c["sts_get_caller_identity_authorized"])
        self.assertFalse(c["single_workflow_dispatch_authorized"])
        self.assertFalse(c["rerun_authorized"])
        self.assertEqual(c["aws_sts_requests_executed"], 0)
        self.assertEqual(c["s3_requests_executed"], 0)
        self.assertIsNone(c["empirical_result"])

    def test_installed_preflight_is_byte_exact_frozen_candidate(self) -> None:
        self.assertTrue(CANDIDATE.is_file())
        self.assertTrue(WORKFLOW.is_file())
        self.assertEqual(CANDIDATE.read_bytes(), WORKFLOW.read_bytes())
        self.assertEqual(hashlib.sha256(CANDIDATE.read_bytes()).hexdigest(), EXPECTED_WORKFLOW_SHA)
        self.assertEqual(hashlib.sha256(WORKFLOW.read_bytes()).hexdigest(), EXPECTED_WORKFLOW_SHA)

    def test_preflight_explicitly_denies_s3_and_has_exactly_one_sts_cli_call(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("run-name: R10 dedicated role STS-only preflight", text)
        self.assertIn('"Effect":"Deny","Action":"s3:*","Resource":"*"', text)
        self.assertEqual(text.count("aws sts get-caller-identity --output json"), 1)
        self.assertNotIn("aws s3", text)
        self.assertNotIn("aws s3api", text)
        self.assertNotIn("collector.py", text)
        self.assertIn("role-duration-seconds: 900", text)
        self.assertIn("retry-max-attempts: 1", text)
        self.assertIn("action-timeout-s: 60", text)

    def test_single_use_release_gate_precedes_oidc_and_exact_release_is_active(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertLess(text.index("test -f"), text.index("aws-actions/configure-aws-credentials"))
        self.assertIn("CURRENT_RUN_ATTEMPT", text)
        self.assertIn("R10 STS preflight rerun forbidden", text)
        self.assertTrue(RELEASE.is_file())
        release = self.load(RELEASE)
        self.assertEqual(release["status"], "RELEASED_FOR_EXACTLY_ONE_R10_STS_ONLY_PREFLIGHT")
        self.assertEqual(release["release_candidate_merge_commit"], "fdefa27955202f4592c9441665f3c40336c501d1")
        self.assertEqual(release["role_arn"], EXPECTED_ROLE_ARN)
        self.assertTrue(release["single_workflow_dispatch_authorized"])
        self.assertFalse(release["rerun_authorized"])
        self.assertFalse(release["release_consumed"])
        self.assertTrue(release["sts_get_caller_identity_authorized"])
        self.assertFalse(release["s3_access_authorized_during_preflight"])
        self.assertEqual(release["aws_sts_requests_executed"], 0)
        self.assertEqual(release["s3_requests_executed"], 0)
        self.assertTrue(DATA_WORKFLOW.is_file())

    def test_all_downstream_and_trading_authority_remains_closed(self) -> None:
        c = self.load(CONTRACT)
        release = self.load(RELEASE)
        for key in (
            "preflight_s3_requests_authorized",
            "preflight_requester_pays_authorized",
            "preflight_get_object_authorized",
            "preflight_list_objects_authorized",
            "preflight_head_object_authorized",
            "preflight_range_get_authorized",
            "preflight_object_body_download_authorized",
            "preflight_decompression_authorized",
            "data_workflow_installation_authorized",
            "historical_window_expansion_authorized",
            "wallet_ranking_authorized",
            "shortlisting_authorized",
            "pnl_or_alpha_analysis_authorized",
            "copyability_analysis_authorized",
            "market_data_ingestion_authorized",
        ):
            self.assertFalse(c[key], key)
        for key in (
            "s3_access_authorized_during_preflight",
            "data_workflow_installation_authorized",
            "historical_window_expansion_authorized",
            "wallet_ranking_authorized",
            "shortlisting_authorized",
            "pnl_or_alpha_analysis_authorized",
            "copyability_analysis_authorized",
            "market_data_ingestion_authorized",
        ):
            self.assertFalse(release[key], key)
        self.assertTrue(all(value is False for value in c["trading_authorizations"].values()))
        self.assertTrue(all(value is False for value in release["trading_authorizations"].values()))

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10_role_preflight.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R10_ROLE_STS_PREFLIGHT_IMPLEMENTATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
