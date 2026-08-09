from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
R4 = ROOT / "research/archive_inventory/r4"
sys.path.insert(0, str(R4))

import collector  # noqa: E402
from lz4_frame import LZ4_FRAME_MAGIC, xxh32  # noqa: E402


class Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        self.value += 0.1
        return self.value


def fixed_now() -> datetime:
    return datetime(2026, 8, 9, 8, 0, tzinfo=timezone.utc)


def tiny_frame(payload: bytes) -> bytes:
    flg = 0x40 | 0x20 | 0x08 | 0x04
    bd = 0x40
    descriptor = bytes((flg, bd)) + len(payload).to_bytes(8, "little")
    header = LZ4_FRAME_MAGIC + descriptor + bytes(((xxh32(descriptor) >> 8) & 0xFF,))
    return (
        header
        + (len(payload) | 0x80000000).to_bytes(4, "little")
        + payload
        + (0).to_bytes(4, "little")
        + xxh32(payload).to_bytes(4, "little")
    )


def synthetic_analysis(field_types: dict[str, list[str]]) -> dict:
    names = sorted(field_types)
    return {
        "lz4_frame_recognized": True,
        "decompression_status": "LZ4_FRAME_DECOMPRESSED",
        "decompressed_byte_count": 100,
        "record_count": 10,
        "top_level_json_type": "object",
        "field_path_names": names,
        "field_path_type_sets": {name: field_types[name] for name in names},
        "field_path_presence_counts": {name: 10 for name in names},
        "maximum_observed_nesting_depth": 1,
        "schema_status": "FULL_SCHEMA_PARSED",
        "failure_class": None,
    }


