from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CANDIDATE = BASE / "r10c_runtime/R10C_EXECUTION_RELEASE_CANDIDATE.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r10c-boundary-record-correlation.yml"
FROZEN = BASE / "r10c_implementation/workflows/hyperliquid-archive-r10c-boundary-record-correlation.yml"


class R10CExecutionReleaseCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.c = json.loads(CANDIDATE.read_text(encoding="utf-8"))

    def test_candidate_is_inert_and_requires_separate_activation(self) -> None:
        self.assertEqual(self.c["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertTrue(self.c["canonical_activation_required"])
        self.assertFalse(self.c["canonical_activation_present"])
        self.assertIsNone(self.c["single_use_window_start_utc"])
        for key in (
            "single_workflow_dispatch_authorized",
            "aws_oidc_authorized",
            "requester_pays_authorized",
            "get_object_authorized",
            "object_body_download_authorized",
            "decompression_authorized",
            "metadata_prefix_processing_authorized",
            "event_time_processing_authorized",
            "aggregate_boundary_correlation_retention_authorized",
            "release_consumed",
            "rerun_authorized",
        ):
            self.assertFalse(self.c[key], key)
        self.assertEqual(self.c["network_requests_executed"], 0)
        self.assertEqual(self.c["aws_iam_mutations_executed"], 0)
        self.assertIsNone(self.c["empirical_result"])

    def test_candidate_preserves_exact_approved_one_object_scope(self) -> None:
        target = self.c["exact_network_target"]
        self.assertEqual(target["key"], "node_fills_by_block/hourly/20250727/9.lz4")
        self.assertEqual(target["expected_size_bytes"], 18147822)
        self.assertEqual(target["expected_etag"], '"5a9941a240118a57f77a4c3ee95b8430-3"')
        self.assertEqual(target["expected_compressed_sha256"], "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339")
        self.assertEqual(target["path_hour_start_ms"], 1753606800000)
        self.assertEqual(target["path_hour_end_ms_exclusive"], 1753610400000)
        e = self.c["execution_envelope"]
        self.assertEqual(e["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(e["maximum_monthly_budget_eur"], 0)
        self.assertEqual(e["maximum_get_object_requests"], 1)
        self.assertEqual(e["maximum_requests_per_object"], 1)
        self.assertEqual(e["maximum_retries_per_request"], 0)
        self.assertEqual(e["maximum_total_compressed_bytes"], 18147822)
        self.assertEqual(e["maximum_total_decompressed_bytes"], 268435456)
        self.assertTrue(e["exact_compressed_sha256_required"])
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
            self.assertFalse(e[key], key)

    def test_future_processing_is_exact_boundary_correlation_only(self) -> None:
        p = self.c["future_processing_authority_if_separately_activated"]
        for key in (
            "decompression",
            "metadata_prefix_processing",
            "event_array_contents_inspection",
            "event_pair_shape_inspection",
            "fill_time_integer_milliseconds_processing",
            "aggregate_boundary_correlation_retention",
        ):
            self.assertTrue(p[key], key)
        self.assertEqual(p["event_array_contents_inspection_scope"], "PAIR_SHAPE_AND_FILL_TIME_ONLY")
        self.assertEqual(p["fill_object_field_allowlist"], ["time"])
        for key in (
            "metadata_timezone_parsing",
            "metadata_timezone_inference",
            "metadata_datetime_conversion",
            "individual_metadata_value_retention",
            "leading_event_string_value_retention",
            "leading_event_string_wallet_semantics",
            "individual_fill_time_retention",
            "economic_fill_field_processing",
            "block_number_value_retention",
            "per_block_identity_retention",
            "per_wallet_processing",
            "wallet_address_retention",
            "raw_compressed_object_retention",
            "raw_decompressed_object_retention",
            "raw_block_record_retention",
            "raw_event_pair_retention",
        ):
            self.assertFalse(p[key], key)
        self.assertTrue(all(v is False for v in self.c["interpretation_boundaries"].values()))
        self.assertTrue(all(v is False for v in self.c["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in self.c["trading_authorizations"].values()))

    def test_parent_counts_and_terminal_classes_are_frozen(self) -> None:
        self.assertEqual(self.c["parent_aggregate_preconditions"]["block_record_count"], 36029)
        self.assertEqual(self.c["parent_aggregate_preconditions"]["fill_time_count"], 223950)
        self.assertEqual(self.c["parent_aggregate_preconditions"]["fill_time_before_path_hour_count"], 2)
        self.assertEqual(self.c["parent_aggregate_preconditions"]["block_time_previous_prefix_count"], 1)
        self.assertEqual(
            self.c["allowed_boundary_record_correlation_classifications"],
            [
                "EXACT_TWO_PRE_HOUR_FILLS_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD",
                "PRE_HOUR_FILLS_DO_NOT_EXACTLY_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD",
                "BOUNDARY_RECORD_CORRELATION_UNRESOLVED",
            ],
        )

    def test_installed_workflow_is_byte_exact_frozen_candidate(self) -> None:
        self.assertEqual(WORKFLOW.read_bytes(), FROZEN.read_bytes())
        self.assertEqual(self.c["workflow_git_blob_sha"], "1cdc522dc0b827cc0173089b2082c6cb9a0896dd")
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10C_RUN", text)
        self.assertLess(
            text.index("Prove exact single-use R10C release before OIDC"),
            text.index("Assume existing R10 role with exact one-object session scope"),
        )
        self.assertIn('"Action":"s3:GetObject"', text)
        self.assertIn("PAIR_SHAPE_AND_FILL_TIME_ONLY", text)

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, "governance/validate_r10c_execution_release_candidate.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10C_EXECUTION_RELEASE_CANDIDATE_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
