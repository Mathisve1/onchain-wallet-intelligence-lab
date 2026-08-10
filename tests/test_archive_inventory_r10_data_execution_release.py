from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RELEASE = BASE / "r10_runtime/R10_EXECUTION_RELEASE_CANONICALIZATION.json"
CANDIDATE = BASE / "r10_data_execution/R10_EXECUTION_RELEASE_CANDIDATE.json"


class R10DataExecutionReleaseTests(unittest.TestCase):
    @staticmethod
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exactly_one_canonical_six_hour_run_is_released_without_rerun(self) -> None:
        r = self.load(RELEASE)
        self.assertEqual(r["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10_RUN")
        self.assertEqual(r["release_candidate_merge_commit"], "9b4862ac8ea5499da81d5e4ab40090b077dd9357")
        self.assertEqual(r["data_workflow_implementation_merge_commit"], "791c1c289976346d1fcb2bb6ca8196cebf1a50c7")
        self.assertEqual(r["single_use_window_start_utc"], "2026-08-10T10:00:00Z")
        self.assertTrue(r["canonical_activation_present"])
        self.assertTrue(r["single_workflow_dispatch_authorized"])
        self.assertFalse(r["rerun_authorized"])
        self.assertFalse(r["release_consumed"])
        self.assertTrue(r["aws_oidc_authorized"])
        self.assertTrue(r["requester_pays_authorized"])
        self.assertTrue(r["get_object_authorized"])
        self.assertTrue(r["object_body_download_authorized"])
        self.assertTrue(r["decompression_authorized"])
        self.assertTrue(r["selected_fill_field_processing_authorized"])
        self.assertTrue(r["wallet_feature_retention_authorized"])
        self.assertIsNone(r["empirical_result"])

    def test_release_preserves_exact_six_object_caps_and_fail_closed_reads(self) -> None:
        r = self.load(RELEASE)
        self.assertEqual(len(r["exact_objects"]), 6)
        self.assertEqual(sum(row["expected_size_bytes"] for row in r["exact_objects"]), 120999698)
        self.assertEqual(r["maximum_get_object_requests"], 6)
        self.assertEqual(r["maximum_requests_per_object"], 1)
        self.assertEqual(r["maximum_total_compressed_bytes"], 120999698)
        self.assertEqual(r["maximum_individual_compressed_bytes"], 21672141)
        self.assertEqual(r["maximum_total_decompressed_bytes"], 1073741824)
        self.assertEqual(r["maximum_individual_decompressed_bytes"], 268435456)
        self.assertEqual(r["maximum_runtime_seconds"], 300)
        self.assertEqual(r["maximum_retries_per_request"], 0)
        self.assertFalse(r["head_object_authorized"])
        self.assertFalse(r["range_get_authorized"])
        self.assertFalse(r["list_objects_v2_authorized"])
        self.assertFalse(r["list_object_versions_authorized"])
        self.assertFalse(r["list_all_my_buckets_authorized"])

    def test_release_opens_no_ranking_copyability_or_trading_authority(self) -> None:
        r = self.load(RELEASE)
        self.assertTrue(all(value is False for value in r["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in r["trading_authorizations"].values()))
        self.assertTrue(all(value is False for value in r["semantic_boundaries"].values()))

    def test_candidate_remains_immutable_inert_snapshot(self) -> None:
        c = self.load(CANDIDATE)
        self.assertEqual(c["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertFalse(c["canonical_activation_present"])
        self.assertFalse(c["single_workflow_dispatch_authorized"])
        self.assertFalse(c["aws_oidc_authorized"])
        self.assertFalse(c["get_object_authorized"])
        self.assertFalse(c["wallet_feature_retention_authorized"])

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10_data_execution_release.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R10_DATA_EXECUTION_RELEASE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
