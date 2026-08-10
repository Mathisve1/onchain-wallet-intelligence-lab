from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
R10A = BASE / "r10a"
CONTRACT = R10A / "R10A_TIMESTAMP_PARTITION_PREREGISTRATION.json"


class R10ATimestampPartitionPreregistrationTests(unittest.TestCase):
    @staticmethod
    def load() -> dict:
        return json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_parent_is_exact_consumed_unresolved_r10_run(self) -> None:
        c = self.load()
        self.assertEqual(c["parent_r10_unresolved_evidence_merge_commit"], "18dbd816bbc33979261247825a5133ee48874d51")
        self.assertEqual(c["parent_r10_run_id"], 31377732916)
        self.assertEqual(c["parent_r10_research_conclusion"], "MULTI_HOUR_FEATURE_PIPELINE_UNRESOLVED")
        self.assertEqual(c["parent_r10_failure_class"], "fill time lies outside source path hour")
        self.assertTrue(c["parent_r10_release_consumed"])
        self.assertFalse(c["parent_r10_rerun_authorized"])
        self.assertEqual(c["parent_r10_wallet_feature_rows_retained"], 0)

    def test_future_request_is_exactly_one_same_hour9_object(self) -> None:
        c = self.load()
        t = c["exact_future_network_target"]
        self.assertEqual(t["key"], "node_fills_by_block/hourly/20250727/9.lz4")
        self.assertEqual(t["path_hour_utc"], "2025-07-27T09:00:00Z")
        self.assertEqual(t["expected_size_bytes"], 18147822)
        self.assertEqual(t["expected_etag"], '"5a9941a240118a57f77a4c3ee95b8430-3"')
        e = c["proposed_request_envelope"]
        self.assertEqual(e["maximum_get_object_requests"], 1)
        self.assertEqual(e["maximum_requests_per_object"], 1)
        self.assertEqual(e["maximum_retries_per_request"], 0)
        self.assertEqual(e["maximum_total_compressed_bytes"], 18147822)
        self.assertEqual(e["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(e["maximum_monthly_budget_eur"], 0)

    def test_diagnostic_retains_aggregate_timing_only(self) -> None:
        c = self.load()
        ts = c["timestamp_processing_rules"]
        self.assertFalse(ts["individual_timestamp_retention_authorized"])
        self.assertFalse(ts["individual_wallet_address_retention_authorized"])
        self.assertFalse(ts["economic_fill_field_processing_authorized"])
        self.assertFalse(ts["wallet_aggregation_authorized"])
        self.assertFalse(ts["timezone_inference_for_local_time_authorized"])
        retained = set(c["retained_aggregate_fields_only"])
        self.assertIn("fill_time_path_hour_offset_histogram", retained)
        self.assertIn("block_time_path_hour_offset_histogram", retained)
        self.assertIn("fill_minus_block_time_delta_histogram", retained)
        self.assertIn("alignment_classification", retained)
        self.assertNotIn("wallet_address", retained)
        self.assertNotIn("closedPnl", retained)
        self.assertTrue(all(value is False for value in c["raw_or_disallowed_retention"].values()))

    def test_existing_role_is_only_proposed_for_narrower_reuse_without_mutation(self) -> None:
        c = self.load()
        iam = c["iam_boundary"]
        self.assertTrue(iam["existing_dedicated_r10_role_reuse_proposed"])
        self.assertFalse(iam["existing_dedicated_r10_role_reuse_authorized_now"])
        self.assertFalse(iam["existing_dedicated_r10_role_mutation_authorized"])
        self.assertFalse(iam["new_role_creation_authorized"])
        self.assertEqual(iam["future_session_policy_allowed_actions_only"], ["s3:GetObject"])
        self.assertEqual(iam["future_session_policy_allowed_object_count"], 1)

    def test_preregistration_opens_zero_runtime_or_downstream_authority(self) -> None:
        c = self.load()
        self.assertEqual(c["status"], "PREREGISTERED_NO_EXECUTION")
        self.assertTrue(all(value is False for value in c["current_runtime_authority"].values()))
        self.assertTrue(all(value is False for value in c["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in c["trading_authorizations"].values()))
        self.assertEqual(c["network_requests_executed_by_preregistration"], 0)
        self.assertEqual(c["aws_iam_mutations_executed_by_preregistration"], 0)
        self.assertIsNone(c["empirical_result"])

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10a_timestamp_partition_preregistration.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R10A_TIMESTAMP_PARTITION_PREREGISTRATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
