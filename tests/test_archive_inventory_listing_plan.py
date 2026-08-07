from __future__ import annotations

import unittest

from src.archive_inventory.listing_plan import ListingPlanError, ListRequestSpec, build_discovery_request, build_page_request, validate_request_spec


class ArchiveListingPlanTests(unittest.TestCase):
    def test_all_registered_families_build_list_only_requests(self) -> None:
        for family in ("node_fills_by_block", "node_fills_legacy", "node_trades_legacy", "explorer_blocks", "replica_cmds", "market_data", "asset_ctxs"):
            spec = build_discovery_request(family)
            self.assertEqual(spec.operation, "ListObjectsV2")
            self.assertEqual(spec.request_payer, "requester")
            self.assertFalse(spec.fetch_owner)
            self.assertEqual(spec.max_keys, 1000)
            self.assertEqual(spec.delimiter, "/")
            kwargs = spec.as_sdk_kwargs()
            self.assertEqual(kwargs["RequestPayer"], "requester")
            self.assertFalse(kwargs["FetchOwner"])
            self.assertNotIn("Key", kwargs)
            self.assertNotIn("Range", kwargs)

    def test_unknown_family_and_prefix_escape_fail(self) -> None:
        with self.assertRaises(ListingPlanError):
            build_discovery_request("wallet_winners")
        base = build_discovery_request("market_data")
        bad = ListRequestSpec(operation=base.operation, dataset_family=base.dataset_family, bucket=base.bucket, prefix="", delimiter="/", max_keys=1000, request_payer="requester", fetch_owner=False)
        with self.assertRaises(ListingPlanError):
            validate_request_spec(bad)

    def test_continuation_token_is_opaque(self) -> None:
        spec, token = build_page_request("asset_ctxs", "opaque+/=token")
        self.assertEqual(token, "opaque+/=token")
        self.assertEqual(spec.operation, "ListObjectsV2")
        with self.assertRaises(ListingPlanError):
            build_page_request("asset_ctxs", "")


if __name__ == "__main__":
    unittest.main()
