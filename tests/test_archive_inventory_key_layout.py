from __future__ import annotations

import unittest

from src.archive_inventory.key_layout import classify_documented_key


class ArchiveKeyLayoutTests(unittest.TestCase):
    def test_market_data_documented_layout(self) -> None:
        row = classify_documented_key("market_data", "market_data/20230916/9/l2Book/SOL.lz4")
        self.assertTrue(row.matched_documented_layout)
        self.assertEqual(row.date, "20230916")
        self.assertEqual(row.hour, 9)
        self.assertEqual(row.datatype, "l2Book")
        self.assertEqual(row.asset, "SOL")

    def test_asset_ctx_layout(self) -> None:
        row = classify_documented_key("asset_ctxs", "asset_ctxs/20230916.csv.lz4")
        self.assertTrue(row.matched_documented_layout)
        self.assertEqual(row.date, "20230916")

    def test_invalid_hour_and_unknown_node_layout_are_not_inferred(self) -> None:
        self.assertFalse(classify_documented_key("market_data", "market_data/20230916/99/l2Book/SOL.lz4").matched_documented_layout)
        self.assertFalse(classify_documented_key("node_fills_by_block", "node_fills_by_block/anything").matched_documented_layout)


if __name__ == "__main__":
    unittest.main()
