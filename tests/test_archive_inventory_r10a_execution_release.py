from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"research/archive_inventory"
RELEASE=BASE/"r10a_runtime/R10A_EXECUTION_RELEASE.json"
CANDIDATE=BASE/"r10a_runtime/R10A_EXECUTION_RELEASE_CANDIDATE.json"


class R10AExecutionReleaseTests(unittest.TestCase):
    def load(self,path:Path)->dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exactly_one_r10a_run_is_open_without_rerun(self)->None:
        r=self.load(RELEASE)
        self.assertEqual(r["status"],"RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10A_RUN")
        self.assertTrue(r["single_workflow_dispatch_authorized"])
        self.assertFalse(r["rerun_authorized"])
        self.assertFalse(r["release_consumed"])
        self.assertEqual(r["maximum_get_object_requests"],1)
        self.assertEqual(r["maximum_requests_per_object"],1)
        self.assertEqual(r["maximum_retries_per_request"],0)

    def test_activation_opens_only_timestamp_diagnostic_scope(self)->None:
        r=self.load(RELEASE)
        self.assertTrue(r["requester_pays_authorized"])
        self.assertTrue(r["get_object_authorized"])
        self.assertTrue(r["decompression_authorized"])
        self.assertTrue(r["timestamp_processing_authorized"])
        self.assertTrue(r["aggregate_alignment_retention_authorized"])
        self.assertFalse(r["wallet_address_retention_authorized"])
        self.assertFalse(r["wallet_aggregation_authorized"])
        self.assertFalse(r["economic_fill_field_processing_authorized"])
        self.assertFalse(r["timezone_inference_for_local_time_authorized"])
        self.assertTrue(all(v is False for v in r["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in r["trading_authorizations"].values()))

    def test_candidate_remains_immutable_inert_snapshot(self)->None:
        c=self.load(CANDIDATE)
        self.assertEqual(c["status"],"RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertFalse(c["canonical_activation_present"])
        self.assertFalse(c["single_workflow_dispatch_authorized"])
        self.assertFalse(c["get_object_authorized"])

    def test_dedicated_validator_passes(self)->None:
        done=subprocess.run([sys.executable,str(ROOT/"governance/validate_r10a_execution_release.py")],cwd=ROOT,capture_output=True,text=True,check=False)
        self.assertEqual(done.returncode,0,done.stdout+done.stderr)
        self.assertIn("R10A_EXECUTION_RELEASE_VALID",done.stdout)


if __name__=="__main__": unittest.main()
