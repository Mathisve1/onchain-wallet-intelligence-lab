from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r11"
SELECTION = BASE / "R11_72H_SELECTION.json"
PREREG = BASE / "R11_72H_PERSISTENCE_SCALING_PREREGISTRATION.json"


class R11PersistenceScalingPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.s = json.loads(SELECTION.read_text(encoding="utf-8"))
        cls.p = json.loads(PREREG.read_text(encoding="utf-8"))

    def test_exact_three_complete_days_are_frozen(self) -> None:
        self.assertEqual(self.s["selected_hour_count"], 72)
        self.assertEqual(self.s["complete_utc_day_count"], 3)
        self.assertEqual(self.s["window_start_utc"], "2025-07-28T00:00:00Z")
        self.assertEqual(self.s["window_end_exclusive_utc"], "2025-07-31T00:00:00Z")
        hours = [row["path_hour_utc"] for row in self.s["exact_targets"]]
        start = datetime(2025, 7, 28, tzinfo=timezone.utc)
        expected = [(start + timedelta(hours=i)).isoformat().replace("+00:00", "Z") for i in range(72)]
        self.assertEqual(hours, expected)
        self.assertEqual(hashlib.sha256(SELECTION.read_bytes()).hexdigest(), "7c134f4b62f547904126a5f810c177484dceeffa246d53c5c35944367d563eb2")

    def test_request_envelope_is_bounded_and_nonexecuting(self) -> None:
        envelope = self.p["proposed_request_envelope"]
        self.assertEqual(envelope["maximum_get_object_requests"], 72)
        self.assertEqual(envelope["maximum_retries_per_request"], 0)
        self.assertEqual(envelope["maximum_total_compressed_bytes"], 2107738436)
        self.assertEqual(envelope["maximum_one_time_budget_eur"], 0.50)
        self.assertTrue(envelope["stop_after_first_failed_or_mismatched_object"])
        self.assertTrue(all(value is False for value in self.p["current_runtime_authority"].values()))
        self.assertEqual(self.p["network_requests_executed_by_r11_preregistration"], 0)

    def test_persistence_is_added_without_performance_claim(self) -> None:
        fields = self.p["proposed_per_wallet_output"]["fields_only"]
        self.assertIn("active_hour_count", fields)
        self.assertIn("active_day_count", fields)
        self.assertEqual(self.p["proposed_per_wallet_output"]["active_day_count_maximum"], 3)
        self.assertFalse(self.p["semantic_boundaries"]["three_day_window_is_sufficient_wallet_performance_history"])
        self.assertFalse(self.p["downstream_authorizations"]["wallet_ranking"])
        self.assertFalse(self.p["downstream_authorizations"]["pnl_or_alpha_analysis"])
        self.assertFalse(self.p["downstream_authorizations"]["copyability_analysis"])

    def test_new_r11_role_is_required_and_r10_role_cannot_be_widened(self) -> None:
        iam = self.p["iam_boundary"]
        self.assertFalse(iam["existing_r10_role_reuse_authorized"])
        self.assertFalse(iam["existing_r10_role_mutation_authorized"])
        self.assertTrue(iam["new_dedicated_r11_role_required"])
        self.assertFalse(iam["new_dedicated_r11_role_creation_authorized_now"])
        self.assertEqual(iam["proposed_persistent_permission_resource_count"], 72)
        self.assertTrue(iam["persistent_permission_resources_are_exact_selection_objects"])

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, "governance/validate_r11_72h_persistence_scaling_preregistration.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R11_72H_PERSISTENCE_SCALING_PREREGISTRATION_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
