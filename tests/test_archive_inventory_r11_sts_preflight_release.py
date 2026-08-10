from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
DATA_CONTRACT = BASE / "r11_data_execution/R11_DATA_WORKFLOW_IMPLEMENTATION_CONTRACT.json"


class R11STSPreflightReleaseTests(unittest.TestCase):
    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r11_sts_preflight_release.py")],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("R11_STS_PREFLIGHT_RELEASE_VALID", completed.stdout)

    def test_release_opens_exactly_one_sts_only_manual_preflight(self) -> None:
        r = json.loads((BASE / "r11_runtime/R11_STS_PREFLIGHT_RELEASE.json").read_text())
        self.assertEqual(r["status"], "RELEASED_FOR_EXACTLY_ONE_R11_STS_ONLY_PREFLIGHT")
        self.assertTrue(r["single_workflow_dispatch_authorized"])
        self.assertTrue(r["sts_get_caller_identity_authorized"])
        self.assertEqual(r["maximum_explicit_aws_cli_calls"], 1)
        self.assertFalse(r["rerun_authorized"])
        self.assertFalse(r["release_consumed"])
        self.assertTrue(r["operator_attestation_reviewed"])

    def test_release_keeps_s3_data_and_downstream_closed(self) -> None:
        r = json.loads((BASE / "r11_runtime/R11_STS_PREFLIGHT_RELEASE.json").read_text())
        for key in (
            "s3_access_authorized_during_preflight", "requester_pays_authorized", "get_object_authorized",
            "list_objects_authorized", "head_object_authorized", "range_get_authorized",
            "object_body_download_authorized", "decompression_authorized", "data_workflow_installation_authorized",
            "wallet_ranking_authorized", "candidate_shortlisting_authorized", "pnl_or_alpha_analysis_authorized",
            "copyability_analysis_authorized", "market_data_ingestion_authorized", "strategy_inference_authorized",
        ):
            self.assertFalse(r[key], key)
        self.assertTrue(all(v is False for v in r["trading_authorizations"].values()))
        self.assertEqual(r["aws_sts_requests_executed"], 0)
        self.assertEqual(r["s3_requests_executed"], 0)
        self.assertEqual(r["object_bytes_downloaded"], 0)

    def test_historical_sts_release_stays_data_closed_if_later_route_is_installed(self) -> None:
        text = (ROOT / ".github/workflows/hyperliquid-archive-r11-role-preflight.yml").read_text()
        self.assertIn('"Effect":"Deny","Action":"s3:*","Resource":"*"', text)
        self.assertEqual(text.count("aws sts get-caller-identity --output json"), 1)

        installed = ROOT / ".github/workflows/hyperliquid-archive-r11-72h-persistence.yml"
        frozen = BASE / "r11_implementation/workflows/hyperliquid-archive-r11-72h-persistence.yml"
        if DATA_CONTRACT.exists():
            later = json.loads(DATA_CONTRACT.read_text())
            self.assertEqual(later["status"], "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE")
            self.assertTrue(later["preflight_release_consumed"])
            self.assertFalse(later["single_workflow_dispatch_authorized"])
            self.assertFalse(later["aws_oidc_authorized_now"])
            self.assertFalse(later["get_object_authorized_now"])
            self.assertTrue(installed.exists())
            self.assertEqual(installed.read_bytes(), frozen.read_bytes())
        else:
            self.assertFalse(installed.exists())


if __name__ == "__main__":
    unittest.main()
