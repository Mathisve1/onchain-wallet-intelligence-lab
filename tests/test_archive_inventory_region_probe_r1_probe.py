from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = ROOT / "research/archive_inventory/region_probe_r1/probe.py"
SPEC = importlib.util.spec_from_file_location("region_probe_r1_probe", PROBE_PATH)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class ArchiveRegionProbeR1ProbeTests(unittest.TestCase):
    def test_sigv4_request_is_exact_head_requester_pays_shape(self) -> None:
        env = {
            "AWS_ACCESS_KEY_ID": "AKIATEST",
            "AWS_SECRET_ACCESS_KEY": "test-secret",
            "AWS_SESSION_TOKEN": "test-token",
        }
        host, target, headers = probe.build_signed_head_request(
            datetime(2026, 8, 8, 15, 0, 0, tzinfo=timezone.utc), env
        )
        self.assertEqual(host, "hl-mainnet-node-data.s3.amazonaws.com")
        self.assertEqual(target, "/")
        self.assertEqual(headers["Host"], host)
        self.assertEqual(headers["x-amz-request-payer"], "requester")
        self.assertEqual(headers["x-amz-security-token"], "test-token")
        self.assertIn("/us-east-1/s3/aws4_request", headers["Authorization"])
        self.assertIn("SignedHeaders=host;x-amz-content-sha256;x-amz-date;x-amz-request-payer;x-amz-security-token", headers["Authorization"])

    def test_valid_region_header_is_research_success_even_on_403(self) -> None:
        calls: list[tuple[float, object]] = []

        def fake_transport(timeout: float, request_time: object) -> tuple[int, str | None, str | None]:
            calls.append((timeout, request_time))
            return 403, "ap-northeast-1", None

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            rc = probe.run_probe(path, fake_transport)
            result = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["terminal_status"], "REGION_PROBE_R1_PASS")
        self.assertEqual(result["http_status"], 403)
        self.assertEqual(result["x_amz_bucket_region"], "ap-northeast-1")
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["s3_http_request_count"], 1)
        self.assertEqual(result["retries_used"], 0)
        self.assertFalse(result["http_redirects_followed"])
        self.assertFalse(result["response_body_read"])
        self.assertFalse(result["list_objects_v2_requested"])
        self.assertFalse(result["object_body_requested"])
        self.assertFalse(result["market_data_ingested"])
        self.assertIsNone(result["empirical_result"])

    def test_missing_or_invalid_region_fails_without_second_transport(self) -> None:
        for value in (None, "", "EU West 1", "a" * 21):
            calls = 0

            def fake_transport(timeout: float, request_time: object, region=value) -> tuple[int, str | None, str | None]:
                nonlocal calls
                calls += 1
                return 403, region, None

            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "result.json"
                rc = probe.run_probe(path, fake_transport)
                result = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(rc, 1)
            self.assertEqual(calls, 1)
            self.assertEqual(result["failure_class"], "MISSING_OR_INVALID_BUCKET_REGION_HEADER")
            self.assertIsNone(result["x_amz_bucket_region"])
            self.assertEqual(result["retries_used"], 0)

    def test_source_never_reads_response_body_or_constructs_other_s3_methods(self) -> None:
        source = PROBE_PATH.read_text(encoding="utf-8")
        self.assertIn('connection.request("HEAD", target, body=None, headers=headers)', source)
        self.assertNotIn("response.read(", source)
        self.assertNotIn('connection.request("GET"', source)
        self.assertNotIn('connection.request("POST"', source)
        self.assertNotIn('connection.request("PUT"', source)
        self.assertNotIn('connection.request("DELETE"', source)
        self.assertNotIn("ListObjectsV2", source)
        self.assertNotIn("GetObject", source)
        self.assertNotIn("HeadObject", source)
        self.assertEqual(source.count('connection.request("HEAD"'), 1)


if __name__ == "__main__":
    unittest.main()
