from __future__ import annotations

import unittest

from src.archive_inventory.contract import load_contract, load_dataset_register


class ArchiveInventoryContractTests(unittest.TestCase):
    def test_contract_is_preregistered_and_nonexecuting(self) -> None:
        contract = load_contract()
        self.assertEqual(contract["status"], "PREREGISTERED_METADATA_ONLY_NO_EXECUTION")
        self.assertFalse(any(contract["execution"].values()))
        self.assertFalse(contract["proposed_canary"]["authorized"])
        self.assertFalse(contract["cost_gate"]["paid_request_authorized"])
        self.assertIsNone(contract["cost_gate"]["maximum_one_time_budget_eur"])
        self.assertEqual(contract["cost_gate"]["maximum_monthly_budget_eur"], 0)
        self.assertFalse(contract["market_data_ingested"])
        self.assertIsNone(contract["empirical_result"])
        self.assertTrue(all(v is False for v in contract["authorizations"].values()))

    def test_exact_seven_dataset_families(self) -> None:
        register = load_dataset_register()
        self.assertEqual({r["family"] for r in register["datasets"]}, {"node_fills_by_block", "node_fills_legacy", "node_trades_legacy", "explorer_blocks", "replica_cmds", "market_data", "asset_ctxs"})
        self.assertEqual({r["bucket"] for r in register["datasets"]}, {"hl-mainnet-node-data", "hyperliquid-archive"})


if __name__ == "__main__":
    unittest.main()
