from __future__ import annotations

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "research/archive_inventory/r8"
R4 = ROOT / "research/archive_inventory/r4"
sys.path.insert(0, str(R8))
sys.path.insert(0, str(R4))

import collector as r8a  # noqa: E402
from lz4_frame import LZ4_FRAME_MAGIC, xxh32  # noqa: E402


def frame(payload: bytes) -> bytes:
    flg = 0x40 | 0x20 | 0x10 | 0x08 | 0x04
    bd = 0x40
    descriptor = bytes((flg, bd)) + len(payload).to_bytes(8, "little")
    encoded = bytearray(LZ4_FRAME_MAGIC + descriptor + bytes(((xxh32(descriptor) >> 8) & 0xFF,)))
    for start in range(0, len(payload), 64 * 1024):
        block = payload[start : start + 64 * 1024]
        encoded.extend((len(block) | 0x80000000).to_bytes(4, "little"))
        encoded.extend(block)
        encoded.extend(xxh32(block).to_bytes(4, "little"))
    encoded.extend((0).to_bytes(4, "little"))
    encoded.extend(xxh32(payload).to_bytes(4, "little"))
    return bytes(encoded)


def block(number: int, events: list[list[object]]) -> bytes:
    return (json.dumps({
        "local_time": f"2025-07-27T08:00:{number:02d}Z",
        "block_time": f"2025-07-27T08:00:{number:02d}Z",
        "block_number": number,
        "events": events,
    }, separators=(",", ":")) + "\n").encode()


