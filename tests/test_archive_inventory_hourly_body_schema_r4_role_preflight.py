from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4"
CONTRACT = BASE / "role_attestation/R4_ROLE_STS_PREFLIGHT_CONTRACT.json"
ATTESTATION = BASE / "role_attestation/R4_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
BODY_RELEASE = BASE / "R4_EXECUTION_RELEASE.json"
BODY_ACTIVATION = BASE / "R4_EXECUTION_RELEASE_CANONICALIZATION.json"
PREFLIGHT_RELEASE = BASE / "role_attestation/R4_ROLE_STS_PREFLIGHT_RELEASE.json"
BODY_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-hourly-body-schema-pilot-r4.yml"
PREFLIGHT_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-hourly-body-schema-role-preflight-r4.yml"
BODY_WORKFLOW_SHA256 = "2499424483179f05472d951c3f9def2c791f156cd7cf36d465e93d4ab9d19677"
PREFLIGHT_IMPLEMENTATION = "3b0a1ae634288646f3757493d4e90258bae21421"


class ArchiveHourlyBodySchemaR4RolePreflightTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_preflight_binds_canonical_attestation_without_rewriting_body_release(self) -> None:
        c = self.load(CONTRACT)
        a = self.load(ATTESTATION)
        release = self.load(BODY_RELEASE)
        self.assertEqual(c["role_attestation_merge_commit"], "c45527941dea7d152e332327ebd0593dc2413bea")
        self.assertEqual(c["operator_attestation_text_sha256"], a["exact_attestation_text_sha256"])
        self.assertTrue(a["operator_attested"])
        self.assertFalse(a["independently_verified"])
        self.assertEqual(release["status"], "RELEASE_CANDIDATE_AWAITING_DEDICATED_R4_ROLE_ATTESTATION")
        self.assertFalse(release["dedicated_r4_role_operator_attested"])
        self.assertFalse(release["dedicated_r4_role_independently_verified"])
        self.assertFalse(release["single_workflow_dispatch_authorized"])
        self.assertFalse(release["execution_ready"])
        self.assertFalse(BODY_ACTIVATION.exists())

    def test_implementation_snapshot_is_inert_and_future_release_is_separate(self) -> None:
        c = self.load(CONTRACT)
        self.assertEqual(c["status"], "IMPLEMENTED_AWAITING_SEPARATE_PREFLIGHT_RELEASE")
        self.assertTrue(c["preflight_release_required"])
        self.assertFalse(c["preflight_release_present"])
        self.assertFalse(c["preflight_execution_authorized"])
        self.assertFalse(c["preflight_s3_requests_authorized"])
        self.assertFalse(c["preflight_get_object_authorized"])
        self.assertFalse(c["preflight_object_body_download_authorized"])
        self.assertFalse(c["r4_body_release_consumed_by_preflight"])
        self.assertFalse(c["r4_body_execution_activation_authorized"])
        if PREFLIGHT_RELEASE.exists():
            later = self.load(PREFLIGHT_RELEASE)
            self.assertEqual(later["preflight_release_id"], "RELEASE_HL_ARCHIVE_R4_ROLE_STS_PREFLIGHT_001")
            self.assertFalse(later["s3_requests_authorized"])
            self.assertFalse(later["body_release_consumed_by_preflight"])

    def test_body_workflow_remains_byte_unchanged(self) -> None:
        self.assertEqual(hashlib.sha256(BODY_WORKFLOW.read_bytes()).hexdigest(), BODY_WORKFLOW_SHA256)

    def test_preflight_workflow_has_same_oidc_name_but_separate_file_and_run_name(self) -> None:
        body = BODY_WORKFLOW.read_text(encoding="utf-8")
        preflight = PREFLIGHT_WORKFLOW.read_text(encoding="utf-8")
        expected_name = "name: Hyperliquid Archive Hourly Body Schema Pilot R4\n"
        pending_assignment = (
            "EXPECTED_PREFLIGHT_IMPLEMENTATION_COMMIT: "
            "PENDING_CANONICAL_PREFLIGHT_IMPLEMENTATION_MERGE"
        )
        self.assertTrue(body.startswith(expected_name))
        self.assertTrue(preflight.startswith(expected_name))
        self.assertIn("run-name: R4 dedicated role STS-only preflight", preflight)
        self.assertIn("workflow_dispatch:", preflight)
        self.assertIn("refs/heads/main", preflight)
        if PREFLIGHT_RELEASE.exists():
            self.assertIn(f"EXPECTED_PREFLIGHT_IMPLEMENTATION_COMMIT: {PREFLIGHT_IMPLEMENTATION}", preflight)
            self.assertNotIn(pending_assignment, preflight)
        else:
            self.assertIn(pending_assignment, preflight)

    def test_preflight_session_policy_explicitly_denies_all_s3_and_has_no_s3_operation(self) -> None:
        text = PREFLIGHT_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("DenyAllS3DuringR4RolePreflight", text)
        self.assertIn('"Effect":"Deny"', text)
        self.assertIn('"Action":"s3:*"', text)
        self.assertNotIn('"Effect":"Allow","Action":"s3:', text)
        self.assertNotIn("aws s3", text)
        self.assertNotIn("x-amz-request-payer", text.lower())
        self.assertNotIn("research/archive_inventory/r4/collector.py", text)
        self.assertNotIn("node_fills/hourly/20250727/8.lz4", text)
        self.assertNotIn("node_fills_by_block/hourly/20250727/8.lz4", text)

    def test_preflight_has_exactly_one_explicit_aws_cli_call_and_minimized_evidence(self) -> None:
        text = PREFLIGHT_WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(text.count("aws sts get-caller-identity --output json"), 1)
        self.assertEqual(text.count("\n          aws "), 1)
        self.assertIn("raw_oidc_token_retained': False", text)
        self.assertIn("aws_credentials_retained': False", text)
        self.assertIn("raw_caller_identity_retained': False", text)
        self.assertIn("s3_http_request_count': 0", text)
        self.assertIn("object_bytes_downloaded': 0", text)
        self.assertIn("body_release_consumed_by_preflight': False", text)
        self.assertIn("body_execution_activation_authorized': False", text)

    def test_actions_are_pinned_and_preflight_release_gate_precedes_oidc(self) -> None:
        text = PREFLIGHT_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", text)
        self.assertIn("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065", text)
        self.assertIn("aws-actions/configure-aws-credentials@e6de054238d6b7531b4efff3b6587d9aade6a06c", text)
        self.assertIn("actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a", text)
        release_gate = text.index("Prove canonical R4 role attestation and preflight release before OIDC")
        single_use = text.index("Enforce single-use R4 STS preflight before AWS OIDC")
        oidc = text.index("Assume dedicated R4 role with all S3 explicitly denied")
        self.assertLess(release_gate, single_use)
        self.assertLess(single_use, oidc)

    def test_dedicated_preflight_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r4_role_preflight.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R4_ROLE_STS_PREFLIGHT_IMPLEMENTATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
