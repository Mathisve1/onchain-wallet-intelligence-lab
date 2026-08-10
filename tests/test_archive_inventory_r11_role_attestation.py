from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class R11RoleAttestationTests(unittest.TestCase):
    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r11_role_attestation.py")],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("R11_ROLE_OPERATOR_ATTESTATION_VALID", completed.stdout)

    def test_attestation_keeps_execution_closed(self) -> None:
        attestation = json.loads(
            (ROOT / "research/archive_inventory/r11_role_attestation/R11_DEDICATED_ROLE_OPERATOR_ATTESTATION.json").read_text()
        )
        self.assertTrue(attestation["role_created_and_policies_applied"])
        self.assertFalse(attestation["sts_only_preflight_completed"])
        self.assertFalse(attestation["execution_release_present"])
        self.assertFalse(attestation["canonical_activation_present"])
        self.assertEqual(attestation["s3_requests_executed_by_role_creation_step"], 0)
        self.assertTrue(all(value is False for value in attestation["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in attestation["trading_authorizations"].values()))

    def test_persistent_permission_is_exact_72_object_allowlist(self) -> None:
        selection = json.loads((ROOT / "research/archive_inventory/r11/R11_72H_SELECTION.json").read_text())
        permission = json.loads((ROOT / "research/archive_inventory/r11_implementation/R11_PERMISSION_POLICY.json").read_text())
        allow = permission["Statement"][0]
        expected = [f"arn:aws:s3:::hl-mainnet-node-data/{row['key']}" for row in selection["exact_targets"]]
        self.assertEqual(allow["Action"], "s3:GetObject")
        self.assertEqual(allow["Resource"], expected)
        self.assertEqual(len(expected), 72)
        self.assertEqual(len(set(expected)), 72)


if __name__ == "__main__":
    unittest.main()
