from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-legacy-format-fingerprint-r5.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")


class ArchiveLegacyFormatFingerprintR5WorkflowTests(unittest.TestCase):
    def test_workflow_reuses_exact_oidc_name_but_has_distinct_file_and_run_name(self) -> None:
        self.assertTrue(TEXT.startswith("name: Hyperliquid Archive Hourly Body Schema Pilot R4\nrun-name: R5 legacy format fingerprint\n"))
        self.assertEqual(WORKFLOW.name, "hyperliquid-archive-legacy-format-fingerprint-r5.yml")
        self.assertNotEqual(WORKFLOW.name, "hyperliquid-archive-hourly-body-schema-pilot-r4.yml")

    def test_manual_only_exact_main_identity_and_pinned_actions(self) -> None:
        self.assertIn("workflow_dispatch:", TEXT)
        self.assertNotIn("pull_request:", TEXT)
        self.assertNotIn("push:", TEXT)
        self.assertIn("refs/heads/main", TEXT)
        self.assertIn("persist-credentials: false", TEXT)
        for pin in (
            "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
            "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
            "aws-actions/configure-aws-credentials@e6de054238d6b7531b4efff3b6587d9aade6a06c",
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
        ):
            self.assertIn(pin, TEXT)

    def test_implementation_and_single_use_release_gates_precede_oidc(self) -> None:
        oidc = TEXT.index("Assume unchanged dedicated AWS role with exact-one-object R5 session permissions")
        self.assertLess(TEXT.index("Prove canonical R5 implementation and release before AWS OIDC"), oidc)
        self.assertLess(TEXT.index("Enforce R5 single-use release before AWS OIDC"), oidc)
        self.assertIn("EXPECTED_IMPLEMENTATION_COMMIT: 40bc4d138c71a4367c9415982f58bcd24c5a57eb", TEXT)
        self.assertNotIn("EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE", TEXT)
        self.assertIn("R5_EXECUTION_RELEASE_CANONICALIZATION.json", TEXT)
        self.assertIn("hyperliquid-archive-legacy-format-fingerprint-r5.yml/runs", TEXT)
        self.assertIn("Run attempt must be 1; re-runs are forbidden", TEXT)

    def test_oidc_session_scope_is_exact_one_legacy_object(self) -> None:
        legacy = "arn:aws:s3:::hl-mainnet-node-data/node_fills/hourly/20250727/8.lz4"
        self.assertIn('"Action":"s3:GetObject"', TEXT)
        self.assertIn(legacy, TEXT)
        self.assertNotIn("arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/8.lz4", TEXT)
        self.assertIn("role-to-assume: arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4", TEXT)
        self.assertIn("role-session-name: HLArchiveLegacyFormatR5", TEXT)
        self.assertIn("retry-max-attempts: 1", TEXT)
        for forbidden in ("s3:ListBucket", "s3:GetObjectVersion", "s3:GetObjectAttributes", "s3:ListAllMyBuckets"):
            self.assertNotIn(forbidden, TEXT)

    def test_artifact_is_minimized_and_contains_no_object_payload(self) -> None:
        for name in (
            "r5-format-context.json", "r5-format-result.json", "r5-format.rc", "R5_FORMAT_FILES.sha256",
        ):
            self.assertIn(name, TEXT)
        self.assertNotIn("8.lz4\n", TEXT.split("path: |", 1)[-1])
        self.assertNotIn("raw-decompressed", TEXT)
        self.assertNotIn("payload.bin", TEXT)

    def test_final_gate_accepts_only_declared_research_results_and_rejects_transport_fail(self) -> None:
        for result in (
            "LEGACY_FORMAT_RESOLVED_AS_NDJSON_PAIR_STRING_OBJECT",
            "LEGACY_FORMAT_RESOLVED_AS_NDJSON_PAIR_OBJECT_STRING",
            "LEGACY_FORMAT_RESOLVED_AS_OTHER_DECLARED_JSON_CLASS",
            "LEGACY_FORMAT_UNRESOLVED",
            "R5_TRANSPORT_OR_INTEGRITY_FAIL",
        ):
            self.assertIn(result, TEXT)
        self.assertIn("terminal_status') == 'R5_LEGACY_FORMAT_FINGERPRINT_COMPLETE'", TEXT)
        self.assertIn("assert rc != 0", TEXT)


if __name__ == "__main__":
    unittest.main()
