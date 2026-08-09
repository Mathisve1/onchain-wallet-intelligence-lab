from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4/role_attestation"
RUN = BASE / "evidence/run-31312067367"


class ArchiveHourlyBodySchemaR4RolePreflightEvidenceTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_run_artifact_and_terminal_result(self) -> None:
        v = self.load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
        r = self.load(RUN / "r4-role-preflight-result.json")
        self.assertEqual(v["run_id"], 31312067367)
        self.assertEqual(v["job_id"], 93241269551)
        self.assertEqual(v["artifact_id"], 9037655204)
        self.assertEqual(v["provider_sha256"], "6d30969525156ad3354c4a9abdb5d661cfc1b7b2d1a6cfd07eb02f4300f20376")
        self.assertTrue(v["provider_digest_matches_independent_download"])
        self.assertEqual(r["terminal_status"], "R4_ROLE_STS_PREFLIGHT_PASS")
        self.assertEqual(r["technical_result"], "DEDICATED_R4_ROLE_ASSUMEABLE_FROM_CANONICAL_MAIN")

    def test_preflight_proves_role_and_zero_s3(self) -> None:
        r = self.load(RUN / "r4-role-preflight-result.json")
        self.assertEqual(r["account_id"], "630956766927")
        self.assertTrue(r["role_session_arn"].endswith("/HLArchiveR4RolePreflight"))
        self.assertEqual(r["explicit_sts_caller_identity_calls"], 1)
        self.assertEqual(r["s3_http_request_count"], 0)
        self.assertEqual(r["object_bytes_downloaded"], 0)
        self.assertFalse(r["requester_pays_requested"])
        self.assertFalse(r["decompression_performed"])

    def test_preflight_release_is_consumed_without_consuming_body_release(self) -> None:
        c = self.load(BASE / "R4_ROLE_STS_PREFLIGHT_RELEASE_CONSUMPTION.json")
        a = self.load(BASE / "HL-ARCHIVE-R4-DEDICATED-ROLE-STS-PREFLIGHT-001-ATTESTATION.json")
        body = self.load(ROOT / "research/archive_inventory/r4/R4_EXECUTION_RELEASE.json")
        self.assertEqual(c["status"], "CONSUMED_SUCCESS")
        self.assertTrue(c["preflight_release_consumed"])
        self.assertFalse(c["rerun_authorized"])
        self.assertFalse(c["body_release_consumed_by_preflight"])
        self.assertTrue(a["operator_attestation_independently_verified_by_preflight"])
        self.assertFalse(a["body_execution_activation_authorized_by_this_attestation"])
        self.assertFalse(body["execution_ready"])
        self.assertFalse(body["single_workflow_dispatch_authorized"])

    def test_dedicated_evidence_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r4_role_preflight_evidence.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R4_ROLE_STS_PREFLIGHT_EVIDENCE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
