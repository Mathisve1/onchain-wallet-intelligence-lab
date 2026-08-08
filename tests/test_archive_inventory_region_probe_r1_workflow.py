from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-region-probe-r1.yml"
BASE = ROOT / "research/archive_inventory/region_probe_r1"


class ArchiveRegionProbeR1WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_is_manual_only_and_exact_main_sha_bound(self) -> None:
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("pull_request:", self.text)
        self.assertNotIn("push:", self.text)
        self.assertIn('test "${DISPATCH_REF}" = "refs/heads/main"', self.text)
        self.assertIn('test "${EXACT_REVIEWED_COMMIT}" = "${DISPATCH_SHA}"', self.text)
        self.assertIn("persist-credentials: false", self.text)

    def test_actions_are_pinned_and_permissions_are_minimal(self) -> None:
        self.assertIn("actions: read", self.text)
        self.assertIn("contents: read", self.text)
        self.assertIn("id-token: write", self.text)
        for sha in (
            "11d5960a326750d5838078e36cf38b85af677262",
            "a26af69be951a213d495a4c3e4e4022e16d87065",
            "e6de054238d6b7531b4efff3b6587d9aade6a06c",
            "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
        ):
            self.assertIn(f"@{sha}", self.text)

    def test_release_gate_and_canonical_implementation_placeholder_precede_oidc(self) -> None:
        gate = self.text.index("Prove approval implementation and separate execution release before AWS OIDC")
        oidc = self.text.index("Assume exact AWS role with explicit deny-all-S3 session policy")
        self.assertLess(gate, oidc)
        self.assertIn("PENDING_CANONICAL_IMPLEMENTATION_MERGE", self.text)
        self.assertIn("canonical implementation SHA not released yet", self.text)
        self.assertIn("post-implementation Region probe execution release is absent", self.text)
        self.assertFalse((BASE / "REGION_PROBE_EXECUTION_RELEASE.json").exists())

    def test_oidc_session_explicitly_denies_all_s3_and_has_no_s3_allow(self) -> None:
        self.assertIn('"Sid":"DenyAllS3DuringRegionProbe"', self.text)
        self.assertIn('"Effect":"Deny","Action":"s3:*","Resource":"*"', self.text)
        self.assertNotIn('"Effect":"Allow","Action":"s3:', self.text)
        self.assertNotIn('"Action":"s3:ListBucket"', self.text)
        self.assertIn("allowed-account-ids: '630956766927'", self.text)
        self.assertIn("role-duration-seconds: 900", self.text)
        self.assertIn("retry-max-attempts: 1", self.text)

    def test_only_probe_code_can_issue_s3_transport_and_no_s3_cli_exists(self) -> None:
        self.assertIn("python research/archive_inventory/region_probe_r1/probe.py", self.text)
        self.assertNotIn("aws s3api", self.text)
        self.assertNotIn("aws s3 ", self.text)
        self.assertNotIn("curl ", self.text)
        self.assertNotIn("wget ", self.text)
        self.assertNotIn("secrets.AWS_ACCESS_KEY_ID", self.text)
        self.assertNotIn("secrets.AWS_SECRET_ACCESS_KEY", self.text)

    def test_single_use_history_gate_precedes_oidc(self) -> None:
        single_use = self.text.index("Enforce single-use release before AWS OIDC")
        oidc = self.text.index("Assume exact AWS role with explicit deny-all-S3 session policy")
        self.assertLess(single_use, oidc)
        self.assertIn("CURRENT_RUN_ATTEMPT", self.text)
        self.assertIn('test "${CURRENT_RUN_ATTEMPT}" = \'1\'', self.text)
        self.assertIn("event=workflow_dispatch&branch=main&per_page=100", self.text)
        self.assertIn("len(runs) < 100", self.text)
        self.assertIn("len(eligible) == 1", self.text)
        self.assertIn("a previous Region probe dispatch already consumed this release", self.text)

    def test_artifact_is_minimized_and_final_gate_is_fail_closed(self) -> None:
        for name in (
            "region-probe-r1-context.json",
            "region-probe-r1-result.json",
            "region-probe-r1.rc",
            "REGION_PROBE_R1_FILES.sha256",
        ):
            self.assertIn(name, self.text)
        self.assertIn("REGION_PROBE_R1_PASS", self.text)
        self.assertIn("s3_http_request_count'] == 1", self.text)
        self.assertIn("response_body_read'] is False", self.text)
        self.assertIn("list_objects_v2_requested'] is False", self.text)
        self.assertIn("object_body_requested'] is False", self.text)
        self.assertIn("market_data_ingested'] is False", self.text)


if __name__ == "__main__":
    unittest.main()
