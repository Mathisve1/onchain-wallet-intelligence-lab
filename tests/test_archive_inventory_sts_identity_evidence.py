from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "research/archive_inventory/aws_access/evidence"
RUN = EVIDENCE / "run-31250176507"
EXPECTED_COMMIT = "f34786eafd3689b575bdd3d2ada932b8ce204a61"
EXPECTED_ACCOUNT = "630956766927"
EXPECTED_ARN = (
    "arn:aws:sts::630956766927:assumed-role/"
    "onchain-wallet-intelligence-hl-archive-metadata-canary/HLArchiveOidcIdentityCheck"
)


class ArchiveStsIdentityEvidenceTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def sha(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_exact_run_identity_and_terminal_result(self) -> None:
        context = self.load(RUN / "sts-identity-context.json")
        result = self.load(RUN / "sts-identity-result.json")
        self.assertEqual(context["workflow_run_id"], 31250176507)
        self.assertEqual(context["workflow_run_attempt"], 1)
        self.assertEqual(context["dispatch_ref"], "refs/heads/main")
        for key in ("dispatch_sha", "reviewed_commit", "checked_out_commit"):
            self.assertEqual(context[key], EXPECTED_COMMIT)
        for obj in (context, result):
            self.assertEqual(obj["terminal_status"], "STS_IDENTITY_MATCH")
            self.assertEqual(obj["observed_account_id"], EXPECTED_ACCOUNT)
            self.assertEqual(obj["observed_assumed_role_arn"], EXPECTED_ARN)
            self.assertEqual(obj["explicit_sts_call_count"], 1)
            self.assertEqual(obj["s3_session_policy"], "EXPLICIT_DENY_ALL_S3")
            self.assertFalse(obj["s3_called"])
            self.assertFalse(obj["requester_pays_used"])
            self.assertFalse(obj["market_data_ingested"])
            self.assertIsNone(obj["empirical_result"])
        self.assertEqual((RUN / "sts-identity.rc").read_text(encoding="utf-8"), "0\n")

    def test_internal_hash_ledger_matches_retained_files(self) -> None:
        expected = {
            "sts-identity-context.json": "858fd3ad0ed591f965a3ce7551089285f9a47385bf26dd1349bd6e990442e650",
            "sts-identity-result.json": "4e637b527807253474c05ec10fbba021b40ee8c7a4677463a0ca97f2062efac9",
            "sts-identity.rc": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
        }
        for name, digest in expected.items():
            self.assertEqual(self.sha(RUN / name), digest)
        ledger = (RUN / "STS_IDENTITY_FILES.sha256").read_text(encoding="utf-8")
        for name, digest in expected.items():
            self.assertIn(f"{digest}  {name}", ledger)

    def test_independent_artifact_verification_is_exact(self) -> None:
        verification = self.load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
        self.assertEqual(verification["workflow_run_id"], 31250176507)
        self.assertEqual(verification["workflow_job_id"], 93085194965)
        self.assertEqual(verification["artifact_id"], 9019744292)
        self.assertEqual(
            verification["provider_digest"],
            "sha256:3ebb71763783135c2c21bb7c0f8a801e0d873208e5a8b9afff473b208a2dc607",
        )
        self.assertEqual(
            verification["downloaded_zip_sha256"],
            "3ebb71763783135c2c21bb7c0f8a801e0d873208e5a8b9afff473b208a2dc607",
        )
        self.assertTrue(verification["validation"]["all_checks_pass"])
        self.assertFalse(verification["validation"]["s3_called"])
        self.assertFalse(verification["validation"]["requester_pays_used"])

    def test_attestation_does_not_open_s3_or_market_gates(self) -> None:
        attestation = self.load(EVIDENCE / "HL-AWS-OIDC-IDENTITY-001-ATTESTATION.json")
        self.assertEqual(attestation["status"], "ATTESTED_STS_IDENTITY_MATCH")
        self.assertEqual(attestation["reviewed_commit"], EXPECTED_COMMIT)
        self.assertEqual(attestation["workflow_run_id"], 31250176507)
        self.assertEqual(attestation["workflow_job_id"], 93085194965)
        self.assertEqual(attestation["artifact_id"], 9019744292)
        self.assertFalse(attestation["persistent_s3_permission_policy_independently_verified"])
        self.assertFalse(attestation["s3_called"])
        self.assertFalse(attestation["requester_pays_used"])
        self.assertFalse(attestation["market_data_ingested"])
        self.assertIsNone(attestation["empirical_result"])
        self.assertTrue(all(value is False for value in attestation["authorizations"].values()))


if __name__ == "__main__":
    unittest.main()
