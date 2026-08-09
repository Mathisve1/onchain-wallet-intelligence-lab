from __future__ import annotations

import json
import unittest
from datetime import timedelta
from unittest.mock import patch

from research.archive_inventory.r10_implementation import collector


ADDRESS_A = "0x" + "1" * 40
ADDRESS_B = "0x" + "2" * 40
ENV = {
    "AWS_ACCESS_KEY_ID": "ASIATEST",
    "AWS_SECRET_ACCESS_KEY": "secret",
    "AWS_SESSION_TOKEN": "token",
}


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


def block_line(events: list[list[object]]) -> bytes:
    return json.dumps({
        "local_time": "2025-07-27T00:00:00Z",
        "block_time": "2025-07-27T00:00:00Z",
        "block_number": 1,
        "events": events,
    }, separators=(",", ":")).encode()


def target(hour: int, *, size: int = 1) -> dict:
    return {
        "path_hour_utc": f"2025-07-27T{hour:02d}:00:00Z",
        "key": f"node_fills_by_block/hourly/20250727/{hour}.lz4",
        "size": size,
        "etag": f'"etag-{hour}"',
    }


class ArchiveR10CollectorTests(unittest.TestCase):
    def test_static_inputs_are_exact_and_inert(self) -> None:
        collector.validate_static_inputs()

    def test_signed_request_is_exact_object_if_match_and_requester_pays(self) -> None:
        frozen = collector.TARGETS[0]
        when = collector.parse_utc("2026-08-09T22:00:00Z")
        host, path, headers = collector.build_signed_request(frozen, when, ENV)
        self.assertEqual(host, "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com")
        self.assertEqual(path, "/node_fills_by_block/hourly/20250727/9.lz4")
        self.assertEqual(headers["If-Match"], frozen["etag"])
        self.assertEqual(headers["x-amz-request-payer"], "requester")
        self.assertIn("if-match;x-amz-content-sha256;x-amz-date;x-amz-request-payer;x-amz-security-token", headers["Authorization"])

    def test_cross_hour_aggregation_tracks_active_hours_and_conserves(self) -> None:
        aggregate = collector.MultiHourAggregator()
        t9 = target(9)
        t10 = target(10)
        start9 = int(collector.parse_utc(t9["path_hour_utc"]).timestamp() * 1000)
        start10 = int(collector.parse_utc(t10["path_hour_utc"]).timestamp() * 1000)
        per9 = {"block_record_count": 0, "event_pair_count": 0, "path_hour_alignment_violation_count": 0}
        per10 = {"block_record_count": 0, "event_pair_count": 0, "path_hour_alignment_violation_count": 0}
        aggregate.add_line(block_line([[ADDRESS_A, fill(start9 + 1, 1)], [ADDRESS_B, fill(start9 + 2, 2, side="B")]]), t9, per9)
        aggregate.add_line(block_line([[ADDRESS_A, fill(start10 + 1, 3, side="B", coin="ETH", closed="-0.5")]]), t10, per10)
        rendered, summary = aggregate.render()
        rows = [json.loads(line) for line in rendered.decode().splitlines()]
        self.assertEqual([row["wallet_address"] for row in rows], [ADDRESS_A, ADDRESS_B])
        self.assertEqual(rows[0]["fill_count"], 2)
        self.assertEqual(rows[0]["active_hour_count"], 2)
        self.assertEqual(rows[0]["distinct_coin_count"], 2)
        self.assertEqual(rows[0]["side_a_count"] + rows[0]["side_b_count"], 2)
        self.assertEqual(rows[0]["duplicate_tid_count"], 0)
        self.assertEqual(summary["sum_fill_count"], 3)
        self.assertEqual(summary["sum_side_count"], 3)
        self.assertEqual(summary["duplicate_wallet_tid_count"], 0)

    def test_out_of_hour_fill_fails_closed(self) -> None:
        aggregate = collector.MultiHourAggregator()
        t9 = target(9)
        end = int((collector.parse_utc(t9["path_hour_utc"]) + timedelta(hours=1)).timestamp() * 1000)
        per9 = {"block_record_count": 0, "event_pair_count": 0, "path_hour_alignment_violation_count": 0}
        with self.assertRaises(collector.R10FeatureUnresolved):
            aggregate.add_line(block_line([[ADDRESS_A, fill(end, 1)]]), t9, per9)
        self.assertEqual(per9["path_hour_alignment_violation_count"], 1)

    def test_duplicate_wallet_tid_is_diagnostic_and_never_blindly_deduped(self) -> None:
        aggregate = collector.MultiHourAggregator()
        t9 = target(9)
        start = int(collector.parse_utc(t9["path_hour_utc"]).timestamp() * 1000)
        per9 = {"block_record_count": 0, "event_pair_count": 0, "path_hour_alignment_violation_count": 0}
        aggregate.add_line(block_line([[ADDRESS_A, fill(start + 1, 7)], [ADDRESS_A, fill(start + 2, 7)]]), t9, per9)
        self.assertEqual(aggregate.states[ADDRESS_A]["fill_count"], 2)
        self.assertEqual(aggregate.states[ADDRESS_A]["duplicate_tid_count"], 1)
        with self.assertRaises(collector.R10FeatureUnresolved):
            aggregate.render()

    def test_execute_synthetic_six_hours_is_one_request_each_and_deterministic(self) -> None:
        synthetic = [target(hour) for hour in range(9, 15)]
        calls: list[str] = []

        def fake_transport(host: str, path: str, headers: dict[str, str], expected_size: int, timeout: float):
            calls.append(path)
            self.assertEqual(expected_size, 1)
            self.assertEqual(headers["x-amz-request-payer"], "requester")
            return 200, {"x-amz-request-charged": "requester", "etag": headers["If-Match"], "content-length": "1"}, b"x"

        def fake_aggregate(_compressed: bytes, t: dict, aggregate: collector.MultiHourAggregator) -> dict:
            start = int(collector.parse_utc(t["path_hour_utc"]).timestamp() * 1000)
            per_hour = {
                "path_hour_utc": t["path_hour_utc"], "object_key": t["key"], "expected_etag": t["etag"],
                "expected_content_length": 1, "observed_content_length": 1, "compressed_sha256": collector.sha256_bytes(b"x"),
                "decompressed_byte_count": 10, "block_record_count": 0, "event_pair_count": 0,
                "path_hour_alignment_violation_count": 0,
            }
            aggregate.add_line(block_line([[ADDRESS_A, fill(start + 1, int(t["path_hour_utc"][11:13]))]]), t, per_hour)
            return per_hour

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
        self.assertEqual(result1["successful_request_count"], 6)
        self.assertEqual(result1["completed_hour_count"], 6)
        self.assertEqual(result1["aggregate_wallet_feature_summary"]["sum_fill_count"], 6)
        self.assertEqual(result2["aggregate_wallet_feature_summary"]["wallet_feature_sha256"], result1["aggregate_wallet_feature_summary"]["wallet_feature_sha256"])

    def test_first_identity_mismatch_stops_before_second_request(self) -> None:
        synthetic = [target(hour) for hour in range(9, 15)]
        calls = 0

        def bad_transport(host: str, path: str, headers: dict[str, str], expected_size: int, timeout: float):
            nonlocal calls
            calls += 1
            return 200, {"x-amz-request-charged": "requester", "etag": '"wrong"', "content-length": "1"}, b"x"

        with patch.object(collector, "validate_static_inputs", lambda: None), patch.object(collector, "TARGETS", synthetic):
            rc, result, output = collector.execute(transport=bad_transport, env=ENV)
        self.assertEqual(rc, 83)
        self.assertEqual(calls, 1)
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["failed_request_count"], 1)
        self.assertEqual(result["terminal_status"], "R10_TRANSPORT_OR_INTEGRITY_FAIL")
        self.assertEqual(output, b"")


if __name__ == "__main__":
    unittest.main()
