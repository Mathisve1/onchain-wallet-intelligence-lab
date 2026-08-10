from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RELEASE = BASE / "r10_runtime/R10_STS_PREFLIGHT_RELEASE.json"
CANDIDATE = BASE / "r10_role_preflight/R10_STS_PREFLIGHT_RELEASE_CANDIDATE.json"
DATA_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml"


class R10STSPreflightReleaseTests(unittest.TestCase):
    @staticmethod
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exactly_one_manual_preflight_is_released_without_rerun(self) -> None:
        r = self.load(RELEASE)
        self.assertEqual(r["status"], "RELEASED_FOR_EXACTLY_ONE_R10_STS_ONLY_PREFLIGHT")
        self.assertEqual(r["release_candidate_merge_commit"], "fdefa27955202f4592c9441665f3c40336c501d1")
        self.assertEqual(r["single_use_window_start_utc"], "2026-08-10T08:43:00Z")
        self.assertTrue(r["single_workflow_dispatch_authorized"])
        self.assertFalse(r["rerun_authorized"])
        self.assertFalse(r["release_consumed"])
        self.assertTrue(r["operator_attestation_reviewed"])
        self.assertTrue(r["sts_get_caller_identity_authorized"])
        self.assertEqual(r["maximum_explicit_aws_cli_calls"], 1)
        self.assertEqual(r["role_duration_seconds"], 900)
        self.assertEqual(r["aws_sts_requests_executed"], 0)
        self.assertEqual(r["s3_requests_executed"], 0)
        self.assertIsNone(r["empirical_result"])

    def test_release_authorizes_no_s3_data_or_trading_action(self) -> None:
        r = self.load(RELEASE)
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
            self.assertFalse(r[key], key)
        self.assertTrue(all(value is False for value in r["trading_authorizations"].values()))
        self.assertFalse(DATA_WORKFLOW.exists())

    def test_inert_release_candidate_remains_immutable(self) -> None:
        c = self.load(CANDIDATE)
        self.assertEqual(c["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertFalse(c["canonical_activation_present"])
        self.assertFalse(c["single_workflow_dispatch_authorized"])
        self.assertFalse(c["sts_get_caller_identity_authorized"])
        self.assertFalse(c["s3_access_authorized_during_preflight"])
        self.assertEqual(c["aws_sts_requests_executed"], 0)
        self.assertEqual(c["s3_requests_executed"], 0)

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10_sts_preflight_release.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R10_STS_PREFLIGHT_RELEASE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
