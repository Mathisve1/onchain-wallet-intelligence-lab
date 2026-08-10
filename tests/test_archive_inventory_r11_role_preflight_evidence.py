from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREFLIGHT = BASE / "r11_role_preflight"
RUN = PREFLIGHT / "evidence/run-31433889087"
RUNTIME = BASE / "r11_runtime"


class R11RolePreflightEvidenceTests(unittest.TestCase):
    @staticmethod
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_run_job_artifact_and_hash_binding(self) -> None:
        v = self.load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
        self.assertEqual(v["run_id"], 31433889087)
        self.assertEqual(v["job_id"], 93603513466)
        self.assertEqual(v["artifact_id"], 9080202425)
        self.assertEqual(v["artifact_name"], "r11-sts-preflight-31433889087")
        self.assertEqual(v["artifact_size_bytes"], 1427)
        self.assertEqual(v["provider_sha256"], "1de9b92dba9ee74152166e4a9890a5a788b36f104499c9323b66e2aa9374eb79")
        self.assertEqual(v["independently_downloaded_zip_sha256"], v["provider_sha256"])
        self.assertTrue(v["provider_digest_matches_independent_download"])
        ledger = {
            "r11-sts-context.json": "49b4d03180f9b8cb720daa9c24e107a984a95d51f7117c8307f30009ddbc421f",
            "r11-sts-result.json": "dee1413bf81200d168904a18a53d88019810475e2de20e3057630487ba77e8eb",
            "r11-sts.rc": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
        }
        self.assertEqual(v["internal_ledger"], ledger)
        for name, digest in ledger.items():
            self.assertEqual(hashlib.sha256((RUN / name).read_bytes()).hexdigest(), digest)

    def test_exact_successful_sts_identity_result_and_zero_s3(self) -> None:
        c = self.load(RUN / "r11-sts-context.json")
        r = self.load(RUN / "r11-sts-result.json")
        self.assertEqual(c["dispatch_sha"], "efad3f278e458a5c35fbfcc11de2b97bbe7cb388")
        self.assertEqual(c["checked_out_commit"], c["dispatch_sha"])
        self.assertEqual(c["dispatch_ref"], "refs/heads/main")
        self.assertEqual(c["workflow_run_attempt"], 1)
        self.assertEqual(c["configure_aws_outcome"], "success")
        self.assertFalse(c["s3_requests_authorized"])
        self.assertEqual(c["s3_requests_executed"], 0)
        self.assertEqual(c["object_bytes_downloaded"], 0)
        self.assertEqual(r["terminal_status"], "R11_STS_PREFLIGHT_PASS")
        self.assertEqual(r["technical_result"], "DEDICATED_R11_ROLE_ASSUMEABLE_FROM_CANONICAL_MAIN")
        self.assertEqual(r["observed_account_id"], "630956766927")
        self.assertEqual(
            r["observed_arn"],
            "arn:aws:sts::630956766927:assumed-role/onchain-wallet-intelligence-hl-archive-scaling-r11/HLArchiveR11STSPreflight",
        )
        self.assertEqual(r["s3_http_request_count"], 0)
        self.assertEqual(r["object_bytes_downloaded"], 0)
        self.assertEqual((RUN / "r11-sts.rc").read_text(encoding="utf-8"), "0\n")

    def test_release_is_consumed_once_without_opening_data_or_trading(self) -> None:
        a = self.load(PREFLIGHT / "HL-ARCHIVE-R11-DEDICATED-ROLE-STS-PREFLIGHT-001-ATTESTATION.json")
        c = self.load(RUNTIME / "R11_STS_PREFLIGHT_RELEASE_CONSUMPTION.json")
        release = self.load(RUNTIME / "R11_STS_PREFLIGHT_RELEASE.json")
        self.assertTrue(a["operator_attestation_independently_verified_by_preflight"])
        self.assertTrue(a["preflight_release_consumed"])
        self.assertFalse(a["rerun_authorized"])
        self.assertFalse(a["data_workflow_installed"])
        self.assertFalse(a["data_execution_release_present"])
        self.assertFalse(a["data_execution_activation_authorized_by_this_attestation"])
        self.assertTrue(all(value is False for value in a["trading_authorizations_after_preflight"].values()))
        self.assertEqual(c["status"], "CONSUMED_SUCCESS")
        self.assertTrue(c["preflight_release_consumed"])
        self.assertFalse(c["rerun_authorized"])
        self.assertEqual(c["s3_requests_executed"], 0)
        self.assertEqual(c["object_bytes_downloaded"], 0)
        self.assertFalse(c["data_workflow_installed"])
        self.assertFalse(c["data_execution_release_present"])
        self.assertFalse(release["release_consumed"])
        self.assertFalse(release["rerun_authorized"])
        self.assertFalse(release["s3_access_authorized_during_preflight"])
        self.assertFalse((ROOT / ".github/workflows/hyperliquid-archive-r11-72h-persistence.yml").exists())

    def test_independent_verification_is_all_pass_and_no_data_authority(self) -> None:
        v = self.load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
        self.assertEqual(v["verification_result"], "ALL_CHECKS_PASS")
        self.assertTrue(v["operator_attestation_independently_verified"])
        self.assertEqual(v["explicit_sts_caller_identity_calls"], 1)
        self.assertFalse(v["s3_requests_authorized"])
        self.assertEqual(v["s3_http_request_count"], 0)
        self.assertEqual(v["object_bytes_downloaded"], 0)
        self.assertFalse(v["data_workflow_installed"])
        self.assertFalse(v["data_execution_release_present"])
        self.assertFalse(v["data_execution_activation_authorized"])

    def test_dedicated_evidence_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r11_role_preflight_evidence.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R11_ROLE_STS_PREFLIGHT_EVIDENCE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
