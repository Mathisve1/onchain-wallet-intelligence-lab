from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
ATTEST = BASE / "r10d_evidence/HL-ARCHIVE-R10D-RECORD-ANCHORED-MULTI-HOUR-FEATURE-REPAIR-001-ATTESTATION.json"
CONSUMPTION = BASE / "r10d_runtime/R10D_EXECUTION_RELEASE_CONSUMPTION.json"
DIAG = BASE / "r10d_evidence/R10D_AGGREGATE_DIAGNOSTICS.json"

class R10DExecutionEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.a=json.loads(ATTEST.read_text())
        cls.c=json.loads(CONSUMPTION.read_text())
        cls.d=json.loads(DIAG.read_text())

    def test_exact_successful_six_hour_result_is_attested(self) -> None:
        self.assertEqual(self.a["status"], "ATTESTED_COMPLETE_R10D_MULTI_HOUR_FEATURE_PIPELINE")
        self.assertEqual(self.a["workflow_run_id"], 31420197671)
        self.assertEqual(self.a["workflow_job_id"], 93558813495)
        self.assertEqual(self.a["artifact_id"], 9075129362)
        self.assertEqual(self.a["technical_result"], "R10D_MULTI_HOUR_FEATURE_PIPELINE_COMPLETE")
        self.assertEqual(self.a["exact_execution_summary"]["completed_hour_count"], 6)
        self.assertEqual(self.a["exact_execution_summary"]["successful_get_object_requests"], 6)

    def test_record_anchored_rule_passed_without_numeric_tolerance(self) -> None:
        self.assertEqual(self.a["record_anchored_rule_id"], "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1")
        self.assertFalse(self.a["numeric_tolerance_authorized"])
        self.assertTrue(all(h["record_anchored_alignment_violation_count"] == 0 for h in self.a["per_hour_summaries"]))
        self.assertTrue(all(h["fill_time_after_path_hour_count"] == 0 for h in self.a["per_hour_summaries"]))

    def test_wallet_feature_output_is_mechanics_evidence_not_ranking(self) -> None:
        self.assertEqual(self.d["wallet_feature_row_count"], 16410)
        self.assertEqual(self.d["sum_fill_count"], 1486542)
        self.assertEqual(self.d["sum_fill_count"], self.d["sum_side_count"])
        self.assertEqual(self.d["duplicate_tid_count_total"], 0)
        self.assertTrue(all(v is False for v in self.d["interpretation_boundaries"].values()))
        self.assertTrue(all(v is False for v in self.d["downstream_actions_performed"].values()))

    def test_release_is_consumed_and_rerun_closed(self) -> None:
        self.assertTrue(self.c["release_consumed"])
        self.assertFalse(self.c["future_r10d_dispatch_authorized"])
        self.assertFalse(self.c["rerun_authorized"])
        self.assertEqual(self.c["remaining_get_object_budget_from_consumed_release"], 0)
        self.assertTrue(self.c["new_network_request_requires_new_preregistration_approval_and_release"])
        self.assertTrue(all(v is False for v in self.c["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in self.c["trading_authorizations"].values()))

    def test_dedicated_validator_passes(self) -> None:
        done=subprocess.run([sys.executable,"governance/validate_r10d_execution_evidence.py"],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(done.returncode,0,done.stdout+done.stderr)
        self.assertIn("R10D_EXECUTION_EVIDENCE_VALID_MULTI_HOUR_FEATURE_PIPELINE_COMPLETE",done.stdout)

if __name__ == "__main__":
    unittest.main()
