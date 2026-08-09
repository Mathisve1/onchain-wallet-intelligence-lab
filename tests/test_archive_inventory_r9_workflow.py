from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-modern-wallet-feature-r9.yml"


class ArchiveR9WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_manual_only_trust_compatible_identity(self) -> None:
        self.assertIn("name: Hyperliquid Archive Hourly Body Schema Pilot R4", self.text)
        self.assertIn("run-name: R9 bounded modern wallet feature pilot", self.text)
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("schedule:", self.text)
        self.assertNotIn("push:\n", self.text)
        self.assertNotIn("pull_request:\n", self.text)
        self.assertIn("DISPATCH_REF: ${{ github.ref }}", self.text)
        self.assertIn("DISPATCH_SHA: ${{ github.sha }}", self.text)
        self.assertIn("test \"${DISPATCH_REF}\" = 'refs/heads/main'", self.text)

    def test_permissions_actions_and_checkout_are_pinned(self) -> None:
        self.assertIn("actions: read", self.text)
        self.assertIn("contents: read", self.text)
        self.assertIn("id-token: write", self.text)
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", self.text)
        self.assertIn("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065", self.text)
        self.assertIn("aws-actions/configure-aws-credentials@e6de054238d6b7531b4efff3b6587d9aade6a06c", self.text)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", self.text)
        self.assertIn("persist-credentials: false", self.text)

    def test_release_and_single_use_gates_precede_oidc(self) -> None:
        proof = self.text.index("Prove canonical R9 implementation and active release before AWS OIDC")
        single = self.text.index("Enforce R9 single-use release before AWS OIDC")
        oidc = self.text.index("Assume unchanged dedicated AWS role with exact-one-object R9 session")
        self.assertLess(proof, oidc)
        self.assertLess(single, oidc)
        self.assertIn("R9_EXECUTION_RELEASE.json", self.text)
        self.assertIn("R9_EXECUTION_RELEASE_CANONICALIZATION.json", self.text)
        self.assertIn("test \"${CURRENT_RUN_ATTEMPT}\" = '1'", self.text)

    def test_oidc_session_is_exact_one_object_get_only(self) -> None:
        self.assertIn('"Action":"s3:GetObject"', self.text)
        self.assertIn("arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/8.lz4", self.text)
        self.assertNotIn("s3:ListBucket", self.text)
        self.assertNotIn("s3:GetObjectVersion", self.text)
        self.assertNotIn("s3:GetObjectAttributes", self.text)
        self.assertNotIn("s3:ListAllMyBuckets", self.text)
        self.assertIn("retry-max-attempts: 1", self.text)

    def test_artifact_is_aggregate_feature_only_and_bounded(self) -> None:
        for filename in ("r9-context.json", "r9-result.json", "r9-wallet-features.ndjson", "r9.rc", "R9_FILES.sha256"):
            self.assertIn(filename, self.text)
        self.assertIn("retention-days: 30", self.text)
        self.assertNotIn("raw-object", self.text)
        self.assertNotIn("decompressed-payload", self.text)

    def test_terminal_gate_locks_conservation_and_semantic_boundaries(self) -> None:
        self.assertIn("summary['top_level_block_record_count'] == 4345", self.text)
        self.assertIn("summary['valid_event_pair_count'] == 17516", self.text)
        self.assertIn("summary['sum_fill_count'] == 17516", self.text)
        self.assertIn("summary['sum_side_count'] == 17516", self.text)
        self.assertIn("row['side_a_count'] + row['side_b_count'] == row['fill_count']", self.text)
        self.assertIn("sum_closed_pnl_interpreted_as_exact_account_return", self.text)
        self.assertIn("sum_closed_pnl_used_as_wallet_ranking_score", self.text)
        self.assertIn("notional_proxy_interpreted_as_copyable_notional", self.text)
        self.assertIn("candidate_shortlisting_performed", self.text)
        self.assertIn("historical_multi_hour_ingestion_performed", self.text)


if __name__ == "__main__":
    unittest.main()
