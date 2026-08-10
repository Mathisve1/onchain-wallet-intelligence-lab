from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
TEXT = BASE / "r10a_approval/APPROVE_HL_ARCHIVE_R10A_TIMESTAMP_PARTITION_DIAGNOSTIC_001.txt"
RECEIPT = BASE / "r10a_approval/APPROVE_HL_ARCHIVE_R10A_TIMESTAMP_PARTITION_DIAGNOSTIC_001.json"


class R10AApprovalTests(unittest.TestCase):
    def test_exact_text_is_hash_bound(self) -> None:
        self.assertEqual(hashlib.sha256(TEXT.read_bytes()).hexdigest(), "c990a1636b745908d9f58c4b119998dfa91b4e8740764081bbb19cb8ad8904f1")

    def test_approval_is_one_object_and_not_execution(self) -> None:
        a = json.loads(RECEIPT.read_text())
        self.assertEqual(a["reviewed_commit"], "7db55db0be5efeeadb569abb5faaadf3bc78254a")
        self.assertEqual(a["approved_future_scope"]["maximum_get_object_requests"], 1)
        self.assertTrue(a["approved_role_reuse"]["existing_dedicated_r10_role_reuse"])
        self.assertFalse(a["approved_role_reuse"]["existing_dedicated_r10_role_mutation"])
        self.assertFalse(a["execution_authorized_by_this_approval"])
        self.assertTrue(all(v is False for v in a["current_runtime_authority"].values()))
        self.assertTrue(all(v is False for v in a["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in a["trading_authorizations"].values()))

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run([sys.executable, str(ROOT / "governance/validate_r10a_approval.py")], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10A_APPROVAL_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
