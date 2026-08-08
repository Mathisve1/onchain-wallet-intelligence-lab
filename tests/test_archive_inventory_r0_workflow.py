from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-metadata-canary-r0.yml"
RELEASE = ROOT / "research/archive_inventory/r0/R0_EXECUTION_RELEASE.json"
IMPLEMENTATION_COMMIT = "cd5c46b25502b671693dd5ebb091e7273399bccf"
APPROVAL_TIME = "2026-08-08T10:10:00Z"


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
        self.assertIn("git rev-parse HEAD", text)

    def test_permissions_and_actions_are_exactly_pinned(self) -> None:
        text = self.text()
        self.assertRegex(text, r"permissions:\n  actions: read\n  contents: read\n  id-token: write")
        for match in re.finditer(r"uses:\s*([^\s]+)", text):
            self.assertRegex(match.group(1), r"@[0-9a-f]{40}$")

    def test_role_and_session_policy_remain_r0_list_only(self) -> None:
        text = self.text()
        self.assertIn("allowed-account-ids: '630956766927'", text)
        self.assertIn('"Action":"s3:ListBucket"', text)
        self.assertEqual(text.count('"s3:max-keys":"25"'), 2)
        for prefix in (
            "node_fills_by_block/*", "node_fills/*", "node_trades/*",
            "explorer_blocks/*", "replica_cmds/*", "market_data/*", "asset_ctxs/*",
        ):
            self.assertIn(prefix, text)
        self.assertNotIn('"Action":"s3:*"', text)
        self.assertNotIn('"Action":"s3:GetObject"', text)
        self.assertNotIn('"Action":"s3:PutObject"', text)

    def test_hard_caps_are_unchanged(self) -> None:
        text = self.text()
        for token in (
            "maximum_list_requests': 7", "maximum_keys_per_request': 25",
            "maximum_total_entries': 175", "maximum_total_response_bytes': 8388608",
            "maximum_runtime_seconds': 180", "maximum_retries_per_request': 0",
            "pagination_authorized': False", "http_redirect_following_authorized': False",
            "DIRECT_SIGV4_HTTPS_NO_REDIRECT_FOLLOW",
            "assert result['s3_http_request_count'] == 7",
            "assert result['retries_used'] == 0",
            "assert result['pagination_followed'] is False",
            "assert result['http_redirects_followed'] is False",
        ):
            self.assertIn(token, text)

    def test_release_is_exact_implementation_and_approval_bound_before_oidc(self) -> None:
        text = self.text()
        self.assertTrue(RELEASE.is_file())
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        self.assertEqual(release["release_id"], "RELEASE_HL_ARCHIVE_METADATA_CANARY_R0_001")
        self.assertEqual(release["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R0_RUN")
        self.assertEqual(release["implementation_commit"], IMPLEMENTATION_COMMIT)
        self.assertEqual(release["single_use_window_start_utc"], APPROVAL_TIME)
        self.assertIn(f"EXPECTED_IMPLEMENTATION_COMMIT: {IMPLEMENTATION_COMMIT}", text)
        self.assertIn(f"SINGLE_USE_WINDOW_START_UTC: '{APPROVAL_TIME}'", text)
        self.assertIn("release['implementation_commit'] == os.environ['EXPECTED_IMPLEMENTATION_COMMIT']", text)
        self.assertIn("release['single_use_window_start_utc'] == approval['recorded_at_utc']", text)
        self.assertIn("CANONICAL_HUMAN_APPROVAL_RECORDED_AT_UTC", text)

    def test_single_use_history_and_rerun_gates_precede_oidc(self) -> None:
        text = self.text()
        self.assertIn("CURRENT_RUN_ATTEMPT: ${{ github.run_attempt }}", text)
        self.assertIn('test "${CURRENT_RUN_ATTEMPT}" = \'1\'', text)
        self.assertIn("api.github.com", text)
        self.assertIn("hyperliquid-archive-metadata-canary-r0.yml/runs", text)
        self.assertIn("event=workflow_dispatch&branch=main&per_page=100", text)
        self.assertIn("len(runs) < 100", text)
        self.assertIn("len(eligible) == 1", text)
        self.assertIn("previous R0 dispatch already consumed this approval-window release", text)
        self.assertIn("created >= window_start", text)
        self.assertNotIn("created >= release_time", text)
        self.assertLess(text.index("Enforce single-use approval-window release before AWS OIDC"), text.index("Assume exact AWS role with R0-only session permissions"))

    def test_only_collector_can_issue_s3_requests(self) -> None:
        text = self.text()
        self.assertNotIn("aws s3api", text)
        self.assertNotIn("aws s3 ", text)
        self.assertIn("python research/archive_inventory/r0/collector.py", text)
        self.assertNotIn("aws-access-key-id:", text)
        self.assertNotIn("aws-secret-access-key:", text)

    def test_artifact_is_metadata_only_and_final_gate_is_fail_closed(self) -> None:
        text = self.text()
        for name in ("r0-metadata-context.json", "r0-metadata-result.json", "r0-metadata.rc", "R0_METADATA_FILES.sha256"):
            self.assertIn(name, text)
        self.assertIn("if-no-files-found: error", text)
        self.assertIn("R0_PRE_OIDC_GATE_FAILED", text)
        self.assertIn("assert result['terminal_status'] == 'R0_METADATA_CANARY_PASS'", text)
        self.assertIn("assert result['request_attempt_count'] == 7", text)
        self.assertIn("assert result['object_body_requested'] is False", text)
        self.assertIn("assert result['market_data_ingested'] is False", text)
        self.assertIn("single_use_window_start_utc", text)

    def test_oidc_session_is_short_lived_and_action_retry_is_one(self) -> None:
        text = self.text()
        self.assertIn("role-duration-seconds: 900", text)
        self.assertIn("retry-max-attempts: 1", text)
        self.assertIn("action-timeout-s: 60", text)
        self.assertIn("unset-current-credentials: true", text)
        self.assertNotIn("AWS_MAX_ATTEMPTS", text)
        self.assertNotIn("AWS_RETRY_MODE", text)


if __name__ == "__main__":
    unittest.main()
