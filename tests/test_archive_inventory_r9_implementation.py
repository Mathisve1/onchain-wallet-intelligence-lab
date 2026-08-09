from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R9 = ROOT / "research/archive_inventory/r9"


class ArchiveR9ImplementationTests(unittest.TestCase):
    def load(self, name: str) -> dict:
        return json.loads((R9 / name).read_text(encoding="utf-8"))

    def test_implementation_is_inert_until_separate_release(self) -> None:
        impl = self.load("R9_IMPLEMENTATION_CONTRACT.json")
        self.assertEqual(impl["status"], "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION")
        self.assertEqual(impl["expected_canonical_implementation_commit"], "PENDING_CANONICAL_IMPLEMENTATION_MERGE")
        self.assertFalse(impl["execution_release_present"])
        self.assertFalse(impl["canonical_activation_present"])
        self.assertTrue(all(value is False for value in impl["current_runtime_authority"].values()))
        self.assertEqual(impl["s3_requests_executed"], 0)
        self.assertEqual(impl["wallet_feature_rows_created"], 0)
        self.assertIsNone(impl["empirical_result"])
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

    def test_exact_lineage_scope_and_caps(self) -> None:
        impl = self.load("R9_IMPLEMENTATION_CONTRACT.json")
        self.assertEqual(impl["r9_preregistration_merge_commit"], "62ce0009c3c4aad70d2a91f242a690cd26ace355")
        self.assertEqual(impl["approval_merge_commit"], "332aa535b0de19a18befb8529450ae88acf35762")
        self.assertEqual(impl["approval_text_sha256"], "1e4642ef2eef660f7971c2632864cf78894340e3408f15d15597e4eb12a04330")
        self.assertEqual(impl["object"]["key"], "node_fills_by_block/hourly/20250727/8.lz4")
        self.assertEqual(impl["object"]["expected_size_bytes"], 1517603)
        self.assertEqual(impl["object"]["expected_top_level_block_record_count"], 4345)
        self.assertEqual(impl["object"]["expected_valid_event_pair_count"], 17516)
        self.assertEqual(impl["maximum_get_object_requests"], 1)
        self.assertEqual(impl["maximum_retries_per_request"], 0)
        self.assertEqual(impl["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(impl["maximum_monthly_budget_eur"], 0)

    def test_future_retention_matches_approved_aggregate_only_output(self) -> None:
        impl = self.load("R9_IMPLEMENTATION_CONTRACT.json")
        self.assertEqual(impl["selected_fill_fields_processed_transiently"], [
            "coin", "side", "time", "px", "sz", "closedPnl", "tid", "crossed", "liquidation"
        ])
        self.assertEqual(impl["wallet_feature_fields_only"], [
            "wallet_address", "fill_count", "first_fill_time", "last_fill_time", "distinct_coin_count",
            "side_a_count", "side_b_count", "crossed_true_count", "liquidation_associated_fill_count",
            "duplicate_tid_count", "sum_abs_px_times_sz_notional_proxy", "sum_closed_pnl_fill_statistic",
        ])
        self.assertEqual(impl["wallet_address_normalization"], "LOWERCASE_EXACT_0X40HEX")
        self.assertEqual(impl["decimal_output_encoding"], "CANONICAL_BASE10_STRING_NO_EXPONENT")
        self.assertTrue(all(value is True for value in impl["future_release_retention_authorizations"].values()))
        self.assertTrue(all(value is False for value in impl["forbidden_retention_authorizations"].values()))
        self.assertTrue(all(value is False for value in impl["semantic_boundaries"].values()))
        self.assertTrue(all(value is False for value in impl["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in impl["trading_authorizations"].values()))

    def test_role_is_reused_without_iam_mutation(self) -> None:
        impl = self.load("R9_IMPLEMENTATION_CONTRACT.json")
        reuse = self.load("R9_AWS_ROLE_REUSE_ANALYSIS.json")
        role = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
        self.assertEqual(impl["reused_dedicated_role_arn"], role)
        self.assertEqual(reuse["reused_role_arn"], role)
        self.assertFalse(reuse["new_sts_preflight_required"])
        self.assertFalse(reuse["aws_iam_mutation_required"])
        self.assertFalse(reuse["aws_iam_mutation_authorized"])
        self.assertFalse(reuse["aws_iam_mutation_performed"])
        self.assertFalse(reuse["persistent_role_scope_expanded"])
        self.assertEqual(reuse["r9_session_scope"]["allowed_actions"], ["s3:GetObject"])
        self.assertEqual(reuse["r9_session_scope"]["allowed_object_arns"], [
            "arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/8.lz4"
        ])

    def test_dedicated_implementation_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r9_implementation.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R9_IMPLEMENTATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
