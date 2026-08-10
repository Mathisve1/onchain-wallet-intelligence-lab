from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
TEXT = BASE / "r11_approval/APPROVE_HL_ARCHIVE_R11_72H_PERSISTENCE_SCALING_001.txt"
RECEIPT = BASE / "r11_approval/APPROVE_HL_ARCHIVE_R11_72H_PERSISTENCE_SCALING_001.json"
EXPECTED_SHA = "1c3ec861d5df30dbdeef4dece7422bc05fab50d59aa58aa36cf3b7f8fea0d3ca"


class R11ApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.a = json.loads(RECEIPT.read_text(encoding="utf-8"))

    def test_normalized_owner_block_is_hash_bound(self) -> None:
        self.assertEqual(hashlib.sha256(TEXT.read_bytes()).hexdigest(), EXPECTED_SHA)
        self.assertTrue(TEXT.read_bytes().endswith(b"\n"))
        self.assertEqual(self.a["exact_approval_text_sha256"], EXPECTED_SHA)
        self.assertEqual(self.a["reviewed_commit"], "dc63f2846652e50755369aa95d0f01ec2e174b02")

    def test_approval_opens_implementation_and_role_creation_not_execution(self) -> None:
        self.assertEqual(self.a["status"], "OWNER_APPROVED_IMPLEMENTATION_AND_DEDICATED_ROLE_CREATION_NO_DATA_EXECUTION")
        self.assertTrue(self.a["approved_dedicated_role_creation"]["new_dedicated_r11_role_creation"])
        self.assertFalse(self.a["execution_authorized_by_this_approval"])
        self.assertTrue(self.a["separate_execution_release_required"])
        self.assertTrue(self.a["separate_canonical_activation_required"])
        self.assertTrue(all(v is False for v in self.a["current_runtime_authority"].values()))

    def test_72h_budget_and_scope_are_exact(self) -> None:
        scope = self.a["approved_future_scope"]
        self.assertEqual(scope["maximum_get_object_requests"], 72)
        self.assertEqual(scope["maximum_retries_per_request"], 0)
        self.assertEqual(scope["maximum_total_compressed_bytes"], 2107738436)
        self.assertEqual(scope["window_start_utc"], "2025-07-28T00:00:00Z")
        self.assertEqual(scope["window_end_exclusive_utc"], "2025-07-31T00:00:00Z")
        self.assertEqual(scope["selected_hour_count"], 72)

    def test_no_ranking_copyability_or_trading_authority(self) -> None:
        self.assertTrue(all(v is False for v in self.a["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in self.a["trading_authorizations"].values()))

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run([sys.executable, "governance/validate_r11_approval.py"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R11_APPROVAL_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
