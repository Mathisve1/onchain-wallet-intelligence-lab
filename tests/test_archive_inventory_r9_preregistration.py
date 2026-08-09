from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R9 = ROOT / "research/archive_inventory/r9"
APPROVAL = R9 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_FEATURE_PILOT_R9_001.json"
IMPLEMENTATION = R9 / "R9_IMPLEMENTATION_CONTRACT.json"


class ArchiveR9PreregistrationTests(unittest.TestCase):
    def load(self, name: str) -> dict:
        return json.loads((R9 / name).read_text(encoding="utf-8"))

    def test_exact_parent_lineage_and_fixture_role(self) -> None:
        c = self.load("MODERN_WALLET_FEATURE_PILOT_R9_CONTRACT.json")
        self.assertEqual(c["parent_r8b_cutover_commit"], "b77debdf57cbe07bfa190fd40946f2fe897e3a33")
        self.assertEqual(c["parent_r8a_evidence_commit"], "04c23127a553c53e9c3c9b80dabb4a9b7e61de61")
        self.assertEqual(c["fixture_role"]["role"], "SERIALIZER_AND_FEATURE_PIPELINE_FIXTURE_ONLY")
        self.assertTrue(c["fixture_role"]["transition_censored_by_r8b"])
        self.assertFalse(c["fixture_role"]["canonical_cross_format_history_eligible"])
        self.assertFalse(c["fixture_role"]["historical_representativeness_inferred"])

    def test_future_request_is_one_exact_integrity_bound_object_but_current_authority_zero(self) -> None:
        c = self.load("MODERN_WALLET_FEATURE_PILOT_R9_CONTRACT.json")
        target = c["exact_future_network_target"]
        env = c["proposed_request_envelope"]
        self.assertEqual(target["key"], "node_fills_by_block/hourly/20250727/8.lz4")
        self.assertEqual(target["expected_size_bytes"], 1517603)
        self.assertEqual(target["expected_valid_event_pair_count"], 17516)
        self.assertEqual(env["maximum_get_object_requests"], 1)
        self.assertEqual(env["maximum_retries_per_request"], 0)
        self.assertEqual(env["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(env["maximum_monthly_budget_eur"], 0)
        self.assertTrue(all(value is False for value in c["current_runtime_authority"].values()))
        self.assertEqual(c["network_requests_executed_by_r9_preregistration"], 0)

    def test_output_is_aggregate_only_and_deterministically_bounded(self) -> None:
        c = self.load("MODERN_WALLET_FEATURE_PILOT_R9_CONTRACT.json")
        out = c["proposed_per_wallet_output"]
        self.assertEqual(out["fields_only"], [
            "wallet_address", "fill_count", "first_fill_time", "last_fill_time", "distinct_coin_count",
            "side_a_count", "side_b_count", "crossed_true_count", "liquidation_associated_fill_count",
            "duplicate_tid_count", "sum_abs_px_times_sz_notional_proxy", "sum_closed_pnl_fill_statistic",
        ])
        self.assertEqual(out["sort_order"], "WALLET_ADDRESS_LEXICOGRAPHIC_ASCENDING")
        self.assertTrue(out["fill_count_conservation_required"])
        self.assertTrue(out["side_count_conservation_required"])
        self.assertEqual(out["decimal_output_encoding"], "CANONICAL_BASE10_STRING_NO_EXPONENT")
        self.assertTrue(all(value is False for value in c["raw_or_disallowed_retention"].values()))

    def test_selected_processing_is_narrow_and_economic_claims_are_conservative(self) -> None:
        c = self.load("MODERN_WALLET_FEATURE_PILOT_R9_CONTRACT.json")
        self.assertEqual(c["selected_fill_fields_for_transient_processing"], [
            "coin", "side", "time", "px", "sz", "closedPnl", "tid", "crossed", "liquidation"
        ])
        rules = c["selected_field_processing_rules"]
        self.assertTrue(rules["exact_decimal_arithmetic_required"])
        self.assertFalse(rules["floating_point_aggregation_authorized"])
        semantic = c["semantic_boundaries"]
        self.assertFalse(semantic["sum_closed_pnl_fill_statistic_is_exact_account_return"])
        self.assertFalse(semantic["sum_closed_pnl_fill_statistic_is_wallet_ranking_score"])
        self.assertFalse(semantic["sum_abs_px_times_sz_notional_proxy_is_copyable_notional"])

    def test_all_downstream_ranking_copyability_and_trading_stay_closed(self) -> None:
        c = self.load("MODERN_WALLET_FEATURE_PILOT_R9_CONTRACT.json")
        self.assertTrue(all(value is False for value in c["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in c["trading_authorizations"].values()))
        self.assertEqual(c["wallet_feature_rows_created_by_r9_preregistration"], 0)
        self.assertIsNone(c["empirical_result"])

    def test_later_approval_and_implementation_are_separate_inert_snapshots(self) -> None:
        c = self.load("MODERN_WALLET_FEATURE_PILOT_R9_CONTRACT.json")
        self.assertTrue(c["human_approval_required_before_implementation"])
        self.assertTrue(c["implementation_required_before_execution_release"])
        self.assertTrue(c["separate_execution_release_required"])
        self.assertTrue(c["separate_canonical_activation_required"])
        if APPROVAL.exists():
            approval = json.loads(APPROVAL.read_text(encoding="utf-8"))
            self.assertEqual(approval["reviewed_commit"], "62ce0009c3c4aad70d2a91f242a690cd26ace355")
            self.assertTrue(approval["implementation_authorized"])
            self.assertFalse(approval["execution_authorized_by_this_record"])
            self.assertTrue(all(value is False for value in approval["current_runtime_authority"].values()))
        if IMPLEMENTATION.exists():
            impl = json.loads(IMPLEMENTATION.read_text(encoding="utf-8"))
            self.assertEqual(impl["approval_merge_commit"], "332aa535b0de19a18befb8529450ae88acf35762")
            self.assertEqual(impl["status"], "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION")
            self.assertTrue(all(value is False for value in impl["current_runtime_authority"].values()))
            self.assertTrue((R9 / "collector.py").is_file())
            self.assertTrue((ROOT / ".github/workflows/hyperliquid-archive-modern-wallet-feature-r9.yml").is_file())
        release_path = R9 / "R9_EXECUTION_RELEASE.json"
        if release_path.exists():
            release = self.load("R9_EXECUTION_RELEASE.json")
            self.assertEqual(release["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
            self.assertFalse(release["execution_ready"])
            self.assertFalse(release["single_workflow_dispatch_authorized"])
            self.assertFalse(release["rerun_authorized"])
            self.assertEqual(release["s3_requests_executed"], 0)
            self.assertEqual(release["wallet_feature_rows_created"], 0)
            self.assertIsNone(release["empirical_result"])
        self.assertFalse((R9 / "R9_EXECUTION_RELEASE_CANONICALIZATION.json").exists())

    def test_dedicated_preregistration_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r9_preregistration.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R9_PREREGISTRATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
