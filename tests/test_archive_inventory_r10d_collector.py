from __future__ import annotations

import json
import unittest
from datetime import timedelta
from unittest.mock import patch

from research.archive_inventory.r10d_implementation import collector

ADDRESS_A = "0x" + "1" * 40
ADDRESS_B = "0x" + "2" * 40
ENV = {"AWS_ACCESS_KEY_ID": "ASIATEST", "AWS_SECRET_ACCESS_KEY": "secret", "AWS_SESSION_TOKEN": "token"}


def fill(time_ms: int, tid: int, *, side: str = "A", coin: str = "BTC", closed: str = "1.25") -> dict:
    return {
        "coin": coin,
        "side": side,
        "time": time_ms,
        "px": "100.5",
        "sz": "2",
        "closedPnl": closed,
        "tid": tid,
        "crossed": side == "A",
        "liquidation": None,
    }


def target(hour: int, *, size: int = 1, known_sha256: str | None = None) -> dict:
    return {
        "path_hour_utc": f"2025-07-27T{hour:02d}:00:00Z",
        "key": f"node_fills_by_block/hourly/20250727/{hour}.lz4",
        "size": size,
        "etag": f'"etag-{hour}"',
        "known_sha256": known_sha256,
    }


def block_line(path_hour: int, block_hour: int, events: list[list[object]]) -> bytes:
    return json.dumps({
        "local_time": f"2025-07-27T{path_hour:02d}:00:00.001",
        "block_time": f"2025-07-27T{block_hour:02d}:59:59.999",
        "block_number": 1,
        "events": events,
    }, separators=(",", ":")).encode()


def per_hour() -> dict:
    return {
        "block_record_count": 0,
        "event_pair_count": 0,
        "local_path_block_path_record_count": 0,
        "local_path_block_previous_record_count": 0,
        "fill_time_before_path_hour_count": 0,
        "fill_time_inside_path_hour_count": 0,
        "fill_time_after_path_hour_count": 0,
        "before_fills_in_local_path_block_previous_records": 0,
        "record_anchored_alignment_violation_count": 0,
    }


