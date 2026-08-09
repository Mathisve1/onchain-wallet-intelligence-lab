from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R9 = ROOT / "research/archive_inventory/r9"


class ArchiveR9ActivationTests(unittest.TestCase):
    def load(self, name: str) -> dict:
        return json.loads((R9 / name).read_text(encoding="utf-8"))

    def test_activation_binds_exact_candidate_and_lineage(self) -> None:
        candidate = self.load("R9_EXECUTION_RELEASE.json")
        activation = self.load("R9_EXECUTION_RELEASE_CANONICALIZATION.json")
        self.assertEqual(activation["candidate_sha256"], "80c66a1ea5637032c61aa47e3299def5e6b590529e25c21250bb4028f62548bc")
        self.assertEqual(activation["release_candidate_merge_commit"], "2ce37ca972907e55de30a4f1aed41ae3cd5b805b")
        self.assertEqual(activation["canonical_implementation_merge_commit"], "35afca156a99cc71360b338968cb842f9f31ab3b")
        self.assertEqual(activation["approval_merge_commit"], "332aa535b0de19a18befb8529450ae88acf35762")
        self.assertEqual(activation["release_id"], candidate["release_id"])

    def test_activation_opens_only_exact_single_manual_runtime_envelope(self) -> None:
        activation = self.load("R9_EXECUTION_RELEASE_CANONICALIZATION.json")
        self.assertEqual(activation["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R9_RUN")
        self.assertEqual(activation["github_event_required"], "workflow_dispatch")
        self.assertEqual(activation["canonical_dispatch_ref_required"], "refs/heads/main")
        self.assertEqual(activation["single_use_window_start_utc"], "2026-08-09T21:12:00Z")
        self.assertTrue(activation["single_workflow_dispatch_authorized"])
        self.assertFalse(activation["rerun_authorized"])
        self.assertFalse(activation["release_consumed"])
        self.assertEqual(activation["maximum_get_object_requests"], 1)
        self.assertEqual(activation["maximum_retries_per_request"], 0)
        self.assertEqual(activation["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(activation["maximum_monthly_budget_eur"], 0)

    def test_activation_feature_retention_and_semantic_limits_are_exact(self) -> None:
        activation = self.load("R9_EXECUTION_RELEASE_CANONICALIZATION.json")
        self.assertEqual(activation["boundary_fixture_role"], "SERIALIZER_AND_FEATURE_PIPELINE_FIXTURE_ONLY")
        self.assertFalse(activation["boundary_fixture_historical_representativeness_authorized"])
        self.assertFalse(activation["canonical_cross_format_history_use_authorized"])
        self.assertEqual(activation["selected_fill_fields_processed"], [
            "coin", "side", "time", "px", "sz", "closedPnl", "tid", "crossed", "liquidation"
        ])
        self.assertEqual(activation["retained_wallet_feature_fields_only"], [
            "wallet_address", "fill_count", "first_fill_time", "last_fill_time", "distinct_coin_count",
            "side_a_count", "side_b_count", "crossed_true_count", "liquidation_associated_fill_count",
            "duplicate_tid_count", "sum_abs_px_times_sz_notional_proxy", "sum_closed_pnl_fill_statistic",
        ])
        self.assertFalse(activation["sum_closed_pnl_is_exact_account_return"])
        self.assertFalse(activation["sum_closed_pnl_is_wallet_ranking_score"])
        self.assertFalse(activation["notional_proxy_is_copyable_notional"])
        self.assertTrue(all(value is False for value in activation["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in activation["trading_authorizations"].values()))
        self.assertEqual(activation["s3_requests_executed"], 0)
        self.assertEqual(activation["wallet_feature_rows_created"], 0)
        self.assertIsNone(activation["empirical_result"])

    def test_candidate_remains_immutable_inert_snapshot(self) -> None:
        candidate = self.load("R9_EXECUTION_RELEASE.json")
        self.assertEqual(candidate["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertFalse(candidate["execution_ready"])
        self.assertFalse(candidate["single_workflow_dispatch_authorized"])
        self.assertFalse(candidate["rerun_authorized"])
        self.assertFalse(candidate["release_consumed"])
        self.assertEqual(candidate["s3_requests_executed"], 0)
        self.assertEqual(candidate["wallet_feature_rows_created"], 0)
        self.assertIsNone(candidate["empirical_result"])

    def test_dedicated_activation_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r9_activation.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R9_ACTIVATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
