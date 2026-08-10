from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CANDIDATE = BASE / "r11_data_execution/R11_EXECUTION_RELEASE_CANDIDATE.json"
RUNTIME_RELEASE = BASE / "r11_runtime/R11_EXECUTION_RELEASE.json"


class R11DataExecutionReleaseCandidateTests(unittest.TestCase):
    @staticmethod
    def load() -> dict:
        return json.loads(CANDIDATE.read_text(encoding="utf-8"))

    def test_candidate_is_inert_and_requires_separate_activation(self) -> None:
        c = self.load()
        self.assertEqual(c["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertEqual(c["data_workflow_implementation_merge_commit"], "932b39d45acccc83cc7bf55d3dc29cb8b51a12cd")
        self.assertTrue(c["canonical_activation_required"])
        self.assertFalse(c["canonical_activation_present"])
        self.assertIsNone(c["single_use_window_start_utc"])
        self.assertIsNone(c["anchor_commit"])
        self.assertFalse(c["single_workflow_dispatch_authorized"])
        self.assertFalse(c["rerun_authorized"])
        self.assertFalse(c["release_consumed"])
        self.assertFalse(c["aws_oidc_authorized"])
        self.assertFalse(c["get_object_authorized"])
        self.assertFalse(c["wallet_feature_retention_authorized"])
        self.assertIsNone(c["empirical_result"])

    def test_candidate_preserves_exact_72_hour_budget_and_transport_envelope(self) -> None:
        c = self.load()
        env = c["execution_envelope"]
        self.assertEqual(c["selected_object_count"], 72)
        self.assertEqual(c["selection_sha256"], "7c134f4b62f547904126a5f810c177484dceeffa246d53c5c35944367d563eb2")
        self.assertEqual(env["maximum_get_object_requests"], 72)
        self.assertEqual(env["maximum_requests_per_object"], 1)
        self.assertEqual(env["maximum_total_compressed_bytes"], 2107738436)
        self.assertEqual(env["maximum_individual_compressed_bytes"], 76616104)
        self.assertEqual(env["maximum_total_decompressed_bytes"], 17179869184)
        self.assertEqual(env["maximum_individual_decompressed_bytes"], 536870912)
        self.assertEqual(env["maximum_runtime_seconds"], 5400)
        self.assertEqual(env["maximum_retries_per_request"], 0)
        self.assertTrue(env["requester_pays_required"])
        self.assertTrue(env["if_match_etag_required"])
        self.assertTrue(env["stop_after_first_failed_or_mismatched_object"])
        self.assertEqual(env["window_start_utc"], "2025-07-28T00:00:00Z")
        self.assertEqual(env["window_end_exclusive_utc"], "2025-07-31T00:00:00Z")

    def test_candidate_preserves_exact_role_intersection_and_record_rule(self) -> None:
        c = self.load()
        scope = c["session_scope"]
        self.assertEqual(scope["allowed_s3_actions_only"], ["s3:GetObject"])
        self.assertEqual(scope["persistent_exact_object_count"], 72)
        self.assertTrue(scope["persistent_permission_must_equal_exact_selection"])
        self.assertEqual(len(scope["session_intersection_resource_arns"]), 3)
        self.assertEqual(c["record_anchored_rule_id"], "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1")
        self.assertFalse(c["numeric_tolerance_authorized"])

    def test_no_ranking_copyability_semantic_or_trading_authority_is_opened(self) -> None:
        c = self.load()
        self.assertTrue(all(value is False for value in c["semantic_boundaries"].values()))
        self.assertTrue(all(value is False for value in c["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in c["trading_authorizations"].values()))
        self.assertEqual(c["network_requests_executed_by_this_candidate"], 0)
        self.assertEqual(c["s3_requests_executed_by_this_candidate"], 0)
        self.assertEqual(c["object_bytes_downloaded_by_this_candidate"], 0)
        self.assertEqual(c["wallet_feature_rows_created_by_this_candidate"], 0)

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r11_data_execution_release_candidate.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R11_DATA_EXECUTION_RELEASE_CANDIDATE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
