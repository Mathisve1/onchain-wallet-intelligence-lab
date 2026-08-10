from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r10b_implementation"
CONTRACT = BASE / "R10B_IMPLEMENTATION_CONTRACT.json"
WORKFLOW = BASE / "workflows/hyperliquid-archive-r10b-batch-metadata-lexical-diagnostic.yml"


class R10BWorkflowCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_candidate_is_manual_inert_and_not_a_release(self) -> None:
        candidate = self.contract["workflow_candidate"]
        self.assertFalse(candidate["installed_now"])
        self.assertTrue(candidate["manual_only"])
        self.assertFalse(self.contract["execution_release_present"])
        self.assertFalse(self.contract["canonical_activation_present"])
        self.assertFalse(self.contract["single_workflow_dispatch_authorized"])
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("schedule:", self.text)

    def test_release_and_single_use_gate_precede_oidc(self) -> None:
        self.assertLess(
            self.text.index("Prove exact single-use R10B release before OIDC"),
            self.text.index("Assume existing R10 role with exact one-object session scope"),
        )
        self.assertIn("release['status']=='RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10B_RUN'", self.text)
        self.assertIn("CURRENT_RUN_ATTEMPT", self.text)
        self.assertIn("R10B rerun forbidden", self.text)

    def test_oidc_session_is_exact_one_object_get_only(self) -> None:
        self.assertIn("role-duration-seconds: 900", self.text)
        self.assertIn("retry-max-attempts: 1", self.text)
        self.assertIn('"Action":"s3:GetObject"', self.text)
        self.assertIn("arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/9.lz4", self.text)
        self.assertNotIn('"Action":"s3:ListBucket"', self.text)
        self.assertNotIn("aws s3 ", self.text.lower())
        self.assertNotIn("aws s3api ", self.text.lower())

    def test_actions_are_pinned_and_trust_compatible_name_is_exact(self) -> None:
        self.assertTrue(self.text.startswith("name: Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10\nrun-name: R10B batch metadata lexical diagnostic\n"))
        for pin in (
            "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
            "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
            "aws-actions/configure-aws-credentials@e6de054238d6b7531b4efff3b6587d9aade6a06c",
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
        ):
            self.assertIn(pin, self.text)

    def test_artifact_is_minimized_and_forbidden_processing_is_terminally_false(self) -> None:
        for name in ("r10b-context.json", "r10b-result.json", "r10b.rc", "R10B_FILES.sha256"):
            self.assertIn(name, self.text)
        for flag in (
            "raw_object_retained", "raw_block_event_fill_retained", "individual_metadata_value_retained",
            "event_array_contents_inspected", "wallet_address_retained", "wallet_aggregation_performed",
            "economic_fill_field_processing_performed", "individual_fill_time_processing_performed",
            "timezone_parsing_performed", "timezone_inference_performed", "datetime_conversion_of_metadata_performed",
            "r10_rule_amendment_performed", "r10_rerun_performed", "six_hour_execution_performed",
            "wallet_ranking_performed", "pnl_or_alpha_analysis_performed", "copyability_analysis_performed",
        ):
            self.assertIn(flag, self.text)


if __name__ == "__main__":
    unittest.main()
