from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R7 = ROOT / "research/archive_inventory/r7"
APPROVAL_ID = "APPROVE_HL_ARCHIVE_WALLET_INDEX_RECONSTRUCTION_R7_001"
APPROVAL_SHA = "43f32634859eb39e4b1e464276f9721ed4ef8bcc30161f1f301f82e0312042a6"


class ArchiveR7ApprovalTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_approval_text_is_hash_bound(self) -> None:
        raw = (R7 / f"approvals/{APPROVAL_ID}.txt").read_bytes()
        approval = self.load(R7 / f"approvals/{APPROVAL_ID}.json")
        self.assertEqual(hashlib.sha256(raw).hexdigest(), APPROVAL_SHA)
        self.assertEqual(approval["exact_approval_text_sha256"], APPROVAL_SHA)
        self.assertEqual(approval["reviewed_commit"], "795281b2992466785ba48314d59feb61ac0b3aef")

    def test_approval_opens_implementation_lane_but_not_runtime(self) -> None:
        approval = self.load(R7 / f"approvals/{APPROVAL_ID}.json")
        self.assertEqual(approval["approval_scope"], "IMPLEMENTATION_AND_LATER_SEPARATE_RELEASE_PATH_ONLY")
        self.assertFalse(approval["execution_authorized_by_this_record"])
        self.assertFalse(approval["request_authorized_by_this_record"])
        self.assertFalse(approval["aws_role_mutation_authorized"])
        self.assertTrue(all(value is False for value in approval["current_runtime_authority"].values()))
        self.assertEqual(approval["s3_requests_executed_under_r7"], 0)
        self.assertEqual(approval["wallet_addresses_retained_under_r7"], 0)
        self.assertIsNone(approval["empirical_result"])

    def test_exact_request_scope_matches_preregistration(self) -> None:
        approval = self.load(R7 / f"approvals/{APPROVAL_ID}.json")
        contract = self.load(R7 / "WALLET_INDEX_RECONSTRUCTION_R7_CONTRACT.json")
        target = contract["exact_future_network_target"]
        envelope = contract["proposed_future_request_envelope"]
        self.assertEqual(approval["object_key"], target["key"])
        self.assertEqual(approval["object_etag"], target["expected_etag"])
        self.assertEqual(approval["expected_compressed_sha256"], target["expected_compressed_sha256"])
        self.assertEqual(approval["expected_decompressed_byte_count"], target["expected_decompressed_byte_count"])
        self.assertEqual(approval["expected_nonempty_record_count"], 162815)
        self.assertEqual(approval["maximum_one_time_budget_eur"], envelope["maximum_one_time_budget_eur"])
        self.assertEqual(approval["maximum_monthly_budget_eur"], 0)
        self.assertEqual(approval["maximum_get_object_requests"], 1)
        self.assertEqual(approval["maximum_retries_per_request"], 0)
        self.assertTrue(approval["requester_pays_authorized_for_later_release"])
        self.assertTrue(approval["get_object_authorized_for_later_release"])

    def test_future_retention_is_only_address_and_fill_count(self) -> None:
        approval = self.load(R7 / f"approvals/{APPROVAL_ID}.json")
        future = approval["future_retention_authorizations"]
        self.assertTrue(future["wallet_address"])
        self.assertTrue(future["leading_string_value"])
        self.assertTrue(future["per_wallet_fill_count"])
        self.assertTrue(future["unique_wallet_count"])
        self.assertEqual(future["wallet_address_normalization"], "LOWERCASE_EXACT_0X40HEX")
        self.assertEqual(future["retained_wallet_index_fields_only"], ["wallet_address", "fill_count"])
        self.assertTrue(all(value is False for value in approval["forbidden_retention_authorizations"].values()))

    def test_downstream_and_trading_authority_remains_closed(self) -> None:
        approval = self.load(R7 / f"approvals/{APPROVAL_ID}.json")
        self.assertTrue(all(value is False for value in approval["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in approval["trading_authorizations"].values()))

    def test_dedicated_approval_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r7_approval.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R7_APPROVAL_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