class ArchiveHourlyBodySchemaR4CollectorTests(unittest.TestCase):
    def test_static_inputs_are_exact_two_approved_objects(self) -> None:
        rows = collector.validate_static_inputs()
        self.assertEqual(rows, [dict(row) for row in collector.EXPECTED_OBJECTS])
        self.assertEqual(sum(row["expected_size_bytes"] for row in rows), 14243987)

    def test_sigv4_request_signs_exact_path_if_match_and_requester_pays(self) -> None:
        env = {
            "AWS_ACCESS_KEY_ID": "AKIDEXAMPLE",
            "AWS_SECRET_ACCESS_KEY": "secret",
            "AWS_SESSION_TOKEN": "session",
        }
        spec = dict(collector.EXPECTED_OBJECTS[0])
        host, path, headers = collector.build_signed_request(spec, fixed_now(), env)
        self.assertEqual(host, "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com")
        self.assertEqual(path, "/node_fills/hourly/20250727/8.lz4")
        self.assertEqual(headers["If-Match"], '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"')
        self.assertEqual(headers["x-amz-request-payer"], "requester")
        self.assertIn("if-match", headers["Authorization"])
        self.assertIn("x-amz-request-payer", headers["Authorization"])
        self.assertNotIn("Range", headers)

    def test_schema_aggregator_retains_names_types_counts_not_values(self) -> None:
        payload = (
            b'{"wallet":"0xabc","nested":{"x":1},"arr":[true,2]}\n'
            b'{"wallet":"0xdef","nested":{"x":2},"arr":[false,3]}\n'
        )
        result = collector.analyze_compressed_object(tiny_frame(payload))
        self.assertEqual(result["schema_status"], "FULL_SCHEMA_PARSED")
        self.assertEqual(result["record_count"], 2)
        self.assertEqual(result["field_path_type_sets"]["/wallet"], ["string"])
        self.assertEqual(result["field_path_type_sets"]["/nested/x"], ["integer"])
        self.assertEqual(result["field_path_type_sets"]["/arr/*"], ["bool", "integer"])
        serialized = str(result)
        self.assertNotIn("0xabc", serialized)
        self.assertNotIn("0xdef", serialized)

    def test_duplicate_nonfinite_or_nonobject_json_is_unresolved_without_fallback(self) -> None:
        for payload in (
            b'{"a":1,"a":2}\n',
            b'{"a":NaN}\n',
            b'[1,2,3]\n',
            b'not-json\n',
        ):
            result = collector.analyze_compressed_object(tiny_frame(payload))
            self.assertEqual(result["schema_status"], "BODY_READABLE_SCHEMA_UNRESOLVED")
            self.assertEqual(result["failure_class"], "UTF8_NDJSON_OBJECT_SCHEMA_UNRESOLVED")

    def test_unrecognized_lz4_is_schema_unresolved_without_alternate_decoder(self) -> None:
        result = collector.analyze_compressed_object(b"not-an-lz4-frame")
        self.assertFalse(result["lz4_frame_recognized"])
        self.assertEqual(result["schema_status"], "SCHEMA_UNRESOLVED")
        self.assertEqual(result["failure_class"], "LZ4_FRAME_UNRECOGNIZED")

    def test_two_successful_exact_objects_produce_resolved_schema_comparison(self) -> None:
        def transport(host: str, path: str, headers: dict[str, str], expected_size: int, timeout: float):
            del host, headers, timeout
            etag = collector.EXPECTED_OBJECTS[0]["expected_etag"] if path.startswith("/node_fills/hourly/") else collector.EXPECTED_OBJECTS[1]["expected_etag"]
            return 200, {
                "x-amz-request-charged": "requester",
                "etag": etag,
                "content-length": str(expected_size),
            }, b"x" * expected_size

        def analyze(raw: bytes) -> dict:
            if len(raw) == collector.EXPECTED_OBJECTS[0]["expected_size_bytes"]:
                return synthetic_analysis({"/a": ["integer"]})
            return synthetic_analysis({"/a": ["integer"], "/b": ["string"]})

        with mock.patch.object(collector, "analyze_compressed_object", side_effect=analyze):
            result = collector.execute_pilot(transport=transport, clock=Clock(), now=fixed_now)
        self.assertEqual(result["terminal_status"], "R4_BODY_SCHEMA_PILOT_COMPLETE")
        self.assertEqual(result["technical_result"], "TWO_OBJECT_SCHEMA_COMPARISON_RESOLVED")
        self.assertEqual(result["schema_comparison_class"], "LEGACY_SCHEMA_SUBSET_OF_MODERN")
        self.assertEqual(result["request_attempt_count"], 2)
        self.assertEqual(result["s3_http_request_count"], 2)
        self.assertEqual(result["successful_request_count"], 2)
        self.assertEqual(result["failed_request_count"], 0)
        self.assertEqual(result["total_compressed_bytes"], 14243987)
        self.assertFalse(result["raw_compressed_object_persisted"])
        self.assertFalse(result["record_payload_retained"])
        self.assertFalse(result["wallet_reconstruction_performed"])
        self.assertFalse(result["market_data_ingested"])

    def test_content_length_or_etag_or_requester_charge_mismatch_stops_before_second_request(self) -> None:
        cases = [
            (200, {"x-amz-request-charged": "requester", "etag": collector.EXPECTED_OBJECTS[0]["expected_etag"], "content-length": "1"}, b"x", "CONTENT_LENGTH_MISMATCH"),
            (200, {"x-amz-request-charged": "requester", "etag": '"different"', "content-length": str(collector.EXPECTED_OBJECTS[0]["expected_size_bytes"])}, b"", "RESPONSE_ETAG_MISMATCH"),
            (200, {"etag": collector.EXPECTED_OBJECTS[0]["expected_etag"], "content-length": str(collector.EXPECTED_OBJECTS[0]["expected_size_bytes"])}, b"", "REQUESTER_PAYS_CHARGE_HEADER_MISMATCH"),
        ]
        for status, response_headers, body, expected_failure in cases:
            calls = []
            def transport(host, path, headers, expected_size, timeout):
                del host, headers, expected_size, timeout
                calls.append(path)
                return status, response_headers, body
            result = collector.execute_pilot(transport=transport, clock=Clock(), now=fixed_now)
            self.assertEqual(result["terminal_status"], "R4_BODY_SCHEMA_PILOT_FAIL")
            self.assertEqual(result["request_attempt_count"], 1)
            self.assertEqual(len(calls), 1)
            self.assertEqual(result["observations"][0]["failure_class"], expected_failure)

    def test_http_412_is_one_attempt_no_retry(self) -> None:
        calls = []
        def transport(host, path, headers, expected_size, timeout):
            del host, headers, expected_size, timeout
            calls.append(path)
            return 412, {}, b""
        result = collector.execute_pilot(transport=transport, clock=Clock(), now=fixed_now)
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["s3_http_request_count"], 1)
        self.assertEqual(result["retries_used"], 0)
        self.assertEqual(result["observations"][0]["failure_class"], "HTTP_412_ETAG_PRECONDITION_FAILED")
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
