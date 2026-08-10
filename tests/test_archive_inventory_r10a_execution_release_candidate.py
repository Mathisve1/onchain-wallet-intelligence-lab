from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CANDIDATE = BASE / "r10a_runtime/R10A_EXECUTION_RELEASE_CANDIDATE.json"


class R10AExecutionReleaseCandidateTests(unittest.TestCase):
    def load(self) -> dict:
        return json.loads(CANDIDATE.read_text(encoding="utf-8"))

    def test_candidate_is_inert_and_separate_from_activation(self) -> None:
        c = self.load()
        self.assertEqual(c["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertTrue(c["canonical_activation_required"])
        self.assertFalse(c["canonical_activation_present"])
        self.assertIsNone(c["single_use_window_start_utc"])
        self.assertFalse(c["single_workflow_dispatch_authorized"])
        self.assertFalse(c["aws_oidc_authorized"])
        self.assertFalse(c["get_object_authorized"])
        self.assertFalse(c["release_consumed"])
        self.assertFalse(c["rerun_authorized"])

    def test_candidate_scope_is_exact_one_object_and_aggregate_timing_only(self) -> None:
        c = self.load()
        self.assertEqual(c["execution_envelope"]["maximum_get_object_requests"], 1)
        self.assertEqual(c["execution_envelope"]["maximum_retries_per_request"], 0)
        self.assertEqual(c["exact_network_target"]["key"], "node_fills_by_block/hourly/20250727/9.lz4")
        p = c["future_processing_authority_if_separately_activated"]
        self.assertTrue(p["timestamp_processing"])
        self.assertTrue(p["aggregate_alignment_retention"])
        self.assertFalse(p["wallet_address_retention"])
        self.assertFalse(p["wallet_aggregation"])
        self.assertFalse(p["economic_fill_field_processing"])
        self.assertTrue(all(v is False for v in c["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in c["trading_authorizations"].values()))

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10a_execution_release_candidate.py")],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10A_EXECUTION_RELEASE_CANDIDATE_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
