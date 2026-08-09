from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-hourly-metadata-inventory-r3.yml"


class ArchiveHourlyMetadataR3WorkflowTests(unittest.TestCase):
    def text(self) -> str:
        return WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_is_manual_only_and_github_native_identity_bound(self) -> None:
        text = self.text()
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("push:", text)
        self.assertIn("EVENT_NAME: ${{ github.event_name }}", text)
        self.assertIn("DISPATCH_REF: ${{ github.ref }}", text)
        self.assertIn("DISPATCH_SHA: ${{ github.sha }}", text)
        self.assertIn("refs/heads/main", text)
        self.assertIn("persist-credentials: false", text)
        self.assertNotIn("reviewed_commit:", text)

    def test_implementation_and_activation_overlay_gate_precede_oidc(self) -> None:
        text = self.text()
        self.assertIn("EXPECTED_IMPLEMENTATION_COMMIT: 3b1dd0df4c5194875e22c1b790e0b41961313aa8", text)
        self.assertIn("EXECUTION_RELEASE_PATH: research/archive_inventory/r3/R3_EXECUTION_RELEASE_CANONICALIZATION.json", text)
        self.assertIn("RELEASE_CANDIDATE_PATH: research/archive_inventory/r3/R3_EXECUTION_RELEASE.json", text)
        self.assertLess(
            text.index("Prove canonical implementation and release before AWS OIDC"),
            text.index("Assume exact AWS role with R3-only session permissions"),
        )
        self.assertLess(
            text.index("Enforce R3 single-use release before AWS OIDC"),
            text.index("Assume exact AWS role with R3-only session permissions"),
        )
        self.assertIn("RELEASED_FOR_EXACTLY_ONE_CANONICAL_R3_RUN", text)

    def test_oidc_session_is_exact_three_prefix_list_only(self) -> None:
        text = self.text()
        self.assertIn('"Action":"s3:ListBucket"', text)
        self.assertIn('"Resource":"arn:aws:s3:::hl-mainnet-node-data"', text)
        self.assertIn("node_fills_by_block/hourly/*", text)
        self.assertIn("node_fills/hourly/*", text)
        self.assertIn("node_trades/hourly/*", text)
        self.assertIn('"s3:max-keys":"1000"', text)
        for forbidden in (
            "s3:GetObject", "s3:GetObjectAttributes", "s3:ListBucketVersions",
            "s3:ListAllMyBuckets", "explorer_blocks/*", "replica_cmds/*",
            "market_data/*", "asset_ctxs/*",
        ):
            self.assertNotIn(forbidden, text)

    def test_exact_approved_caps_are_rechecked_before_oidc(self) -> None:
        text = self.text()
        for assertion in (
            "assert approval['maximum_list_requests'] == 48",
            "assert approval['maximum_pages_per_family'] == 16",
            "assert approval['maximum_keys_per_request'] == 1000",
            "assert approval['maximum_total_entries'] == 48000",
            "assert approval['maximum_total_response_bytes'] == 33554432",
            "assert approval['maximum_runtime_seconds'] == 300",
            "assert approval['maximum_retries_per_request'] == 0",
            "assert approval['pagination_authorized'] is True",
            "assert approval['continuation_token_values_retained'] is False",
        ):
            self.assertIn(assertion, text)

    def test_single_use_history_check_and_rerun_guard_precede_oidc(self) -> None:
        text = self.text()
        self.assertIn("CURRENT_RUN_ATTEMPT", text)
        self.assertIn("Run attempt must be 1; re-runs are forbidden", text)
        self.assertIn("?event=workflow_dispatch&branch=main&per_page=100", text)
        self.assertIn("a previous dispatch already consumed the R3 release", text)
        self.assertIn("single_use_window_start_utc", text)
        self.assertLess(
            text.index("Run attempt must be 1; re-runs are forbidden"),
            text.index("Assume exact AWS role with R3-only session permissions"),
        )

    def test_collector_output_is_minimized_and_final_gate_is_fail_closed(self) -> None:
        text = self.text()
        self.assertIn("python research/archive_inventory/r3/collector.py", text)
        self.assertIn(">/dev/null", text)
        self.assertIn("R3_METADATA_FILES.sha256", text)
        self.assertIn("retention-days: 90", text)
        self.assertIn("compression-level: 6", text)
        self.assertIn("R3_HOURLY_METADATA_INVENTORY_PASS", text)
        self.assertIn("THREE_HOURLY_FAMILIES_COMPLETE_OR_CENSORED", text)
        self.assertIn("continuation_token_values_retained'] is False", text)
        self.assertIn("object_body_requested'] is False", text)
        self.assertIn("market_data_ingested'] is False", text)

    def test_permissions_and_actions_are_pinned(self) -> None:
        text = self.text()
        self.assertIn("actions: read", text)
        self.assertIn("contents: read", text)
        self.assertIn("id-token: write", text)
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", text)
        self.assertIn("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065", text)
        self.assertIn("aws-actions/configure-aws-credentials@e6de054238d6b7531b4efff3b6587d9aade6a06c", text)
        self.assertIn("actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a", text)


if __name__ == "__main__":
    unittest.main()
