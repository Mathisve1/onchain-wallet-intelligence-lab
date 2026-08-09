from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r6a"
APPROVAL_TEXT = BASE / "approvals/APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001.txt"
APPROVAL = BASE / "approvals/APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001.json"
CONTRACT = BASE / "LEGACY_USER_KEY_LEXICAL_R6A_CONTRACT.json"
STATUS = BASE / "APPROVAL_STATUS.md"
VALIDATOR = ROOT / "governance/validate_r6a_approval.py"

APPROVAL_SHA = "b24c67f527a320e533408fd821d10b5e2ea01d020c837e87ae5e5bbd386c94ed"
PREREG_MERGE = "870fdf3e10a761d6c4589d43def8e436f3a129b5"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


class ArchiveR6AApprovalTests(unittest.TestCase):
    def test_exact_approval_text_is_hash_bound(self) -> None:
        self.assertEqual(hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest(), APPROVAL_SHA)
        approval = load(APPROVAL)
        self.assertEqual(approval["exact_approval_text_sha256"], APPROVAL_SHA)
        self.assertEqual(approval["reviewed_commit"], PREREG_MERGE)

    def test_approval_opens_implementation_lane_but_not_runtime(self) -> None:
        approval = load(APPROVAL)
        self.assertEqual(approval["approval_scope"], "IMPLEMENTATION_AND_LATER_SEPARATE_RELEASE_PATH_ONLY")
        self.assertFalse(approval["execution_authorized_by_this_record"])
        self.assertFalse(approval["request_authorized_by_this_record"])
        self.assertTrue(approval["requester_pays_authorized_for_later_release"])
        self.assertTrue(approval["get_object_authorized_for_later_release"])
        self.assertTrue(approval["decompression_authorized_for_later_release"])
        self.assertTrue(approval["lexical_classification_authorized_for_later_release"])
        self.assertTrue(all(value is False for value in approval["current_runtime_authority"].values()))

    def test_scope_is_exact_one_object_and_aggregate_counts_only(self) -> None:
        approval = load(APPROVAL)
        self.assertEqual(approval["maximum_get_object_requests"], 1)
        self.assertEqual(approval["maximum_retries_per_request"], 0)
        self.assertEqual(approval["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(approval["maximum_monthly_budget_eur"], 0)
        self.assertEqual(approval["object_key"], "node_fills/hourly/20250727/8.lz4")
        self.assertEqual(approval["expected_nonempty_record_count"], 162815)
        self.assertTrue(all(approval["lexical_count_authorizations"].values()))
        self.assertTrue(all(value is False for value in approval["retention_authorizations"].values()))

    def test_wallet_market_and_trading_authorities_remain_closed(self) -> None:
        approval = load(APPROVAL)
        self.assertTrue(all(value is False for value in approval["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in approval["trading_authorizations"].values()))
        self.assertEqual(approval["s3_requests_executed_under_r6a"], 0)
        self.assertIsNone(approval["empirical_result"])

    def test_preregistration_snapshot_remains_inert(self) -> None:
        contract = load(CONTRACT)
        authority = contract["current_runtime_authority"]
        self.assertFalse(authority["human_approval_recorded"])
        self.assertFalse(authority["implementation_authorized"])
        self.assertFalse(authority["execution_authorized"])
        self.assertFalse(authority["get_object_authorized"])
        self.assertFalse(authority["decompression_authorized"])
        self.assertFalse(authority["lexical_classification_authorized"])
        self.assertEqual(authority["s3_requests_executed"], 0)
        self.assertIsNone(authority["empirical_result"])

    def test_status_is_explicitly_nonexecuting(self) -> None:
        text = STATUS.read_text(encoding="utf-8")
        self.assertIn("HUMAN_APPROVED_IMPLEMENTATION_LANE_ONLY_NO_RUNTIME", text)
        self.assertIn(APPROVAL_SHA, text)
        self.assertIn(PREREG_MERGE, text)
        self.assertIn("does **not** itself authorize", text)

    def test_dedicated_approval_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(VALIDATOR)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R6A_APPROVAL_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
