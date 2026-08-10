from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "research/archive_inventory/r10c_implementation/workflows/hyperliquid-archive-r10c-boundary-record-correlation.yml"
INSTALLED = ROOT / ".github/workflows/hyperliquid-archive-r10c-boundary-record-correlation.yml"


class R10CWorkflowCandidateTests(unittest.TestCase):
    @classmethod
    def text(cls) -> str:
        return CANDIDATE.read_text(encoding="utf-8")

    def test_candidate_is_manual_and_installed_only_byte_exact_if_present(self) -> None:
        text = self.text()
        self.assertIn("on:\n  workflow_dispatch:\n", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("push:", text)
        if INSTALLED.exists():
            self.assertEqual(INSTALLED.read_bytes(), CANDIDATE.read_bytes())

    def test_trust_compatible_name_and_distinct_run_name(self) -> None:
        text = self.text()
        self.assertIn("name: Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10", text)
        self.assertIn("run-name: R10C boundary record correlation", text)
        self.assertIn("HLArchiveR10CBoundaryCorrelation", text)

    def test_actions_are_pinned_and_checkout_drops_credentials(self) -> None:
        text = self.text()
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", text)
        self.assertIn("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065", text)
        self.assertIn("aws-actions/configure-aws-credentials@e6de054238d6b7531b4efff3b6587d9aade6a06c", text)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", text)
        self.assertIn("persist-credentials: false", text)

    def test_release_gate_precedes_oidc_and_is_single_use(self) -> None:
        text = self.text()
        release = text.index("Prove exact single-use R10C release before OIDC")
        oidc = text.index("Assume existing R10 role with exact one-object session scope")
        execute = text.index("Execute bounded R10C diagnostic once")
        self.assertLess(release, oidc)
        self.assertLess(oidc, execute)
        self.assertIn("R10C_EXECUTION_RELEASE.json", text)
        self.assertIn("CURRENT_RUN_ATTEMPT", text)
        self.assertIn("R10C rerun forbidden", text)
        self.assertIn("len(eligible)==1", text)

    def test_oidc_scope_is_one_exact_getobject(self) -> None:
        text = self.text()
        self.assertIn('"Action":"s3:GetObject"', text)
        self.assertIn('arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/9.lz4', text)
        self.assertNotIn('"Action":"s3:ListBucket"', text)
        self.assertIn("retry-max-attempts: 1", text)
        self.assertIn("role-duration-seconds: 900", text)

    def test_artifact_is_minimized_and_terminal_gate_is_fail_closed(self) -> None:
        text = self.text()
        self.assertIn("r10c-context.json", text)
        self.assertIn("r10c-result.json", text)
        self.assertIn("r10c.rc", text)
        self.assertIn("R10C_FILES.sha256", text)
        self.assertNotIn("raw-object", text)
        self.assertIn("EXACT_TWO_PRE_HOUR_FILLS_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD", text)
        self.assertIn("PRE_HOUR_FILLS_DO_NOT_EXACTLY_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD", text)
        self.assertIn("BOUNDARY_RECORD_CORRELATION_UNRESOLVED", text)
        self.assertIn("R10C_TRANSPORT_OR_INTEGRITY_FAIL", text)

    def test_processing_boundary_is_explicit(self) -> None:
        text = self.text()
        self.assertIn("PAIR_SHAPE_AND_FILL_TIME_ONLY", text)
        self.assertIn("fill_object_field_allowlist", text)
        self.assertIn("wallet_address_retention_authorized", text)
        self.assertIn("economic_fill_field_processing_authorized", text)


if __name__ == "__main__":
    unittest.main()
