from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ArchiveIAMBoundaryTests(unittest.TestCase):
    def test_policy_binds_exact_prefix_sets_to_exact_buckets(self) -> None:
        policy = json.loads((ROOT / "research/archive_inventory/IAM_POLICY_TEMPLATE.json").read_text(encoding="utf-8"))
        statements = {row["Sid"]: row for row in policy["Statement"]}

        node = statements["AllowNodeDataExactPrefixListing"]
        self.assertEqual(node["Effect"], "Allow")
        self.assertEqual(node["Action"], "s3:ListBucket")
        self.assertEqual(node["Resource"], "arn:aws:s3:::hl-mainnet-node-data")
        self.assertEqual(
            set(node["Condition"]["StringLike"]["s3:prefix"]),
            {
                "node_fills_by_block/*",
                "node_fills/*",
                "node_trades/*",
                "explorer_blocks/*",
                "replica_cmds/*",
            },
        )

        archive = statements["AllowArchiveExactPrefixListing"]
        self.assertEqual(archive["Effect"], "Allow")
        self.assertEqual(archive["Action"], "s3:ListBucket")
        self.assertEqual(archive["Resource"], "arn:aws:s3:::hyperliquid-archive")
        self.assertEqual(
            set(archive["Condition"]["StringLike"]["s3:prefix"]),
            {"market_data/*", "asset_ctxs/*"},
        )

        deny = statements["ExplicitlyDenyObjectBodiesAndMutation"]
        self.assertEqual(deny["Effect"], "Deny")
        denied = set(deny["Action"])
        self.assertIn("s3:GetObject", denied)
        self.assertIn("s3:PutObject", denied)
        self.assertIn("s3:DeleteObject", denied)

    def test_pricing_template_cannot_authorize_spend(self) -> None:
        pricing = json.loads((ROOT / "research/archive_inventory/PRICING_EVIDENCE_TEMPLATE.json").read_text(encoding="utf-8"))
        self.assertEqual(pricing["status"], "PENDING_PRE_EXECUTION_PRICING_REFRESH")
        self.assertIsNone(pricing["maximum_one_time_budget_eur"])
        self.assertFalse(pricing["paid_request_authorized"])


if __name__ == "__main__":
    unittest.main()
