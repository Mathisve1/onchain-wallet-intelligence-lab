from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "research/archive_inventory/r10d_runtime/R10D_EXECUTION_RELEASE.json"
CANDIDATE = ROOT / "research/archive_inventory/r10d_runtime/R10D_EXECUTION_RELEASE_CANDIDATE.json"


class R10DExecutionReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.r = json.loads(RELEASE.read_text(encoding="utf-8"))
        cls.c = json.loads(CANDIDATE.read_text(encoding="utf-8"))

    def test_exactly_one_canonical_r10d_run_is_released_without_rerun(self) -> None:
        self.assertEqual(self.r["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10D_RUN")
        self.assertEqual(self.r["single_use_window_start_utc"], "2026-08-10T18:20:00Z")
        self.assertTrue(self.r["single_workflow_dispatch_authorized"])
        self.assertFalse(self.r["rerun_authorized"])
        self.assertFalse(self.r["release_consumed"])

    def test_release_preserves_exact_approved_six_object_caps(self) -> None:
        self.assertEqual(self.r["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(self.r["maximum_monthly_budget_eur"], 0)
        self.assertEqual(self.r["maximum_get_object_requests"], 6)
        self.assertEqual(self.r["maximum_requests_per_object"], 1)
        self.assertEqual(self.r["maximum_retries_per_request"], 0)
        self.assertEqual(self.r["maximum_total_compressed_bytes"], 120999698)
        self.assertEqual(self.r["maximum_runtime_seconds"], 300)
        self.assertEqual(self.r["request_order"], "PATH_HOUR_ASCENDING")
        self.assertTrue(self.r["stop_after_first_failed_or_mismatched_object"])

    def test_record_anchored_rule_has_no_numeric_tolerance(self) -> None:
        self.assertEqual(self.r["record_anchored_rule_id"], "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1")
        self.assertFalse(self.r["numeric_tolerance_authorized"])
        self.assertFalse(self.r["metadata_timezone_parsing_authorized"])
        self.assertFalse(self.r["metadata_timezone_inference_authorized"])
        self.assertFalse(self.r["metadata_datetime_conversion_authorized"])

    def test_release_opens_runtime_scope_but_no_downstream_or_trading_authority(self) -> None:
        for key in ("requester_pays_authorized", "get_object_authorized", "object_body_download_authorized", "decompression_authorized", "metadata_prefix_processing_authorized", "selected_fill_field_processing_authorized", "wallet_feature_retention_authorized"):
            self.assertTrue(self.r[key], key)
        self.assertTrue(all(v is False for v in self.r["semantic_boundaries"].values()))
        self.assertTrue(all(v is False for v in self.r["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in self.r["trading_authorizations"].values()))
        self.assertEqual(self.r["network_requests_executed_by_release_creation"], 0)
        self.assertEqual(self.r["aws_iam_mutations_executed_by_release_creation"], 0)
        self.assertEqual(self.r["wallet_feature_rows_created_by_release_creation"], 0)
        self.assertIsNone(self.r["empirical_result"])

    def test_candidate_remains_immutable_inert_snapshot(self) -> None:
        self.assertEqual(self.c["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertFalse(self.c["canonical_activation_present"])
        self.assertFalse(self.c["single_workflow_dispatch_authorized"])
        self.assertFalse(self.c["aws_oidc_authorized"])
        self.assertFalse(self.c["get_object_authorized"])
        self.assertFalse(self.c["release_consumed"])

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run([sys.executable, "governance/validate_r10d_execution_release.py"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10D_EXECUTION_RELEASE_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