class R10DCollectorTests(unittest.TestCase):
    def test_static_inputs_are_exact_and_inert(self) -> None:
        collector.validate_static_inputs()

    def test_path_block_record_accepts_only_inside_fill(self) -> None:
        agg = collector.RecordAnchoredAggregator()
        t = target(10)
        start = int(collector.base.parse_utc(t["path_hour_utc"]).timestamp() * 1000)
        p = per_hour()
        agg.add_line(block_line(10, 10, [[ADDRESS_A, fill(start + 1, 1)]]), t, p)
        self.assertEqual(p["local_path_block_path_record_count"], 1)
        self.assertEqual(p["fill_time_inside_path_hour_count"], 1)
        self.assertEqual(p["record_anchored_alignment_violation_count"], 0)

    def test_previous_block_record_accepts_before_fill_without_numeric_tolerance(self) -> None:
        agg = collector.RecordAnchoredAggregator()
        t = target(10)
        start = int(collector.base.parse_utc(t["path_hour_utc"]).timestamp() * 1000)
        p = per_hour()
        agg.add_line(block_line(10, 9, [[ADDRESS_A, fill(start - 51, 1)]]), t, p)
        self.assertEqual(p["local_path_block_previous_record_count"], 1)
        self.assertEqual(p["fill_time_before_path_hour_count"], 1)
        self.assertEqual(p["before_fills_in_local_path_block_previous_records"], 1)
        self.assertEqual(p["record_anchored_alignment_violation_count"], 0)

    def test_path_block_before_fill_fails_closed(self) -> None:
        agg = collector.RecordAnchoredAggregator()
        t = target(10)
        start = int(collector.base.parse_utc(t["path_hour_utc"]).timestamp() * 1000)
        p = per_hour()
        with self.assertRaises(collector.base.R10FeatureUnresolved):
            agg.add_line(block_line(10, 10, [[ADDRESS_A, fill(start - 1, 1)]]), t, p)
        self.assertEqual(p["record_anchored_alignment_violation_count"], 1)

    def test_previous_block_inside_fill_fails_closed(self) -> None:
        agg = collector.RecordAnchoredAggregator()
        t = target(10)
        start = int(collector.base.parse_utc(t["path_hour_utc"]).timestamp() * 1000)
        p = per_hour()
        with self.assertRaises(collector.base.R10FeatureUnresolved):
            agg.add_line(block_line(10, 9, [[ADDRESS_A, fill(start + 1, 1)]]), t, p)
        self.assertEqual(p["record_anchored_alignment_violation_count"], 1)

    def test_previous_block_fill_older_than_immediately_previous_hour_fails_closed(self) -> None:
        agg = collector.RecordAnchoredAggregator()
        t = target(10)
        start = int(collector.base.parse_utc(t["path_hour_utc"]).timestamp() * 1000)
        p = per_hour()
        with self.assertRaises(collector.base.R10FeatureUnresolved):
            agg.add_line(block_line(10, 9, [[ADDRESS_A, fill(start - 3_600_001, 1)]]), t, p)
        self.assertEqual(p["record_anchored_alignment_violation_count"], 1)

    def test_next_or_other_block_prefix_fails_closed(self) -> None:
        agg = collector.RecordAnchoredAggregator()
        t = target(10)
        start = int(collector.base.parse_utc(t["path_hour_utc"]).timestamp() * 1000)
        p = per_hour()
        with self.assertRaises(collector.base.R10FeatureUnresolved):
            agg.add_line(block_line(10, 11, [[ADDRESS_A, fill(start + 1, 1)]]), t, p)
        self.assertEqual(p["record_anchored_alignment_violation_count"], 1)

    def test_local_time_prefix_must_match_path_hour(self) -> None:
        agg = collector.RecordAnchoredAggregator()
        t = target(10)
        start = int(collector.base.parse_utc(t["path_hour_utc"]).timestamp() * 1000)
        p = per_hour()
        with self.assertRaises(collector.base.R10FeatureUnresolved):
            agg.add_line(block_line(9, 10, [[ADDRESS_A, fill(start + 1, 1)]]), t, p)
        self.assertEqual(p["record_anchored_alignment_violation_count"], 1)

    def test_execute_synthetic_six_hours_is_deterministic_and_preserves_feature_contract(self) -> None:
        synthetic = [target(hour) for hour in range(9, 15)]
        calls: list[str] = []

        def fake_transport(host: str, path: str, headers: dict[str, str], expected_size: int, timeout: float):
            calls.append(path)
            return 200, {"x-amz-request-charged": "requester", "etag": headers["If-Match"], "content-length": "1"}, b"x"

        def fake_aggregate(_compressed: bytes, t: dict, aggregate: collector.RecordAnchoredAggregator) -> dict:
            hour = int(t["path_hour_utc"][11:13])
            start = int(collector.base.parse_utc(t["path_hour_utc"]).timestamp() * 1000)
            p = {
                "path_hour_utc": t["path_hour_utc"], "object_key": t["key"], "expected_etag": t["etag"],
                "expected_content_length": 1, "observed_content_length": 1, "compressed_sha256": collector.base.sha256_bytes(b"x"),
                "decompressed_byte_count": 10, **per_hour(),
            }
            aggregate.add_line(block_line(hour, hour, [[ADDRESS_A, fill(start + 1, hour)]]), t, p)
            return p

        with patch.object(collector, "validate_static_inputs", lambda: None), patch.object(collector, "TARGETS", synthetic), patch.object(collector, "aggregate_lz4_object", fake_aggregate):
            rc1, result1, output1 = collector.execute(transport=fake_transport, env=ENV)
            calls1 = list(calls)
            calls.clear()
            rc2, result2, output2 = collector.execute(transport=fake_transport, env=ENV)
        self.assertEqual(rc1, rc2, 0)
        self.assertEqual(calls1, [f"/node_fills_by_block/hourly/20250727/{hour}.lz4" for hour in range(9, 15)])
        self.assertEqual(calls, calls1)
        self.assertEqual(output1, output2)
        row = json.loads(output1.decode().strip())
        self.assertEqual(row["wallet_address"], ADDRESS_A)
        self.assertEqual(row["fill_count"], 6)
        self.assertEqual(row["active_hour_count"], 6)
        self.assertEqual(result1["completed_hour_count"], 6)
        self.assertEqual(result1["technical_result"], "R10D_MULTI_HOUR_FEATURE_PIPELINE_COMPLETE")
        self.assertFalse(result1["numeric_tolerance_authorized"])
        self.assertEqual(result2["aggregate_wallet_feature_summary"]["wallet_feature_sha256"], result1["aggregate_wallet_feature_summary"]["wallet_feature_sha256"])

    def test_preknown_hour_sha_mismatch_stops_before_second_request(self) -> None:
        wrong = "0" * 64
        synthetic = [target(9, known_sha256=wrong)] + [target(hour) for hour in range(10, 15)]
        calls = 0

        def fake_transport(host: str, path: str, headers: dict[str, str], expected_size: int, timeout: float):
            nonlocal calls
            calls += 1
            return 200, {"x-amz-request-charged": "requester", "etag": headers["If-Match"], "content-length": "1"}, b"x"

        with patch.object(collector, "validate_static_inputs", lambda: None), patch.object(collector, "TARGETS", synthetic):
            rc, result, output = collector.execute(transport=fake_transport, env=ENV)
        self.assertEqual(rc, 84)
        self.assertEqual(calls, 1)
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["failed_request_count"], 1)
        self.assertEqual(result["terminal_status"], "R10D_TRANSPORT_OR_INTEGRITY_FAIL")
        self.assertEqual(output, b"")

    def test_signed_request_reuses_exact_r10_transport_shape(self) -> None:
        t = collector.TARGETS[0]
        frozen = {"path_hour_utc": t["path_hour_utc"], "key": t["key"], "size": t["size"], "etag": t["etag"]}
        when = collector.base.parse_utc("2026-08-10T17:00:00Z")
        host, path, headers = collector.base.build_signed_request(frozen, when, ENV)
        self.assertEqual(host, "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com")
        self.assertEqual(path, "/node_fills_by_block/hourly/20250727/9.lz4")
        self.assertEqual(headers["If-Match"], t["etag"])
        self.assertEqual(headers["x-amz-request-payer"], "requester")


if __name__ == "__main__":
    unittest.main()
