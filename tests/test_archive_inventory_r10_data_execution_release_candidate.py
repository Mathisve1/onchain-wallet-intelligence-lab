from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CANDIDATE = BASE / "r10_data_execution/R10_EXECUTION_RELEASE_CANDIDATE.json"
RUNTIME_RELEASE = BASE / "r10_runtime/R10_EXECUTION_RELEASE_CANONICALIZATION.json"


class R10DataExecutionReleaseCandidateTests(unittest.TestCase):
    @staticmethod
    def load() -> dict:
        return json.loads(CANDIDATE.read_text(encoding="utf-8"))

    def test_candidate_is_inert_and_requires_separate_activation(self) -> None:
        c = self.load()
        self.assertEqual(c["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertEqual(c["data_workflow_implementation_merge_commit"], "791c1c289976346d1fcb2bb6ca8196cebf1a50c7")
        self.assertTrue(c["canonical_activation_required"])
        self.assertFalse(c["canonical_activation_present"])
        self.assertIsNone(c["single_use_window_start_utc"])
        self.assertFalse(c["single_workflow_dispatch_authorized"])
        self.assertFalse(c["rerun_authorized"])
        self.assertFalse(c["release_consumed"])
        self.assertFalse(c["aws_oidc_authorized"])
        self.assertFalse(c["get_object_authorized"])
        self.assertFalse(c["wallet_feature_retention_authorized"])
        self.assertIsNone(c["empirical_result"])
        self.assertTrue(RUNTIME_RELEASE.is_file())

    def test_candidate_preserves_exact_six_object_budget_and_transport_envelope(self) -> None:
        c = self.load()
        env = c["execution_envelope"]
        self.assertEqual(len(c["exact_objects"]), 6)
        self.assertEqual(sum(row["expected_size_bytes"] for row in c["exact_objects"]), 120999698)
        self.assertEqual(env["maximum_get_object_requests"], 6)
        self.assertEqual(env["maximum_requests_per_object"], 1)
        self.assertEqual(env["maximum_total_compressed_bytes"], 120999698)
        self.assertEqual(env["maximum_individual_compressed_bytes"], 21672141)
        self.assertEqual(env["maximum_total_decompressed_bytes"], 1073741824)
        self.assertEqual(env["maximum_individual_decompressed_bytes"], 268435456)
        self.assertEqual(env["maximum_runtime_seconds"], 300)
        self.assertEqual(env["maximum_retries_per_request"], 0)
        self.assertTrue(env["requester_pays_required"])
        self.assertTrue(env["if_match_etag_required"])
        self.assertTrue(env["stop_after_first_failed_or_mismatched_object"])

    def test_no_ranking_copyability_or_trading_authority_is_opened(self) -> None:
        c = self.load()
        self.assertTrue(all(value is False for value in c["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in c["trading_authorizations"].values()))
        self.assertTrue(all(value is False for value in c["semantic_boundaries"].values()))

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10_data_execution_release_candidate.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R10_DATA_EXECUTION_RELEASE_CANDIDATE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
