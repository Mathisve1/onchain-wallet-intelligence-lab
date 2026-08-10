from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CONTRACT = BASE / "r10d/R10D_RECORD_ANCHORED_BOUNDARY_REPAIR_PREREGISTRATION.json"


class R10DRecordAnchoredBoundaryRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.c = json.loads(CONTRACT.read_text())

    def test_exact_consumed_r10_and_r10c_lineage_is_bound(self) -> None:
        self.assertEqual(self.c["parent_r10_run_id"], 31377732916)
        self.assertEqual(self.c["parent_r10_result"], "MULTI_HOUR_FEATURE_PIPELINE_UNRESOLVED")
        self.assertEqual(self.c["parent_r10_failure_class"], "fill time lies outside source path hour")
        self.assertTrue(self.c["parent_r10_release_consumed"])
        self.assertFalse(self.c["parent_r10_rerun_authorized"])
        self.assertEqual(self.c["parent_r10c_evidence_merge_commit"], "83842a3947e8eec518fa4a05ca71a2b81079976b")
        self.assertEqual(self.c["parent_r10c_result"], "EXACT_TWO_PRE_HOUR_FILLS_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD")

    def test_repair_uses_record_anchor_and_no_numeric_tolerance(self) -> None:
        rule = self.c["record_anchored_alignment_rule"]
        self.assertTrue(rule["local_time_raw_prefix_must_match_source_path_hour_for_every_record"])
        self.assertEqual(rule["block_time_raw_prefix_allowed_buckets"], ["MATCHES_PATH_DATE_HOUR_PREFIX","MATCHES_PREVIOUS_DATE_HOUR_PREFIX"])
        self.assertTrue(rule["block_time_next_or_other_prefix_is_fail_closed"])
        self.assertFalse(rule["numeric_tolerance_authorized"])
        self.assertIsNone(rule["fill_time_numeric_tolerance_milliseconds"])
        self.assertEqual(rule["path_block_record_allowed_fill_partitions"], ["INSIDE_PATH_HOUR"])
        self.assertEqual(rule["previous_block_record_allowed_fill_partitions"], ["BEFORE_PATH_HOUR"])
        self.assertEqual(rule["after_path_hour_fill_count_required_for_success"], 0)
        self.assertFalse(rule["hours10_to14_boundary_pattern_predeclared"])

    def test_future_scope_is_same_six_r10_objects_and_budget(self) -> None:
        self.assertEqual(len(self.c["exact_future_network_targets"]), 6)
        env = self.c["proposed_request_envelope"]
        self.assertEqual(env["maximum_get_object_requests"], 6)
        self.assertEqual(env["maximum_retries_per_request"], 0)
        self.assertEqual(env["maximum_one_time_budget_eur"], 0.10)
        self.assertTrue(env["stop_after_first_failed_or_mismatched_object"])
        self.assertFalse(env["head_object_authorized"])
        self.assertFalse(env["list_objects_v2_authorized"])

    def test_wallet_feature_mechanics_are_proposed_but_ranking_and_trading_closed(self) -> None:
        self.assertTrue(self.c["unchanged_r10_feature_contract"]["selected_fill_field_processing_unchanged_from_r10"])
        self.assertIn("wallet_address", self.c["unchanged_r10_feature_contract"]["proposed_per_wallet_output_fields_only"])
        self.assertFalse(self.c["downstream_authorizations"]["wallet_ranking"])
        self.assertFalse(self.c["downstream_authorizations"]["candidate_shortlisting"])
        self.assertFalse(self.c["downstream_authorizations"]["pnl_or_alpha_analysis"])
        self.assertTrue(all(v is False for v in self.c["trading_authorizations"].values()))

    def test_preregistration_opens_zero_runtime_authority(self) -> None:
        self.assertEqual(self.c["status"], "PREREGISTERED_NO_EXECUTION")
        self.assertTrue(all(v is False for v in self.c["current_runtime_authority"].values()))
        self.assertEqual(self.c["network_requests_executed_by_preregistration"], 0)
        self.assertEqual(self.c["wallet_feature_rows_created_by_preregistration"], 0)
        self.assertTrue(self.c["human_approval_required_before_implementation"])
        self.assertTrue(self.c["separate_execution_release_required"])
        self.assertTrue(self.c["separate_canonical_activation_required"])

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, "governance/validate_r10d_record_anchored_boundary_repair_preregistration.py"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10D_RECORD_ANCHORED_BOUNDARY_REPAIR_PREREGISTRATION_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
