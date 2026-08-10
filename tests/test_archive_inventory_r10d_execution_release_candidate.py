from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CANDIDATE = BASE / "r10d_runtime/R10D_EXECUTION_RELEASE_CANDIDATE.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r10d-record-anchored-multihour-feature.yml"
FROZEN = BASE / "r10d_implementation/workflows/hyperliquid-archive-r10d-record-anchored-multihour-feature.yml"


class R10DExecutionReleaseCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.c = json.loads(CANDIDATE.read_text(encoding="utf-8"))

    def test_candidate_is_inert_and_requires_separate_activation(self) -> None:
        self.assertEqual(self.c["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertTrue(self.c["canonical_activation_required"])
        self.assertFalse(self.c["canonical_activation_present"])
        self.assertIsNone(self.c["single_use_window_start_utc"])
        for key in (
            "single_workflow_dispatch_authorized", "aws_oidc_authorized", "requester_pays_authorized",
            "get_object_authorized", "object_body_download_authorized", "decompression_authorized",
            "metadata_prefix_processing_authorized", "selected_fill_field_processing_authorized",
            "wallet_feature_retention_authorized", "release_consumed", "rerun_authorized",
        ):
            self.assertFalse(self.c[key], key)
        self.assertEqual(self.c["network_requests_executed"], 0)
        self.assertEqual(self.c["aws_iam_mutations_executed"], 0)
        self.assertEqual(self.c["wallet_feature_rows_created"], 0)
        self.assertIsNone(self.c["empirical_result"])

    def test_candidate_preserves_exact_six_object_budget_and_order(self) -> None:
        self.assertEqual(len(self.c["exact_network_targets"]), 6)
        self.assertEqual([row["key"] for row in self.c["exact_network_targets"]], [f"node_fills_by_block/hourly/20250727/{hour}.lz4" for hour in range(9, 15)])
        e = self.c["execution_envelope"]
        self.assertEqual(e["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(e["maximum_monthly_budget_eur"], 0)
        self.assertEqual(e["maximum_get_object_requests"], 6)
        self.assertEqual(e["maximum_requests_per_object"], 1)
        self.assertEqual(e["maximum_retries_per_request"], 0)
        self.assertEqual(e["maximum_total_compressed_bytes"], 120999698)
        self.assertEqual(e["maximum_total_decompressed_bytes"], 1073741824)
        self.assertEqual(e["request_order"], "PATH_HOUR_ASCENDING")
        self.assertTrue(e["stop_after_first_failed_or_mismatched_object"])

    def test_future_processing_is_record_anchored_and_no_numeric_tolerance(self) -> None:
        p = self.c["future_processing_authority_if_separately_activated"]
        self.assertEqual(p["record_anchored_rule_id"], "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1")
        self.assertTrue(p["decompression"])
        self.assertTrue(p["metadata_raw_prefix_processing"])
        self.assertTrue(p["event_pair_shape_processing"])
        self.assertTrue(p["selected_fill_field_processing"])
        self.assertTrue(p["fill_time_integer_milliseconds_processing"])
        self.assertTrue(p["wallet_feature_retention"])
        self.assertFalse(p["numeric_tolerance_authorized"])
        self.assertFalse(p["metadata_timezone_parsing"])
        self.assertFalse(p["metadata_timezone_inference"])
        self.assertFalse(p["metadata_datetime_conversion"])
        self.assertTrue(all(v is False for v in self.c["semantic_boundaries"].values()))
        self.assertTrue(all(v is False for v in self.c["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in self.c["trading_authorizations"].values()))

    def test_installed_workflow_is_byte_exact_frozen_candidate(self) -> None:
        self.assertEqual(WORKFLOW.read_bytes(), FROZEN.read_bytes())
        self.assertEqual(self.c["workflow_git_blob_sha"], "8b63ac4f00e05e0533793cd91c6b0d13cad26213")
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10D_RUN", text)
        self.assertLess(text.index("Prove exact single-use R10D release before OIDC"), text.index("Assume exact existing R10 role with exact-six session scope"))
        self.assertEqual(text.count("arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/"), 6)

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, "governance/validate_r10d_execution_release_candidate.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10D_EXECUTION_RELEASE_CANDIDATE_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
