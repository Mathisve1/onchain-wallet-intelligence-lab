from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R10 = ROOT / "research/archive_inventory/r10"
TXT = R10 / "approvals/APPROVE_HL_ARCHIVE_POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_001.txt"
JSON_PATH = R10 / "approvals/APPROVE_HL_ARCHIVE_POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_001.json"
CONTRACT = R10 / "POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_CONTRACT.json"


class ArchiveR10ApprovalTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_approval_text_is_hash_bound(self) -> None:
        approval = self.load(JSON_PATH)
        self.assertEqual(approval["reviewed_commit"], "37e4486a7f68982feafcb361bd40dffd546def05")
        self.assertEqual(approval["exact_approval_text_sha256"], "ec631e7e6d40cb63383afd012a989419f97cd603ff144e4c5dfb90c18ff90882")
        self.assertEqual(hashlib.sha256(TXT.read_bytes()).hexdigest(), approval["exact_approval_text_sha256"])

    def test_approval_opens_implementation_and_role_creation_but_not_runtime(self) -> None:
        approval = self.load(JSON_PATH)
        self.assertEqual(approval["status"], "OWNER_APPROVED_IMPLEMENTATION_AND_DEDICATED_ROLE_CREATION_NO_EXECUTION")
        role = approval["dedicated_role_authorization"]
        self.assertTrue(role["new_dedicated_r10_role_creation_authorized"])
        self.assertFalse(role["existing_r4_role_reuse_authorized"])
        self.assertFalse(role["existing_r4_role_mutation_authorized"])
        self.assertFalse(approval["execution_authorized_by_this_approval"])
        self.assertTrue(all(value is False for value in approval["current_runtime_authority"].values()))

    def test_scope_matches_preregistered_six_object_envelope(self) -> None:
        approval = self.load(JSON_PATH)
        contract = self.load(CONTRACT)
        self.assertEqual(approval["approved_future_scope"]["maximum_get_object_requests"], 6)
        self.assertEqual(approval["approved_future_scope"]["maximum_total_compressed_bytes"], 120999698)
        self.assertEqual(len(approval["approved_future_objects"]), 6)
        self.assertEqual(
            [row["key"] for row in approval["approved_future_objects"]],
            [row["key"] for row in contract["exact_future_network_targets"]],
        )
        self.assertEqual(
            [row["size_bytes"] for row in approval["approved_future_objects"]],
            [row["expected_size_bytes"] for row in contract["exact_future_network_targets"]],
        )
        self.assertEqual(
            [row["etag"] for row in approval["approved_future_objects"]],
            [row["expected_etag"] for row in contract["exact_future_network_targets"]],
        )

    def test_downstream_and_trading_authority_remains_closed(self) -> None:
        approval = self.load(JSON_PATH)
        self.assertTrue(all(value is False for value in approval["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in approval["trading_authorizations"].values()))
        self.assertTrue(approval["separate_execution_release_required"])
        self.assertTrue(approval["separate_canonical_activation_required"])

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10_approval.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R10_APPROVAL_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
