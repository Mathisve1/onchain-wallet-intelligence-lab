from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "research/archive_inventory/r10b_implementation/collector.py"
SPEC = importlib.util.spec_from_file_location("r10b_collector", COLLECTOR)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class ExplodingList(list):
    def __iter__(self):
        raise AssertionError("events iteration forbidden")

    def __len__(self):
        raise AssertionError("events length inspection forbidden")

    def __getitem__(self, item):
        raise AssertionError("events indexing forbidden")


class R10BImplementationTests(unittest.TestCase):
    def test_lexical_classes_are_exact_and_precedence_bound(self) -> None:
        cases = {
            "2025-07-27T09:00:00.123Z": "ISO8601_Z_FRACTION",
            "2025-07-27T09:00:00Z": "ISO8601_Z_SECONDS",
            "2025-07-27T09:00:00.123+02:00": "ISO8601_OFFSET_FRACTION",
            "2025-07-27T09:00:00+02:00": "ISO8601_OFFSET_SECONDS",
            "2025-07-27T09:00:00.123": "ISO8601_NAIVE_FRACTION",
            "2025-07-27T09:00:00": "ISO8601_NAIVE_SECONDS",
            "1753606800000": "DECIMAL_INTEGER_STRING",
            "not-a-time": "OTHER",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(mod.classify_lexical(value), expected)

    def test_raw_prefix_buckets_do_not_parse_or_infer_timezone(self) -> None:
        self.assertEqual(mod.prefix_bucket("2025-07-27T09:anything"), "MATCHES_PATH_DATE_HOUR_PREFIX")
        self.assertEqual(mod.prefix_bucket("2025-07-27T08:anything"), "MATCHES_PREVIOUS_DATE_HOUR_PREFIX")
        self.assertEqual(mod.prefix_bucket("2025-07-27T10:anything"), "MATCHES_NEXT_DATE_HOUR_PREFIX")
        self.assertEqual(mod.prefix_bucket("1753606800000"), "OTHER_PREFIX")

    def test_event_array_contents_are_not_inspected(self) -> None:
        summary = mod.new_summary('"5a9941a240118a57f77a4c3ee95b8430-3"', b"x")
        agg = mod.MetadataLexicalAggregator(summary)
        agg.add_block({
            "local_time": "2025-07-27T09:00:00",
            "block_time": "2025-07-27T09:00:00",
            "block_number": 1,
            "events": ExplodingList([["forbidden"]]),
        })
        out = agg.finalize()
        self.assertEqual(out["block_record_count"], 1)
        self.assertEqual(out["lexical_diagnostic_classification"], "BATCH_METADATA_LEXICALLY_PATH_HOUR_CONSISTENT")
        self.assertNotIn("event", json.dumps(out).lower())

    def test_consistent_crossing_and_unresolved_classifications(self) -> None:
        def classify(local_time: str, block_time: str) -> str:
            summary = mod.new_summary('"5a9941a240118a57f77a4c3ee95b8430-3"', b"x")
            agg = mod.MetadataLexicalAggregator(summary)
            agg.add_block({"local_time": local_time, "block_time": block_time, "block_number": 1, "events": []})
            return agg.finalize()["lexical_diagnostic_classification"]

        self.assertEqual(classify("2025-07-27T09:01:02", "2025-07-27T09:01:02"), "BATCH_METADATA_LEXICALLY_PATH_HOUR_CONSISTENT")
        self.assertEqual(classify("2025-07-27T08:59:59", "2025-07-27T09:00:00"), "BATCH_METADATA_LEXICALLY_CROSSES_PATH_HOUR")
        self.assertEqual(classify("1753606800000", "1753606800001"), "BATCH_METADATA_LEXICAL_FORMAT_UNRESOLVED")

    def test_strict_json_rejects_duplicate_keys_and_nonfinite(self) -> None:
        with self.assertRaises(mod.StrictJSONError):
            mod.strict_loads('{"local_time":"a","local_time":"b"}')
        with self.assertRaises(mod.StrictJSONError):
            mod.strict_loads('{"x":NaN}')

    def test_metadata_length_cap_fails_closed(self) -> None:
        summary = mod.new_summary('"5a9941a240118a57f77a4c3ee95b8430-3"', b"x")
        agg = mod.MetadataLexicalAggregator(summary)
        with self.assertRaises(mod.DiagnosticUnresolved):
            agg.add_block({"local_time": "x" * 129, "block_time": "y", "block_number": 1, "events": []})

    def test_signed_request_is_exact_one_object_requester_pays(self) -> None:
        host, path, headers = mod.build_signed_request(
            datetime(2026, 8, 10, 13, 0, tzinfo=timezone.utc),
            {"AWS_ACCESS_KEY_ID": "A", "AWS_SECRET_ACCESS_KEY": "S", "AWS_SESSION_TOKEN": "T"},
        )
        self.assertEqual(host, "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com")
        self.assertEqual(path, "/node_fills_by_block/hourly/20250727/9.lz4")
        self.assertEqual(headers["If-Match"], '"5a9941a240118a57f77a4c3ee95b8430-3"')
        self.assertEqual(headers["x-amz-request-payer"], "requester")

    def test_source_has_no_event_loop_or_economic_fields_or_metadata_datetime_parser(self) -> None:
        source = COLLECTOR.read_text(encoding="utf-8")
        self.assertNotIn('for pair in block["events"]', source)
        self.assertNotIn("for pair in block['events']", source)
        for token in ("closedPnl", "feeToken", "startPosition"):
            self.assertNotIn(token, source)
        self.assertNotIn("datetime.fromisoformat(", source)
        self.assertNotIn("datetime.fromtimestamp(", source)

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, "governance/validate_r10b_implementation.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10B_IMPLEMENTATION_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
