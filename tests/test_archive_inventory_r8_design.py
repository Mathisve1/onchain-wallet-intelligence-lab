from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "research/archive_inventory/r8"


class ArchiveR8DesignTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_r7_parent_is_exact_and_no_wallets_are_ranked(self) -> None:
        design = self.load(R8 / "PERFORMANCE_COPYABILITY_DATA_DESIGN_R8_CONTRACT.json")
        derivation = self.load(R8 / "R7_DERIVATION.json")
        self.assertEqual(design["parent_r7_evidence_commit"], "7802d741f193671e50356c6001dcae149e0fc88a")
        self.assertEqual(design["parent_r7_run_id"], 31330248235)
        self.assertEqual(design["parent_r7_unique_wallet_count"], 4637)
        self.assertEqual(design["parent_r7_sum_fill_count"], 162815)
        self.assertEqual(design["wallets_ranked_by_r8"], 0)
        self.assertFalse(derivation["r8_static_design_uses_concrete_wallet_rows"])
        self.assertFalse(derivation["r8_static_design_ranks_parent_wallets"])
        self.assertFalse(derivation["r8_static_design_queries_parent_wallets"])

    def test_minimum_field_set_keeps_account_return_semantics_conservative(self) -> None:
        design = self.load(R8 / "PERFORMANCE_COPYABILITY_DATA_DESIGN_R8_CONTRACT.json")
        fields = design["minimum_archive_candidate_field_set"]
        flat = {item for items in fields.values() for item in items}
        for required in (
            "wallet_address", "time", "coin", "side", "dir", "px", "sz",
            "closedPnl", "fee", "feeToken", "startPosition", "tid", "crossed", "liquidation_presence",
        ):
            self.assertIn(required, flat)
        semantics = design["semantic_boundaries"]
        self.assertFalse(semantics["closed_pnl_sum_is_exact_account_return"])
        self.assertTrue(semantics["closed_pnl_may_be_used_as_fill_derived_statistic"])
        self.assertTrue(semantics["fee_must_not_be_blindly_subtracted_from_closed_pnl_without_formula_proof"])
        self.assertFalse(semantics["crossed_maker_taker_semantics_proven"])
        self.assertFalse(semantics["one_wallet_address_equals_one_human_or_economic_entity"])
        self.assertFalse(semantics["portfolio_graphs_are_precise_accounting"])

    def test_population_archive_then_shortlist_api_pipeline_is_frozen(self) -> None:
        design = self.load(R8 / "PERFORMANCE_COPYABILITY_DATA_DESIGN_R8_CONTRACT.json")
        self.assertEqual([row["stage"] for row in design["proposed_research_pipeline"]], [
            "A_GLOBAL_ARCHIVE_SCREEN", "B_CANDIDATE_REDUCTION",
            "C_SHORTLIST_PUBLIC_API_ENRICHMENT", "D_COPYABILITY_EXECUTION_RESEARCH",
        ])
        self.assertTrue(design["api_scaling_constraint"]["per_address_user_fills_is_not_primary_population_scan"])
        self.assertTrue(design["api_scaling_constraint"]["shortlist_first_required"])
        self.assertTrue(all(value is False for value in design["current_authority"].values()))
        self.assertTrue(all(value is False for value in design["trading_authorizations"].values()))

    def test_r8a_is_one_exact_modern_object_and_preregistration_authority_zero(self) -> None:
        r8a = self.load(R8 / "MODERN_WALLET_INDEX_BRIDGE_R8A_CONTRACT.json")
        target = r8a["exact_future_network_target"]
        envelope = r8a["proposed_future_request_envelope"]
        self.assertEqual(target["key"], "node_fills_by_block/hourly/20250727/8.lz4")
        self.assertEqual(target["expected_size_bytes"], 1517603)
        self.assertEqual(target["expected_etag"], '"60d4c1277f76651b5f04666bbe8d7594"')
        self.assertEqual(target["expected_compressed_sha256"], "928e1cd6bd7d69ad7243c263bacee48e53e4762ae9e99ef75f45007f6c0e6105")
        self.assertEqual(target["expected_decompressed_byte_count"], 7380378)
        self.assertEqual(target["expected_top_level_block_record_count"], 4345)
        self.assertEqual(envelope["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(envelope["maximum_monthly_budget_eur"], 0)
        self.assertEqual(envelope["maximum_get_object_requests"], 1)
        self.assertEqual(envelope["maximum_retries_per_request"], 0)
        self.assertTrue(all(value is False for value in r8a["current_runtime_authority"].values()))
        self.assertEqual(r8a["network_requests_executed_by_this_preregistration"], 0)

    def test_r8a_retains_only_address_and_fill_count(self) -> None:
        r8a = self.load(R8 / "MODERN_WALLET_INDEX_BRIDGE_R8A_CONTRACT.json")
        retention = r8a["proposed_future_retention_boundary"]
        self.assertTrue(retention["wallet_address_retention_authorized"])
        self.assertTrue(retention["leading_string_value_retention_authorized"])
        self.assertTrue(retention["per_wallet_fill_count_retention_authorized"])
        self.assertTrue(retention["unique_wallet_count_retention_authorized"])
        self.assertTrue(retention["valid_event_pair_count_retention_authorized"])
        self.assertEqual(retention["retained_wallet_index_fields_only"], ["wallet_address", "fill_count"])
        self.assertFalse(retention["performance_field_values_retention_authorized"])
        self.assertFalse(retention["fill_object_retention_authorized"])
        self.assertFalse(retention["payload_values_in_evidence_authorized"])
        self.assertFalse(r8a["downstream_authorizations"]["historical_multi_hour_ingestion"])
        self.assertFalse(r8a["downstream_authorizations"]["wallet_ranking"])
        self.assertFalse(r8a["downstream_authorizations"]["pnl_or_alpha_analysis"])
        self.assertFalse(r8a["downstream_authorizations"]["copyability_analysis"])
        self.assertTrue(all(value is False for value in r8a["trading_authorizations"].values()))

    def test_preregistration_snapshot_stays_inert_after_separate_approval_and_implementation(self) -> None:
        r8a = self.load(R8 / "MODERN_WALLET_INDEX_BRIDGE_R8A_CONTRACT.json")
        approval = self.load(R8 / "approvals/APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001.json")
        impl = self.load(R8 / "R8A_IMPLEMENTATION_CONTRACT.json")
        self.assertEqual(r8a["status"], "PREREGISTERED_NO_EXECUTION")
        self.assertTrue(r8a["human_approval_required_before_implementation"])
        self.assertTrue(r8a["implementation_required_before_execution_release"])
        self.assertTrue(r8a["separate_execution_release_required"])
        self.assertTrue(all(value is False for value in r8a["current_runtime_authority"].values()))
        self.assertTrue(all(value is False for value in approval["current_runtime_authority"].values()))
        self.assertTrue(all(value is False for value in impl["current_runtime_authority"].values()))
        self.assertTrue((R8 / "collector.py").is_file())
        self.assertTrue((ROOT / ".github/workflows/hyperliquid-archive-modern-wallet-index-r8a.yml").is_file())
        self.assertFalse((R8 / "R8A_EXECUTION_RELEASE.json").exists())
        self.assertFalse((R8 / "R8A_EXECUTION_RELEASE_CANONICALIZATION.json").exists())

    def test_dedicated_r8_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r8_design.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R8_STATIC_DESIGN_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
