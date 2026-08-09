from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R7 = ROOT / "research/archive_inventory/r7"


class ArchiveR7PreregistrationTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_parent_r6a_evidence_and_semantic_contract_are_exact(self) -> None:
        contract = self.load(R7 / "WALLET_INDEX_RECONSTRUCTION_R7_CONTRACT.json")
        self.assertEqual(contract["parent_r6a_evidence_commit"], "6b7dcd85e6d0f82b63ab8c4dd50d56ef8dc72a57")
        self.assertEqual(contract["parent_r6a_run_id"], 31328268134)
        semantic = contract["working_semantic_contract"]
        self.assertEqual(semantic["leading_string_label"], "HYPERLIQUID_USER_ADDRESS")
        self.assertEqual(
            semantic["status"],
            "HIGH_CONFIDENCE_CONVERGENT_STATIC_AND_LEXICAL_EVIDENCE_NOT_DIRECT_SERIALIZER_PROOF",
        )
        self.assertFalse(semantic["direct_unpublished_serializer_proof_claimed"])

    def test_future_network_scope_is_exact_one_object_but_current_authority_is_zero(self) -> None:
        contract = self.load(R7 / "WALLET_INDEX_RECONSTRUCTION_R7_CONTRACT.json")
        target = contract["exact_future_network_target"]
        envelope = contract["proposed_future_request_envelope"]
        self.assertEqual(target["key"], "node_fills/hourly/20250727/8.lz4")
        self.assertEqual(target["expected_nonempty_record_count"], 162815)
        self.assertEqual(target["required_leading_string_pattern"], "^0x[0-9a-f]{40}$")
        self.assertEqual(envelope["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(envelope["maximum_monthly_budget_eur"], 0)
        self.assertEqual(envelope["maximum_get_object_requests"], 1)
        self.assertEqual(envelope["maximum_retries_per_request"], 0)
        self.assertTrue(all(value is False for value in contract["current_runtime_authority"].values()))
        self.assertEqual(contract["network_requests_executed_by_this_preregistration"], 0)

    def test_proposed_retention_is_address_plus_fill_count_only(self) -> None:
        contract = self.load(R7 / "WALLET_INDEX_RECONSTRUCTION_R7_CONTRACT.json")
        retention = contract["proposed_future_retention_boundary"]
        self.assertTrue(retention["wallet_address_retention_authorized"])
        self.assertTrue(retention["leading_string_value_retention_authorized"])
        self.assertTrue(retention["per_wallet_fill_count_retention_authorized"])
        self.assertTrue(retention["unique_wallet_count_retention_authorized"])
        self.assertEqual(retention["retained_wallet_index_fields_only"], ["wallet_address", "fill_count"])
        self.assertFalse(retention["raw_compressed_object_retention_authorized"])
        self.assertFalse(retention["raw_decompressed_payload_retention_authorized"])
        self.assertFalse(retention["record_payload_retention_authorized"])
        self.assertFalse(retention["fill_object_retention_authorized"])
        self.assertFalse(retention["payload_values_in_evidence_authorized"])
        for key in (
            "coin_value_retention_authorized",
            "price_value_retention_authorized",
            "size_value_retention_authorized",
            "side_value_retention_authorized",
            "time_value_retention_authorized",
            "closed_pnl_value_retention_authorized",
            "fee_value_retention_authorized",
            "transaction_hash_retention_authorized",
            "order_id_retention_authorized",
            "trade_id_retention_authorized",
            "client_order_id_retention_authorized",
        ):
            self.assertFalse(retention[key], key)

    def test_deterministic_wallet_index_conservation_rule_is_frozen(self) -> None:
        contract = self.load(R7 / "WALLET_INDEX_RECONSTRUCTION_R7_CONTRACT.json")
        output = contract["deterministic_output_contract"]
        self.assertTrue(output["one_row_per_unique_wallet"])
        self.assertTrue(output["wallet_address_unique"])
        self.assertEqual(output["wallet_address_sort_order"], "LEXICOGRAPHIC_ASCENDING")
        self.assertTrue(output["fill_count_positive_integer"])
        self.assertEqual(output["sum_fill_count_required"], 162815)
        self.assertFalse(output["duplicate_wallet_rows_authorized"])

    def test_downstream_wallet_intelligence_and_trading_stay_closed(self) -> None:
        contract = self.load(R7 / "WALLET_INDEX_RECONSTRUCTION_R7_CONTRACT.json")
        self.assertTrue(all(value is False for value in contract["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in contract["trading_authorizations"].values()))
        claims = " ".join(contract["claims_not_authorized_by_r7_success"])
        self.assertIn("entity clustering", claims)
        self.assertIn("copyability", claims)
        self.assertIn("PnL or alpha", claims)
        self.assertIn("live trading suitability", claims)

    def test_preregistration_is_inert_and_requires_new_human_approval(self) -> None:
        contract = self.load(R7 / "WALLET_INDEX_RECONSTRUCTION_R7_CONTRACT.json")
        self.assertEqual(contract["status"], "PREREGISTERED_NO_EXECUTION")
        self.assertTrue(contract["human_approval_required_before_implementation"])
        self.assertTrue(contract["implementation_required_before_execution_release"])
        self.assertTrue(contract["separate_execution_release_required"])
        self.assertEqual(contract["wallet_addresses_retained_by_this_preregistration"], 0)
        self.assertIsNone(contract["empirical_result"])
        self.assertFalse((R7 / "collector.py").exists())
        self.assertFalse((ROOT / ".github/workflows/hyperliquid-archive-wallet-index-r7.yml").exists())

    def test_dedicated_preregistration_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r7_preregistration.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R7_PREREGISTRATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
