from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RUN = BASE / "r10c_evidence/run-31410638224"
ATTEST = BASE / "r10c_evidence/HL-ARCHIVE-R10C-BOUNDARY-RECORD-CORRELATION-001-ATTESTATION.json"
CONSUMPTION = BASE / "r10c_runtime/R10C_EXECUTION_RELEASE_CONSUMPTION.json"
RESULT = "EXACT_TWO_PRE_HOUR_FILLS_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD"


class R10CExecutionEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads((RUN / "r10c-result.json").read_text())
        cls.attest = json.loads(ATTEST.read_text())
        cls.consumption = json.loads(CONSUMPTION.read_text())

    def test_exact_run_artifact_and_terminal_result_are_bound(self) -> None:
        v = json.loads((RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json").read_text())
        self.assertEqual(v["workflow_run_id"], 31410638224)
        self.assertEqual(v["workflow_job_id"], 93527564608)
        self.assertEqual(v["artifact_id"], 9071422220)
        self.assertEqual(v["provider_zip_sha256"], "60602f1e5b4e5456504af9bbd65b64826cdf2b86a47bc1b2e690507dbf0a0f48")
        self.assertTrue(v["provider_digest_matches_independent_download"])
        self.assertEqual(self.result["technical_result"], RESULT)
        self.assertEqual(self.result["terminal_status"], "R10C_BOUNDARY_RECORD_CORRELATION_COMPLETE")

    def test_two_pre_hour_fills_exactly_colocate_with_one_cross_prefix_record(self) -> None:
        s = self.result["diagnostic_summary"]
        cross = "MATCHES_PATH_DATE_HOUR_PREFIX|MATCHES_PREVIOUS_DATE_HOUR_PREFIX"
        self.assertEqual(s["block_record_count"], 36029)
        self.assertEqual(s["fill_time_count"], 223950)
        self.assertEqual(s["fill_time_before_path_hour_count"], 2)
        self.assertEqual(s["fill_time_inside_path_hour_count"], 223948)
        self.assertEqual(s["fill_time_after_path_hour_count"], 0)
        self.assertEqual(s["block_record_count_with_any_before_fill"], 1)
        self.assertEqual(s["block_record_counts_by_local_prefix_and_block_prefix"][cross], 1)
        self.assertEqual(s["block_records_with_before_fill_by_local_prefix_and_block_prefix"][cross], 1)
        self.assertEqual(s["fill_counts_by_local_prefix_block_prefix_and_fill_partition"][cross + "|BEFORE_PATH_HOUR"], 2)
        self.assertTrue(self.attest["claims_proven"]["both_pre_hour_fills_colocate_in_that_single_cross_prefix_record"])

    def test_result_remains_aggregate_and_nonsemantic(self) -> None:
        self.assertTrue(self.result["aggregate_boundary_correlation_retained"])
        self.assertTrue(self.result["event_array_contents_inspected"])
        self.assertTrue(self.result["fill_time_processing_performed"])
        for key in (
            "individual_metadata_value_retained", "individual_fill_time_retained", "wallet_address_retained",
            "wallet_aggregation_performed", "economic_fill_field_processing_performed", "block_number_value_retained",
            "per_block_identity_retained", "raw_compressed_object_retained", "raw_decompressed_object_retained",
            "raw_block_record_retained", "raw_event_pair_retained",
        ):
            self.assertFalse(self.result[key], key)
        self.assertFalse(self.attest["claims_not_proven"]["local_time_timezone_semantics"])
        self.assertFalse(self.attest["claims_not_proven"]["block_time_timezone_semantics"])
        self.assertFalse(self.attest["claims_not_proven"]["cross_prefix_pattern_generalizes_to_other_hours_or_dates"])
        self.assertFalse(self.attest["claims_not_proven"]["a_51ms_fill_time_tolerance_is_safe_for_general_history"])

    def test_release_is_consumed_and_no_downstream_authority_opens(self) -> None:
        self.assertTrue(self.consumption["release_consumed"])
        self.assertFalse(self.consumption["future_r10c_dispatch_authorized"])
        self.assertFalse(self.consumption["rerun_authorized"])
        self.assertEqual(self.consumption["remaining_get_object_budget_from_consumed_release"], 0)
        self.assertTrue(self.consumption["new_network_request_requires_new_preregistration_approval_and_release"])
        self.assertTrue(all(v is False for v in self.consumption["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in self.consumption["trading_authorizations"].values()))

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, "governance/validate_r10c_execution_evidence.py"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10C_EXECUTION_EVIDENCE_VALID_" + RESULT, done.stdout)


if __name__ == "__main__":
    unittest.main()
