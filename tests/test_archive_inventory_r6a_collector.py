from __future__ import annotations

import hashlib
import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
R6A = ROOT / "research/archive_inventory/r6a"
COLLECTOR_PATH = R6A / "collector.py"
spec = importlib.util.spec_from_file_location("r6a_lexical_collector", COLLECTOR_PATH)
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
    return datetime(2026, 8, 9, 17, 0, tzinfo=timezone.utc)


class ArchiveR6ALexicalCollectorTests(unittest.TestCase):
    def test_static_inputs_are_exact_same_r5_bound_object(self) -> None:
        target = collector.validate_static_inputs()
        self.assertEqual(target["key"], "node_fills/hourly/20250727/8.lz4")
        self.assertEqual(target["expected_size_bytes"], 12726384)
        self.assertEqual(target["expected_etag"], '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"')
        self.assertEqual(target["expected_compressed_sha256"], "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622")
        self.assertEqual(target["expected_decompressed_byte_count"], 62169139)

    def test_sigv4_request_signs_exact_path_if_match_and_requester_pays(self) -> None:
        host, path, headers = collector.build_signed_request(fixed_now(), FAKE_AWS_ENV)
        self.assertEqual(host, "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com")
        self.assertEqual(path, "/node_fills/hourly/20250727/8.lz4")
        self.assertEqual(headers["If-Match"], '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"')
        self.assertEqual(headers["x-amz-request-payer"], "requester")
        self.assertIn("if-match", headers["Authorization"])
        self.assertIn("x-amz-request-payer", headers["Authorization"])
        self.assertNotIn("Range", headers)

    def test_streaming_aggregator_counts_address_shapes_without_retaining_values(self) -> None:
        lower = "0x" + "11" * 20
        mixed = "0x" + "Aa" * 20
        invalid = "not-an-address"
        payload = (
            f'["{lower}",{{"coin":"BTC","px":"1"}}]\n'
            f'["{mixed}",{{"coin":"ETH","px":"2"}}]\n'
            f'["{invalid}",{{"coin":"SOL","px":"3"}}]\n'
        ).encode()
        chunks = [payload[:13], payload[13:59], payload[59:101], payload[101:]]
        byte_count, evidence = collector.aggregate_decompressed_chunks(chunks)
        self.assertEqual(byte_count, len(payload))
        self.assertEqual(evidence["nonempty_record_count"], 3)
        self.assertEqual(evidence["pair_string_object_record_count"], 3)
        self.assertEqual(evidence["leading_string_count"], 3)
        self.assertEqual(evidence["leading_string_length_42_count"], 2)
        self.assertEqual(evidence["leading_string_0x40hex_count"], 2)
        self.assertEqual(evidence["leading_string_lowercase_0x40hex_count"], 1)
        self.assertEqual(evidence["leading_string_non_0x40hex_count"], 1)
        serialized = str(evidence)
        for forbidden in (lower, mixed, invalid, "BTC", "ETH", "SOL"):
            self.assertNotIn(forbidden, serialized)

    def test_chunk_boundaries_do_not_change_record_counts(self) -> None:
        a = "0x" + "1" * 40
        b = "0x" + "2" * 40
        payload = f'["{a}",{{"x":1}}]\n["{b}",{{"x":2}}]'.encode()
        chunks = [payload[i : i + 1] for i in range(len(payload))]
        byte_count, evidence = collector.aggregate_decompressed_chunks(chunks)
        self.assertEqual(byte_count, len(payload))
        self.assertEqual(evidence["nonempty_record_count"], 2)
        self.assertEqual(evidence["leading_string_0x40hex_count"], 2)
        self.assertNotIn(a, str(evidence))
        self.assertNotIn(b, str(evidence))

    def test_duplicate_keys_and_nonfinite_constants_are_unresolved(self) -> None:
        for payload in (
            b'["0x1111111111111111111111111111111111111111",{"a":1,"a":2}]\n',
            b'["0x1111111111111111111111111111111111111111",{"a":NaN}]\n',
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(collector.R6ALexicalUnresolved):
                    collector.aggregate_decompressed_chunks([payload])

    def test_conclusion_requires_exact_record_shape_and_count(self) -> None:
        all_match = {
            "nonempty_record_count": 2,
            "pair_string_object_record_count": 2,
            "leading_string_count": 2,
            "leading_string_0x40hex_count": 2,
        }
        some_mismatch = dict(all_match, leading_string_0x40hex_count=1)
        wrong_shape = dict(all_match, pair_string_object_record_count=1)
        with mock.patch.object(collector, "EXPECTED_NONEMPTY_RECORDS", 2):
            self.assertEqual(
                collector.classify_lexical_evidence(all_match),
                "ALL_LEADING_STRINGS_MATCH_HYPERLIQUID_ADDRESS_SHAPE",
            )
            self.assertEqual(
                collector.classify_lexical_evidence(some_mismatch),
                "SOME_LEADING_STRINGS_DO_NOT_MATCH_HYPERLIQUID_ADDRESS_SHAPE",
            )
            self.assertEqual(
                collector.classify_lexical_evidence(wrong_shape),
                "R6A_LEXICAL_SHAPE_UNRESOLVED",
            )

    def test_execute_success_is_one_request_and_aggregate_only_under_synthetic_caps(self) -> None:
        body = b"Xabc"
        first = "0x" + "1" * 40
        second = "0x" + "A" * 40
        decompressed = f'["{first}",{{"secret":"VALUE_A"}}]\n["{second}",{{"secret":"VALUE_B"}}]\n'.encode()
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
            mock.patch.object(collector, "EXPECTED_NONEMPTY_RECORDS", 2),
            mock.patch.object(collector, "LZ4_FRAME_MAGIC", b"X"),
            mock.patch.object(collector, "iter_lz4_frame", return_value=iter([decompressed[:17], decompressed[17:]])),
        ):
            rc, result = collector.execute(transport=transport, request_time=fixed_now, env=FAKE_AWS_ENV)
        self.assertEqual(rc, 0)
        self.assertEqual(result["terminal_status"], "R6A_LEXICAL_CONFIRMATION_COMPLETE")
        self.assertEqual(result["research_conclusion"], "ALL_LEADING_STRINGS_MATCH_HYPERLIQUID_ADDRESS_SHAPE")
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["s3_http_request_count"], 1)
        self.assertEqual(result["successful_request_count"], 1)
        evidence = result["lexical_aggregates"]
        self.assertEqual(evidence["leading_string_0x40hex_count"], 2)
        self.assertEqual(evidence["leading_string_lowercase_0x40hex_count"], 1)
        serialized = str(result)
        for forbidden in (first, second, "VALUE_A", "VALUE_B"):
            self.assertNotIn(forbidden, serialized)
        self.assertFalse(result["leading_string_values_retained"])
        self.assertFalse(result["wallet_addresses_retained"])
        self.assertFalse(result["leading_string_hashes_retained"])
        self.assertFalse(result["distinct_address_set_retained"])
        self.assertFalse(result["wallet_reconstruction_performed"])
        self.assertFalse(result["market_data_ingested"])

    def test_execute_some_nonmatching_is_research_result_not_transport_failure(self) -> None:
        body = b"Xabc"
        good = "0x" + "1" * 40
        decompressed = f'["{good}",{{"x":1}}]\n["bad",{{"x":2}}]\n'.encode()
        body_sha = hashlib.sha256(body).hexdigest()

        def transport(host, path, headers, expected_size, timeout):
            del host, path, headers, timeout
            return 200, {
                "content-length": str(expected_size),
                "etag": collector.EXPECTED_ETAG,
                "x-amz-request-charged": "requester",
            }, body

        with (
            mock.patch.object(collector, "validate_static_inputs", return_value={}),
            mock.patch.object(collector, "EXPECTED_SIZE_BYTES", 4),
            mock.patch.object(collector, "MAX_TOTAL_COMPRESSED_BYTES", 4),
            mock.patch.object(collector, "EXPECTED_COMPRESSED_SHA256", body_sha),
            mock.patch.object(collector, "EXPECTED_DECOMPRESSED_BYTES", len(decompressed)),
            mock.patch.object(collector, "EXPECTED_NONEMPTY_RECORDS", 2),
            mock.patch.object(collector, "LZ4_FRAME_MAGIC", b"X"),
            mock.patch.object(collector, "iter_lz4_frame", return_value=iter([decompressed])),
        ):
            rc, result = collector.execute(transport=transport, request_time=fixed_now, env=FAKE_AWS_ENV)
        self.assertEqual(rc, 0)
        self.assertEqual(result["research_conclusion"], "SOME_LEADING_STRINGS_DO_NOT_MATCH_HYPERLIQUID_ADDRESS_SHAPE")
        self.assertEqual(result["lexical_aggregates"]["leading_string_non_0x40hex_count"], 1)
        self.assertNotIn(good, str(result))
        self.assertNotIn("bad", str(result))

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
            rc, result = collector.execute(transport=transport, request_time=fixed_now, env=FAKE_AWS_ENV)
        self.assertNotEqual(rc, 0)
        self.assertEqual(result["terminal_status"], "R6A_TRANSPORT_OR_INTEGRITY_FAIL")
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["s3_http_request_count"], 1)
        self.assertEqual(result["retries_used"], 0)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
