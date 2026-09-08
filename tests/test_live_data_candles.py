"""Candle request, parse, storage and paging behaviour.

The shapes here come from the L2 candle probe evidence
(``research/wallet_copyability/live_data/evidence/L2_CANDLE_PROBE_001.json``):
keys ``t T o h l c v n i s``, at most 5000 candles per response counted
backwards from ``endTime``, and a rolling retention rather than an archive.
"""

from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from src.live_data import cli
from src.live_data.hyperliquid_rest import (
    HttpRequest,
    HttpResponse,
    MAX_CANDLES_PER_RESPONSE,
    RestError,
    build_info_body,
)
from src.live_data.models import Candle, PayloadError, parse_candles
from src.live_data.schema import _CANDLES_TABLE, _SCHEMA_STATEMENTS, SCHEMA_VERSION
from src.live_data.storage import RUN_STATUS_COMPLETED, RUN_STATUS_FAILED, LiveDataStore
from src.live_data.watch import IngestError
from tests.test_live_data_ingest import IngestTestCase

FIFTEEN_MINUTES_MS = 900_000
FIRST_OPEN_MS = 1_784_015_100_000


def candle_payload(open_time_ms: int, *, coin: str = "BTC", interval: str = "15m") -> dict:
    """One candle in the venue's own key shape."""
    return {
        "t": open_time_ms,
        "T": open_time_ms + FIFTEEN_MINUTES_MS - 1,
        "s": coin,
        "i": interval,
        "o": "64000.5",
        "h": "64250.0",
        "l": "63900.25",
        "c": "64100.0",
        "v": "182.34",
        "n": 1421,
    }


def candle_page(
    count: int, *, first_open_ms: int = FIRST_OPEN_MS, coin: str = "BTC"
) -> list[dict]:
    """A page of consecutive 15-minute candles, oldest first as the venue sends them."""
    return [
        candle_payload(first_open_ms + index * FIFTEEN_MINUTES_MS, coin=coin)
        for index in range(count)
    ]


class RequestBodyTests(unittest.TestCase):
    def test_the_candle_parameters_are_nested_under_req(self) -> None:
        body = build_info_body(
            "candleSnapshot",
            coin="BTC",
            interval="15m",
            start_time=1_700_000_000_000,
            end_time=1_700_086_400_000,
        )
        self.assertEqual(
            body,
            {
                "type": "candleSnapshot",
                "req": {
                    "coin": "BTC",
                    "interval": "15m",
                    "startTime": 1_700_000_000_000,
                    "endTime": 1_700_086_400_000,
                },
            },
        )

    def test_an_unsupported_interval_is_refused(self) -> None:
        with self.assertRaises(RestError) as caught:
            build_info_body(
                "candleSnapshot", coin="BTC", interval="7m", start_time=1, end_time=2
            )
        self.assertIn("7m", str(caught.exception))

    def test_every_probed_interval_is_accepted(self) -> None:
        for interval in ("1m", "5m", "15m", "1h", "4h", "1d"):
            with self.subTest(interval=interval):
                body = build_info_body(
                    "candleSnapshot", coin="BTC", interval=interval, start_time=1, end_time=2
                )
                self.assertEqual(body["req"]["interval"], interval)

    def test_a_missing_parameter_is_refused(self) -> None:
        with self.assertRaises(RestError):
            build_info_body("candleSnapshot", coin="BTC", interval="15m", start_time=1)

    def test_an_end_time_before_the_start_is_refused(self) -> None:
        with self.assertRaises(RestError):
            build_info_body(
                "candleSnapshot", coin="BTC", interval="15m", start_time=10, end_time=9
            )

    def test_an_unknown_parameter_is_refused(self) -> None:
        with self.assertRaises(RestError):
            build_info_body(
                "candleSnapshot",
                coin="BTC",
                interval="15m",
                start_time=1,
                end_time=2,
                user="0x" + "ab" * 20,
            )


