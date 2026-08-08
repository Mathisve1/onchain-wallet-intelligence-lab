from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-nodedata-canary-r2.yml"
BASE = ROOT / "research/archive_inventory/r2"
LEGACY_RELEASE = BASE / "R2_EXECUTION_RELEASE.json"
SUCCESSOR_RELEASE = BASE / "R2_EXECUTION_RELEASE_002.json"
CONSUMPTION = BASE / "R2_EXECUTION_RELEASE_001_CONSUMPTION.json"
IMPLEMENTATION_COMMIT = "142ce50be20507761c4cce37b325ac69d57f8b25"


class ArchiveNodeDataCanaryR2WorkflowTests(unittest.TestCase):
    def text(self) -> str:
        return WORKFLOW.read_text(encoding="utf-8")

    def test_manual_only_and_github_native_identity_gates_exist(self) -> None:
        text = self.text()
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("push:", text)
        self.assertNotIn("reviewed_commit:", text)
        self.assertNotIn("inputs.reviewed_commit", text)
        self.assertIn("EVENT_NAME: ${{ github.event_name }}", text)
        self.assertIn("DISPATCH_REF: ${{ github.ref }}", text)
        self.assertIn("DISPATCH_SHA: ${{ github.sha }}", text)
        self.assertIn("ref: ${{ env.DISPATCH_SHA }}", text)
        self.assertIn('if [[ "${EVENT_NAME}" != "workflow_dispatch" ]]', text)
        self.assertIn('if [[ "${DISPATCH_REF}" != "refs/heads/main" ]]', text)
        self.assertIn('if [[ ! "${DISPATCH_SHA}" =~ ^[0-9a-f]{40}$ ]]', text)
        self.assertIn('if [[ "${observed_head}" != "${DISPATCH_SHA}" ]]', text)
        for code in (41, 42, 43, 44):
            self.assertIn(f"exit {code}", text)

    def test_predecessor_and_successor_release_are_separate(self) -> None:
        text = self.text()
        self.assertIn("EXECUTION_RELEASE_PATH: research/archive_inventory/r2/R2_EXECUTION_RELEASE.json", text)
        self.assertIn("SUCCESSOR_EXECUTION_RELEASE_PATH: research/archive_inventory/r2/R2_EXECUTION_RELEASE_002.json", text)
        self.assertIn("PREDECESSOR_CONSUMPTION_PATH: research/archive_inventory/r2/R2_EXECUTION_RELEASE_001_CONSUMPTION.json", text)
        self.assertTrue(LEGACY_RELEASE.is_file())
        self.assertTrue(SUCCESSOR_RELEASE.is_file())
        self.assertTrue(CONSUMPTION.is_file())

    def test_approval_and_canonical_implementation_remain_exactly_bound(self) -> None:
        text = self.text()
        self.assertIn("PREREGISTRATION_COMMIT: 39b40cccc7e9a3fdbc439d06fb188e946d9da2aa", text)
        self.assertIn("APPROVAL_MERGE_COMMIT: 151e08f54037ca7d3a0a9c17d3bdfb84d707a66e", text)
        self.assertIn("APPROVAL_TEXT_SHA256: 728f4e21c045eb10e883bdf0f2e970686f0e6b6cc4dc67a4f214a882cf1831c6", text)
        self.assertIn(f"EXPECTED_IMPLEMENTATION_COMMIT: {IMPLEMENTATION_COMMIT}", text)
        self.assertNotIn("EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE", text)

    def test_successor_release_proof_occurs_before_oidc(self) -> None:
        text = self.text()
        identity = text.index("Verify canonical manual main dispatch and checked-out identity")
        proof = text.index("Prove canonical implementation and single-use release before AWS OIDC")
        single_use = text.index("Enforce successor single-use release before AWS OIDC")
        configure = text.index("aws-actions/configure-aws-credentials@")
        execute = text.index("Execute bounded five-prefix R2 collector")
        self.assertLess(identity, proof)
        self.assertLess(proof, single_use)
        self.assertLess(single_use, configure)
        self.assertLess(configure, execute)
        self.assertIn("python governance/validate_r2_successor_release.py", text)
        self.assertIn("a previous dispatch already consumed R2 successor release 002", text)
        self.assertIn("Run attempt must be 1; re-runs are forbidden", text)

    def test_oidc_session_is_exact_five_prefix_list_only(self) -> None:
        text = self.text()
        self.assertIn("aws-region: ap-northeast-1", text)
        self.assertIn('"Action":"s3:ListBucket"', text)
        self.assertIn('"Resource":"arn:aws:s3:::hl-mainnet-node-data"', text)
        self.assertIn('"s3:max-keys":"25"', text)
        for prefix in (
            "node_fills_by_block/*", "node_fills/*", "node_trades/*", "explorer_blocks/*", "replica_cmds/*",
        ):
            self.assertIn(prefix, text)
        self.assertNotIn('"Action":"s3:GetObject"', text)
        self.assertNotIn('"Action":"s3:HeadObject"', text)
        self.assertNotIn('"Resource":"arn:aws:s3:::hyperliquid-archive"', text)
        self.assertNotIn("market_data/*", text)
        self.assertNotIn("asset_ctxs/*", text)

    def test_successor_release_keeps_broader_capabilities_closed(self) -> None:
        text = self.text()
        for key in (
            "get_object_authorized", "head_object_authorized", "get_object_attributes_authorized",
            "range_get_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized",
            "object_body_download_authorized", "decompression_authorized", "market_data_ingestion_authorized",
            "larger_300_request_inventory_authorized",
        ):
            self.assertIn(key, text)
        self.assertIn("assert release['rerun_authorized'] is False", text)
        self.assertIn("assert release['single_workflow_dispatch_authorized'] is True", text)

    def test_evidence_is_metadata_only_and_bounded(self) -> None:
        text = self.text()
        self.assertIn("maximum_list_requests': 5", text)
        self.assertIn("maximum_keys_per_request': 25", text)
        self.assertIn("maximum_total_entries': 125", text)
        self.assertIn("maximum_total_response_bytes': 8388608", text)
        self.assertIn("maximum_runtime_seconds': 120", text)
        self.assertIn("retries_used': 0", text)
        self.assertIn("pagination_followed': False", text)
        self.assertIn("http_redirects_followed': False", text)
        self.assertIn("object_body_requested': False", text)
        self.assertIn("decompression_used': False", text)
        self.assertIn("market_data_ingested': False", text)


if __name__ == "__main__":
    unittest.main()
