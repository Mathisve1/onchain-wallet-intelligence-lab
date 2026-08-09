from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R9 = ROOT / "research/archive_inventory/r9"


class ArchiveR9ReleaseTests(unittest.TestCase):
    def load(self, name: str) -> dict:
        return json.loads((R9 / name).read_text(encoding="utf-8"))

    def test_candidate_is_inert_and_separate_from_activation(self) -> None:
        release = self.load("R9_EXECUTION_RELEASE.json")
        self.assertEqual(release["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertFalse(release["execution_ready"])
        self.assertFalse(release["single_workflow_dispatch_authorized"])
        self.assertFalse(release["rerun_authorized"])
        self.assertFalse(release["release_consumed"])
        activation_path = R9 / "R9_EXECUTION_RELEASE_CANONICALIZATION.json"
        if activation_path.exists():
            activation = self.load("R9_EXECUTION_RELEASE_CANONICALIZATION.json")
            self.assertEqual(activation["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R9_RUN")
            self.assertTrue(activation["single_workflow_dispatch_authorized"])
            self.assertFalse(activation["rerun_authorized"])
            self.assertFalse(activation["release_consumed"])
            self.assertEqual(activation["s3_requests_executed"], 0)
            self.assertEqual(activation["wallet_feature_rows_created"], 0)
            self.assertIsNone(activation["empirical_result"])
        self.assertEqual(release["s3_requests_executed"], 0)
        self.assertEqual(release["wallet_feature_rows_created"], 0)
        self.assertIsNone(release["empirical_result"])

    def test_exact_canonical_lineage_and_object_scope(self) -> None:
        release = self.load("R9_EXECUTION_RELEASE.json")
        self.assertEqual(release["r9_preregistration_merge_commit"], "62ce0009c3c4aad70d2a91f242a690cd26ace355")
        self.assertEqual(release["approval_merge_commit"], "332aa535b0de19a18befb8529450ae88acf35762")
        self.assertEqual(release["canonical_implementation_merge_commit"], "35afca156a99cc71360b338968cb842f9f31ab3b")
        self.assertEqual(release["object_key"], "node_fills_by_block/hourly/20250727/8.lz4")
        self.assertEqual(release["expected_valid_event_pair_count"], 17516)
        self.assertEqual(release["maximum_get_object_requests"], 1)
        self.assertEqual(release["maximum_retries_per_request"], 0)
        self.assertEqual(release["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(release["maximum_monthly_budget_eur"], 0)

    def test_feature_and_semantic_boundaries_are_exact(self) -> None:
        release = self.load("R9_EXECUTION_RELEASE.json")
        self.assertEqual(release["boundary_fixture_role"], "SERIALIZER_AND_FEATURE_PIPELINE_FIXTURE_ONLY")
        self.assertFalse(release["boundary_fixture_historical_representativeness_authorized"])
        self.assertFalse(release["canonical_cross_format_history_use_authorized"])
        self.assertEqual(release["selected_fill_fields_processed"], [
            "coin", "side", "time", "px", "sz", "closedPnl", "tid", "crossed", "liquidation"
        ])
        self.assertEqual(release["retained_wallet_feature_fields_only"], [
            "wallet_address", "fill_count", "first_fill_time", "last_fill_time", "distinct_coin_count",
            "side_a_count", "side_b_count", "crossed_true_count", "liquidation_associated_fill_count",
            "duplicate_tid_count", "sum_abs_px_times_sz_notional_proxy", "sum_closed_pnl_fill_statistic",
        ])
        self.assertFalse(release["sum_closed_pnl_is_exact_account_return"])
        self.assertFalse(release["sum_closed_pnl_is_wallet_ranking_score"])
        self.assertFalse(release["notional_proxy_is_copyable_notional"])
        self.assertTrue(all(value is False for value in release["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in release["trading_authorizations"].values()))

    def test_dedicated_release_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r9_release.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R9_RELEASE_CANDIDATE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