class CandleParseTests(unittest.TestCase):
    def test_a_probe_shaped_row_parses_into_typed_fields(self) -> None:
        candle = Candle.parse(candle_payload(FIRST_OPEN_MS))
        self.assertEqual(candle.coin, "BTC")
        self.assertEqual(candle.interval, "15m")
        self.assertEqual(candle.open_time_ms, FIRST_OPEN_MS)
        self.assertEqual(candle.close_time_ms, FIRST_OPEN_MS + FIFTEEN_MINUTES_MS - 1)
        self.assertEqual(candle.open, Decimal("64000.5"))
        self.assertEqual(candle.high, Decimal("64250.0"))
        self.assertEqual(candle.low, Decimal("63900.25"))
        self.assertEqual(candle.close, Decimal("64100.0"))
        self.assertEqual(candle.volume, Decimal("182.34"))
        self.assertEqual(candle.trade_count, 1421)

    def test_a_row_for_another_coin_is_refused(self) -> None:
        page = [candle_payload(FIRST_OPEN_MS), candle_payload(FIRST_OPEN_MS, coin="ETH")]
        with self.assertRaises(PayloadError) as caught:
            parse_candles(page, "BTC", "15m")
        self.assertIn("ETH", str(caught.exception))

    def test_a_row_for_another_interval_is_refused(self) -> None:
        page = [candle_payload(FIRST_OPEN_MS, interval="1h")]
        with self.assertRaises(PayloadError):
            parse_candles(page, "BTC", "15m")

    def test_a_float_price_is_refused(self) -> None:
        row = candle_payload(FIRST_OPEN_MS)
        row["c"] = 64100.0
        with self.assertRaises(PayloadError):
            Candle.parse(row)

    def test_a_close_time_before_the_open_is_refused(self) -> None:
        row = candle_payload(FIRST_OPEN_MS)
        row["T"] = FIRST_OPEN_MS - 1
        with self.assertRaises(PayloadError):
            Candle.parse(row)

    def test_a_negative_trade_count_is_refused(self) -> None:
        row = candle_payload(FIRST_OPEN_MS)
        row["n"] = -1
        with self.assertRaises(PayloadError):
            Candle.parse(row)


class CandleStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.db_path = Path(self._tempdir.name) / "live.sqlite3"
        self.store = LiveDataStore(self.db_path)
        self.addCleanup(self.store.close)

    def _rows(self, page: list[dict]) -> list[tuple[Candle, dict]]:
        return [(Candle.parse(row), row) for row in page]

    def test_the_same_candle_written_twice_yields_one_row(self) -> None:
        page = candle_page(3)
        first = self.store.write_candles(self._rows(page), ingested_at_ms=1)
        second = self.store.write_candles(self._rows(page), ingested_at_ms=2)
        self.assertEqual((first.seen, first.written), (3, 3))
        self.assertEqual((second.seen, second.written), (3, 0))
        self.assertEqual(self.store.count("candles"), 3)

    def test_the_same_open_time_at_another_interval_is_a_separate_row(self) -> None:
        self.store.write_candles(self._rows(candle_page(1)), ingested_at_ms=1)
        other = [candle_payload(FIRST_OPEN_MS, interval="1h")]
        self.store.write_candles(self._rows(other), ingested_at_ms=1)
        self.assertEqual(self.store.count("candles"), 2)

    def test_prices_are_stored_as_text_with_their_raw_payload(self) -> None:
        self.store.write_candles(self._rows(candle_page(1)), ingested_at_ms=7)
        row = self.store.connection.execute("SELECT * FROM candles").fetchone()
        self.assertEqual(row["close"], "64100.0")
        self.assertEqual(row["trade_count"], 1421)
        self.assertEqual(row["ingested_at_ms"], 7)
        self.assertEqual(json.loads(row["raw_payload"])["t"], FIRST_OPEN_MS)

    def test_a_non_candle_row_is_refused(self) -> None:
        with self.assertRaises(Exception):
            self.store.write_candles([("not a candle", {})], ingested_at_ms=1)


