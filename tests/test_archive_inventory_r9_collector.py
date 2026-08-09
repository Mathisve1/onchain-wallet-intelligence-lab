from __future__ import annotations

import json
import unittest
from decimal import Decimal

from research.archive_inventory.r9 import collector


class ArchiveR9CollectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        lines: list[bytes] = []
        index = 0
        for block_number in range(collector.EXPECTED_BLOCK_COUNT):
            event_count = 5 if block_number < 136 else 4
            events = []
            for _ in range(event_count):
                fill = {
                    "coin": "BTC" if index % 2 == 0 else "ETH",
                    "side": "A" if index % 2 == 0 else "B",
                    "time": 1_750_000_000_000 + index,
                    "px": "10.50",
                    "sz": "2",
                    "closedPnl": "1.25" if index % 2 == 0 else "-0.25",
                    "tid": 0,
                    "crossed": index % 2 == 0,
                    "liquidation": {"method": "market"} if index % 1000 == 0 else None,
                }
                events.append(["0x1111111111111111111111111111111111111111", fill])
                index += 1
            block = {
                "local_time": "2025-07-27T08:00:00Z",
                "block_time": "2025-07-27T08:00:00Z",
                "block_number": block_number,
                "events": events,
            }
            lines.append(json.dumps(block, separators=(",", ":")).encode("utf-8") + b"\n")
        assert index == collector.EXPECTED_EVENT_PAIR_COUNT
        cls.payload = b"".join(lines)

    def test_static_inputs_are_exact_and_inert(self) -> None:
        collector.validate_static_inputs()
        self.assertEqual(collector.OBJECT_KEY, "node_fills_by_block/hourly/20250727/8.lz4")
        self.assertEqual(collector.EXPECTED_SIZE, 1517603)
        self.assertEqual(collector.EXPECTED_BLOCK_COUNT, 4345)
        self.assertEqual(collector.EXPECTED_EVENT_PAIR_COUNT, 17516)
        self.assertEqual(collector.MAX_RUNTIME_SECONDS, 120)
        self.assertEqual(collector.MAX_OUTPUT_BYTES, 33554432)

    def test_aggregate_is_deterministic_exact_decimal_and_conservative(self) -> None:
        output, summary = collector.aggregate_decompressed(self.payload)
        self.assertEqual(summary["top_level_block_record_count"], 4345)
        self.assertEqual(summary["valid_event_pair_count"], 17516)
        self.assertEqual(summary["wallet_feature_row_count"], 1)
        self.assertEqual(summary["sum_fill_count"], 17516)
        self.assertEqual(summary["sum_side_count"], 17516)
        self.assertEqual(summary["wallet_feature_fields_only"], collector.OUTPUT_FIELDS)
        self.assertEqual(summary["wallet_feature_sha256"], collector.sha256_bytes(output))

        rows = output.splitlines()
        self.assertEqual(len(rows), 1)
        row = json.loads(rows[0])
        self.assertEqual(list(row.keys()), collector.OUTPUT_FIELDS)
        self.assertEqual(row["wallet_address"], "0x1111111111111111111111111111111111111111")
        self.assertEqual(row["fill_count"], 17516)
        self.assertEqual(row["side_a_count"], 8758)
        self.assertEqual(row["side_b_count"], 8758)
        self.assertEqual(row["distinct_coin_count"], 2)
        self.assertEqual(row["crossed_true_count"], 8758)
        self.assertEqual(row["liquidation_associated_fill_count"], 18)
        self.assertEqual(row["duplicate_tid_count"], 17515)
        self.assertEqual(row["sum_abs_px_times_sz_notional_proxy"], "367836")
        self.assertEqual(row["sum_closed_pnl_fill_statistic"], "8758")
        self.assertLessEqual(row["first_fill_time"], row["last_fill_time"])

        output2, summary2 = collector.aggregate_decompressed(self.payload)
        self.assertEqual(output, output2)
        self.assertEqual(summary, summary2)

    def test_invalid_selected_field_fails_closed_before_result(self) -> None:
        bad = {
            "local_time": "x",
            "block_time": "x",
            "block_number": 1,
            "events": [[
                "0x1111111111111111111111111111111111111111",
                {"coin":"BTC","side":"X","time":1,"px":"1","sz":"1","closedPnl":"0","tid":1,"crossed":False},
            ]],
        }
        payload = json.dumps(bad, separators=(",", ":")).encode() + b"\n"
        with self.assertRaises(collector.R9FeatureUnresolved):
            collector.aggregate_decompressed(payload)

    def test_strict_json_rejects_duplicate_and_nonfinite_values(self) -> None:
        with self.assertRaises(collector.R9JSONError):
            collector.strict_loads('{"x":1,"x":2}')
        with self.assertRaises(collector.R9JSONError):
            collector.strict_loads('{"x":NaN}')

    def test_decimal_encoding_is_canonical_and_no_float_is_needed(self) -> None:
        self.assertEqual(collector.canonical_decimal(Decimal("10.5000")), "10.5")
        self.assertEqual(collector.canonical_decimal(Decimal("0.000")), "0")
        self.assertEqual(collector.canonical_decimal(Decimal("-0.000")), "0")
        self.assertEqual(collector.canonical_decimal(Decimal("1E+3")), "1000")

    def test_signed_request_reuses_exact_r8a_transport_shape(self) -> None:
        env = {
            "AWS_ACCESS_KEY_ID": "AKIATEST",
            "AWS_SECRET_ACCESS_KEY": "test-secret",
            "AWS_SESSION_TOKEN": "test-session",
        }
        from datetime import datetime, timezone
        host, path, headers = collector.r8a_transport.build_signed_request(
            datetime(2026, 8, 9, 20, 0, tzinfo=timezone.utc), env
        )
        self.assertEqual(host, "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com")
        self.assertEqual(path, "/node_fills_by_block/hourly/20250727/8.lz4")
        self.assertEqual(headers["If-Match"], collector.EXPECTED_ETAG)
        self.assertEqual(headers["x-amz-request-payer"], "requester")
        self.assertIn("SignedHeaders=host;if-match;x-amz-content-sha256;x-amz-date;x-amz-request-payer;x-amz-security-token", headers["Authorization"])


if __name__ == "__main__":
    unittest.main()
