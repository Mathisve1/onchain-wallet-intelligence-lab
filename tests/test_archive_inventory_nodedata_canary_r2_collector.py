from __future__ import annotations

import importlib.util
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "research/archive_inventory/r2/collector.py"
SPEC = importlib.util.spec_from_file_location("r2_collector", MODULE_PATH)
assert SPEC and SPEC.loader
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


def success_xml(bucket: str, prefix: str, keys: list[str], truncated: bool = False, token: str | None = None) -> bytes:
    contents = "".join(
        f"<Contents><Key>{key}</Key><LastModified>2026-08-08T00:00:00.000Z</LastModified>"
        f"<ETag>&quot;etag&quot;</ETag><Size>123</Size><StorageClass>STANDARD</StorageClass></Contents>"
        for key in keys
    )
    token_xml = f"<NextContinuationToken>{token}</NextContinuationToken>" if token is not None else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        f"<Name>{bucket}</Name><Prefix>{prefix}</Prefix><KeyCount>{len(keys)}</KeyCount>"
        f"<MaxKeys>25</MaxKeys><IsTruncated>{str(truncated).lower()}</IsTruncated>"
        f"{contents}{token_xml}</ListBucketResult>"
    ).encode("utf-8")


class ArchiveNodeDataCanaryR2CollectorTests(unittest.TestCase):
    def test_static_inputs_bind_exact_five_prefixes(self) -> None:
        rows = collector.validate_static_inputs()
        self.assertEqual(
            [(row["dataset_family_id"], row["bucket"], row["prefix"]) for row in rows],
            [
                ("node_fills_by_block", "hl-mainnet-node-data", "node_fills_by_block/"),
                ("node_fills", "hl-mainnet-node-data", "node_fills/"),
                ("node_trades", "hl-mainnet-node-data", "node_trades/"),
                ("explorer_blocks", "hl-mainnet-node-data", "explorer_blocks/"),
                ("replica_cmds", "hl-mainnet-node-data", "replica_cmds/"),
            ],
        )

    def test_sigv4_uses_regional_endpoint_region_and_requester_pays(self) -> None:
        env = {
            "AWS_ACCESS_KEY_ID": "AKIATEST",
            "AWS_SECRET_ACCESS_KEY": "secret",
            "AWS_SESSION_TOKEN": "token",
        }
        when = datetime(2026, 8, 8, 20, 0, 0, tzinfo=timezone.utc)
        host, target, headers = collector.build_signed_request(
            "hl-mainnet-node-data",
            "node_fills/",
            when,
            env,
        )
        self.assertEqual(host, "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com")
        self.assertIn("list-type=2", target)
        self.assertIn("max-keys=25", target)
        self.assertIn("prefix=node_fills%2F", target)
        self.assertEqual(headers["x-amz-request-payer"], "requester")
        self.assertIn("/20260808/ap-northeast-1/s3/aws4_request", headers["Authorization"])
        with self.assertRaises(collector.R2ContractError):
            collector.build_signed_request("hl-mainnet-node-data", "market_data/", when, env)
        with self.assertRaises(collector.R2ContractError):
            collector.build_signed_request("hyperliquid-archive", "node_fills/", when, env)

    def test_success_parser_retains_metadata_but_not_continuation_value(self) -> None:
        body = success_xml(
            "hl-mainnet-node-data",
            "node_fills/",
            ["node_fills/0002", "node_fills/0001"],
            truncated=True,
            token="SECRET_CONTINUATION_VALUE",
        )
        observation, count = collector.parse_success_xml(
            body,
            "node_fills",
            "hl-mainnet-node-data",
            "node_fills/",
            2,
            {"x-amz-request-charged": "requester"},
            "2026-08-08T20:00:00Z",
        )
        self.assertEqual(count, 2)
        self.assertEqual(observation["signing_region"], "ap-northeast-1")
        self.assertTrue(observation["is_truncated"])
        self.assertTrue(observation["next_continuation_token_present"])
        self.assertNotIn("SECRET_CONTINUATION_VALUE", repr(observation))
        self.assertEqual([row["key"] for row in observation["entries"]], ["node_fills/0001", "node_fills/0002"])
        self.assertTrue(all(set(row) == {"key", "size_bytes", "last_modified", "etag", "storage_class"} for row in observation["entries"]))

    def test_success_parser_requires_requester_charged_on_success(self) -> None:
        body = success_xml("hl-mainnet-node-data", "node_trades/", [])
        with self.assertRaises(collector.R2ContractError):
            collector.parse_success_xml(
                body,
                "node_trades",
                "hl-mainnet-node-data",
                "node_trades/",
                3,
                {},
                "2026-08-08T20:00:00Z",
            )

    def test_execute_canary_makes_exactly_five_first_page_requests(self) -> None:
        calls: list[tuple[str, str, float, int]] = []

        def transport(bucket: str, prefix: str, timeout: float, remaining: int):
            calls.append((bucket, prefix, timeout, remaining))
            body = success_xml(bucket, prefix, [prefix + "k"])
            return 200, {"x-amz-request-charged": "requester"}, body

        ticks = iter([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
        with tempfile.TemporaryDirectory() as td:
            result = collector.execute_canary(
                Path(td) / "result.json",
                transport=transport,
                monotonic=lambda: next(ticks),
                now=lambda: "2026-08-08T20:00:00Z",
            )
        self.assertEqual(result["terminal_status"], "R2_NODEDATA_METADATA_CANARY_PASS")
        self.assertEqual(result["technical_result"], "FIVE_PREFIX_METADATA_LISTABLE")
        self.assertEqual(result["request_attempt_count"], 5)
        self.assertEqual(result["s3_http_request_count"], 5)
        self.assertEqual(result["successful_request_count"], 5)
        self.assertEqual(result["failed_request_count"], 0)
        self.assertEqual(len(calls), 5)
        self.assertEqual([prefix for _, prefix, _, _ in calls], [
            "node_fills_by_block/",
            "node_fills/",
            "node_trades/",
            "explorer_blocks/",
            "replica_cmds/",
        ])
        self.assertEqual(result["retries_used"], 0)
        self.assertFalse(result["pagination_followed"])
        self.assertFalse(result["http_redirects_followed"])
        self.assertFalse(result["continuation_token_values_retained"])
        self.assertFalse(result["object_body_requested"])
        self.assertFalse(result["decompression_used"])
        self.assertFalse(result["market_data_ingested"])
        self.assertIsNone(result["empirical_result"])

    def test_non_200_is_coarse_failure_and_never_retried(self) -> None:
        calls = 0

        def transport(bucket: str, prefix: str, timeout: float, remaining: int):
            nonlocal calls
            calls += 1
            return 403, {}, b"<Error><Code>AccessDenied</Code><Message>redacted</Message></Error>"

        ticks = iter([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
        with tempfile.TemporaryDirectory() as td:
            result = collector.execute_canary(
                Path(td) / "result.json",
                transport=transport,
                monotonic=lambda: next(ticks),
                now=lambda: "2026-08-08T20:00:00Z",
            )
        self.assertEqual(calls, 5)
        self.assertEqual(result["request_attempt_count"], 5)
        self.assertEqual(result["successful_request_count"], 0)
        self.assertEqual(result["failed_request_count"], 5)
        self.assertEqual(result["terminal_status"], "R2_NODEDATA_METADATA_CANARY_FAIL")
        self.assertTrue(all(row["http_or_sdk_status_class"] == "S3_AccessDenied" for row in result["observations"]))

    def test_response_cap_breach_fails_closed_without_extra_request(self) -> None:
        calls = 0

        def transport(bucket: str, prefix: str, timeout: float, remaining: int):
            nonlocal calls
            calls += 1
            return 200, {"x-amz-request-charged": "requester"}, b"x" * (remaining + 1)

        ticks = iter([0.0, 0.1, 0.2])
        with tempfile.TemporaryDirectory() as td:
            result = collector.execute_canary(
                Path(td) / "result.json",
                transport=transport,
                monotonic=lambda: next(ticks),
                now=lambda: "2026-08-08T20:00:00Z",
            )
        self.assertEqual(calls, 1)
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["terminal_status"], "R2_NODEDATA_METADATA_CANARY_FAIL")
        self.assertEqual(result["observations"][0]["http_or_sdk_status_class"], "RESPONSE_BYTE_CAP_EXCEEDED")


if __name__ == "__main__":
    unittest.main()
