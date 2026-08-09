from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "research/archive_inventory/r3/collector.py"
SPEC = importlib.util.spec_from_file_location("r3_collector", MODULE_PATH)
assert SPEC and SPEC.loader
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


def key(prefix: str, date: str, hour: int) -> str:
    return f"{prefix}{date}/{hour}.lz4"


def success_xml(
    bucket: str,
    prefix: str,
    keys: list[str],
    truncated: bool = False,
    token: str | None = None,
) -> bytes:
    contents = "".join(
        f"<Contents><Key>{item}</Key><LastModified>2026-08-09T00:00:00.000Z</LastModified>"
        f"<ETag>&quot;etag&quot;</ETag><Size>123</Size><StorageClass>STANDARD</StorageClass></Contents>"
        for item in keys
    )
    token_xml = f"<NextContinuationToken>{token}</NextContinuationToken>" if token is not None else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        f"<Name>{bucket}</Name><Prefix>{prefix}</Prefix><KeyCount>{len(keys)}</KeyCount>"
        f"<MaxKeys>1000</MaxKeys><IsTruncated>{str(truncated).lower()}</IsTruncated>"
        f"{contents}{token_xml}</ListBucketResult>"
    ).encode("utf-8")


def ticking_clock(step: float = 0.01):
    value = -step

    def tick() -> float:
        nonlocal value
        value += step
        return value

    return tick


