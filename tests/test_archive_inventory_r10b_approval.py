from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
TEXT = BASE / "r10b_approval/APPROVE_HL_ARCHIVE_R10B_BATCH_METADATA_LEXICAL_DIAGNOSTIC_001.txt"
RECEIPT = BASE / "r10b_approval/APPROVE_HL_ARCHIVE_R10B_BATCH_METADATA_LEXICAL_DIAGNOSTIC_001.json"
EXPECTED_SHA = "981b9277b652117c2a3648fa3870015d3efe590a595e84bcba22cf0b3f8f8061"


class R10BApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.approval = json.loads(RECEIPT.read_text(encoding="utf-8"))

    def test_exact_text_is_hash_bound(self) -> None:
        self.assertEqual(hashlib.sha256(TEXT.read_bytes()).hexdigest(), EXPECTED_SHA)
        self.assertTrue(TEXT.read_bytes().endswith(b"\n"))

    def test_approval_is_explicit_but_not_execution(self) -> None:
        a = self.approval
        self.assertEqual(a["reviewed_commit"], "8ba7b0928ac45c66dd6df756491928fddbe2a060")
        self.assertEqual(a["approval_source_user_text"], "ga verder hiermee, ik heb je toestemming gegeven")
        self.assertFalse(a["execution_authorized_by_this_approval"])
        self.assertTrue(a["separate_execution_release_required"])
        self.assertTrue(a["separate_canonical_activation_required"])
        self.assertTrue(all(v is False for v in a["current_runtime_authority"].values()))

    def test_scope_is_exactly_one_existing_object(self) -> None:
        s = self.approval["approved_future_scope"]
        self.assertEqual(s["maximum_get_object_requests"], 1)
        self.assertEqual(s["maximum_retries_per_request"], 0)
        self.assertEqual(s["maximum_total_compressed_bytes"], 18147822)
        self.assertEqual(s["object_expected_compressed_sha256"], "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339")
        role = self.approval["approved_role_reuse"]
        self.assertTrue(role["existing_dedicated_r10_role_reuse"])
        self.assertFalse(role["existing_dedicated_r10_role_mutation"])
        self.assertEqual(role["future_session_policy_allowed_s3_actions_only"], ["s3:GetObject"])
        self.assertEqual(role["future_session_policy_allowed_object_count"], 1)

    def test_processing_is_lexical_only(self) -> None:
        p = self.approval["approved_future_processing"]
        self.assertTrue(p["decompression"])
        self.assertTrue(p["metadata_lexical_processing"])
        self.assertTrue(p["aggregate_lexical_retention"])
        for key in ("timezone_parsing","timezone_inference","datetime_conversion","individual_metadata_value_retention","event_array_contents_inspection","wallet_address_retention","wallet_aggregation","economic_fill_field_processing","individual_fill_time_processing","raw_object_retention"):
            self.assertFalse(p[key], key)
        self.assertTrue(all(v is False for v in self.approval["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in self.approval["trading_authorizations"].values()))

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run([sys.executable, "governance/validate_r10b_approval.py"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
