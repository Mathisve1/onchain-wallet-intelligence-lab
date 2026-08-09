from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-modern-wallet-index-r8a.yml"


class ArchiveR8AWorkflowTests(unittest.TestCase):
    def text(self) -> str:
        return WORKFLOW.read_text(encoding="utf-8")

    def test_manual_only_trust_compatible_identity(self) -> None:
        text = self.text()
        self.assertTrue(text.startswith("name: Hyperliquid Archive Hourly Body Schema Pilot R4\nrun-name: R8A modern wallet-index bridge\n"))
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("push:", text)
        self.assertIn("DISPATCH_REF: ${{ github.ref }}", text)
        self.assertIn("DISPATCH_SHA: ${{ github.sha }}", text)
        self.assertIn("test \"${DISPATCH_REF}\" = 'refs/heads/main'", text)

    def test_permissions_actions_and_checkout_are_pinned(self) -> None:
        text = self.text()
        self.assertIn("actions: read", text)
        self.assertIn("contents: read", text)
        self.assertIn("id-token: write", text)
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", text)
        self.assertIn("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065", text)
        self.assertIn("aws-actions/configure-aws-credentials@e6de054238d6b7531b4efff3b6587d9aade6a06c", text)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", text)
        self.assertIn("persist-credentials: false", text)

    def test_release_and_single_use_gates_precede_oidc(self) -> None:
        text = self.text()
        oidc = text.index("Assume unchanged dedicated AWS role with exact-one-object R8A session")
        self.assertLess(text.index("Prove canonical R8A implementation and active release before AWS OIDC"), oidc)
        self.assertLess(text.index("Enforce R8A single-use release before AWS OIDC"), oidc)
        self.assertLess(text.index("Freeze pending R8A run context before AWS authentication"), oidc)
        self.assertIn("CURRENT_RUN_ATTEMPT", text)
        self.assertIn("assert len(eligible) == 1", text)

    def test_oidc_session_is_exact_one_object_get_only(self) -> None:
        text = self.text()
        self.assertIn('"Action":"s3:GetObject"', text)
        self.assertIn("arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/8.lz4", text)
        for forbidden in ("s3:ListBucket", "s3:GetObjectVersion", "s3:GetObjectAttributes", "s3:ListAllMyBuckets"):
            self.assertNotIn(forbidden, text)

    def test_artifact_contains_wallet_index_but_no_raw_object(self) -> None:
        text = self.text()
        for filename in ("r8a-context.json", "r8a-result.json", "r8a-wallet-index.ndjson", "r8a.rc", "R8A_FILES.sha256"):
            self.assertIn(filename, text)
        self.assertNotIn("raw-object", text)
        self.assertNotIn("decompressed-payload", text)
        self.assertIn("retention-days: 30", text)

    def test_terminal_gate_validates_sort_conservation_and_no_performance_fields(self) -> None:
        text = self.text()
        self.assertIn("summary['top_level_block_record_count'] == 4345", text)
        self.assertIn("addresses == sorted(addresses)", text)
        self.assertIn("len(addresses) == len(set(addresses))", text)
        self.assertIn("sum(row['fill_count'] for row in rows) == summary['valid_event_pair_count']", text)
        self.assertIn("performance_field_values_retained", text)
        self.assertIn("wallet_ranking_performed", text)
        self.assertIn("copyability_analysis_performed", text)
        self.assertIn("pnl_or_alpha_analysis_performed", text)


if __name__ == "__main__":
    unittest.main()
