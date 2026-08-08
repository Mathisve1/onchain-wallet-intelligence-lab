from __future__ import annotations

import importlib.util
import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR_PATH = ROOT / "research/archive_inventory/r0/collector.py"
SPEC = importlib.util.spec_from_file_location("r0_collector", COLLECTOR_PATH)
assert SPEC is not None and SPEC.loader is not None
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        current = self.value
        self.value += 0.1
        return current


def list_xml(bucket: str, prefix: str, *, truncated: bool = True, token: str | None = "DO-NOT-RETAIN", entries: int = 1) -> bytes:
    contents = "".join(
        f"<Contents><Key>{prefix}sample-{index}</Key><LastModified>2026-08-08T00:00:00.000Z</LastModified><ETag>&quot;abc{index}&quot;</ETag><Size>{100 + index}</Size><StorageClass>STANDARD</StorageClass></Contents>"
        for index in range(entries)
    )
    token_xml = f"<NextContinuationToken>{token}</NextContinuationToken>" if token else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        f"<Name>{bucket}</Name><Prefix>{prefix}</Prefix><KeyCount>{entries}</KeyCount>"
        f"<MaxKeys>25</MaxKeys><IsTruncated>{str(truncated).lower()}</IsTruncated>"
        f"{contents}{token_xml}</ListBucketResult>"
    ).encode()


