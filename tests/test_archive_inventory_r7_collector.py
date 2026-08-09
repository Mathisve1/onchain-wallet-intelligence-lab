from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
R7 = ROOT / "research/archive_inventory/r7"
COLLECTOR_PATH = R7 / "collector.py"
spec = importlib.util.spec_from_file_location("r7_wallet_index_collector", COLLECTOR_PATH)
assert spec is not None and spec.loader is not None
collector = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = collector
spec.loader.exec_module(collector)

FAKE_AWS_ENV = {
    "AWS_ACCESS_KEY_ID": "AKIDEXAMPLE",
    "AWS_SECRET_ACCESS_KEY": "secret",
    "AWS_SESSION_TOKEN": "session",
}


def fixed_now() -> datetime:
    return datetime(2026, 8, 9, 18, 30, tzinfo=timezone.utc)


class ArchiveR7WalletIndexCollectorTests(unittest.TestCase):
    def test_static_inputs_bind_exact_approved_object(self) -> None:
        target = collector.validate_static_inputs()
        self.assertEqual(target["key"], "node_fills/hourly/20250727/8.lz4")
        self.assertEqual(target["expected_size_bytes"], 12726384)
        self.assertEqual(target["expected_nonempty_record_count"], 162815)
        self.assertEqual(target["required_leading_string_pattern"], "^0x[0-9a-f]{40}$")

    def test_sigv4_request_is_exact_if_match_requester_pays_get(self) -> None:
        host, path, headers = collector.build_signed_request(fixed_now(), FAKE_AWS_ENV)
        self.assertEqual(host, "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com")
        self.assertEqual(path, "/node_fills/hourly/20250727/8.lz4")
        self.assertEqual(headers["If-Match"], '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"')
        self.assertEqual(headers["x-amz-request-payer"], "requester")
        self.assertIn("if-match", headers["Authorization"])
        self.assertIn("x-amz-request-payer", headers["Authorization"])
        self.assertNotIn("Range", headers)

    def test_streaming_index_groups_addresses_and_retains_no_fill_values(self) -> None:
        a = "0x" + "1" * 40
        b = "0x" + "2" * 40
        payload = (
            f'["{b}",{{"coin":"BTC","px":"999","secret":"NOPE"}}]\n'
            f'["{a}",{{"coin":"ETH","px":"888","secret":"NOPE2"}}]\n'
            f'["{b}",{{"coin":"SOL","px":"777","secret":"NOPE3"}}]\n'
        ).encode()
        with mock.patch.object(collector, "EXPECTED_NONEMPTY_RECORDS", 3):
            byte_count, index_bytes, summary = collector.aggregate_decompressed_chunks(
                [payload[:11], payload[11:77], payload[77:]]
            )
        self.assertEqual(byte_count, len(payload))
        self.assertEqual(summary["unique_wallet_count"], 2)
        self.assertEqual(summary["sum_fill_count"], 3)
        rows = [json.loads(line) for line in index_bytes.decode().splitlines()]
        self.assertEqual(rows, [
            {"wallet_address": a, "fill_count": 1},
            {"wallet_address": b, "fill_count": 2},
        ])
        serialized = index_bytes.decode()
        for forbidden in ("BTC", "ETH", "SOL", "999", "888", "777", "NOPE"):
            self.assertNotIn(forbidden, serialized)

    def test_invalid_address_or_record_shape_is_unresolved(self) -> None:
        cases = [
            b'["0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",{"x":1}]\n',
            b'["not-an-address",{"x":1}]\n',
            b'{"x":1}\n',
            b'["0x1111111111111111111111111111111111111111",{"a":1,"a":2}]\n',
            b'["0x1111111111111111111111111111111111111111",{"a":NaN}]\n',
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                with mock.patch.object(collector, "EXPECTED_NONEMPTY_RECORDS", 1):
                    with self.assertRaises(collector.R7ReconstructionUnresolved):
                        collector.aggregate_decompressed_chunks([payload])

    def test_output_cap_is_fail_closed(self) -> None:
        a = "0x" + "1" * 40
        payload = f'["{a}",{{"x":1}}]\n'.encode()
        with (
            mock.patch.object(collector, "EXPECTED_NONEMPTY_RECORDS", 1),
            mock.patch.object(collector, "MAX_WALLET_INDEX_BYTES", 10),
        ):
            with self.assertRaises(collector.R7ReconstructionUnresolved):
                collector.aggregate_decompressed_chunks([payload])

    def test_execute_success_is_one_request_and_returns_deterministic_index(self) -> None:
        body = b"Xabc"
        a = "0x" + "1" * 40
        b = "0x" + "2" * 40
        decompressed = (
            f'["{b}",{{"secret":"VALUE_B"}}]\n'
            f'["{a}",{{"secret":"VALUE_A"}}]\n'
            f'["{b}",{{"secret":"VALUE_C"}}]\n'
        ).encode()
        body_sha = hashlib.sha256(body).hexdigest()

        def transport(host, path, headers, expected_size, timeout):
            del timeout
            self.assertEqual(host, collector.REGIONAL_ENDPOINT)
            self.assertEqual(path, "/node_fills/hourly/20250727/8.lz4")
            self.assertEqual(headers["x-amz-request-payer"], "requester")
            self.assertEqual(expected_size, 4)
            return 200, {
                "content-length": "4",
                "etag": collector.EXPECTED_ETAG,
                "x-amz-request-charged": "requester",
            }, body

        with (
            mock.patch.object(collector, "validate_static_inputs", return_value={}),
            mock.patch.object(collector, "EXPECTED_SIZE_BYTES", 4),
            mock.patch.object(collector, "MAX_TOTAL_COMPRESSED_BYTES", 4),
            mock.patch.object(collector, "EXPECTED_COMPRESSED_SHA256", body_sha),
            mock.patch.object(collector, "EXPECTED_DECOMPRESSED_BYTES", len(decompressed)),
            mock.patch.object(collector, "EXPECTED_NONEMPTY_RECORDS", 3),
            mock.patch.object(collector, "LZ4_FRAME_MAGIC", b"X"),
            mock.patch.object(collector, "iter_lz4_frame", return_value=iter([decompressed[:17], decompressed[17:]])),
        ):
            rc, result, index_bytes = collector.execute(transport=transport, request_time=fixed_now, env=FAKE_AWS_ENV)
        self.assertEqual(rc, 0)
        self.assertEqual(result["terminal_status"], "R7_WALLET_INDEX_STUDY_COMPLETE")
        self.assertEqual(result["research_conclusion"], "WALLET_INDEX_RECONSTRUCTION_COMPLETE")
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["s3_http_request_count"], 1)
        self.assertEqual(result["successful_request_count"], 1)
        self.assertTrue(result["wallet_addresses_retained"])
        self.assertTrue(result["per_wallet_fill_counts_retained"])
        rows = [json.loads(line) for line in index_bytes.decode().splitlines()]
        self.assertEqual(rows[0]["wallet_address"], a)
        self.assertEqual(rows[1]["wallet_address"], b)
        self.assertEqual(rows[1]["fill_count"], 2)
        self.assertEqual(result["wallet_index_summary"]["wallet_index_sha256"], hashlib.sha256(index_bytes).hexdigest())
        for forbidden in ("VALUE_A", "VALUE_B", "VALUE_C"):
            self.assertNotIn(forbidden, str(result))
            self.assertNotIn(forbidden, index_bytes.decode())
        self.assertFalse(result["fill_object_retained"])
        self.assertFalse(result["payload_values_retained"])
        self.assertFalse(result["entity_clustering_performed"])
        self.assertFalse(result["pnl_or_alpha_analysis_performed"])

    def test_integrity_mismatch_is_single_attempt_no_retry(self) -> None:
        calls: list[str] = []

        def transport(host, path, headers, expected_size, timeout):
            del host, headers, timeout
            calls.append(path)
            return 200, {
                "content-length": str(expected_size),
                "etag": '"wrong"',
                "x-amz-request-charged": "requester",
            }, b"x" * expected_size

        with mock.patch.object(collector, "validate_static_inputs", return_value={}):
            rc, result, index_bytes = collector.execute(transport=transport, request_time=fixed_now, env=FAKE_AWS_ENV)
        self.assertNotEqual(rc, 0)
        self.assertEqual(result["terminal_status"], "R7_TRANSPORT_OR_INTEGRITY_FAIL")
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["retries_used"], 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(index_bytes, b"")


if __name__ == "__main__":
    unittest.main()
