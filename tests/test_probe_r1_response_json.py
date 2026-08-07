from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE_ROOT = ROOT / "research/wallet_copyability/probe_r1"
sys.path.insert(0, str(PROBE_ROOT))

import http_client


class ProbeR1ResponseJSONTests(unittest.TestCase):
    def record(self, body: bytes) -> http_client.ResponseRecord:
        return http_client.ResponseRecord(
            http_status=200,
            body=body,
            content_type="application/json",
            elapsed_ms=1.0,
            transport_error_class=None,
            transport_error_message=None,
        )

    def test_duplicate_object_keys_fail(self) -> None:
        status, summary = http_client.classify_body(
            "json_object",
            self.record(b'{"a":1,"a":2}'),
        )
        self.assertEqual(status, "FAIL")
        self.assertEqual(summary["json_status"], "INVALID_JSON")
        self.assertEqual(summary["response_class"], "UNSUPPORTED")

    def test_nonfinite_constants_fail(self) -> None:
        for body in (
            b'{"x":NaN}',
            b'{"x":Infinity}',
            b'{"x":-Infinity}',
        ):
            with self.subTest(body=body):
                status, summary = http_client.classify_body(
                    "json_object",
                    self.record(body),
                )
                self.assertEqual(status, "FAIL")
                self.assertEqual(summary["json_status"], "INVALID_JSON")

    def test_finite_unique_json_still_passes(self) -> None:
        status, summary = http_client.classify_body(
            "json_object",
            self.record(b'{"a":1,"b":[2,3]}'),
        )
        self.assertEqual(status, "PASS")
        self.assertEqual(summary["json_status"], "VALID_JSON")
        self.assertEqual(summary["top_level_keys"], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
