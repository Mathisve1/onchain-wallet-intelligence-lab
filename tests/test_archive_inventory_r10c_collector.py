from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from research.archive_inventory.r10c_implementation import collector as c


class R10CCollectorTests(unittest.TestCase):
    @staticmethod
    def small_expected() -> dict[str, int]:
        return {
            "block_record_count": 2,
            "fill_time_count": 3,
            "fill_time_before_path_hour_count": 2,
            "fill_time_inside_path_hour_count": 1,
            "fill_time_after_path_hour_count": 0,
            "local_time_path_prefix_count": 2,
            "block_time_path_prefix_count": 1,
            "block_time_previous_prefix_count": 1,
        }

    @staticmethod
    def small_summary() -> dict:
        return c.new_summary(c.TARGET["etag"], b"synthetic")

    def test_exact_positive_colocation_classification(self) -> None:
        s = self.small_summary()
        path = "MATCHES_PATH_DATE_HOUR_PREFIX"
        prev = "MATCHES_PREVIOUS_DATE_HOUR_PREFIX"
        s["block_record_count"] = 2
        s["event_pair_count"] = 3
        s["fill_time_count"] = 3
        s["fill_time_before_path_hour_count"] = 2
        s["fill_time_inside_path_hour_count"] = 1
        s["block_record_counts_by_local_prefix_and_block_prefix"][c.block_pair_key(path, prev)] = 1
        s["block_record_counts_by_local_prefix_and_block_prefix"][c.block_pair_key(path, path)] = 1
        s["fill_counts_by_local_prefix_block_prefix_and_fill_partition"][c.fill_key(path, prev, "BEFORE_PATH_HOUR")] = 2
        s["fill_counts_by_local_prefix_block_prefix_and_fill_partition"][c.fill_key(path, path, "INSIDE_PATH_HOUR")] = 1
        s["block_records_with_before_fill_by_local_prefix_and_block_prefix"][c.block_pair_key(path, prev)] = 1
        s["block_record_count_with_any_before_fill"] = 1
        self.assertEqual(c.classify_correlation(s, self.small_expected()), c.POSITIVE)
        self.assertEqual(s["boundary_record_correlation_classification"], c.POSITIVE)

    def test_negative_when_pre_hour_fills_do_not_colocate(self) -> None:
        s = self.small_summary()
        path = "MATCHES_PATH_DATE_HOUR_PREFIX"
        prev = "MATCHES_PREVIOUS_DATE_HOUR_PREFIX"
        s["block_record_count"] = 2
        s["event_pair_count"] = 3
        s["fill_time_count"] = 3
        s["fill_time_before_path_hour_count"] = 2
        s["fill_time_inside_path_hour_count"] = 1
        s["block_record_counts_by_local_prefix_and_block_prefix"][c.block_pair_key(path, prev)] = 1
        s["block_record_counts_by_local_prefix_and_block_prefix"][c.block_pair_key(path, path)] = 1
        s["fill_counts_by_local_prefix_block_prefix_and_fill_partition"][c.fill_key(path, path, "BEFORE_PATH_HOUR")] = 2
        s["fill_counts_by_local_prefix_block_prefix_and_fill_partition"][c.fill_key(path, prev, "INSIDE_PATH_HOUR")] = 1
        s["block_records_with_before_fill_by_local_prefix_and_block_prefix"][c.block_pair_key(path, path)] = 1
        s["block_record_count_with_any_before_fill"] = 1
        self.assertEqual(c.classify_correlation(s, self.small_expected()), c.NEGATIVE)

    def test_parent_or_conservation_mismatch_is_unresolved(self) -> None:
        s = self.small_summary()
        with self.assertRaises(c.DiagnosticUnresolved):
            c.classify_correlation(s, self.small_expected())

    def test_aggregator_reads_only_pair_shape_and_fill_time(self) -> None:
        s = self.small_summary()
        a = c.BoundaryCorrelationAggregator(s)
        record = {
            "local_time": "2025-07-27T09:00:00.001",
            "block_time": "2025-07-27T08:59:59.999",
            "block_number": 123,
            "events": [["opaque-leading-string", {"time": c.TARGET["path_hour_start_ms"] - 1, "px": "ignored", "closedPnl": "ignored"}]],
        }
        a.add_line((json.dumps(record) + "\n").encode())
        path = "MATCHES_PATH_DATE_HOUR_PREFIX"
        prev = "MATCHES_PREVIOUS_DATE_HOUR_PREFIX"
        self.assertEqual(s["block_record_count"], 1)
        self.assertEqual(s["event_pair_count"], 1)
        self.assertEqual(s["fill_time_before_path_hour_count"], 1)
        self.assertEqual(s["block_record_counts_by_local_prefix_and_block_prefix"][c.block_pair_key(path, prev)], 1)
        self.assertNotIn("opaque-leading-string", repr(s))
        self.assertNotIn("123", repr(s))
        self.assertNotIn("ignored", repr(s))

    def test_duplicate_json_and_nonfinite_values_are_rejected(self) -> None:
        s = self.small_summary()
        a = c.BoundaryCorrelationAggregator(s)
        duplicate = b'{"local_time":"2025-07-27T09:00:00.1","local_time":"x","block_time":"2025-07-27T09:00:00.1","block_number":1,"events":[]}'
        with self.assertRaises(c.DiagnosticUnresolved):
            a.add_line(duplicate)
        nonfinite = b'{"local_time":"2025-07-27T09:00:00.1","block_time":"2025-07-27T09:00:00.1","block_number":1,"events":[["x",{"time":NaN}]]}'
        with self.assertRaises(c.DiagnosticUnresolved):
            a.add_line(nonfinite)

    def test_prefix_and_fill_partition_rules_are_raw_and_frozen(self) -> None:
        self.assertEqual(c.prefix_bucket("2025-07-27T09:xx"), "MATCHES_PATH_DATE_HOUR_PREFIX")
        self.assertEqual(c.prefix_bucket("2025-07-27T08:anything"), "MATCHES_PREVIOUS_DATE_HOUR_PREFIX")
        self.assertEqual(c.fill_partition(c.TARGET["path_hour_start_ms"] - 1), "BEFORE_PATH_HOUR")
        self.assertEqual(c.fill_partition(c.TARGET["path_hour_start_ms"]), "INSIDE_PATH_HOUR")
        self.assertEqual(c.fill_partition(c.TARGET["path_hour_end_ms"] - 1), "INSIDE_PATH_HOUR")
        self.assertEqual(c.fill_partition(c.TARGET["path_hour_end_ms"]), "AFTER_PATH_HOUR")

    def test_signed_request_is_exact_one_object_requester_pays(self) -> None:
        env = {"AWS_ACCESS_KEY_ID": "AKID", "AWS_SECRET_ACCESS_KEY": "SECRET", "AWS_SESSION_TOKEN": "TOKEN"}
        host, path, headers = c.build_signed_request(datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc), env)
        self.assertEqual(host, "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com")
        self.assertEqual(path, "/node_fills_by_block/hourly/20250727/9.lz4")
        self.assertEqual(headers["If-Match"], c.TARGET["etag"])
        self.assertEqual(headers["x-amz-request-payer"], "requester")
        self.assertIn("SignedHeaders=host;if-match;x-amz-content-sha256;x-amz-date;x-amz-request-payer;x-amz-security-token", headers["Authorization"])

    def test_transport_failure_is_single_attempt_nonzero(self) -> None:
        calls = []
        def transport(host: str, path: str, headers: dict[str, str], expected_size: int, timeout_seconds: float):
            calls.append((host, path, expected_size))
            return 403, {}, b""
        env = {"AWS_ACCESS_KEY_ID": "AKID", "AWS_SECRET_ACCESS_KEY": "SECRET", "AWS_SESSION_TOKEN": "TOKEN"}
        rc, result = c.execute(transport=transport, request_time=lambda: datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc), env=env)
        self.assertEqual(rc, 85)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["s3_http_request_count"], 1)
        self.assertEqual(result["failed_request_count"], 1)
        self.assertEqual(result["terminal_status"], "R10C_TRANSPORT_OR_INTEGRITY_FAIL")
        self.assertEqual(result["retries_used"], 0)


if __name__ == "__main__":
    unittest.main()
