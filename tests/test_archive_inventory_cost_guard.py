from __future__ import annotations

import unittest

from src.archive_inventory.cost_guard import GuardViolation, InventoryGuard, estimate_request_cost_usd, estimate_transfer_cost_usd


class ArchiveCostGuardTests(unittest.TestCase):
    def test_cost_math_is_linear_and_nonnegative(self) -> None:
        self.assertAlmostEqual(estimate_request_cost_usd(300, 0.005), 0.0015)
        self.assertAlmostEqual(estimate_transfer_cost_usd(250_000_000, 0.09), 0.0225)
        with self.assertRaises(ValueError):
            estimate_request_cost_usd(-1, 0.005)

    def test_failed_attempts_count_before_network_response(self) -> None:
        guard = InventoryGuard(started_monotonic=0.0)
        guard.before_request("market_data", now_monotonic=1.0, retry_index=0)
        self.assertEqual(guard.total_requests, 1)
        guard.before_request("market_data", now_monotonic=2.0, retry_index=1)
        self.assertEqual(guard.total_requests, 2)

    def test_repeated_token_and_caps_fail_closed(self) -> None:
        guard = InventoryGuard(started_monotonic=0.0)
        guard.before_request("market_data", now_monotonic=1.0, retry_index=0)
        guard.record_response("market_data", response_bytes=100, entry_count=10, next_continuation_token="same")
        guard.before_request("market_data", now_monotonic=2.0, retry_index=0)
        with self.assertRaises(GuardViolation):
            guard.record_response("market_data", response_bytes=100, entry_count=10, next_continuation_token="same")

    def test_runtime_retry_family_byte_and_per_response_entry_limits(self) -> None:
        guard = InventoryGuard(started_monotonic=0.0)
        with self.assertRaises(GuardViolation):
            guard.before_request("market_data", now_monotonic=901.0, retry_index=0)
        with self.assertRaises(GuardViolation):
            guard.before_request("market_data", now_monotonic=1.0, retry_index=2)
        with self.assertRaises(GuardViolation):
            guard.before_request("unknown", now_monotonic=1.0, retry_index=0)

        guard = InventoryGuard(started_monotonic=0.0)
        guard.before_request("asset_ctxs", now_monotonic=1.0, retry_index=0)
        with self.assertRaises(GuardViolation):
            guard.record_response("asset_ctxs", response_bytes=268435457, entry_count=1, next_continuation_token=None)

        guard = InventoryGuard(started_monotonic=0.0)
        guard.before_request("node_fills_by_block", now_monotonic=1.0, retry_index=0)
        with self.assertRaises(GuardViolation):
            guard.record_response("node_fills_by_block", response_bytes=1000, entry_count=1001, next_continuation_token=None)


if __name__ == "__main__":
    unittest.main()
