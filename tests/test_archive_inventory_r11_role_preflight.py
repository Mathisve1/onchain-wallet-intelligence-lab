from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"


class R11RolePreflightTests(unittest.TestCase):
    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r11_role_preflight.py")],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("R11_ROLE_STS_PREFLIGHT_IMPLEMENTATION_VALID", completed.stdout)

    def test_installed_preflight_is_byte_exact_frozen_candidate(self) -> None:
        candidate = BASE / "r11_implementation/workflows/hyperliquid-archive-r11-role-preflight.yml"
        installed = ROOT / ".github/workflows/hyperliquid-archive-r11-role-preflight.yml"
        self.assertEqual(installed.read_bytes(), candidate.read_bytes())

    def test_preflight_is_s3_denied_and_sts_only(self) -> None:
        text = (ROOT / ".github/workflows/hyperliquid-archive-r11-role-preflight.yml").read_text()
        self.assertIn('"Effect":"Deny","Action":"s3:*","Resource":"*"', text)
        self.assertEqual(text.count("aws sts get-caller-identity --output json"), 1)
        self.assertNotIn("aws s3 ", text.lower())
        self.assertNotIn("aws s3api ", text.lower())
        self.assertNotIn("research.archive_inventory.r11_implementation.collector", text)

    def test_contract_is_inert_and_data_route_absent(self) -> None:
        contract = json.loads((BASE / "r11_role_preflight/R11_STS_PREFLIGHT_CONTRACT.json").read_text())
        self.assertEqual(contract["status"], "IMPLEMENTED_AWAITING_SEPARATE_PREFLIGHT_RELEASE")
        self.assertFalse(contract["preflight_execution_authorized"])
        self.assertFalse(contract["sts_get_caller_identity_authorized"])
        self.assertFalse(contract["single_workflow_dispatch_authorized"])
        self.assertFalse(contract["preflight_s3_requests_authorized"])
        self.assertFalse(contract["data_workflow_installation_authorized"])
        self.assertFalse((ROOT / ".github/workflows/hyperliquid-archive-r11-72h-persistence.yml").exists())
        self.assertTrue(all(v is False for v in contract["trading_authorizations"].values()))


if __name__ == "__main__":
    unittest.main()
