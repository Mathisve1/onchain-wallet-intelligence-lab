from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-metadata-canary-r0.yml"


class ArchiveR0WorkflowTests(unittest.TestCase):
    def text(self) -> str:
        return WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_is_manual_only_and_exact_main_sha_bound(self) -> None:
        text = self.text()
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("push:", text)
        self.assertIn("EXACT_REVIEWED_COMMIT: ${{ inputs.reviewed_commit }}", text)
        self.assertIn('test "${DISPATCH_REF}" = "refs/heads/main"', text)
        self.assertIn('test "${EXACT_REVIEWED_COMMIT}" = "${DISPATCH_SHA}"', text)
        self.assertIn('git rev-parse HEAD', text)

    def test_permissions_and_actions_are_exactly_pinned(self) -> None:
        text = self.text()
        self.assertRegex(text, r"permissions:\n  contents: read\n  id-token: write")
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", text)
        self.assertIn("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065", text)
        self.assertIn("aws-actions/configure-aws-credentials@e6de054238d6b7531b4efff3b6587d9aade6a06c", text)
        self.assertIn("actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a", text)
        for match in re.finditer(r"uses:\s*([^\s]+)", text):
            self.assertRegex(match.group(1), r"@[0-9a-f]{40}$")

    def test_role_and_session_policy_are_exact_r0_list_only(self) -> None:
        text = self.text()
        self.assertIn("arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-metadata-canary", text)
        self.assertIn("allowed-account-ids: '630956766927'", text)
        self.assertIn('"Action":"s3:ListBucket"', text)
        self.assertIn('"Resource":"arn:aws:s3:::hl-mainnet-node-data"', text)
        self.assertIn('"Resource":"arn:aws:s3:::hyperliquid-archive"', text)
        for prefix in (
            "node_fills_by_block/*",
            "node_fills/*",
            "node_trades/*",
            "explorer_blocks/*",
            "replica_cmds/*",
            "market_data/*",
            "asset_ctxs/*",
        ):
            self.assertIn(prefix, text)
        self.assertEqual(text.count('"s3:max-keys":"25"'), 2)
        self.assertNotIn('"Action":"s3:*"', text)
        self.assertNotIn('"Action":"s3:GetObject"', text)
        self.assertNotIn('"Action":"s3:PutObject"', text)

    def test_retry_pagination_and_runtime_caps_are_hard_bound(self) -> None:
        text = self.text()
        self.assertIn("AWS_MAX_ATTEMPTS: '1'", text)
        self.assertIn("AWS_RETRY_MODE: standard", text)
        self.assertIn("retry-max-attempts: 1", text)
        self.assertIn("maximum_list_requests': 7", text)
        self.assertIn("maximum_keys_per_request': 25", text)
        self.assertIn("maximum_total_entries': 175", text)
        self.assertIn("maximum_total_response_bytes': 8388608", text)
        self.assertIn("maximum_runtime_seconds': 180", text)
        self.assertIn("maximum_retries_per_request': 0", text)
        self.assertIn("pagination_authorized': False", text)
        self.assertIn("assert result['retries_used'] == 0", text)
        self.assertIn("assert result['pagination_followed'] is False", text)

    def test_only_collector_can_issue_s3_command(self) -> None:
        text = self.text()
        self.assertNotIn("aws s3api", text)
        self.assertIn("python research/archive_inventory/r0/collector.py", text)
        self.assertNotIn("secrets.AWS_ACCESS_KEY_ID", text)
        self.assertNotIn("secrets.AWS_SECRET_ACCESS_KEY", text)
        self.assertNotIn("aws-access-key-id:", text)
        self.assertNotIn("aws-secret-access-key:", text)

    def test_artifact_is_metadata_only_and_final_gate_is_fail_closed(self) -> None:
        text = self.text()
        for name in (
            "r0-metadata-context.json",
            "r0-metadata-result.json",
            "r0-metadata.rc",
            "R0_METADATA_FILES.sha256",
        ):
            self.assertIn(name, text)
        self.assertIn("if-no-files-found: error", text)
        self.assertIn("assert result['terminal_status'] == 'R0_METADATA_CANARY_PASS'", text)
        self.assertIn("assert result['request_attempt_count'] == 7", text)
        self.assertIn("assert result['successful_request_count'] == 7", text)
        self.assertIn("assert result['object_body_requested'] is False", text)
        self.assertIn("assert result['market_data_ingested'] is False", text)


if __name__ == "__main__":
    unittest.main()
