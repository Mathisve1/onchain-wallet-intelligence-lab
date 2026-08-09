from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R9 = ROOT / "research/archive_inventory/r9"
APPROVAL = R9 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001.json"
TEXT = R9 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001.txt"


class ArchiveR9ApprovalTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_approval_text_is_hash_bound(self) -> None:
        self.assertEqual(hashlib.sha256(TEXT.read_bytes()).hexdigest(), "1e4642ef2eef660f7971c2632864cf78894340e3408f15d15597e4eb12a04330")
        approval = self.load(APPROVAL)
        self.assertEqual(approval["reviewed_commit"], "62ce0009c3c4aad70d2a91f242a690cd26ace355")
        self.assertEqual(approval["exact_approval_text_sha256"], hashlib.sha256(TEXT.read_bytes()).hexdigest())

    def test_approval_opens_implementation_lane_but_not_runtime(self) -> None:
        approval = self.load(APPROVAL)
        self.assertTrue(approval["implementation_authorized"])
        self.assertFalse(approval["execution_authorized_by_this_record"])
        self.assertTrue(approval["separate_execution_release_required"])
        self.assertTrue(approval["separate_canonical_activation_required"])
        self.assertTrue(all(value is False for value in approval["current_runtime_authority"].values()))
        self.assertEqual(approval["s3_requests_executed"], 0)
        self.assertEqual(approval["wallet_feature_rows_created"], 0)
        self.assertIsNone(approval["empirical_result"])

    def test_scope_is_exact_one_fixture_and_feature_aggregate_only(self) -> None:
        approval = self.load(APPROVAL)
        self.assertEqual(approval["maximum_get_object_requests"], 1)
        self.assertEqual(approval["maximum_retries_per_request"], 0)
        self.assertEqual(approval["object_key"], "node_fills_by_block/hourly/20250727/8.lz4")
        self.assertEqual(approval["expected_valid_event_pair_count"], 17516)
        self.assertFalse(approval["fixture_boundary"]["boundary_fixture_historical_representativeness_authorized"])
        self.assertFalse(approval["fixture_boundary"]["canonical_cross_format_history_use_authorized"])
        self.assertTrue(all(value is False for value in approval["forbidden_retention_authorizations"].values()))
        self.assertTrue(all(value is False for value in approval["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in approval["trading_authorizations"].values()))

    def test_semantic_overclaims_remain_closed(self) -> None:
        approval = self.load(APPROVAL)
        self.assertFalse(approval["semantic_boundaries"]["sum_closed_pnl_is_exact_account_return"])
        self.assertFalse(approval["semantic_boundaries"]["sum_closed_pnl_is_wallet_ranking_score"])
        self.assertFalse(approval["semantic_boundaries"]["notional_proxy_is_copyable_notional"])

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r9_approval.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R9_APPROVAL_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
