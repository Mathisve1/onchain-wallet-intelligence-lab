from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4"
CONTRACT = BASE / "role_attestation/R4_ROLE_STS_PREFLIGHT_CONTRACT.json"
ATTESTATION = BASE / "role_attestation/R4_DEDICATED_ROLE_OPERATOR_ATTESTATION.json"
ANCHOR = BASE / "role_attestation/R4_ROLE_STS_PREFLIGHT_RELEASE_ANCHOR.json"
RELEASE = BASE / "role_attestation/R4_ROLE_STS_PREFLIGHT_RELEASE.json"
BODY_RELEASE = BASE / "R4_EXECUTION_RELEASE.json"
BODY_ACTIVATION = BASE / "R4_EXECUTION_RELEASE_CANONICALIZATION.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-hourly-body-schema-role-preflight-r4.yml"
IMPLEMENTATION = "3b0a1ae634288646f3757493d4e90258bae21421"


class ArchiveHourlyBodySchemaR4RolePreflightReleaseTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_release_binds_exact_implementation_attestation_and_anchor(self) -> None:
        c = self.load(CONTRACT)
        a = self.load(ATTESTATION)
        anchor = self.load(ANCHOR)
        release = self.load(RELEASE)
        self.assertEqual(release["preflight_id"], c["preflight_id"])
        self.assertEqual(release["preflight_implementation_commit"], IMPLEMENTATION)
        self.assertEqual(release["role_attestation_merge_commit"], "c45527941dea7d152e332327ebd0593dc2413bea")
        self.assertEqual(release["operator_attestation_text_sha256"], a["exact_attestation_text_sha256"])
        self.assertEqual(release["anchor_commit"], "1c01ee6275b4c3ca1afd89385c5c740e99cbc362")
        self.assertEqual(release["single_use_window_start_utc"], "2026-08-09T10:36:28Z")
        self.assertFalse(anchor["execution_authorized_by_this_file"])
        self.assertEqual(anchor["requests_executed"], 0)

    def test_release_opens_exactly_one_sts_identity_dispatch_and_no_s3(self) -> None:
        release = self.load(RELEASE)
        self.assertEqual(release["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_STS_PREFLIGHT")
        self.assertTrue(release["single_workflow_dispatch_authorized"])
        self.assertFalse(release["rerun_authorized"])
        self.assertTrue(release["sts_get_caller_identity_authorized"])
        self.assertEqual(release["maximum_explicit_aws_cli_calls"], 1)
        self.assertEqual(release["inline_session_policy"], "DENY_ALL_S3_ON_ALL_RESOURCES")
        for key in (
            "s3_requests_authorized", "requester_pays_authorized", "get_object_authorized",
            "list_objects_authorized", "head_object_authorized", "range_get_authorized",
            "object_body_download_authorized", "decompression_authorized",
            "body_release_consumed_by_preflight", "body_execution_activation_authorized",
        ):
            self.assertFalse(release[key], key)
        self.assertEqual(release["s3_requests_executed"], 0)
        self.assertEqual(release["object_bytes_downloaded"], 0)
        self.assertIsNone(release["empirical_result"])

    def test_body_release_snapshot_remains_inert_and_later_activation_is_separate(self) -> None:
        body = self.load(BODY_RELEASE)
        self.assertEqual(body["status"], "RELEASE_CANDIDATE_AWAITING_DEDICATED_R4_ROLE_ATTESTATION")
        self.assertFalse(body["single_workflow_dispatch_authorized"])
        self.assertFalse(body["requester_pays_authorized"])
        self.assertFalse(body["get_object_authorized"])
        self.assertFalse(body["decompression_authorized"])
        self.assertFalse(body["execution_ready"])
        if BODY_ACTIVATION.exists():
            activation = self.load(BODY_ACTIVATION)
            self.assertTrue(activation["release_candidate_immutable"])
            self.assertEqual(activation["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R4_RUN")
            self.assertEqual(activation["preflight_run_id"], 31312067367)
            self.assertTrue(activation["preflight_release_consumed"])
            self.assertFalse(activation["preflight_rerun_authorized"])
            self.assertEqual(activation["preflight_s3_requests_executed"], 0)
            self.assertTrue(activation["dedicated_r4_role_independently_verified"])
            self.assertTrue(activation["single_workflow_dispatch_authorized"])
            self.assertFalse(activation["rerun_authorized"])

    def test_workflow_is_bound_to_canonical_preflight_implementation(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        pending_assignment = (
            "EXPECTED_PREFLIGHT_IMPLEMENTATION_COMMIT: "
            "PENDING_CANONICAL_PREFLIGHT_IMPLEMENTATION_MERGE"
        )
        self.assertIn(f"EXPECTED_PREFLIGHT_IMPLEMENTATION_COMMIT: {IMPLEMENTATION}", text)
        self.assertNotIn(pending_assignment, text)
        self.assertIn("DenyAllS3DuringR4RolePreflight", text)
        self.assertEqual(text.count("aws sts get-caller-identity --output json"), 1)
        self.assertNotIn("aws s3", text)

    def test_release_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r4_role_preflight_release.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R4_ROLE_STS_PREFLIGHT_RELEASE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
