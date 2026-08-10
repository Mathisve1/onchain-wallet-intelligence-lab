from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREREG = BASE / "r10d/R10D_RECORD_ANCHORED_BOUNDARY_REPAIR_PREREGISTRATION.json"
TEXT = BASE / "r10d_approval/APPROVE_HL_ARCHIVE_R10D_RECORD_ANCHORED_MULTI_HOUR_FEATURE_REPAIR_001.txt"
RECEIPT = BASE / "r10d_approval/APPROVE_HL_ARCHIVE_R10D_RECORD_ANCHORED_MULTI_HOUR_FEATURE_REPAIR_001.json"
EXPECTED_SHA = "d8d1466a5da40c4fe32523ba81bfa165e0b88221cc70534f0f0a118870c1275f"


class R10DApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.p = json.loads(PREREG.read_text(encoding="utf-8"))
        cls.a = json.loads(RECEIPT.read_text(encoding="utf-8"))

    def test_exact_approval_text_is_hash_bound(self) -> None:
        self.assertEqual(hashlib.sha256(TEXT.read_bytes()).hexdigest(), EXPECTED_SHA)
        self.assertEqual(self.a["exact_approval_text_sha256"], EXPECTED_SHA)
        self.assertEqual(self.a["reviewed_commit"], "b8e8d1080be27ff9db3fb639804b4040fdc7c2a0")

    def test_approval_opens_implementation_not_execution(self) -> None:
        self.assertEqual(self.a["status"], "OWNER_APPROVED_IMPLEMENTATION_NO_EXECUTION")
        self.assertFalse(self.a["execution_authorized_by_this_approval"])
        self.assertTrue(self.a["separate_execution_release_required"])
        self.assertTrue(self.a["separate_canonical_activation_required"])
        self.assertTrue(all(v is False for v in self.a["current_runtime_authority"].values()))

    def test_scope_matches_preregistration(self) -> None:
        scope = self.a["approved_future_scope"]
        env = self.p["proposed_request_envelope"]
        for key in (
            "maximum_one_time_budget_eur", "maximum_monthly_budget_eur", "maximum_get_object_requests",
            "maximum_requests_per_object", "maximum_retries_per_request", "maximum_total_compressed_bytes",
            "maximum_individual_compressed_bytes", "maximum_total_decompressed_bytes",
            "maximum_individual_decompressed_bytes", "maximum_runtime_seconds", "request_order",
            "stop_after_first_failed_or_mismatched_object",
        ):
            self.assertEqual(scope[key], env[key], key)
        self.assertEqual(len(self.p["exact_future_network_targets"]), 6)

    def test_record_anchored_rule_is_exact_and_has_no_numeric_tolerance(self) -> None:
        rule = self.a["approved_record_anchored_alignment_rule"]
        self.assertTrue(rule["local_time_raw_prefix_must_match_source_path_hour_for_every_record"])
        self.assertEqual(rule["block_time_raw_prefix_allowed_buckets"], ["MATCHES_PATH_DATE_HOUR_PREFIX", "MATCHES_PREVIOUS_DATE_HOUR_PREFIX"])
        self.assertTrue(rule["block_time_next_or_other_prefix_is_fail_closed"])
        self.assertTrue(rule["fill_time_integer_milliseconds_processing"])
        self.assertFalse(rule["numeric_tolerance_authorized"])
        self.assertEqual(rule["path_block_record_allowed_fill_partitions"], ["INSIDE_PATH_HOUR"])
        self.assertEqual(rule["previous_block_record_allowed_fill_partitions"], ["BEFORE_PATH_HOUR"])
        self.assertTrue(rule["previous_block_record_before_fill_must_be_within_immediately_previous_epoch_hour"])
        self.assertEqual(rule["after_path_hour_fill_count_required_for_success"], 0)

    def test_wallet_feature_retention_is_approved_but_ranking_and_trading_stay_closed(self) -> None:
        self.assertTrue(self.a["wallet_feature_retention_authorized_for_future_separate_execution_release"])
        self.assertTrue(all(v is False for v in self.a["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in self.a["trading_authorizations"].values()))

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, "governance/validate_r10d_approval.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10D_APPROVAL_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
