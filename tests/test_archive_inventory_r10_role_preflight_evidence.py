from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREFLIGHT = BASE / "r10_role_preflight"
RUN = PREFLIGHT / "evidence/run-31372438333"
RUNTIME = BASE / "r10_runtime"


class R10RolePreflightEvidenceTests(unittest.TestCase):
    @staticmethod
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_run_job_artifact_and_hash_binding(self) -> None:
        v = self.load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
        self.assertEqual(v["run_id"], 31372438333)
        self.assertEqual(v["job_id"], 93404183373)
        self.assertEqual(v["artifact_id"], 9056594122)
        self.assertEqual(v["artifact_name"], "r10-sts-preflight-31372438333")
        self.assertEqual(v["artifact_size_bytes"], 1425)
        self.assertEqual(v["provider_sha256"], "e2b5e68709eb8858f3d7b1fc4f17522b021f83c5aeacd04d719479a3703b5a26")
        self.assertTrue(v["provider_digest_matches_independent_download"])
        ledger = {
            "r10-sts-context.json": "328d0dd43e9ffac5d0bf8bda05f44500f503100da1adb2516e861d13a5da3e80",
            "r10-sts-result.json": "9524f1a383dddf73f525fef978f81df0a2399adec694dceebe616fc1c305bbd2",
            "r10-sts.rc": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
        }
        self.assertEqual(v["internal_ledger"], ledger)
        for name, digest in ledger.items():
            self.assertEqual(hashlib.sha256((RUN / name).read_bytes()).hexdigest(), digest)

    def test_exact_successful_sts_identity_result_and_zero_s3(self) -> None:
        c = self.load(RUN / "r10-sts-context.json")
        r = self.load(RUN / "r10-sts-result.json")
        self.assertEqual(c["dispatch_sha"], "8316f05f8fdfd444073e69e292cb89766ac89d7b")
        self.assertEqual(c["dispatch_ref"], "refs/heads/main")
        self.assertEqual(c["workflow_run_attempt"], 1)
        self.assertEqual(c["configure_aws_outcome"], "success")
        self.assertFalse(c["s3_requests_authorized"])
        self.assertEqual(c["s3_requests_executed"], 0)
        self.assertEqual(r["terminal_status"], "R10_STS_PREFLIGHT_PASS")
        self.assertEqual(r["technical_result"], "STS_IDENTITY_MATCH")
        self.assertEqual(r["observed_account_id"], "630956766927")
        self.assertEqual(
            r["observed_arn"],
            "arn:aws:sts::630956766927:assumed-role/onchain-wallet-intelligence-hl-archive-multihour-r10/HLArchiveR10STSPreflight",
        )
        self.assertEqual(r["s3_requests_executed"], 0)
        self.assertEqual((RUN / "r10-sts.rc").read_text(encoding="utf-8"), "0\n")

    def test_release_is_consumed_once_without_opening_data_or_trading(self) -> None:
        a = self.load(PREFLIGHT / "HL-ARCHIVE-R10-DEDICATED-ROLE-STS-PREFLIGHT-001-ATTESTATION.json")
        c = self.load(RUNTIME / "R10_STS_PREFLIGHT_RELEASE_CONSUMPTION.json")
        release = self.load(RUNTIME / "R10_STS_PREFLIGHT_RELEASE.json")
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
        self.assertFalse(c["data_workflow_installed"])
        self.assertFalse(c["data_execution_release_present"])
        self.assertFalse(release["release_consumed"])
        self.assertFalse(release["rerun_authorized"])
        self.assertFalse(release["s3_access_authorized_during_preflight"])
        self.assertTrue((ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml").is_file())

    def test_dedicated_evidence_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10_role_preflight_evidence.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R10_ROLE_STS_PREFLIGHT_EVIDENCE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