class CandleMigrationTests(unittest.TestCase):
    """Version 3 databases hold the L1 tape and must gain candles in place."""

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.db_path = Path(self._tempdir.name) / "v3.sqlite3"

    def _build_version_three(self) -> None:
        connection = sqlite3.connect(self.db_path)
        for statement in _SCHEMA_STATEMENTS:
            if statement == _CANDLES_TABLE:
                continue
            connection.execute(statement)
        connection.execute("INSERT INTO schema_version (version, applied_at_ms) VALUES (3, 0)")
        connection.execute(
            "INSERT INTO wallets (address, label, first_seen_at_ms, last_seen_at_ms) "
            "VALUES ('0xabc', NULL, 1, 1)"
        )
        connection.commit()
        connection.close()

    def test_a_version_three_database_migrates_in_place(self) -> None:
        self._build_version_three()
        with LiveDataStore(self.db_path) as store:
            version = store.connection.execute(
                "SELECT MAX(version) AS v FROM schema_version"
            ).fetchone()["v"]
            self.assertEqual(version, SCHEMA_VERSION)
            self.assertEqual(SCHEMA_VERSION, 4)
            self.assertEqual(store.count("candles"), 0)
            # The migration adds a table; it does not rebuild the database.
            self.assertEqual(store.count("wallets"), 1)
            store.write_candles(
                [(Candle.parse(row), row) for row in candle_page(2)], ingested_at_ms=1
            )
            self.assertEqual(store.count("candles"), 2)


