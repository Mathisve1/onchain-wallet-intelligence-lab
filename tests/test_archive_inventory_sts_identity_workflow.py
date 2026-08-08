from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hyperliquid-aws-oidc-identity-check.yml"
ACCESS = ROOT / "research/archive_inventory/aws_access"


class ArchiveStsIdentityWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.contract = json.loads((ACCESS / "STS_IDENTITY_CHECK_CONTRACT.json").read_text(encoding="utf-8"))
        self.pending = json.loads((ACCESS / "PENDING_STS_IDENTITY_EVIDENCE.json").read_text(encoding="utf-8"))

    def test_contract_is_sts_only_and_all_market_gates_stay_closed(self) -> None:
        self.assertEqual(self.contract["check_id"], "HL-AWS-OIDC-IDENTITY-001")
        self.assertEqual(self.contract["status"], "PREREGISTERED_STS_ONLY_MANUAL_RUN_ALLOWED")
        scope = self.contract["network_scope"]
        self.assertTrue(scope["oidc_token_request_authorized"])
        self.assertTrue(scope["assume_role_with_web_identity_authorized"])
        self.assertTrue(scope["explicit_sts_get_caller_identity_authorized"])
        self.assertEqual(scope["s3_session_policy"], "EXPLICIT_DENY_ALL_S3")
        for key in (
            "s3_api_calls_authorized",
            "requester_pays_authorized",
            "list_objects_authorized",
            "get_object_authorized",
            "head_object_authorized",
            "range_get_authorized",
            "object_body_download_authorized",
        ):
            self.assertFalse(scope[key])
        self.assertFalse(self.contract["market_data_ingested"])
        self.assertIsNone(self.contract["empirical_result"])
        self.assertTrue(all(value is False for value in self.contract["authorizations"].values()))

    def test_pending_evidence_is_not_a_result(self) -> None:
        self.assertEqual(self.pending["status"], "PENDING_MANUAL_CANONICAL_MAIN_RUN")
        for key in (
            "dispatch_ref", "dispatch_sha", "reviewed_commit", "checked_out_commit",
            "workflow_run_id", "workflow_run_attempt", "observed_account_id",
            "observed_assumed_role_arn",
        ):
            self.assertIsNone(self.pending[key])
        self.assertFalse(self.pending["s3_called"])
        self.assertFalse(self.pending["requester_pays_used"])
        self.assertFalse(self.pending["market_data_ingested"])
        self.assertIsNone(self.pending["empirical_result"])

    def test_workflow_is_manual_only_and_exact_main_sha_bound(self) -> None:
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("pull_request:", self.text)
        self.assertNotRegex(self.text, r"(?m)^\s*push:\s*$")
        self.assertIn("EXACT_REVIEWED_COMMIT: ${{ inputs.reviewed_commit }}", self.text)
        self.assertIn('test "${DISPATCH_REF}" = "refs/heads/main"', self.text)
        self.assertIn('test "${EXACT_REVIEWED_COMMIT}" = "${DISPATCH_SHA}"', self.text)
        self.assertIn('observed="$(git rev-parse HEAD)"', self.text)
        self.assertIn('test "${observed}" = "${EXACT_REVIEWED_COMMIT}"', self.text)

    def test_workflow_permissions_are_minimal_for_oidc(self) -> None:
        self.assertRegex(self.text, r"(?ms)^permissions:\n  contents: read\n  id-token: write\n")
        for forbidden in ("contents: write", "actions: write", "issues: write", "pull-requests: write", "packages: write"):
            self.assertNotIn(forbidden, self.text)
        self.assertNotIn("secrets.", self.text)

    def test_actions_are_exactly_pinned(self) -> None:
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", self.text)
        self.assertIn("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065", self.text)
        self.assertIn("aws-actions/configure-aws-credentials@e6de054238d6b7531b4efff3b6587d9aade6a06c", self.text)
        self.assertIn("actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a", self.text)
        for line in self.text.splitlines():
            if "uses:" in line:
                ref = line.split("@", 1)[1].strip()
                self.assertRegex(ref, r"^[0-9a-f]{40}$")

    def test_role_assumption_is_account_bound_short_lived_and_s3_denied(self) -> None:
        self.assertIn("role-to-assume: arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-metadata-canary", self.text)
        self.assertIn("allowed-account-ids: '630956766927'", self.text)
        self.assertIn("role-duration-seconds: 900", self.text)
        self.assertIn("role-session-name: HLArchiveOidcIdentityCheck", self.text)
        self.assertIn("retry-max-attempts: 3", self.text)
        self.assertIn("action-timeout-s: 60", self.text)
        self.assertIn('"Sid":"DenyAllS3ForIdentityCheck"', self.text)
        self.assertIn('"Effect":"Deny"', self.text)
        self.assertIn('"Action":"s3:*"', self.text)
        self.assertIn('"Resource":"*"', self.text)

    def test_static_repository_gates_run_before_aws_oidc(self) -> None:
        gate = self.text.index("Prove repository and STS-only gates before OIDC network access")
        configure = self.text.index("Assume exact AWS role through GitHub OIDC with S3 denied for this session")
        self.assertLess(gate, configure)
        self.assertIn("python -m unittest discover -s tests -v", self.text[gate:configure])
        self.assertIn("python governance/validate_repository.py", self.text[gate:configure])

    def test_explicit_aws_cli_scope_is_exactly_one_sts_identity_call(self) -> None:
        commands = re.findall(r"(?m)^\s*aws\s+([^\n]+)$", self.text)
        self.assertEqual(commands, ['sts get-caller-identity --output json >"${raw}"'])
        lowered = self.text.lower()
        for forbidden in (
            "aws s3 ", "aws s3api", "listobject", "request-payer", "requestpayer",
            "getobject", "headobject", "hl-mainnet-node-data", "hyperliquid-archive",
        ):
            self.assertNotIn(forbidden, lowered)

    def test_artifact_is_minimized_and_no_raw_identity_payload_is_retained(self) -> None:
        self.assertIn("raw_path.unlink(missing_ok=True)", self.text)
        self.assertNotIn("sts-identity-raw.json\n", self.text.split("path: |", 1)[-1])
        self.assertIn("sts-identity-context.json", self.text)
        self.assertIn("sts-identity-result.json", self.text)
        self.assertIn("STS_IDENTITY_FILES.sha256", self.text)
        for secret_name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
            self.assertNotIn(secret_name, self.text)


if __name__ == "__main__":
    unittest.main()
