from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-wallet-index-r7.yml"


class ArchiveR7WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_manual_only_trust_compatible_identity(self) -> None:
        self.assertTrue(self.text.startswith(
            "name: Hyperliquid Archive Hourly Body Schema Pilot R4\n"
            "run-name: R7 bounded wallet-index reconstruction\n"
        ))
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("pull_request:", self.text)
        self.assertNotIn("\n  push:", self.text)
        self.assertIn("DISPATCH_REF: ${{ github.ref }}", self.text)
        self.assertIn("DISPATCH_SHA: ${{ github.sha }}", self.text)
        self.assertIn('test "${DISPATCH_REF}" = "refs/heads/main"', self.text)

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
        release = self.text.index("Prove canonical R7 implementation and active release before AWS OIDC")
        single = self.text.index("Enforce R7 single-use release before AWS OIDC")
        oidc = self.text.index("Assume unchanged dedicated AWS role with exact-one-object R7 session")
        self.assertLess(release, oidc)
        self.assertLess(single, oidc)
        self.assertIn("R7_EXECUTION_RELEASE.json", self.text)
        self.assertIn("R7_EXECUTION_RELEASE_CANONICALIZATION.json", self.text)
        self.assertIn("CURRENT_RUN_ATTEMPT", self.text)
        self.assertIn("len(eligible) == 1", self.text)

    def test_oidc_session_is_exact_one_object_get_only(self) -> None:
        self.assertIn('"Action":"s3:GetObject"', self.text)
        self.assertIn(
            '"Resource":"arn:aws:s3:::hl-mainnet-node-data/node_fills/hourly/20250727/8.lz4"',
            self.text,
        )
        for forbidden in ("s3:ListBucket", "s3:GetObjectVersion", "s3:GetObjectAttributes", "s3:ListAllMyBuckets"):
            self.assertNotIn(forbidden, self.text)

    def test_artifact_contains_wallet_index_but_no_raw_object(self) -> None:
        for filename in ("r7-context.json", "r7-result.json", "r7-wallet-index.ndjson", "r7.rc", "R7_FILES.sha256"):
            self.assertIn(filename, self.text)
        self.assertNotIn("raw-object.lz4", self.text)
        self.assertNotIn("decompressed-payload", self.text)
        self.assertIn("wallet_index_output_byte_cap", self.text)
        self.assertIn("retained_wallet_index_fields_only", self.text)

    def test_terminal_gate_validates_addresses_counts_sort_and_conservation(self) -> None:
        self.assertIn("re.fullmatch(r'^0x[0-9a-f]{40}$'", self.text)
        self.assertIn("addresses == sorted(addresses)", self.text)
        self.assertIn("len(addresses) == len(set(addresses))", self.text)
        self.assertIn("sum(row['fill_count'] for row in rows) == 162815", self.text)
        self.assertIn("summary['wallet_index_sha256']", self.text)
        self.assertIn("WALLET_INDEX_RECONSTRUCTION_COMPLETE", self.text)
        self.assertIn("WALLET_INDEX_RECONSTRUCTION_UNRESOLVED", self.text)


if __name__ == "__main__":
    unittest.main()
