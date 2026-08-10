from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CANDIDATE = BASE / "r10_role_preflight/R10_STS_PREFLIGHT_RELEASE_CANDIDATE.json"
RUNTIME = BASE / "r10_runtime"
RELEASE = RUNTIME / "R10_STS_PREFLIGHT_RELEASE.json"
DATA_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml"


class R10STSPreflightReleaseCandidateTests(unittest.TestCase):
    @staticmethod
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_candidate_remains_inert_after_separate_activation(self) -> None:
        c = self.load(CANDIDATE)
        self.assertEqual(c["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertEqual(c["preflight_implementation_merge_commit"], "57583e70f0067d045dc8d51d9e8c67c27fa8b818")
        self.assertTrue(c["canonical_activation_required"])
        self.assertFalse(c["canonical_activation_present"])
        self.assertIsNone(c["single_use_window_start_utc"])
        self.assertIsNone(c["anchor_commit"])
        self.assertFalse(c["single_workflow_dispatch_authorized"])
        self.assertFalse(c["rerun_authorized"])
        self.assertFalse(c["sts_get_caller_identity_authorized"])
        self.assertFalse(c["release_consumed"])
        self.assertEqual(c["aws_sts_requests_executed"], 0)
        self.assertEqual(c["s3_requests_executed"], 0)
        self.assertIsNone(c["empirical_result"])

    def test_separate_runtime_release_is_exactly_one_sts_only_dispatch(self) -> None:
        self.assertTrue(RELEASE.is_file())
        r = self.load(RELEASE)
        self.assertEqual(r["status"], "RELEASED_FOR_EXACTLY_ONE_R10_STS_ONLY_PREFLIGHT")
        self.assertEqual(r["release_candidate_merge_commit"], "fdefa27955202f4592c9441665f3c40336c501d1")
        self.assertTrue(r["single_workflow_dispatch_authorized"])
        self.assertFalse(r["rerun_authorized"])
        self.assertFalse(r["release_consumed"])
        self.assertTrue(r["sts_get_caller_identity_authorized"])
        self.assertFalse(r["s3_access_authorized_during_preflight"])
        self.assertFalse(r["data_workflow_installation_authorized"])
        self.assertEqual(r["aws_sts_requests_executed"], 0)
        self.assertEqual(r["s3_requests_executed"], 0)
        self.assertEqual(sorted(path.name for path in RUNTIME.iterdir() if path.is_file()), ["R10_STS_PREFLIGHT_RELEASE.json", "R10_STS_PREFLIGHT_RELEASE_CONSUMPTION.json"])

    def test_candidate_and_release_open_no_s3_data_or_trading_authority(self) -> None:
        c = self.load(CANDIDATE)
        r = self.load(RELEASE)
        for document in (c, r):
            for key in (
                "s3_access_authorized_during_preflight",
                "requester_pays_authorized",
                "get_object_authorized",
                "list_objects_authorized",
                "head_object_authorized",
                "range_get_authorized",
                "object_body_download_authorized",
                "decompression_authorized",
                "data_workflow_installation_authorized",
                "historical_window_expansion_authorized",
                "wallet_ranking_authorized",
                "shortlisting_authorized",
                "pnl_or_alpha_analysis_authorized",
                "copyability_analysis_authorized",
                "market_data_ingestion_authorized",
            ):
                self.assertFalse(document[key], key)
            self.assertTrue(all(value is False for value in document["trading_authorizations"].values()))
        self.assertTrue(DATA_WORKFLOW.is_file())

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10_sts_preflight_release_candidate.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R10_STS_PREFLIGHT_RELEASE_CANDIDATE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