class ArchiveR8ACollectorTests(unittest.TestCase):
    def test_streaming_index_groups_addresses_and_retains_no_fill_values(self) -> None:
        a = "0x" + "1" * 40
        b = "0x" + "2" * 40
        aggregate = r8a.ModernWalletIndexAggregator()
        with mock.patch.object(r8a, "EXPECTED_BLOCK_RECORDS", 2):
            aggregate.add_line(block(1, [[a, {"coin":"BTC","px":"1"}], [b, {"closedPnl":"10"}]]).rstrip(b"\n"))
            aggregate.add_line(block(2, [[a, {"fee":"5"}]]).rstrip(b"\n"))
            rendered, summary = aggregate.render()
        rows = [json.loads(line) for line in rendered.decode().splitlines()]
        self.assertEqual(rows, [
            {"wallet_address": a, "fill_count": 2},
            {"wallet_address": b, "fill_count": 1},
        ])
        self.assertEqual(summary["top_level_block_record_count"], 2)
        self.assertEqual(summary["valid_event_pair_count"], 3)
        self.assertEqual(summary["sum_fill_count"], 3)
        self.assertNotIn("BTC", rendered.decode())
        self.assertNotIn("closedPnl", rendered.decode())
        self.assertNotIn("fee", rendered.decode())

    def test_invalid_address_shape_and_strict_json_are_unresolved(self) -> None:
        aggregate = r8a.ModernWalletIndexAggregator()
        with self.assertRaises(r8a.R8ABridgeUnresolved):
            aggregate.add_line(block(1, [["0xABC", {}]]).rstrip(b"\n"))
        duplicate = b'{"local_time":"x","local_time":"y","block_time":"x","block_number":1,"events":[]}'
        with self.assertRaises(r8a.R8ABridgeUnresolved):
            r8a.ModernWalletIndexAggregator().add_line(duplicate)
        nonfinite = b'{"local_time":"x","block_time":"x","block_number":1,"events":[],"x":NaN}'
        with self.assertRaises(r8a.R8ABridgeUnresolved):
            r8a.ModernWalletIndexAggregator().add_line(nonfinite)

    def test_sigv4_request_is_exact_if_match_requester_pays_get(self) -> None:
        env = {"AWS_ACCESS_KEY_ID":"AKID", "AWS_SECRET_ACCESS_KEY":"SECRET", "AWS_SESSION_TOKEN":"TOKEN"}
        host, path, headers = r8a.build_signed_request(datetime(2026, 8, 9, 19, 0, tzinfo=timezone.utc), env)
        self.assertEqual(host, "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com")
        self.assertEqual(path, "/node_fills_by_block/hourly/20250727/8.lz4")
        self.assertEqual(headers["If-Match"], '"60d4c1277f76651b5f04666bbe8d7594"')
        self.assertEqual(headers["x-amz-request-payer"], "requester")
        self.assertIn("SignedHeaders=host;if-match;x-amz-content-sha256;x-amz-date;x-amz-request-payer;x-amz-security-token", headers["Authorization"])
        self.assertNotIn("Range", headers)

    def test_execute_success_is_one_request_and_returns_deterministic_index(self) -> None:
        a = "0x" + "a" * 40
        b = "0x" + "b" * 40
        payload = block(1, [[b, {}], [a, {}]]) + block(2, [[a, {}]])
        encoded = frame(payload)
        calls = []

        def transport(host, path, headers, expected_size, timeout):
            calls.append((host, path, headers, expected_size, timeout))
            return 200, {
                "content-length": str(len(encoded)),
                "etag": '"synthetic"',
                "x-amz-request-charged": "requester",
            }, encoded

        env = {"AWS_ACCESS_KEY_ID":"AKID", "AWS_SECRET_ACCESS_KEY":"SECRET", "AWS_SESSION_TOKEN":"TOKEN"}
        patches = {
            "EXPECTED_SIZE_BYTES": len(encoded),
            "EXPECTED_ETAG": '"synthetic"',
            "EXPECTED_COMPRESSED_SHA256": hashlib.sha256(encoded).hexdigest(),
            "EXPECTED_DECOMPRESSED_BYTES": len(payload),
            "EXPECTED_BLOCK_RECORDS": 2,
            "MAX_TOTAL_COMPRESSED_BYTES": len(encoded),
            "MAX_TOTAL_DECOMPRESSED_BYTES": len(payload) + 1,
        }
        with mock.patch.object(r8a, "validate_static_inputs", return_value=None), mock.patch.multiple(r8a, **patches):
            rc, result, index = r8a.execute(transport=transport, request_time=lambda: datetime(2026,8,9,19,0,tzinfo=timezone.utc), env=env)
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["retries_used"], 0)
        self.assertEqual(result["research_conclusion"], "MODERN_WALLET_INDEX_BRIDGE_COMPLETE")
        self.assertEqual(result["wallet_index_summary"]["valid_event_pair_count"], 3)
        rows = [json.loads(line) for line in index.decode().splitlines()]
        self.assertEqual(rows, [{"wallet_address":a,"fill_count":2},{"wallet_address":b,"fill_count":1}])

    def test_integrity_mismatch_is_single_attempt_no_retry(self) -> None:
        payload = block(1, [["0x" + "1" * 40, {}]])
        encoded = frame(payload)
        calls = 0
        def transport(*_args):
            nonlocal calls
            calls += 1
            return 200, {"content-length":str(len(encoded)), "etag":'"synthetic"', "x-amz-request-charged":"requester"}, encoded
        env = {"AWS_ACCESS_KEY_ID":"AKID", "AWS_SECRET_ACCESS_KEY":"SECRET", "AWS_SESSION_TOKEN":"TOKEN"}
        patches = {
            "EXPECTED_SIZE_BYTES": len(encoded),
            "EXPECTED_ETAG": '"synthetic"',
            "EXPECTED_COMPRESSED_SHA256": "0" * 64,
            "MAX_TOTAL_COMPRESSED_BYTES": len(encoded),
        }
        with mock.patch.object(r8a, "validate_static_inputs", return_value=None), mock.patch.multiple(r8a, **patches):
            rc, result, index = r8a.execute(transport=transport, request_time=lambda: datetime(2026,8,9,19,0,tzinfo=timezone.utc), env=env)
        self.assertEqual(rc, 1)
        self.assertEqual(calls, 1)
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["retries_used"], 0)
        self.assertEqual(index, b"")
        self.assertEqual(result["research_conclusion"], "R8A_TRANSPORT_OR_INTEGRITY_FAIL")


if __name__ == "__main__":
    unittest.main()
