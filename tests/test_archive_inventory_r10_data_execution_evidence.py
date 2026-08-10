from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RUN = BASE / "r10_data_execution/evidence/run-31377732916"
ATTEST = BASE / "r10_data_execution/HL-ARCHIVE-POST-BOUNDARY-MULTI-HOUR-FEATURE-R10-001-ATTESTATION.json"
CONSUMPTION = BASE / "r10_data_execution/R10_EXECUTION_RELEASE_CONSUMPTION.json"


class R10DataExecutionEvidenceTests(unittest.TestCase):
    @staticmethod
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_unresolved_run_and_artifact_are_bound(self) -> None:
        v = self.load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
        self.assertEqual(v["run_id"], 31377732916)
        self.assertEqual(v["job_id"], 93420701174)
        self.assertEqual(v["artifact_id"], 9058595361)
        self.assertEqual(v["provider_sha256"], "e6aebcbc0c73aecbea994fb4bd095c56f6c86b9ba5aa0dc152bee125b08f33bb")
        self.assertTrue(v["provider_digest_matches_independent_download"])
        self.assertEqual(v["return_code_value"], 0)
        self.assertEqual(v["job_conclusion"], "success")

    def test_green_job_is_research_unresolved_not_feature_success(self) -> None:
        result = self.load(RUN / "r10-result.json")
        self.assertEqual(result["terminal_status"], "R10_MULTI_HOUR_FEATURE_STUDY_COMPLETE")
        self.assertEqual(result["research_conclusion"], "MULTI_HOUR_FEATURE_PIPELINE_UNRESOLVED")
        self.assertEqual(result["failure_class"], "fill time lies outside source path hour")
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["successful_request_count"], 1)
        self.assertEqual(result["s3_http_request_count"], 1)
        self.assertEqual(result["completed_hour_count"], 0)
        self.assertFalse(result["wallet_feature_retained"])
        self.assertEqual((RUN / "r10-wallet-features.ndjson").read_bytes(), b"")

    def test_release_is_consumed_and_never_rerunnable(self) -> None:
        c = self.load(CONSUMPTION)
        a = self.load(ATTEST)
        self.assertEqual(c["status"], "CONSUMED_RESEARCH_UNRESOLVED")
        self.assertTrue(c["release_consumed"])
        self.assertFalse(c["future_r10_dispatch_authorized"])
        self.assertFalse(c["rerun_authorized"])
        self.assertTrue(c["remaining_budget_is_not_reusable_without_new_release"])
        self.assertTrue(a["new_network_request_requires_new_preregistration_approval_and_release"])
        self.assertTrue(all(value is False for value in c["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in c["trading_authorizations"].values()))

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10_data_execution_evidence.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R10_DATA_EXECUTION_EVIDENCE_VALID_UNRESOLVED", completed.stdout)


if __name__ == "__main__":
    unittest.main()
