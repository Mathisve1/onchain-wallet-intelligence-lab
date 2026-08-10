from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R10 = ROOT / "research/archive_inventory/r10"
CONTRACT = R10 / "POST_BOUNDARY_MULTI_HOUR_FEATURE_R10_CONTRACT.json"
SELECTION = R10 / "R3_OBJECT_SELECTION.json"
IAM = R10 / "R10_IAM_DESIGN.json"


class ArchiveR10PreregistrationTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_six_unambiguous_post_boundary_hours_are_frozen(self) -> None:
        c = self.load(CONTRACT)
        s = self.load(SELECTION)
        self.assertEqual(c["historical_window_role"]["window_start_utc"], "2025-07-27T09:00:00Z")
        self.assertEqual(c["historical_window_role"]["window_end_exclusive_utc"], "2025-07-27T15:00:00Z")
        self.assertEqual(c["historical_window_role"]["selected_hour_count"], 6)
        self.assertFalse(c["historical_window_role"]["censored_boundary_hour_included"])
        self.assertEqual(len(c["exact_future_network_targets"]), 6)
        self.assertEqual(s["aggregate_selected_compressed_bytes"], 120999698)
        self.assertTrue(s["selection_contiguous_by_path_hour"])
        self.assertFalse(s["selection_includes_censored_boundary_hour"])

    def test_future_network_is_bounded_but_current_authority_is_zero(self) -> None:
        c = self.load(CONTRACT)
        envelope = c["proposed_request_envelope"]
        self.assertEqual(envelope["maximum_get_object_requests"], 6)
        self.assertEqual(envelope["maximum_requests_per_object"], 1)
        self.assertEqual(envelope["maximum_retries_per_request"], 0)
        self.assertEqual(envelope["maximum_total_compressed_bytes"], 120999698)
        self.assertEqual(envelope["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(envelope["maximum_monthly_budget_eur"], 0)
        self.assertEqual(envelope["request_order"], "PATH_HOUR_ASCENDING")
        self.assertTrue(envelope["stop_after_first_failed_or_mismatched_object"])
        self.assertTrue(all(value is False for value in c["current_runtime_authority"].values()))
        self.assertEqual(c["network_requests_executed_by_r10_preregistration"], 0)

    def test_cross_object_mechanics_are_fail_closed(self) -> None:
        c = self.load(CONTRACT)
        parse_rules = c["decompression_and_parse_rules"]
        cross = c["cross_object_aggregation_rules"]
        self.assertTrue(parse_rules["fill_time_must_fall_within_source_path_hour_utc"])
        self.assertEqual(parse_rules["path_hour_alignment_violation_count_required_for_success"], 0)
        self.assertEqual(cross["duplicate_identity_key"], "WALLET_ADDRESS_PLUS_TID")
        self.assertEqual(cross["duplicate_wallet_tid_count_required_for_clean_success"], 0)
        self.assertFalse(cross["blind_duplicate_deduplication_authorized"])
        self.assertTrue(cross["fill_count_conservation_required"])
        self.assertTrue(cross["side_count_conservation_required"])
        self.assertFalse(cross["per_hour_wallet_feature_rows_retention_authorized"])

    def test_output_adds_only_active_hour_count_to_r9_feature_shape(self) -> None:
        c = self.load(CONTRACT)
        fields = c["proposed_per_wallet_output"]["fields_only"]
        self.assertEqual(fields, [
            "wallet_address", "fill_count", "active_hour_count", "first_fill_time", "last_fill_time",
            "distinct_coin_count", "side_a_count", "side_b_count", "crossed_true_count",
            "liquidation_associated_fill_count", "duplicate_tid_count",
            "sum_abs_px_times_sz_notional_proxy", "sum_closed_pnl_fill_statistic",
        ])
        self.assertEqual(c["proposed_per_wallet_output"]["active_hour_count_maximum"], 6)
        self.assertTrue(all(value is False for value in c["raw_or_disallowed_retention"].values()))
        self.assertTrue(all(value is False for value in c["semantic_boundaries"].values()))

    def test_no_ranking_shortlisting_or_trading_is_opened(self) -> None:
        c = self.load(CONTRACT)
        self.assertTrue(all(value is False for value in c["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in c["trading_authorizations"].values()))
        self.assertFalse(c["historical_window_role"]["six_hour_window_supports_wallet_quality_ranking"])
        self.assertEqual(c["wallet_feature_rows_created_by_r10_preregistration"], 0)
        self.assertIsNone(c["empirical_result"])

    def test_existing_r4_role_must_not_be_widened(self) -> None:
        c = self.load(CONTRACT)
        iam = self.load(IAM)
        self.assertFalse(iam["existing_r4_role_reuse_possible"])
        self.assertFalse(iam["existing_r4_role_reuse_authorized"])
        self.assertFalse(iam["existing_role_mutation_authorized"])
        self.assertTrue(iam["new_dedicated_role_required_for_future_execution"])
        self.assertFalse(iam["iam_role_creation_authorized_now"])
        self.assertFalse(c["iam_boundary"]["existing_r4_role_mutation_authorized"])
        self.assertTrue(c["iam_boundary"]["new_dedicated_r10_role_required"])
        self.assertFalse(c["iam_boundary"]["new_dedicated_r10_role_creation_authorized_now"])

    def test_preregistration_requires_separate_human_and_runtime_gates(self) -> None:
        c = self.load(CONTRACT)
        self.assertTrue(c["human_approval_required_before_implementation"])
        self.assertTrue(c["separate_iam_role_operator_gate_required"])
        self.assertTrue(c["separate_sts_preflight_release_required"])
        self.assertTrue(c["implementation_required_before_execution_release"])
        self.assertTrue(c["separate_execution_release_required"])
        self.assertTrue(c["separate_canonical_activation_required"])
        self.assertFalse((R10 / "approvals").exists())
        self.assertFalse((R10 / "collector.py").exists())
        self.assertFalse((R10 / "R10_IMPLEMENTATION_CONTRACT.json").exists())
        self.assertTrue((ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml").is_file())

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10_preregistration.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R10_PREREGISTRATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
