from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
DATA = BASE / "r10_data_execution"
CONTRACT = DATA / "R10_DATA_WORKFLOW_IMPLEMENTATION_CONTRACT.json"
SOURCE = BASE / "r10_implementation/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml"
PREFLIGHT = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-role-preflight-r10.yml"

SOURCE_SHA = "89d44c623cb2352d691bccbed1932107050f4a66606e9a23146c492bbf65e0f6"
WORKFLOW_SHA = "4d3b85c01a5f529e16e8516a47e83931521438e978a17fdabdf8397b0f0c275e"


class R10DataWorkflowImplementationTests(unittest.TestCase):
    @staticmethod
    def load() -> dict:
        return json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_stage_is_installed_but_not_released(self) -> None:
        c = self.load()
        self.assertEqual(c["status"], "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE")
        self.assertTrue(c["execution_release_required"])
        self.assertFalse(c["execution_release_candidate_present"])
        self.assertTrue(c["canonical_activation_required"])
        self.assertFalse(c["canonical_activation_present"])
        self.assertFalse(c["single_workflow_dispatch_authorized"])
        self.assertFalse(c["aws_oidc_authorized_now"])
        self.assertFalse(c["get_object_authorized_now"])
        self.assertFalse(c["rerun_authorized"])
        self.assertEqual(c["s3_requests_executed_by_this_stage"], 0)
        self.assertEqual(c["object_bytes_downloaded_by_this_stage"], 0)
        self.assertIsNone(c["empirical_result"])

    def test_frozen_candidate_is_immutable_and_binding_adjustment_is_nonexpanding(self) -> None:
        c = self.load()
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(), SOURCE_SHA)
        self.assertEqual(c["source_frozen_data_workflow_candidate_sha256"], SOURCE_SHA)
        self.assertEqual(hashlib.sha256(WORKFLOW.read_bytes()).hexdigest(), WORKFLOW_SHA)
        self.assertEqual(c["installed_data_workflow_sha256"], WORKFLOW_SHA)
        self.assertTrue(c["candidate_binding_adjustment"]["required"])
        self.assertFalse(c["candidate_binding_adjustment"]["scope_expanding"])
        self.assertTrue(c["candidate_binding_adjustment"]["source_candidate_immutable"])

    def test_consumed_preflight_route_is_retained_fail_closed_and_data_route_is_installed(self) -> None:
        self.assertTrue(PREFLIGHT.is_file())
        self.assertEqual(hashlib.sha256(PREFLIGHT.read_bytes()).hexdigest(), "fefef8a7bb40e965c9ed77e9892057ac8e0a64dcfa60d7f3e7dba8f1651b5f4d")
        self.assertTrue(WORKFLOW.is_file())
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("id-token: write", text)
        self.assertIn("role-duration-seconds: 900", text)
        self.assertIn("R10_STS_PREFLIGHT_RELEASE_CONSUMPTION.json", text)
        self.assertIn("HL-ARCHIVE-R10-DEDICATED-ROLE-STS-PREFLIGHT-001-ATTESTATION.json", text)
        self.assertEqual(text.count("s3:GetObject"), 1)
        self.assertNotIn("aws s3", text)
        self.assertNotIn("aws s3api", text)

    def test_exact_six_object_and_budget_envelope_is_unchanged(self) -> None:
        c = self.load()
        env = c["execution_envelope"]
        self.assertEqual(env["maximum_get_object_requests"], 6)
        self.assertEqual(env["maximum_requests_per_object"], 1)
        self.assertEqual(env["maximum_total_compressed_bytes"], 120999698)
        self.assertEqual(env["maximum_total_decompressed_bytes"], 1073741824)
        self.assertEqual(env["maximum_retries_per_request"], 0)
        self.assertEqual(env["selected_hour_count"], 6)
        self.assertEqual(c["session_scope"]["allowed_s3_actions_only"], ["s3:GetObject"])
        self.assertEqual(c["session_scope"]["allowed_object_count"], 6)
        self.assertEqual(len(c["session_scope"]["exact_object_arns"]), 6)

    def test_downstream_and_trading_authority_remains_closed(self) -> None:
        c = self.load()
        self.assertTrue(all(value is False for value in c["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in c["trading_authorizations"].values()))

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10_data_workflow.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R10_DATA_WORKFLOW_IMPLEMENTATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
