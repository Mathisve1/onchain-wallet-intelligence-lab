from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CANDIDATE = BASE / "r10b_runtime/R10B_EXECUTION_RELEASE_CANDIDATE.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r10b-batch-metadata-lexical-diagnostic.yml"
FROZEN = BASE / "r10b_implementation/workflows/hyperliquid-archive-r10b-batch-metadata-lexical-diagnostic.yml"


class R10BExecutionReleaseCandidateTests(unittest.TestCase):
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
            "metadata_lexical_processing_authorized", "aggregate_lexical_retention_authorized",
            "release_consumed", "rerun_authorized",
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
        e = self.c["execution_envelope"]
        self.assertEqual(e["maximum_get_object_requests"], 1)
        self.assertEqual(e["maximum_requests_per_object"], 1)
        self.assertEqual(e["maximum_retries_per_request"], 0)
        self.assertTrue(e["exact_compressed_sha256_required"])

    def test_future_processing_is_lexical_only(self) -> None:
        p = self.c["future_processing_authority_if_separately_activated"]
        self.assertTrue(p["decompression"])
        self.assertTrue(p["metadata_lexical_processing"])
        self.assertTrue(p["aggregate_lexical_retention"])
        for key in (
            "timezone_parsing", "timezone_inference", "datetime_conversion", "individual_metadata_value_retention",
            "event_array_contents_inspection", "event_pair_count_retention", "block_number_value_retention",
            "wallet_address_retention", "wallet_aggregation", "economic_fill_field_processing",
            "individual_fill_time_processing", "raw_object_retention", "raw_block_event_fill_retention",
        ):
            self.assertFalse(p[key], key)
        self.assertTrue(all(v is False for v in self.c["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in self.c["trading_authorizations"].values()))

    def test_installed_workflow_is_byte_exact_frozen_candidate(self) -> None:
        self.assertEqual(WORKFLOW.read_bytes(), FROZEN.read_bytes())
        self.assertEqual(self.c["workflow_git_blob_sha"], "e093fe6a95b543dc3cfd860f460debd8f8a4f944")
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10B_RUN", text)
        self.assertLess(text.index("Prove exact single-use R10B release before OIDC"), text.index("Assume existing R10 role with exact one-object session scope"))

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, "governance/validate_r10b_execution_release_candidate.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10B_EXECUTION_RELEASE_CANDIDATE_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