class ArchiveHourlyMetadataR3CollectorTests(unittest.TestCase):
    def test_static_inputs_bind_exact_three_hourly_prefixes(self) -> None:
        rows = collector.validate_static_inputs()
        self.assertEqual(
            [(row["dataset_family_id"], row["bucket"], row["prefix"]) for row in rows],
            [
                ("node_fills_by_block", "hl-mainnet-node-data", "node_fills_by_block/hourly/"),
                ("node_fills", "hl-mainnet-node-data", "node_fills/hourly/"),
                ("node_trades", "hl-mainnet-node-data", "node_trades/hourly/"),
            ],
        )

    def test_query_uses_only_prefix_maxkeys_and_previous_continuation_token(self) -> None:
        first = collector.canonical_query("node_fills/hourly/")
        self.assertIn("list-type=2", first)
        self.assertIn("max-keys=1000", first)
        self.assertIn("prefix=node_fills%2Fhourly%2F", first)
        self.assertNotIn("continuation-token", first)
        self.assertNotIn("start-after", first)
        self.assertNotIn("delimiter", first)
        second = collector.canonical_query("node_fills/hourly/", "opaque+/=token")
        self.assertIn("continuation-token=opaque%2B%2F%3Dtoken", second)
        self.assertNotIn("start-after", second)
        self.assertNotIn("delimiter", second)

    def test_sigv4_is_regional_requester_pays_and_token_is_signed(self) -> None:
        env = {
            "AWS_ACCESS_KEY_ID": "AKIATEST",
            "AWS_SECRET_ACCESS_KEY": "secret",
            "AWS_SESSION_TOKEN": "session",
        }
        when = datetime(2026, 8, 9, 5, 0, 0, tzinfo=timezone.utc)
        host, target, headers = collector.build_signed_request(
            "hl-mainnet-node-data",
            "node_trades/hourly/",
            "opaque-token",
            when,
            env,
        )
        self.assertEqual(host, "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com")
        self.assertIn("continuation-token=opaque-token", target)
        self.assertEqual(headers["x-amz-request-payer"], "requester")
        self.assertIn("/20260809/ap-northeast-1/s3/aws4_request", headers["Authorization"])
        with self.assertRaises(collector.R3ContractError):
            collector.build_signed_request(
                "hl-mainnet-node-data",
                "explorer_blocks/",
                None,
                when,
                env,
            )

    def test_success_parser_returns_token_only_out_of_band(self) -> None:
        prefix = "node_fills/hourly/"
        body = success_xml(
            "hl-mainnet-node-data",
            prefix,
            [key(prefix, "20250525", 14), key(prefix, "20250525", 15)],
            truncated=True,
            token="SECRET_TOKEN_VALUE",
        )
        observation, count, token = collector.parse_success_xml(
            body,
            "node_fills",
            "hl-mainnet-node-data",
            prefix,
            2,
            1,
            {"x-amz-request-charged": "requester"},
            "2026-08-09T05:00:00Z",
        )
        self.assertEqual(count, 2)
        self.assertEqual(token, "SECRET_TOKEN_VALUE")
        self.assertTrue(observation["next_continuation_token_present"])
        self.assertNotIn("SECRET_TOKEN_VALUE", json.dumps(observation, sort_keys=True))
        self.assertEqual(observation["page_ordinal"], 1)
        self.assertEqual([row["entry_ordinal"] for row in observation["entries"]], [1, 2])

    def test_terminal_page_cannot_return_next_token(self) -> None:
        prefix = "node_fills/hourly/"
        body = success_xml(
            "hl-mainnet-node-data",
            prefix,
            [key(prefix, "20250525", 14)],
            truncated=False,
            token="unexpected",
        )
        with self.assertRaises(collector.R3ContractError):
            collector.parse_success_xml(
                body,
                "node_fills",
                "hl-mainnet-node-data",
                prefix,
                1,
                1,
                {"x-amz-request-charged": "requester"},
                "2026-08-09T05:00:00Z",
            )

    def test_one_terminal_page_per_family_is_complete_without_pagination(self) -> None:
        calls: list[tuple[str, str, str | None]] = []

        def transport(bucket: str, prefix: str, token: str | None, timeout: float, remaining: int):
            calls.append((bucket, prefix, token))
            return 200, {"x-amz-request-charged": "requester"}, success_xml(
                bucket, prefix, [key(prefix, "20260101", 0)], truncated=False
            )

        with tempfile.TemporaryDirectory() as td:
            result = collector.execute_inventory(
                Path(td) / "result.json",
                transport=transport,
                monotonic=ticking_clock(),
                now=lambda: "2026-08-09T05:00:00Z",
            )
        self.assertEqual(result["terminal_status"], "R3_HOURLY_METADATA_INVENTORY_PASS")
        self.assertEqual(result["technical_result"], "THREE_HOURLY_FAMILIES_COMPLETE")
        self.assertEqual(result["request_attempt_count"], 3)
        self.assertEqual(result["successful_request_count"], 3)
        self.assertEqual(result["continuation_request_count"], 0)
        self.assertFalse(result["pagination_followed"])
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(token is None for _, _, token in calls))
        self.assertTrue(all(row["family_status"] == "COMPLETE" for row in result["family_summaries"]))

    def test_two_pages_per_family_follow_only_previous_token(self) -> None:
        page_by_prefix: dict[str, int] = {}
        seen_calls: list[tuple[str, str | None]] = []

        def transport(bucket: str, prefix: str, token: str | None, timeout: float, remaining: int):
            page = page_by_prefix.get(prefix, 0) + 1
            page_by_prefix[prefix] = page
            seen_calls.append((prefix, token))
            if page == 1:
                self.assertIsNone(token)
                return 200, {"x-amz-request-charged": "requester"}, success_xml(
                    bucket,
                    prefix,
                    [key(prefix, "20260101", 0)],
                    truncated=True,
                    token=f"next-{prefix}",
                )
            self.assertEqual(token, f"next-{prefix}")
            return 200, {"x-amz-request-charged": "requester"}, success_xml(
                bucket,
                prefix,
                [key(prefix, "20260101", 1)],
                truncated=False,
            )

        with tempfile.TemporaryDirectory() as td:
            result = collector.execute_inventory(
                Path(td) / "result.json",
                transport=transport,
                monotonic=ticking_clock(),
                now=lambda: "2026-08-09T05:00:00Z",
            )
        self.assertEqual(result["request_attempt_count"], 6)
        self.assertEqual(result["continuation_request_count"], 3)
        self.assertTrue(result["pagination_followed"])
        self.assertEqual(result["technical_result"], "THREE_HOURLY_FAMILIES_COMPLETE")
        encoded = json.dumps(result, sort_keys=True)
        self.assertNotIn("next-node_", encoded)
        self.assertFalse(result["continuation_token_values_retained"])
        for observation in result["observations"]:
            self.assertNotIn("continuation_token", observation)
            self.assertNotIn("next_continuation_token", observation)
        self.assertEqual(len(seen_calls), 6)

    def test_page_16_truncation_is_censored_and_never_fetches_page_17(self) -> None:
        page_by_prefix: dict[str, int] = {}
        calls = 0

        def transport(bucket: str, prefix: str, token: str | None, timeout: float, remaining: int):
            nonlocal calls
            calls += 1
            page = page_by_prefix.get(prefix, 0) + 1
            page_by_prefix[prefix] = page
            if page > 1:
                self.assertEqual(token, f"token-{prefix}-{page - 1}")
            else:
                self.assertIsNone(token)
            return 200, {"x-amz-request-charged": "requester"}, success_xml(
                bucket,
                prefix,
                [key(prefix, f"2026{((page - 1) // 28) + 1:02d}{((page - 1) % 28) + 1:02d}", 0)],
                truncated=True,
                token=f"token-{prefix}-{page}",
            )

        with tempfile.TemporaryDirectory() as td:
            result = collector.execute_inventory(
                Path(td) / "result.json",
                transport=transport,
                monotonic=ticking_clock(),
                now=lambda: "2026-08-09T05:00:00Z",
            )
        self.assertEqual(calls, 48)
        self.assertEqual(result["request_attempt_count"], 48)
        self.assertEqual(result["successful_request_count"], 48)
        self.assertEqual(result["failed_request_count"], 0)
        self.assertEqual(result["terminal_status"], "R3_HOURLY_METADATA_INVENTORY_PASS")
        self.assertEqual(result["technical_result"], "THREE_HOURLY_FAMILIES_COMPLETE_OR_CENSORED")
        self.assertTrue(all(row["page_count"] == 16 for row in result["family_summaries"]))
        self.assertTrue(all(row["family_status"] == "CENSORED_BY_LIMIT" for row in result["family_summaries"]))
        self.assertTrue(all(row["gap_status"] == "CENSORED_BY_LIMIT" for row in result["family_summaries"]))

    def test_repeated_continuation_token_fails_before_third_request(self) -> None:
        calls = 0
        prefix = "node_fills_by_block/hourly/"

        def transport(bucket: str, observed_prefix: str, token: str | None, timeout: float, remaining: int):
            nonlocal calls
            calls += 1
            self.assertEqual(observed_prefix, prefix)
            hour = calls - 1
            return 200, {"x-amz-request-charged": "requester"}, success_xml(
                bucket,
                observed_prefix,
                [key(observed_prefix, "20260101", hour)],
                truncated=True,
                token="same-token",
            )

        with tempfile.TemporaryDirectory() as td:
            result = collector.execute_inventory(
                Path(td) / "result.json",
                transport=transport,
                monotonic=ticking_clock(),
                now=lambda: "2026-08-09T05:00:00Z",
            )
        self.assertEqual(calls, 2)
        self.assertEqual(result["request_attempt_count"], 2)
        self.assertEqual(result["terminal_status"], "R3_HOURLY_METADATA_INVENTORY_FAIL")
        self.assertEqual(result["terminal_failure_status"], "CONTINUATION_TOKEN_CYCLE")
        self.assertEqual(result["successful_request_count"], 1)
        self.assertEqual(result["failed_request_count"], 1)
        self.assertEqual(result["observations"][-1]["http_or_sdk_status_class"], "CONTINUATION_TOKEN_CYCLE")

    def test_duplicate_key_on_second_page_fails_closed(self) -> None:
        calls = 0
        prefix = "node_fills_by_block/hourly/"
        duplicate = key(prefix, "20260101", 0)

        def transport(bucket: str, observed_prefix: str, token: str | None, timeout: float, remaining: int):
            nonlocal calls
            calls += 1
            if calls == 1:
                return 200, {"x-amz-request-charged": "requester"}, success_xml(
                    bucket, observed_prefix, [duplicate], truncated=True, token="next"
                )
            return 200, {"x-amz-request-charged": "requester"}, success_xml(
                bucket, observed_prefix, [duplicate], truncated=False
            )

        with tempfile.TemporaryDirectory() as td:
            result = collector.execute_inventory(
                Path(td) / "result.json",
                transport=transport,
                monotonic=ticking_clock(),
                now=lambda: "2026-08-09T05:00:00Z",
            )
        self.assertEqual(calls, 2)
        self.assertEqual(result["terminal_status"], "R3_HOURLY_METADATA_INVENTORY_FAIL")
        self.assertEqual(result["successful_request_count"], 1)
        self.assertEqual(result["failed_request_count"], 1)
        self.assertEqual(result["observations"][-1]["http_or_sdk_status_class"], "INVALID_OR_OVERSIZE_LIST_RESPONSE")

    def test_invalid_hourly_layout_stops_after_first_request(self) -> None:
        calls = 0

        def transport(bucket: str, prefix: str, token: str | None, timeout: float, remaining: int):
            nonlocal calls
            calls += 1
            return 200, {"x-amz-request-charged": "requester"}, success_xml(
                bucket, prefix, [prefix + "20260101/24.lz4"], truncated=False
            )

        with tempfile.TemporaryDirectory() as td:
            result = collector.execute_inventory(
                Path(td) / "result.json",
                transport=transport,
                monotonic=ticking_clock(),
                now=lambda: "2026-08-09T05:00:00Z",
            )
        self.assertEqual(calls, 1)
        self.assertEqual(result["terminal_failure_status"], "UNRESOLVED_LAYOUT")
        self.assertEqual(result["family_summaries"][0]["family_status"], "UNRESOLVED_LAYOUT")
        self.assertEqual(result["observations"][-1]["http_or_sdk_status_class"], "UNRESOLVED_LAYOUT")

    def test_non_200_stops_entire_inventory_without_retry(self) -> None:
        calls = 0

        def transport(bucket: str, prefix: str, token: str | None, timeout: float, remaining: int):
            nonlocal calls
            calls += 1
            return 403, {}, b"<Error><Code>AccessDenied</Code><Message>redacted</Message></Error>"

        with tempfile.TemporaryDirectory() as td:
            result = collector.execute_inventory(
                Path(td) / "result.json",
                transport=transport,
                monotonic=ticking_clock(),
                now=lambda: "2026-08-09T05:00:00Z",
            )
        self.assertEqual(calls, 1)
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["failed_request_count"], 1)
        self.assertEqual(result["terminal_status"], "R3_HOURLY_METADATA_INVENTORY_FAIL")
        self.assertEqual(result["observations"][0]["http_or_sdk_status_class"], "S3_AccessDenied")
        self.assertEqual(result["retries_used"], 0)

    def test_complete_gap_analysis_ignores_boundaries_and_proves_internal_gap(self) -> None:
        stamps = [datetime(2026, 1, 1, 20, tzinfo=timezone.utc)]
        stamps.extend(
            datetime(2026, 1, 2, hour, tzinfo=timezone.utc)
            for hour in range(24)
            if hour != 7
        )
        stamps.append(datetime(2026, 1, 3, 2, tzinfo=timezone.utc))
        summary = collector.summarize_family(
            "node_fills",
            "node_fills/hourly/",
            "COMPLETE",
            [],
            stamps,
        )
        self.assertEqual(summary["gap_status"], "PROVEN_KEY_GAP")
        self.assertEqual(summary["missing_internal_hour_count"], 1)
        self.assertEqual(summary["missing_internal_hours_utc"], ["2026-01-02T07:00:00Z"])
        self.assertNotIn("2026-01-01T00:00:00Z", summary["missing_internal_hours_utc"])
        self.assertNotIn("2026-01-03T23:00:00Z", summary["missing_internal_hours_utc"])

    def test_transition_analysis_requires_both_fill_families_complete(self) -> None:
        summaries = [
            {
                "dataset_family_id": "node_fills",
                "family_status": "COMPLETE",
                "latest_path_hour_utc": "2025-07-27T09:00:00Z",
                "earliest_path_hour_utc": "2025-05-25T14:00:00Z",
            },
            {
                "dataset_family_id": "node_fills_by_block",
                "family_status": "COMPLETE",
                "latest_path_hour_utc": "2026-08-01T00:00:00Z",
                "earliest_path_hour_utc": "2025-07-27T10:00:00Z",
            },
        ]
        result = collector.build_transition_analysis(summaries)
        self.assertEqual(result["status"], "COMPLETE_METADATA_BOUNDARY_COMPARISON")
        self.assertEqual(result["delta_hours_modern_start_minus_legacy_end"], 1)
        self.assertEqual(result["relation"], "METADATA_CONTIGUOUS_HOURLY_BOUNDARY")
        self.assertFalse(result["schema_or_body_continuity_inferred"])
        summaries[0]["family_status"] = "CENSORED_BY_LIMIT"
        unresolved = collector.build_transition_analysis(summaries)
        self.assertEqual(unresolved["status"], "UNRESOLVED_DUE_TO_INCOMPLETE_ENUMERATION")


if __name__ == "__main__":
    unittest.main()
