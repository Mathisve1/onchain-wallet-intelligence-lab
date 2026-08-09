from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-legacy-user-key-lexical-r6a.yml"
OBJECT_ARN = "arn:aws:s3:::hl-mainnet-node-data/node_fills/hourly/20250727/8.lz4"


class ArchiveR6AWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_manual_only_trust_compatible_name_and_distinct_run_name(self) -> None:
        self.assertTrue(
            self.text.startswith(
                "name: Hyperliquid Archive Hourly Body Schema Pilot R4\n"
                "run-name: R6A legacy user-key lexical confirmation\n"
            )
        )
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("pull_request:", self.text)
        self.assertNotIn("push:", self.text)
        self.assertIn("refs/heads/main", self.text)

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
        configure = self.text.index("Assume unchanged dedicated AWS role with exact-one-object R6A session permissions")
        self.assertLess(self.text.index("Prove canonical R6A implementation and release before AWS OIDC"), configure)
        self.assertLess(self.text.index("Enforce R6A single-use release before AWS OIDC"), configure)
        self.assertIn("EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE", self.text)
        self.assertIn("R6A_EXECUTION_RELEASE_CANONICALIZATION.json", self.text)
        self.assertIn("CURRENT_RUN_ATTEMPT", self.text)
        self.assertIn("re-runs are forbidden", self.text)
        self.assertIn("hyperliquid-archive-legacy-user-key-lexical-r6a.yml/runs", self.text)

    def test_oidc_session_is_exact_one_object_get_only(self) -> None:
        self.assertIn(OBJECT_ARN, self.text)
        self.assertIn('"Action":"s3:GetObject"', self.text)
        self.assertNotIn("node_fills_by_block/hourly/20250727/8.lz4", self.text)
        for forbidden in ("s3:ListBucket", "s3:GetObjectVersion", "s3:GetObjectAttributes", "s3:ListAllMyBuckets"):
            self.assertNotIn(forbidden, self.text)
        self.assertIn("retry-max-attempts: 1", self.text)
        self.assertIn("role-duration-seconds: 900", self.text)

    def test_artifact_is_minimized_to_context_result_rc_and_hash_ledger(self) -> None:
        for filename in (
            "r6a-lexical-context.json",
            "r6a-lexical-result.json",
            "r6a-lexical.rc",
            "R6A_LEXICAL_FILES.sha256",
        ):
            self.assertIn(filename, self.text)
        self.assertIn("leading_string_values_retained", self.text)
        self.assertIn("wallet_addresses_retained", self.text)
        self.assertIn("leading_string_hashes_retained", self.text)
        self.assertIn("distinct_address_set_retained", self.text)
        self.assertNotIn("raw-object", self.text)
        self.assertNotIn("decompressed-payload", self.text)

    def test_final_gate_accepts_declared_research_results_but_rejects_transport_failure(self) -> None:
        self.assertIn("ALL_LEADING_STRINGS_MATCH_HYPERLIQUID_ADDRESS_SHAPE", self.text)
        self.assertIn("SOME_LEADING_STRINGS_DO_NOT_MATCH_HYPERLIQUID_ADDRESS_SHAPE", self.text)
        self.assertIn("R6A_LEXICAL_SHAPE_UNRESOLVED", self.text)
        self.assertIn("R6A_TRANSPORT_OR_INTEGRITY_FAIL", self.text)
        self.assertIn("raise SystemExit(1)", self.text)
        self.assertIn("evidence['nonempty_record_count'] == 162815", self.text)
        self.assertIn("evidence['pair_string_object_record_count'] == 162815", self.text)
        self.assertIn("evidence['leading_string_count'] == 162815", self.text)


if __name__ == "__main__":
    unittest.main()