class FetchCandlesTests(IngestTestCase):
    def test_a_single_short_page_ends_the_walk(self) -> None:
        orchestrator, transport = self.build([candle_page(3)])
        report = orchestrator.fetch_candles("BTC", "15m", FIRST_OPEN_MS, FIRST_OPEN_MS + 10**7)
        self.assertEqual(report["pages"], 1)
        self.assertEqual((report["rows"], report["written"]), (3, 3))
        self.assertTrue(report["exhausted"])
        self.assertEqual(report["first_open_ms"], FIRST_OPEN_MS)
        self.assertEqual(report["max_gap_ms"], FIFTEEN_MINUTES_MS)
        self.assertEqual(len(transport.bodies), 1)
        self.assertEqual(transport.bodies[0]["req"]["endTime"], FIRST_OPEN_MS + 10**7)

    def test_a_full_page_is_followed_by_a_request_ending_before_its_earliest_open(self) -> None:
        older_first_open = FIRST_OPEN_MS - 50 * FIFTEEN_MINUTES_MS
        full = candle_page(MAX_CANDLES_PER_RESPONSE)
        short = candle_page(4, first_open_ms=older_first_open)
        start_ms = older_first_open - FIFTEEN_MINUTES_MS
        end_ms = FIRST_OPEN_MS + MAX_CANDLES_PER_RESPONSE * FIFTEEN_MINUTES_MS
        orchestrator, transport = self.build([full, short])
        report = orchestrator.fetch_candles("BTC", "15m", start_ms, end_ms)

        self.assertEqual(len(transport.bodies), 2)
        self.assertEqual(transport.bodies[0]["req"]["endTime"], end_ms)
        self.assertEqual(transport.bodies[1]["req"]["endTime"], FIRST_OPEN_MS - 1)
        self.assertEqual(transport.bodies[1]["req"]["startTime"], start_ms)
        self.assertEqual(report["pages"], 2)
        self.assertEqual(report["rows"], MAX_CANDLES_PER_RESPONSE + 4)
        self.assertTrue(report["exhausted"])
        self.assertEqual(report["first_open_ms"], older_first_open)

    def test_a_full_page_reaching_the_window_start_ends_the_walk(self) -> None:
        orchestrator, transport = self.build([candle_page(MAX_CANDLES_PER_RESPONSE)])
        report = orchestrator.fetch_candles(
            "BTC",
            "15m",
            FIRST_OPEN_MS,
            FIRST_OPEN_MS + MAX_CANDLES_PER_RESPONSE * FIFTEEN_MINUTES_MS,
        )
        self.assertEqual(len(transport.bodies), 1)
        self.assertTrue(report["exhausted"])

    def test_the_page_cap_stops_a_full_page_walk_and_says_so(self) -> None:
        older_first_open = FIRST_OPEN_MS - 10_000 * FIFTEEN_MINUTES_MS
        pages = [
            candle_page(MAX_CANDLES_PER_RESPONSE),
            candle_page(MAX_CANDLES_PER_RESPONSE, first_open_ms=older_first_open),
        ]
        orchestrator, transport = self.build(pages)
        report = orchestrator.fetch_candles(
            "BTC", "15m", 1, FIRST_OPEN_MS + 10**9, max_pages=2
        )
        self.assertEqual(report["pages"], 2)
        self.assertFalse(report["exhausted"])
        self.assertEqual(len(transport.bodies), 2)

    def test_a_repeated_page_stops_the_walk_instead_of_looping(self) -> None:
        # A venue that answers every request with the same full page would
        # otherwise be paged until the page cap, re-fetching the same candles.
        page = candle_page(MAX_CANDLES_PER_RESPONSE)
        orchestrator, transport = self.build([page, page, page, page])
        report = orchestrator.fetch_candles(
            "BTC", "15m", 1, FIRST_OPEN_MS + 10**9, max_pages=4
        )
        self.assertEqual(len(transport.bodies), 2)
        self.assertEqual(report["pages"], 2)
        self.assertFalse(report["exhausted"])
        self.assertIn("no backwards progress", report["note"])
        run = self.store.recent_runs(1)[0]
        self.assertEqual(run["status"], RUN_STATUS_COMPLETED)
        self.assertIn("no backwards progress", run["notes"])

    def test_a_walk_that_made_progress_records_no_note(self) -> None:
        orchestrator, _ = self.build([candle_page(3)])
        report = orchestrator.fetch_candles("BTC", "15m", FIRST_OPEN_MS, FIRST_OPEN_MS + 10**7)
        self.assertNotIn("note", report)
        self.assertIsNone(self.store.recent_runs(1)[0]["notes"])

    def test_the_largest_gap_between_consecutive_opens_is_recorded(self) -> None:
        page = candle_page(2) + [candle_payload(FIRST_OPEN_MS + 10 * FIFTEEN_MINUTES_MS)]
        orchestrator, _ = self.build([page])
        report = orchestrator.fetch_candles("BTC", "15m", FIRST_OPEN_MS, FIRST_OPEN_MS + 10**7)
        self.assertEqual(report["max_gap_ms"], 9 * FIFTEEN_MINUTES_MS)

    def test_one_candle_has_no_gap(self) -> None:
        orchestrator, _ = self.build([candle_page(1)])
        report = orchestrator.fetch_candles("BTC", "15m", FIRST_OPEN_MS, FIRST_OPEN_MS + 10**7)
        self.assertEqual(report["max_gap_ms"], 0)
        self.assertEqual(report["first_open_ms"], report["last_open_ms"])

    def test_a_completed_run_records_the_candle_coverage(self) -> None:
        orchestrator, _ = self.build([candle_page(2)])
        orchestrator.fetch_candles("BTC", "15m", FIRST_OPEN_MS, FIRST_OPEN_MS + 10**7)
        run = self.store.recent_runs(1)[0]
        self.assertEqual(run["mode"], "fetch_candles")
        self.assertEqual(run["status"], RUN_STATUS_COMPLETED)
        coverage = json.loads(run["coverage"])
        self.assertEqual(coverage["candles"]["coin"], "BTC")
        self.assertEqual(coverage["candles"]["interval"], "15m")
        self.assertEqual(coverage["candles"]["rows"], 2)
        self.assertEqual(coverage["candles"]["written"], 2)
        self.assertTrue(coverage["candles"]["exhausted"])
        self.assertEqual(coverage["requests"]["attempted"], 1)
        self.assertIn("weight", coverage["requests"])

    def test_a_failing_transport_records_a_failed_run(self) -> None:
        orchestrator, _ = self.build([{"unexpected": "object"}])
        with self.assertRaises(Exception):
            orchestrator.fetch_candles("BTC", "15m", FIRST_OPEN_MS, FIRST_OPEN_MS + 10**7)
        run = self.store.recent_runs(1)[0]
        self.assertEqual(run["mode"], "fetch_candles")
        self.assertEqual(run["status"], RUN_STATUS_FAILED)
        self.assertEqual(run["error_count"], 1)
        self.assertEqual(json.loads(run["coverage"])["candles"]["coin"], "BTC")

    def test_a_refetched_window_writes_nothing_new(self) -> None:
        orchestrator, _ = self.build([candle_page(3), candle_page(3)])
        first = orchestrator.fetch_candles("BTC", "15m", FIRST_OPEN_MS, FIRST_OPEN_MS + 10**7)
        second = orchestrator.fetch_candles("BTC", "15m", FIRST_OPEN_MS, FIRST_OPEN_MS + 10**7)
        self.assertEqual(first["written"], 3)
        self.assertEqual((second["rows"], second["written"]), (3, 0))
        self.assertEqual(self.store.count("candles"), 3)

    def test_a_reversed_window_is_refused_before_any_request(self) -> None:
        orchestrator, transport = self.build([])
        with self.assertRaises(IngestError):
            orchestrator.fetch_candles("BTC", "15m", 10, 9)
        self.assertEqual(transport.bodies, [])

    def test_a_nonpositive_page_cap_is_refused(self) -> None:
        orchestrator, _ = self.build([])
        with self.assertRaises(IngestError):
            orchestrator.fetch_candles("BTC", "15m", 1, 2, max_pages=0)


