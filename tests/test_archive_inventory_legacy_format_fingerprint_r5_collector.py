from __future__ import annotations

import hashlib
import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
R5 = ROOT / "research/archive_inventory/r5"
COLLECTOR_PATH = R5 / "collector.py"
spec = importlib.util.spec_from_file_location("r5_legacy_format_collector", COLLECTOR_PATH)
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
    return datetime(2026, 8, 9, 13, 0, tzinfo=timezone.utc)


class ArchiveLegacyFormatFingerprintR5CollectorTests(unittest.TestCase):
    def test_static_inputs_are_exact_one_r4_bound_object(self) -> None:
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

    def test_classifier_resolves_declared_classes_in_precedence_order(self) -> None:
        cases = [
            (b'["alpha",{"px":"1","nested":{"x":2}}]\n["beta",{"px":"2","nested":{"x":3}}]\n', "UTF8_NDJSON_PAIR_STRING_OBJECT", "LEGACY_FORMAT_RESOLVED_AS_NDJSON_PAIR_STRING_OBJECT"),
            (b'[{"px":"1"},"alpha"]\n[{"px":"2"},"beta"]\n', "UTF8_NDJSON_PAIR_OBJECT_STRING", "LEGACY_FORMAT_RESOLVED_AS_NDJSON_PAIR_OBJECT_STRING"),
            (b'[1,2,3]\n[4,5,6]\n', "UTF8_NDJSON_ARRAY_OTHER", "LEGACY_FORMAT_RESOLVED_AS_OTHER_DECLARED_JSON_CLASS"),
            (b'{"a":1}\n{"a":2}\n', "UTF8_NDJSON_OBJECT_STREAM", "LEGACY_FORMAT_RESOLVED_AS_OTHER_DECLARED_JSON_CLASS"),
            (b'{"a":1}\n[1,2]\n', "UTF8_NDJSON_MIXED_JSON_ROOTS", "LEGACY_FORMAT_RESOLVED_AS_OTHER_DECLARED_JSON_CLASS"),
            (b'[\n  {"a":1},\n  {"a":2}\n]\n', "UTF8_SINGLE_JSON_ARRAY_DOCUMENT", "LEGACY_FORMAT_RESOLVED_AS_OTHER_DECLARED_JSON_CLASS"),
            (b'{\n  "a": 1,\n  "b": [2,3]\n}\n', "UTF8_SINGLE_JSON_OBJECT_DOCUMENT", "LEGACY_FORMAT_RESOLVED_AS_OTHER_DECLARED_JSON_CLASS"),
            (b'{"a":1}{"a":2}', "UTF8_CONCATENATED_JSON_VALUES", "LEGACY_FORMAT_RESOLVED_AS_OTHER_DECLARED_JSON_CLASS"),
            (b'not-json\n', "UTF8_NONJSON_OR_UNRESOLVED", "LEGACY_FORMAT_UNRESOLVED"),
            (b'\xff\xfe\xfd', "NON_UTF8_OR_UNRESOLVED", "LEGACY_FORMAT_UNRESOLVED"),
        ]
        for payload, expected_class, expected_conclusion in cases:
            with self.subTest(expected_class=expected_class):
                result = collector.classify_decompressed_payload(payload)
                self.assertEqual(result["format_class"], expected_class)
                self.assertEqual(result["research_conclusion"], expected_conclusion)

    def test_structural_evidence_retains_names_types_counts_but_never_values(self) -> None:
        payload = (
            b'["0x1111111111111111111111111111111111111111",{"coin":"BTC","px":"12345.67","oid":987654321,"nested":{"secret":"VALUE_A"}}]\n'
            b'["0x2222222222222222222222222222222222222222",{"coin":"ETH","px":"765.43","oid":123456789,"nested":{"secret":"VALUE_B"}}]\n'
        )
        result = collector.classify_decompressed_payload(payload)
        self.assertEqual(result["format_class"], "UTF8_NDJSON_PAIR_STRING_OBJECT")
        evidence = result["structural_evidence"]
        self.assertEqual(evidence["nonempty_record_count"], 2)
        self.assertEqual(evidence["array_arity_histogram"], {"2": 2})
        self.assertEqual(evidence["array_element_type_signature_counts"], {"string,object": 2})
        self.assertIn("/*/coin", evidence["object_field_path_names"])
        self.assertIn("/*/nested/secret", evidence["object_field_path_names"])
        serialized = str(result)
        for forbidden in (
            "0x1111111111111111111111111111111111111111",
            "0x2222222222222222222222222222222222222222",
            "BTC", "ETH", "12345.67", "765.43", "987654321", "123456789", "VALUE_A", "VALUE_B",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertFalse(result["payload_values_retained"])
        self.assertFalse(result["string_values_retained"])
        self.assertFalse(result["numeric_values_retained"])
        self.assertFalse(result["wallet_addresses_retained"])
        self.assertFalse(result["record_payload_retained"])

    def test_duplicate_keys_and_nonfinite_constants_are_not_accepted_as_valid_json_records(self) -> None:
        for payload in (b'{"a":1,"a":2}\n', b'{"a":NaN}\n'):
            result = collector.classify_decompressed_payload(payload)
            self.assertEqual(result["format_class"], "UTF8_NONJSON_OR_UNRESOLVED")
            self.assertEqual(result["research_conclusion"], "LEGACY_FORMAT_UNRESOLVED")

    def test_execute_success_is_one_request_and_structural_only_under_synthetic_caps(self) -> None:
        body = b"Xabc"
        decompressed = b'["secret",{"a":1}]\n'
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
            mock.patch.object(collector, "LZ4_FRAME_MAGIC", b"X"),
            mock.patch.object(collector, "iter_lz4_frame", return_value=iter([decompressed])),
        ):
            rc, result = collector.execute(transport=transport, request_time=fixed_now, env=FAKE_AWS_ENV)
        self.assertEqual(rc, 0)
        self.assertEqual(result["terminal_status"], "R5_LEGACY_FORMAT_FINGERPRINT_COMPLETE")
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["s3_http_request_count"], 1)
        self.assertEqual(result["successful_request_count"], 1)
        self.assertEqual(result["research_conclusion"], "LEGACY_FORMAT_RESOLVED_AS_NDJSON_PAIR_STRING_OBJECT")
        self.assertNotIn("secret", str(result))
        self.assertFalse(result["wallet_reconstruction_performed"])
        self.assertFalse(result["market_data_ingested"])

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
        self.assertEqual(result["terminal_status"], "R5_TRANSPORT_OR_INTEGRITY_FAIL")
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["s3_http_request_count"], 1)
        self.assertEqual(result["retries_used"], 0)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
