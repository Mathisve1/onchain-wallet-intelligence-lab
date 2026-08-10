from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"


class R11STSPreflightReleaseCandidateTests(unittest.TestCase):
    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r11_sts_preflight_release_candidate.py")],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("R11_STS_PREFLIGHT_RELEASE_CANDIDATE_VALID", completed.stdout)

    def test_candidate_is_inert_and_separate_from_activation(self) -> None:
        c = json.loads((BASE / "r11_role_preflight/R11_STS_PREFLIGHT_RELEASE_CANDIDATE.json").read_text())
        self.assertEqual(c["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertTrue(c["canonical_activation_required"])
        self.assertFalse(c["canonical_activation_present"])
        self.assertIsNone(c["single_use_window_start_utc"])
        self.assertIsNone(c["anchor_commit"])
        self.assertFalse(c["single_workflow_dispatch_authorized"])
        self.assertFalse(c["sts_get_caller_identity_authorized"])
        self.assertFalse(c["release_consumed"])

    def test_candidate_opens_no_s3_data_or_trading_authority(self) -> None:
        c = json.loads((BASE / "r11_role_preflight/R11_STS_PREFLIGHT_RELEASE_CANDIDATE.json").read_text())
        for key in (
            "s3_access_authorized_during_preflight", "requester_pays_authorized", "get_object_authorized",
            "list_objects_authorized", "head_object_authorized", "range_get_authorized",
            "object_body_download_authorized", "decompression_authorized", "data_workflow_installation_authorized",
            "wallet_ranking_authorized", "candidate_shortlisting_authorized", "pnl_or_alpha_analysis_authorized",
            "copyability_analysis_authorized", "market_data_ingestion_authorized", "strategy_inference_authorized",
        ):
            self.assertFalse(c[key], key)
        self.assertTrue(all(v is False for v in c["trading_authorizations"].values()))
        self.assertEqual(c["aws_sts_requests_executed"], 0)
        self.assertEqual(c["s3_requests_executed"], 0)

    def test_preflight_workflow_is_sts_only_and_data_route_absent(self) -> None:
        text = (ROOT / ".github/workflows/hyperliquid-archive-r11-role-preflight.yml").read_text()
        self.assertIn('"Effect":"Deny","Action":"s3:*","Resource":"*"', text)
        self.assertEqual(text.count("aws sts get-caller-identity --output json"), 1)
        self.assertFalse((ROOT / ".github/workflows/hyperliquid-archive-r11-72h-persistence.yml").exists())


if __name__ == "__main__":
    unittest.main()
