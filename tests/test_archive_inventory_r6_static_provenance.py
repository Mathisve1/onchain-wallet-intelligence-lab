from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/archive_inventory/r6/STATIC_PROVENANCE_REPORT.json"


class ArchiveR6StaticProvenanceTests(unittest.TestCase):
    def load(self) -> dict:
        return json.loads(REPORT.read_text(encoding="utf-8"))

    def test_result_is_high_confidence_static_inference_not_direct_proof(self) -> None:
        report = self.load()
        self.assertEqual(
            report["terminal_result"],
            "LEADING_STRING_USER_ADDRESS_SEMANTICS_HIGH_CONFIDENCE_STATIC_INFERENCE",
        )
        self.assertEqual(report["semantic_label"], "HYPERLIQUID_USER_ADDRESS")
        self.assertEqual(
            report["semantic_label_status"],
            "SUPPORTED_INFERENCE_NOT_DIRECT_SERIALIZER_PROOF",
        )
        self.assertEqual(report["confidence_class"], "HIGH")

    def test_historical_primary_sources_predate_target_object(self) -> None:
        report = self.load()
        sources = {
            item["source_id"]: item
            for item in report["primary_source_evidence"]
        }
        for source_id in (
            "HL-NODE-WRITE-FILLS-COMMIT-20250527",
            "HL-NODE-BATCH-BY-BLOCK-COMMIT-20250627",
            "HL-PYSDK-0160-TYPES",
            "HL-PYSDK-0160-INFO-USER-FILLS",
            "HL-PYSDK-0160-WS-USER-FILLS",
        ):
            self.assertTrue(sources[source_id]["predates_target_object"], source_id)
            self.assertTrue(sources[source_id]["immutable"], source_id)

    def test_r5_shape_is_bound_without_reinterpreting_r5(self) -> None:
        report = self.load()
        parent = report["parent_r5"]
        self.assertEqual(parent["canonical_evidence_merge_commit"], "4400963aa972ed878650116202cc72880e667849")
        self.assertEqual(parent["nonempty_record_count"], 162815)
        self.assertEqual(parent["array_element_type_signature"], "string,object")
        self.assertFalse(parent["semantic_wallet_or_user_label_inferred_by_r5"])
        self.assertFalse(
            report["r5_structural_correspondence"][
                "archive_string_value_or_lexical_shape_observed_by_r6"
            ]
        )

    def test_static_study_opens_no_network_wallet_or_trading_authority(self) -> None:
        report = self.load()
        self.assertTrue(all(value is False for value in report["method_boundary"].values() if isinstance(value, bool) and value is not report["method_boundary"]["public_primary_sources_only"]))
        self.assertTrue(report["method_boundary"]["public_primary_sources_only"])
        self.assertTrue(all(value is False for value in report["current_authorizations"].values()))

    def test_r6a_remains_proposed_and_requires_new_human_approval(self) -> None:
        gate = self.load()["next_minimum_empirical_gate_if_required"]
        self.assertEqual(gate["status"], "PROPOSED_NOT_AUTHORIZED")
        self.assertTrue(gate["new_paid_request_required"])
        self.assertTrue(gate["separate_human_scope_and_budget_approval_required"])
        self.assertTrue(gate["execution_release_required"])
        self.assertFalse(gate["proposed_value_retention"])
        self.assertFalse(gate["proposed_wallet_address_retention"])
        self.assertFalse(gate["proposed_payload_retention"])

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r6_static_provenance.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R6_STATIC_PROVENANCE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