class CandleCommandTests(unittest.TestCase):
    """The CLI walks the coins it was given once and pauses between them."""

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.db_path = Path(self._tempdir.name) / "live.sqlite3"
        self.bodies: list[dict] = []
        self.pauses: list[float] = []

    def _transport(self, request: HttpRequest) -> HttpResponse:
        body = json.loads(request.body)
        self.bodies.append(body)
        coin = body["req"]["coin"]
        return HttpResponse(status_code=200, body=json.dumps(candle_page(2, coin=coin)))

    def _run(self, argv: list[str]) -> int:
        args = cli.build_parser().parse_args(["--db", str(self.db_path), "candles"] + argv)
        return cli._cmd_candles(
            args, cli.Dependencies(transport=self._transport), sleeper=self.pauses.append
        )

    def test_each_coin_is_fetched_once_with_one_fixed_pause_between_coins(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = self._run(["--coins", "BTC,ETH", "--interval", "15m", "--days", "52"])
        self.assertEqual(code, 0)
        self.assertEqual([body["req"]["coin"] for body in self.bodies], ["BTC", "ETH"])
        self.assertEqual(self.pauses, [cli.CANDLE_REQUEST_PAUSE_SECONDS])
        self.assertEqual(cli.CANDLE_REQUEST_PAUSE_SECONDS, 2.5)
        report = json.loads(buffer.getvalue())
        self.assertEqual([entry["coin"] for entry in report["candles"]], ["BTC", "ETH"])
        with LiveDataStore(self.db_path) as store:
            self.assertEqual(store.count("candles"), 4)

    def test_an_explicit_window_overrides_the_day_count(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self._run(["--coins", "BTC", "--start-ms", "1000", "--end-ms", "2000"])
        self.assertEqual(self.bodies[0]["req"], {
            "coin": "BTC", "interval": "15m", "startTime": 1000, "endTime": 2000
        })

    def test_a_reversed_explicit_window_is_refused_before_any_request(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            code = self._run(["--coins", "BTC", "--start-ms", "2000", "--end-ms", "1000"])
        self.assertEqual(code, 2)
        self.assertEqual(self.bodies, [])

    def test_without_a_transport_the_command_refuses_rather_than_building_one(self) -> None:
        args = cli.build_parser().parse_args(
            ["--db", str(self.db_path), "candles", "--coins", "BTC"]
        )
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli._cmd_candles(args, cli.Dependencies()), 2)

    def test_an_unsupported_interval_is_refused_by_the_parser(self) -> None:
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["candles", "--coins", "BTC", "--interval", "7m"])

    def test_coins_are_taken_as_a_comma_separated_list(self) -> None:
        args = cli.build_parser().parse_args(["candles", "--coins", "BTC,ETH,SOL"])
        self.assertEqual(args.coins, ("BTC", "ETH", "SOL"))
        self.assertEqual(args.interval, "15m")
        self.assertEqual(args.days, 52)


if __name__ == "__main__":
    unittest.main()
