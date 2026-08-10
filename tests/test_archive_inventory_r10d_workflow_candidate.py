from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "research/archive_inventory/r10d_implementation/workflows/hyperliquid-archive-r10d-record-anchored-multihour-feature.yml"
INSTALLED = ROOT / ".github/workflows/hyperliquid-archive-r10d-record-anchored-multihour-feature.yml"


class R10DWorkflowCandidateTests(unittest.TestCase):
    @classmethod
    def text(cls) -> str:
        return CANDIDATE.read_text(encoding="utf-8")

    def test_candidate_is_manual_and_lifecycle_safe(self) -> None:
        text = self.text()
        self.assertIn("on:\n  workflow_dispatch:\n", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("push:", text)
        if INSTALLED.exists():
            self.assertEqual(INSTALLED.read_bytes(), CANDIDATE.read_bytes())

    def test_trust_compatible_name_and_distinct_run_name(self) -> None:
        text = self.text()
        self.assertIn("name: Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10", text)
        self.assertIn("run-name: R10D record-anchored multi-hour feature repair", text)
        self.assertIn("HLArchiveR10DRecordAnchored", text)

    def test_actions_are_pinned_and_checkout_drops_credentials(self) -> None:
        text = self.text()
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", text)
        self.assertIn("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065", text)
        self.assertIn("aws-actions/configure-aws-credentials@e6de054238d6b7531b4efff3b6587d9aade6a06c", text)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", text)
        self.assertIn("persist-credentials: false", text)

    def test_release_gate_precedes_oidc_and_is_single_use(self) -> None:
        text = self.text()
        release = text.index("Prove exact single-use R10D release before OIDC")
        oidc = text.index("Assume exact existing R10 role with exact-six session scope")
        execute = text.index("Execute bounded R10D collector once")
        self.assertLess(release, oidc)
        self.assertLess(oidc, execute)
        self.assertIn("R10D_EXECUTION_RELEASE.json", text)
        self.assertIn("CURRENT_RUN_ATTEMPT", text)
        self.assertIn("R10D rerun forbidden", text)
        self.assertIn("len(eligible)==1", text)

    def test_oidc_scope_is_six_exact_getobjects_only(self) -> None:
        text = self.text()
        self.assertIn('"Action":"s3:GetObject"', text)
        self.assertEqual(text.count("arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/"), 6)
        self.assertNotIn('"Action":"s3:ListBucket"', text)
        self.assertIn("retry-max-attempts: 1", text)
        self.assertIn("role-duration-seconds: 900", text)

    def test_record_anchored_boundary_is_explicit_and_no_tolerance(self) -> None:
        text = self.text()
        self.assertIn("RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1", text)
        self.assertIn("numeric_tolerance_authorized", text)
        self.assertIn("metadata_timezone_parsing_authorized", text)
        self.assertIn("record_anchored_alignment_violation_count", text)

    def test_artifact_and_terminal_gate_are_bounded(self) -> None:
        text = self.text()
        self.assertIn("r10d-context.json", text)
        self.assertIn("r10d-result.json", text)
        self.assertIn("r10d-wallet-features.ndjson", text)
        self.assertIn("R10D_FILES.sha256", text)
        self.assertIn("R10D_MULTI_HOUR_FEATURE_PIPELINE_COMPLETE", text)
        self.assertIn("R10D_MULTI_HOUR_FEATURE_PIPELINE_UNRESOLVED", text)
        self.assertIn("R10D_TRANSPORT_OR_INTEGRITY_FAIL", text)
        self.assertIn("wallet_ranking_performed", text)
        self.assertIn("pnl_or_alpha_analysis_performed", text)
        self.assertIn("copyability_analysis_performed", text)


if __name__ == "__main__":
    unittest.main()
