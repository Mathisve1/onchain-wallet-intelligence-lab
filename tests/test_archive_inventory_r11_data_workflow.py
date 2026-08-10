from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CONTRACT = BASE / "r11_data_execution/R11_DATA_WORKFLOW_IMPLEMENTATION_CONTRACT.json"
SOURCE = BASE / "r11_implementation/workflows/hyperliquid-archive-r11-72h-persistence.yml"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11-72h-persistence.yml"


class R11DataWorkflowTests(unittest.TestCase):
    @staticmethod
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r11_data_workflow.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R11_DATA_WORKFLOW_IMPLEMENTATION_VALID", completed.stdout)

    def test_installed_workflow_is_byte_exact_frozen_candidate(self) -> None:
        self.assertTrue(WORKFLOW.is_file())
        self.assertEqual(WORKFLOW.read_bytes(), SOURCE.read_bytes())

    def test_stage_is_inert_after_consumed_sts_preflight(self) -> None:
        c = self.load(CONTRACT)
        self.assertEqual(c["status"], "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE")
        self.assertEqual(c["r11_sts_preflight_evidence_merge_commit"], "db935f6c44639ba2a2fa66d8c1b4d0d1d26b254a")
        self.assertTrue(c["preflight_release_consumed"])
        self.assertTrue(c["execution_release_required"])
        self.assertFalse(c["execution_release_candidate_present"])
        self.assertTrue(c["canonical_activation_required"])
        self.assertFalse(c["canonical_activation_present"])
        self.assertFalse(c["single_workflow_dispatch_authorized"])
        self.assertFalse(c["rerun_authorized"])
        for key in (
            "aws_oidc_authorized_now",
            "requester_pays_authorized_now",
            "get_object_authorized_now",
            "object_body_download_authorized_now",
            "decompression_authorized_now",
            "selected_fill_field_processing_authorized_now",
            "wallet_feature_retention_authorized_now",
        ):
            self.assertFalse(c[key], key)
        self.assertEqual(c["s3_requests_executed_by_this_stage"], 0)
        self.assertEqual(c["object_bytes_downloaded_by_this_stage"], 0)
        self.assertEqual(c["wallet_feature_rows_created_by_this_stage"], 0)
        self.assertTrue(all(v is False for v in c["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in c["trading_authorizations"].values()))

    def test_exact_approved_72_hour_envelope_and_session_intersection(self) -> None:
        c = self.load(CONTRACT)
        env = c["execution_envelope"]
        self.assertEqual(env["maximum_get_object_requests"], 72)
        self.assertEqual(env["maximum_requests_per_object"], 1)
        self.assertEqual(env["maximum_retries_per_request"], 0)
        self.assertEqual(env["maximum_one_time_budget_eur"], 0.50)
        self.assertEqual(env["maximum_monthly_budget_eur"], 0)
        self.assertEqual(env["maximum_total_compressed_bytes"], 2107738436)
        self.assertEqual(env["maximum_total_decompressed_bytes"], 17179869184)
        self.assertEqual(env["maximum_runtime_seconds"], 5400)
        self.assertEqual(env["selected_hour_count"], 72)
        self.assertEqual(env["window_start_utc"], "2025-07-28T00:00:00Z")
        self.assertEqual(env["window_end_exclusive_utc"], "2025-07-31T00:00:00Z")
        scope = c["session_scope"]
        self.assertEqual(scope["allowed_s3_actions_only"], ["s3:GetObject"])
        self.assertEqual(scope["persistent_exact_object_count"], 72)
        self.assertTrue(scope["persistent_permission_must_equal_exact_selection"])
        self.assertEqual(len(scope["session_intersection_resource_arns"]), 3)
        self.assertTrue(all(arn.endswith("/*") for arn in scope["session_intersection_resource_arns"]))

    def test_workflow_cannot_self_execute_without_separate_release(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("R11_EXECUTION_RELEASE.json", text)
        self.assertIn("RELEASED_FOR_EXACTLY_ONE_CANONICAL_R11_RUN", text)
        self.assertIn("rerun_authorized", text)
        self.assertIn("release_consumed", text)
        self.assertIn("role-duration-seconds: 7200", text)
        self.assertIn("research.archive_inventory.r11_implementation.collector", text)
        self.assertIn("r11-wallet-features.ndjson", text)
        self.assertNotIn("aws s3 ", text.lower())
        self.assertNotIn("aws s3api ", text.lower())
        self.assertIn("wallet_ranking_performed", text)
        self.assertIn("pnl_or_alpha_analysis_performed", text)
        self.assertIn("copyability_analysis_performed", text)


if __name__ == "__main__":
    unittest.main()
