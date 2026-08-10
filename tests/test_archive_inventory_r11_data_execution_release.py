from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RELEASE = BASE / "r11_runtime/R11_EXECUTION_RELEASE.json"
CANDIDATE = BASE / "r11_data_execution/R11_EXECUTION_RELEASE_CANDIDATE.json"
IMPLEMENTATION = BASE / "r11_data_execution/R11_DATA_WORKFLOW_IMPLEMENTATION_CONTRACT.json"


class R11DataExecutionReleaseTests(unittest.TestCase):
    @staticmethod
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exactly_one_canonical_r11_run_is_released_without_rerun(self) -> None:
        r = self.load(RELEASE)
        self.assertEqual(r["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R11_RUN")
        self.assertEqual(r["release_candidate_merge_commit"], "0cf741d7bf853598e293936648d2fdc9a27975a1")
        self.assertEqual(r["activation_base_commit"], "0cf741d7bf853598e293936648d2fdc9a27975a1")
        self.assertEqual(r["single_use_window_start_utc"], "2026-08-10T21:57:00Z")
        self.assertTrue(r["canonical_activation_present"])
        self.assertTrue(r["single_workflow_dispatch_authorized"])
        self.assertFalse(r["rerun_authorized"])
        self.assertFalse(r["release_consumed"])

    def test_activation_opens_only_exact_approved_runtime_mechanics(self) -> None:
        r = self.load(RELEASE)
        for key in (
            "aws_oidc_authorized", "requester_pays_authorized", "get_object_authorized",
            "object_body_download_authorized", "decompression_authorized",
            "selected_fill_field_processing_authorized", "wallet_feature_retention_authorized",
        ):
            self.assertTrue(r[key], key)
        for key in (
            "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
            "list_object_versions_authorized", "list_all_my_buckets_authorized",
            "get_object_attributes_authorized", "get_object_version_authorized",
            "http_redirect_following_authorized",
        ):
            self.assertFalse(r[key], key)
        self.assertEqual(r["network_requests_executed_by_activation"], 0)
        self.assertEqual(r["s3_requests_executed_by_activation"], 0)
        self.assertEqual(r["object_bytes_downloaded_by_activation"], 0)
        self.assertEqual(r["wallet_feature_rows_created_by_activation"], 0)

    def test_exact_72_hour_caps_role_intersection_and_record_rule(self) -> None:
        r = self.load(RELEASE)
        self.assertEqual(r["selected_object_count"], 72)
        self.assertEqual(r["maximum_one_time_budget_eur"], 0.50)
        self.assertEqual(r["maximum_monthly_budget_eur"], 0)
        self.assertEqual(r["maximum_get_object_requests"], 72)
        self.assertEqual(r["maximum_requests_per_object"], 1)
        self.assertEqual(r["maximum_retries_per_request"], 0)
        self.assertEqual(r["maximum_total_compressed_bytes"], 2107738436)
        self.assertEqual(r["maximum_individual_compressed_bytes"], 76616104)
        self.assertEqual(r["maximum_total_decompressed_bytes"], 17179869184)
        self.assertEqual(r["maximum_individual_decompressed_bytes"], 536870912)
        self.assertEqual(r["maximum_runtime_seconds"], 5400)
        self.assertEqual(r["window_start_utc"], "2025-07-28T00:00:00Z")
        self.assertEqual(r["window_end_exclusive_utc"], "2025-07-31T00:00:00Z")
        self.assertEqual(r["record_anchored_rule_id"], "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1")
        self.assertFalse(r["numeric_tolerance_authorized"])
        scope = r["session_scope"]
        self.assertEqual(scope["allowed_s3_actions_only"], ["s3:GetObject"])
        self.assertEqual(scope["persistent_exact_object_count"], 72)
        self.assertTrue(scope["persistent_permission_must_equal_exact_selection"])
        self.assertEqual(len(scope["session_intersection_resource_arns"]), 3)

    def test_ranking_performance_copyability_and_trading_remain_closed(self) -> None:
        r = self.load(RELEASE)
        self.assertTrue(all(v is False for v in r["semantic_boundaries"].values()))
        self.assertTrue(all(v is False for v in r["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in r["trading_authorizations"].values()))
        self.assertIsNone(r["empirical_result"])

    def test_earlier_candidate_and_implementation_remain_inert(self) -> None:
        c = self.load(CANDIDATE)
        i = self.load(IMPLEMENTATION)
        self.assertEqual(c["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertFalse(c["canonical_activation_present"])
        self.assertFalse(c["single_workflow_dispatch_authorized"])
        self.assertFalse(c["aws_oidc_authorized"])
        self.assertFalse(c["get_object_authorized"])
        self.assertEqual(i["status"], "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE")
        self.assertFalse(i["single_workflow_dispatch_authorized"])
        self.assertFalse(i["aws_oidc_authorized_now"])
        self.assertFalse(i["get_object_authorized_now"])

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r11_data_execution_release.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R11_DATA_EXECUTION_RELEASE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