class ArchiveR0CollectorTests(unittest.TestCase):
    def test_sigv4_request_is_exact_requester_pays_list_v2(self) -> None:
        env = {
            "AWS_ACCESS_KEY_ID": "AKIDEXAMPLE",
            "AWS_SECRET_ACCESS_KEY": "SECRETEXAMPLE",
            "AWS_SESSION_TOKEN": "SESSIONTOKENEXAMPLE",
        }
        host, target, headers = collector.build_signed_request(
            "hyperliquid-archive",
            "asset_ctxs/",
            datetime(2026, 8, 8, 10, 0, 0, tzinfo=timezone.utc),
            env,
        )
        self.assertEqual(host, "hyperliquid-archive.s3.amazonaws.com")
        self.assertEqual(target, "/?list-type=2&max-keys=25&prefix=asset_ctxs%2F")
        self.assertEqual(headers["x-amz-request-payer"], "requester")
        self.assertEqual(headers["x-amz-content-sha256"], collector.EMPTY_PAYLOAD_SHA256)
        self.assertEqual(headers["x-amz-date"], "20260808T100000Z")
        self.assertEqual(headers["x-amz-security-token"], "SESSIONTOKENEXAMPLE")
        self.assertTrue(
            headers["Authorization"].startswith(
                "AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20260808/us-east-1/s3/aws4_request,"
            )
        )
        self.assertIn(
            "SignedHeaders=host;x-amz-content-sha256;x-amz-date;x-amz-request-payer;x-amz-security-token",
            headers["Authorization"],
        )

    def test_unregistered_prefix_fails_before_network(self) -> None:
        env = {
            "AWS_ACCESS_KEY_ID": "A",
            "AWS_SECRET_ACCESS_KEY": "B",
            "AWS_SESSION_TOKEN": "C",
        }
        with self.assertRaises(collector.R0ContractError):
            collector.build_signed_request(
                "hl-mainnet-node-data",
                "not-approved/",
                datetime(2026, 8, 8, tzinfo=timezone.utc),
                env,
            )

    def test_success_executes_exactly_seven_http_transports_and_never_retains_token(self) -> None:
        calls: list[tuple[str, str]] = []

        def transport(bucket: str, prefix: str, timeout_seconds: float, maximum_body_bytes: int):
            calls.append((bucket, prefix))
            return 200, {"x-amz-request-charged": "requester"}, list_xml(bucket, prefix)

        output = ROOT / ".tmp-r0-success.json"
        try:
            result = collector.execute_canary(
                output,
                transport=transport,
                monotonic=FakeClock(),
                now=lambda: "2026-08-08T10:00:00Z",
            )
            self.assertEqual(result["terminal_status"], "R0_METADATA_CANARY_PASS")
            self.assertEqual(result["request_attempt_count"], 7)
            self.assertEqual(result["s3_http_request_count"], 7)
            self.assertEqual(result["successful_request_count"], 7)
            self.assertEqual(result["failed_request_count"], 0)
            self.assertEqual(result["total_entries"], 7)
            self.assertEqual(result["retries_used"], 0)
            self.assertFalse(result["pagination_followed"])
            self.assertFalse(result["http_redirects_followed"])
            self.assertEqual(len(calls), 7)
            self.assertEqual(
                calls,
                [(bucket, prefix) for _, bucket, prefix in collector.EXPECTED_DATASETS],
            )
            serialized = output.read_text(encoding="utf-8")
            self.assertNotIn("DO-NOT-RETAIN", serialized)
            self.assertTrue(all(row["next_continuation_token_present"] for row in result["observations"]))
            self.assertTrue(all(row["request_charged"] == "requester" for row in result["observations"]))
        finally:
            output.unlink(missing_ok=True)

    def test_one_access_denied_family_is_failure_without_retry(self) -> None:
        calls: list[tuple[str, str]] = []

        def transport(bucket: str, prefix: str, timeout_seconds: float, maximum_body_bytes: int):
            calls.append((bucket, prefix))
            if len(calls) == 3:
                return 403, {}, b"<Error><Code>AccessDenied</Code><Message>Denied</Message></Error>"
            return 200, {"x-amz-request-charged": "requester"}, list_xml(bucket, prefix, truncated=False, token=None, entries=0)

        output = ROOT / ".tmp-r0-fail.json"
        try:
            result = collector.execute_canary(
                output,
                transport=transport,
                monotonic=FakeClock(),
                now=lambda: "2026-08-08T10:00:00Z",
            )
            self.assertEqual(result["terminal_status"], "R0_METADATA_CANARY_FAIL")
            self.assertEqual(result["request_attempt_count"], 7)
            self.assertEqual(result["s3_http_request_count"], 7)
            self.assertEqual(result["successful_request_count"], 6)
            self.assertEqual(result["failed_request_count"], 1)
            self.assertEqual(len(calls), 7)
            self.assertEqual(result["observations"][2]["http_or_sdk_status_class"], "S3_AccessDenied")
        finally:
            output.unlink(missing_ok=True)

    def test_redirect_is_failure_and_is_not_followed(self) -> None:
        calls: list[tuple[str, str]] = []

        def transport(bucket: str, prefix: str, timeout_seconds: float, maximum_body_bytes: int):
            calls.append((bucket, prefix))
            return 301, {"location": "https://different-region.invalid/"}, b"<Error><Code>PermanentRedirect</Code></Error>"

        output = ROOT / ".tmp-r0-redirect.json"
        try:
            result = collector.execute_canary(
                output,
                transport=transport,
                monotonic=FakeClock(),
                now=lambda: "2026-08-08T10:00:00Z",
            )
            self.assertEqual(len(calls), 7)
            self.assertEqual(result["s3_http_request_count"], 7)
            self.assertFalse(result["http_redirects_followed"])
            self.assertTrue(all(row["http_or_sdk_status_class"] == "S3_PermanentRedirect" for row in result["observations"]))
        finally:
            output.unlink(missing_ok=True)

    def test_success_without_request_charged_header_fails_closed(self) -> None:
        calls = 0

        def transport(bucket: str, prefix: str, timeout_seconds: float, maximum_body_bytes: int):
            nonlocal calls
            calls += 1
            return 200, {}, list_xml(bucket, prefix, truncated=False, token=None, entries=0)

        output = ROOT / ".tmp-r0-charged.json"
        try:
            result = collector.execute_canary(output, transport=transport, monotonic=FakeClock(), now=lambda: "2026-08-08T10:00:00Z")
            self.assertEqual(calls, 1)
            self.assertEqual(result["terminal_status"], "R0_METADATA_CANARY_FAIL")
            self.assertEqual(result["s3_http_request_count"], 1)
            self.assertEqual(result["observations"][0]["http_or_sdk_status_class"], "INVALID_SUCCESS_RESPONSE")
        finally:
            output.unlink(missing_ok=True)

    def test_source_uses_direct_https_and_has_no_aws_cli_or_redirect_client(self) -> None:
        source = COLLECTOR_PATH.read_text(encoding="utf-8")
        self.assertIn("http.client.HTTPSConnection", source)
        self.assertIn('connection.request("GET"', source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("urllib.request", source)
        self.assertNotIn("boto3", source)
        self.assertNotIn("botocore", source)
        self.assertNotIn('"aws"', source)
        self.assertNotIn("continuation-token", source.lower())
        for literal in (
            "GetObject",
            "HeadObject",
            "GetObjectAttributes",
            "ListObjectVersions",
            "ListAllMyBuckets",
            "PutObject",
            "DeleteObject",
            "RestoreObject",
        ):
            self.assertNotIn(literal, source)


if __name__ == "__main__":
    unittest.main()
