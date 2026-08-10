from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RELEASE = BASE / "r10b_runtime/R10B_EXECUTION_RELEASE.json"
CANDIDATE = BASE / "r10b_runtime/R10B_EXECUTION_RELEASE_CANDIDATE.json"


class R10BExecutionReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.r = json.loads(RELEASE.read_text(encoding="utf-8"))
        cls.c = json.loads(CANDIDATE.read_text(encoding="utf-8"))

    def test_exactly_one_canonical_r10b_run_is_released_without_rerun(self) -> None:
        self.assertEqual(self.r["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10B_RUN")
        self.assertEqual(self.r["single_use_window_start_utc"], "2026-08-10T13:40:00Z")
        self.assertTrue(self.r["single_workflow_dispatch_authorized"])
        self.assertFalse(self.r["rerun_authorized"])
        self.assertFalse(self.r["release_consumed"])

    def test_release_preserves_exact_one_object_budget_and_integrity_envelope(self) -> None:
        self.assertEqual(self.r["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(self.r["maximum_monthly_budget_eur"], 0)
        self.assertEqual(self.r["maximum_get_object_requests"], 1)
        self.assertEqual(self.r["maximum_requests_per_object"], 1)
        self.assertEqual(self.r["maximum_retries_per_request"], 0)
        self.assertEqual(self.r["maximum_total_compressed_bytes"], 18147822)
        self.assertEqual(self.r["object_key"], "node_fills_by_block/hourly/20250727/9.lz4")
        self.assertEqual(self.r["object_expected_etag"], '"5a9941a240118a57f77a4c3ee95b8430-3"')
        self.assertEqual(self.r["object_expected_compressed_sha256"], "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339")
        self.assertTrue(self.r["requester_pays_authorized"])
        self.assertTrue(self.r["get_object_authorized"])
        for key in ("head_object_authorized", "range_get_authorized", "list_objects_v2_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized", "get_object_attributes_authorized", "get_object_version_authorized", "http_redirect_following_authorized"):
            self.assertFalse(self.r[key], key)

    def test_release_opens_only_aggregate_metadata_lexical_processing(self) -> None:
        for key in ("object_body_download_authorized", "decompression_authorized", "metadata_lexical_processing_authorized", "aggregate_lexical_retention_authorized"):
            self.assertTrue(self.r[key], key)
        for key in (
            "timezone_parsing_authorized", "timezone_inference_authorized", "datetime_conversion_authorized",
            "individual_metadata_value_retention_authorized", "event_array_contents_inspection_authorized",
            "event_pair_count_retention_authorized", "block_number_value_retention_authorized",
            "wallet_address_retention_authorized", "wallet_aggregation_authorized",
            "economic_fill_field_processing_authorized", "individual_fill_time_processing_authorized",
            "raw_object_retention_authorized", "raw_block_event_fill_retention_authorized",
        ):
            self.assertFalse(self.r[key], key)

    def test_release_opens_no_r10_rerun_ranking_copyability_or_trading_authority(self) -> None:
        self.assertTrue(all(v is False for v in self.r["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in self.r["trading_authorizations"].values()))
        self.assertEqual(self.r["network_requests_executed_by_release_creation"], 0)
        self.assertEqual(self.r["aws_iam_mutations_executed_by_release_creation"], 0)
        self.assertIsNone(self.r["empirical_result"])

    def test_candidate_remains_immutable_and_inert_after_activation(self) -> None:
        self.assertEqual(self.c["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertFalse(self.c["canonical_activation_present"])
        self.assertFalse(self.c["single_workflow_dispatch_authorized"])
        self.assertFalse(self.c["aws_oidc_authorized"])
        self.assertFalse(self.c["get_object_authorized"])
        self.assertFalse(self.c["release_consumed"])

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, "governance/validate_r10b_execution_release.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10B_EXECUTION_RELEASE_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
