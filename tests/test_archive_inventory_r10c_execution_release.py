from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RELEASE = BASE / "r10c_runtime/R10C_EXECUTION_RELEASE.json"
CANDIDATE = BASE / "r10c_runtime/R10C_EXECUTION_RELEASE_CANDIDATE.json"


class R10CExecutionReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.r = json.loads(RELEASE.read_text(encoding="utf-8"))
        cls.c = json.loads(CANDIDATE.read_text(encoding="utf-8"))

    def test_exactly_one_canonical_r10c_run_is_released_without_rerun(self) -> None:
        self.assertEqual(self.r["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10C_RUN")
        self.assertEqual(self.r["single_use_window_start_utc"], "2026-08-10T16:32:00Z")
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
        self.assertEqual(self.r["maximum_individual_compressed_bytes"], 18147822)
        self.assertEqual(self.r["maximum_total_decompressed_bytes"], 268435456)
        self.assertEqual(self.r["maximum_individual_decompressed_bytes"], 268435456)
        self.assertEqual(self.r["object_key"], "node_fills_by_block/hourly/20250727/9.lz4")
        self.assertEqual(self.r["object_expected_etag"], '"5a9941a240118a57f77a4c3ee95b8430-3"')
        self.assertEqual(self.r["object_expected_compressed_sha256"], "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339")
        self.assertTrue(self.r["requester_pays_authorized"])
        self.assertTrue(self.r["get_object_authorized"])
        for key in (
            "head_object_authorized",
            "range_get_authorized",
            "list_objects_v2_authorized",
            "list_object_versions_authorized",
            "list_all_my_buckets_authorized",
            "get_object_attributes_authorized",
            "get_object_version_authorized",
            "http_redirect_following_authorized",
        ):
            self.assertFalse(self.r[key], key)

    def test_release_opens_only_approved_boundary_correlation_processing(self) -> None:
        for key in (
            "object_body_download_authorized",
            "decompression_authorized",
            "metadata_prefix_processing_authorized",
            "event_array_contents_inspection_authorized",
            "event_pair_shape_inspection_authorized",
            "fill_time_integer_milliseconds_processing_authorized",
            "aggregate_boundary_correlation_retention_authorized",
        ):
            self.assertTrue(self.r[key], key)
        self.assertEqual(self.r["event_array_contents_inspection_scope"], "PAIR_SHAPE_AND_FILL_TIME_ONLY")
        self.assertEqual(self.r["fill_object_field_allowlist"], ["time"])
        for key in (
            "metadata_timezone_parsing_authorized",
            "metadata_timezone_inference_authorized",
            "metadata_datetime_conversion_authorized",
            "individual_metadata_value_retention_authorized",
            "leading_event_string_value_retention_authorized",
            "leading_event_string_wallet_semantics_authorized",
            "individual_fill_time_retention_authorized",
            "economic_fill_field_processing_authorized",
            "block_number_value_retention_authorized",
            "per_block_identity_retention_authorized",
            "per_wallet_processing_authorized",
            "wallet_address_retention_authorized",
            "raw_compressed_object_retention_authorized",
            "raw_decompressed_object_retention_authorized",
            "raw_block_record_retention_authorized",
            "raw_event_pair_retention_authorized",
        ):
            self.assertFalse(self.r[key], key)

    def test_parent_counts_and_terminal_classes_are_unchanged(self) -> None:
        self.assertEqual(
            self.r["parent_aggregate_preconditions"],
            {
                "block_record_count": 36029,
                "fill_time_count": 223950,
                "fill_time_before_path_hour_count": 2,
                "fill_time_inside_path_hour_count": 223948,
                "fill_time_after_path_hour_count": 0,
                "local_time_path_prefix_count": 36029,
                "block_time_path_prefix_count": 36028,
                "block_time_previous_prefix_count": 1,
            },
        )
        self.assertEqual(
            self.r["allowed_boundary_record_correlation_classifications"],
            [
                "EXACT_TWO_PRE_HOUR_FILLS_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD",
                "PRE_HOUR_FILLS_DO_NOT_EXACTLY_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD",
                "BOUNDARY_RECORD_CORRELATION_UNRESOLVED",
            ],
        )

    def test_release_opens_no_r10_rerun_ranking_copyability_or_trading_authority(self) -> None:
        self.assertTrue(all(v is False for v in self.r["interpretation_boundaries"].values()))
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
        self.assertFalse(self.c["rerun_authorized"])

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, "governance/validate_r10c_execution_release.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10C_EXECUTION_RELEASE_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
