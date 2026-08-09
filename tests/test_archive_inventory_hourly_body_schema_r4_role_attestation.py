from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4"
TEXT = BASE / "role_attestation/R4_DEDICATED_ROLE_OPERATOR_ATTESTATION.txt"
ATTESTATION = BASE / "role_attestation/R4_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
TRUST = BASE / "R4_OIDC_TRUST_POLICY_TEMPLATE.json"
PERMISSION = BASE / "R4_IAM_POLICY_TEMPLATE.json"
RELEASE = BASE / "R4_EXECUTION_RELEASE.json"
ACTIVATION = BASE / "R4_EXECUTION_RELEASE_CANONICALIZATION.json"


class ArchiveHourlyBodySchemaR4RoleAttestationTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_operator_text_is_hash_bound(self) -> None:
        a = self.load(ATTESTATION)
        self.assertEqual(
            hashlib.sha256(TEXT.read_bytes()).hexdigest(),
            "5af72489211b1ad79e35f0491502e34d518df7c14ae6f2f8d56fbd2c3a5a83c2",
        )
        self.assertEqual(a["exact_attestation_text_sha256"], hashlib.sha256(TEXT.read_bytes()).hexdigest())

    def test_attested_policies_match_canonical_templates(self) -> None:
        a = self.load(ATTESTATION)
        self.assertEqual(hashlib.sha256(TRUST.read_bytes()).hexdigest(), a["trust_policy_sha256"])
        self.assertEqual(hashlib.sha256(PERMISSION.read_bytes()).hexdigest(), a["permission_policy_sha256"])
        self.assertEqual(a["role_arn"], "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4")
        self.assertTrue(a["role_created_and_policies_applied"])
        self.assertFalse(a["existing_metadata_role_modified"])

    def test_operator_attestation_requires_independent_sts_preflight(self) -> None:
        a = self.load(ATTESTATION)
        self.assertTrue(a["operator_attested"])
        self.assertFalse(a["independently_verified"])
        self.assertTrue(a["sts_only_preflight_required"])
        self.assertFalse(a["sts_only_preflight_completed"])
        self.assertFalse(a["preflight_s3_requests_authorized"])
        self.assertFalse(a["preflight_object_body_download_authorized"])
        self.assertFalse(a["preflight_decompression_authorized"])
        self.assertFalse(a["r4_execution_activation_authorized_by_this_attestation"])
        self.assertFalse(a["r4_execution_ready"])

    def test_release_candidate_remains_immutable_and_later_activation_is_separate(self) -> None:
        release = self.load(RELEASE)
        self.assertEqual(release["status"], "RELEASE_CANDIDATE_AWAITING_DEDICATED_R4_ROLE_ATTESTATION")
        self.assertFalse(release["dedicated_r4_role_operator_attested"])
        self.assertFalse(release["dedicated_r4_role_independently_verified"])
        self.assertFalse(release["single_workflow_dispatch_authorized"])
        self.assertFalse(release["requester_pays_authorized"])
        self.assertFalse(release["get_object_authorized"])
        self.assertFalse(release["decompression_authorized"])
        self.assertFalse(release["execution_ready"])
        if ACTIVATION.exists():
            activation = self.load(ACTIVATION)
            self.assertTrue(activation["release_candidate_immutable"])
            self.assertEqual(activation["role_attestation_merge_commit"], "c45527941dea7d152e332327ebd0593dc2413bea")
            self.assertEqual(activation["operator_attestation_text_sha256"], "5af72489211b1ad79e35f0491502e34d518df7c14ae6f2f8d56fbd2c3a5a83c2")
            self.assertTrue(activation["dedicated_r4_role_operator_attested"])
            self.assertTrue(activation["dedicated_r4_role_independently_verified"])
            self.assertEqual(activation["preflight_run_id"], 31312067367)
            self.assertFalse(activation["rerun_authorized"])

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r4_role_attestation.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R4_ROLE_OPERATOR_ATTESTATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
