from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "research/archive_inventory/r8"


class ArchiveR8AApprovalTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_approval_text_is_hash_bound(self) -> None:
        text = R8 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.txt"
        approval = self.load(R8 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.json")
        self.assertEqual(hashlib.sha256(text.read_bytes()).hexdigest(), "cb39246e2e5f345b14f87c15ac2c4d6aa993bcc9fbd28076f5f57eff94420e64")
        self.assertEqual(approval["exact_approval_text_sha256"], "cb39246e2e5f345b14f87c15ac2c4d6aa993bcc9fbd28076f5f57eff94420e64")
        self.assertEqual(approval["reviewed_commit"], "526f92cf3666c8bb616ecb61b6f9881387c1d7ed")

    def test_scope_is_one_exact_modern_object(self) -> None:
        approval = self.load(R8 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.json")
        self.assertEqual(approval["object_key"], "node_fills_by_block/hourly/20250727/8.lz4")
        self.assertEqual(approval["object_size_bytes"], 1517603)
        self.assertEqual(approval["expected_top_level_block_record_count"], 4345)
        self.assertEqual(approval["maximum_get_object_requests"], 1)
        self.assertEqual(approval["maximum_retries_per_request"], 0)
        self.assertEqual(approval["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(approval["maximum_monthly_budget_eur"], 0)

    def test_future_retention_is_address_plus_count_only(self) -> None:
        approval = self.load(R8 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.json")
        future = approval["future_retention_authorizations"]
        self.assertTrue(future["wallet_address"])
        self.assertTrue(future["leading_string_value"])
        self.assertTrue(future["per_wallet_fill_count"])
        self.assertTrue(future["unique_wallet_count"])
        self.assertTrue(future["valid_event_pair_count"])
        self.assertEqual(future["retained_wallet_index_fields_only"], ["wallet_address", "fill_count"])
        self.assertTrue(all(value is False for value in approval["forbidden_retention_authorizations"].values()))

    def test_approval_opens_implementation_lane_but_not_runtime(self) -> None:
        approval = self.load(R8 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.json")
        self.assertEqual(approval["approval_scope"], "IMPLEMENTATION_AND_LATER_SEPARATE_RELEASE_PATH_ONLY")
        self.assertFalse(approval["execution_authorized_by_this_record"])
        self.assertFalse(approval["request_authorized_by_this_record"])
        self.assertTrue(all(value is False for value in approval["current_runtime_authority"].values()))
        self.assertEqual(approval["s3_requests_executed_under_r8a"], 0)
        self.assertEqual(approval["wallet_addresses_retained_under_r8a"], 0)
        self.assertIsNone(approval["empirical_result"])

    def test_downstream_and_trading_authority_remains_closed(self) -> None:
        approval = self.load(R8 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.json")
        self.assertTrue(all(value is False for value in approval["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in approval["trading_authorizations"].values()))

    def test_dedicated_approval_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r8a_approval.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R8A_APPROVAL_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
