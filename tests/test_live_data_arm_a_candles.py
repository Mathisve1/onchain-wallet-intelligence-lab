"""Tests for the arm A candle fetch collector script (phase 6).

No network calls: a fake orchestrator stands in for
:class:`~src.live_data.ingest.IngestOrchestrator`, and a recording ``sleep``
stands in for :func:`time.sleep`.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from research.wallet_copyability.live_data_collector.arm_a_candles import (
    FIFTEEN_MINUTE_MS,
    fetch_all,
    main,
    plan_window,
    post_check,
)


class FakeOrchestrator:
    """Records every ``fetch_candles`` call and answers from a script."""

    def __init__(self, coverage_by_coin: dict, *, raise_for: set[str] = frozenset()):
        self.calls: list[tuple[str, str, int, int]] = []
        self._coverage_by_coin = coverage_by_coin
        self._raise_for = raise_for

    def fetch_candles(self, coin: str, interval: str, start_ms: int, end_ms: int) -> dict:
        self.calls.append((coin, interval, start_ms, end_ms))
        if coin in self._raise_for:
            raise RuntimeError(f"boom for {coin}")
        return self._coverage_by_coin[coin]


class RecordingSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _coverage(coin: str, rows: int, max_gap_ms: int, *, exhausted: bool = True) -> dict:
    return {
        "coin": coin,
        "interval": "15m",
        "pages": 1,
        "rows": rows,
        "written": rows,
        "first_open_ms": 0,
        "last_open_ms": rows * FIFTEEN_MINUTE_MS,
        "max_gap_ms": max_gap_ms,
        "exhausted": exhausted,
    }


class PlanWindowTests(unittest.TestCase):
    def test_window_is_t0_minus_days_to_t0(self) -> None:
        t0_ms = 10_000 * 86_400_000
        start_ms, end_ms = plan_window(t0_ms, days=52)
        self.assertEqual(end_ms, t0_ms)
        self.assertEqual(start_ms, t0_ms - 52 * 86_400_000)

    def test_default_days_is_fifty_two(self) -> None:
        t0_ms = 10_000 * 86_400_000
        start_ms, _ = plan_window(t0_ms)
        self.assertEqual(start_ms, t0_ms - 52 * 86_400_000)


class FetchAllTests(unittest.TestCase):
    def test_requests_every_coin_in_order_with_the_planned_window(self) -> None:
        t0_ms = 200 * 86_400_000
        orchestrator = FakeOrchestrator(
            {
                "BTC": _coverage("BTC", 4992, 900_000),
                "ETH": _coverage("ETH", 4992, 900_000),
                "SOL": _coverage("SOL", 4992, 900_000),
            }
        )
        sleep = RecordingSleep()

        results = fetch_all(
            orchestrator,
            ["BTC", "ETH", "SOL"],
            t0_ms=t0_ms,
            sleep=sleep,
            log=lambda _msg: None,
        )

        start_ms, end_ms = plan_window(t0_ms, 52)
        self.assertEqual(
            orchestrator.calls,
            [
                ("BTC", "15m", start_ms, end_ms),
                ("ETH", "15m", start_ms, end_ms),
                ("SOL", "15m", start_ms, end_ms),
            ],
        )
        self.assertEqual([r["coin"] for r in results], ["BTC", "ETH", "SOL"])

    def test_pauses_between_coins_but_not_after_the_last(self) -> None:
        orchestrator = FakeOrchestrator(
            {"BTC": _coverage("BTC", 10, 900_000), "ETH": _coverage("ETH", 10, 900_000)}
        )
        sleep = RecordingSleep()

        fetch_all(
            orchestrator, ["BTC", "ETH"], t0_ms=1_000_000, pause_seconds=2.5, sleep=sleep,
            log=lambda _msg: None,
        )

        self.assertEqual(sleep.calls, [2.5])

    def test_no_pause_for_a_single_coin(self) -> None:
        orchestrator = FakeOrchestrator({"BTC": _coverage("BTC", 10, 900_000)})
        sleep = RecordingSleep()

        fetch_all(orchestrator, ["BTC"], t0_ms=1_000_000, sleep=sleep, log=lambda _msg: None)

        self.assertEqual(sleep.calls, [])

    def test_a_failing_coin_is_recorded_and_the_loop_continues(self) -> None:
        orchestrator = FakeOrchestrator(
            {"BTC": _coverage("BTC", 10, 900_000), "SOL": _coverage("SOL", 20, 900_000)},
            raise_for={"ETH"},
        )
        sleep = RecordingSleep()
        logged: list[str] = []

        results = fetch_all(
            orchestrator, ["BTC", "ETH", "SOL"], t0_ms=1_000_000, sleep=sleep, log=logged.append
        )

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["coin"], "BTC")
        self.assertEqual(results[1], {"coin": "ETH", "error": "RuntimeError: boom for ETH"})
        self.assertEqual(results[2]["coin"], "SOL")
        # BTC and SOL were still both requested: one bad coin did not abort the arm.
        self.assertEqual([c[0] for c in orchestrator.calls], ["BTC", "ETH", "SOL"])
        self.assertTrue(any("ETH" in message for message in logged))
        # Pauses still happen between every pair of coins, error or not.
        self.assertEqual(sleep.calls, [2.5, 2.5])


class PostCheckTests(unittest.TestCase):
    def test_exactly_interval_ms_gap_is_complete(self) -> None:
        results = [_coverage("BTC", 100, FIFTEEN_MINUTE_MS)]
        checked = post_check(results, interval_ms=FIFTEEN_MINUTE_MS)
        self.assertEqual(checked["out_of_scope"], [])
        self.assertTrue(checked["per_coin"][0]["complete"])
        self.assertEqual(checked["totals"]["complete"], 1)

    def test_interval_ms_plus_one_gap_is_out_of_scope(self) -> None:
        results = [_coverage("BTC", 100, FIFTEEN_MINUTE_MS + 1)]
        checked = post_check(results, interval_ms=FIFTEEN_MINUTE_MS)
        self.assertEqual(checked["out_of_scope"], ["BTC"])
        self.assertFalse(checked["per_coin"][0]["complete"])
        self.assertEqual(checked["totals"]["out_of_scope"], 1)

    def test_an_error_entry_is_out_of_scope(self) -> None:
        results = [{"coin": "ETH", "error": "RuntimeError: boom"}]
        checked = post_check(results)
        self.assertEqual(checked["out_of_scope"], ["ETH"])
        self.assertEqual(checked["per_coin"][0]["rows"], 0)
        self.assertFalse(checked["per_coin"][0]["complete"])

    def test_zero_rows_is_out_of_scope_even_without_an_error(self) -> None:
        results = [_coverage("BTC", 0, 0)]
        checked = post_check(results)
        self.assertEqual(checked["out_of_scope"], ["BTC"])

    def test_totals_sum_rows_across_coins(self) -> None:
        results = [
            _coverage("BTC", 4992, FIFTEEN_MINUTE_MS),
            _coverage("ETH", 4990, FIFTEEN_MINUTE_MS + 1),
        ]
        checked = post_check(results)
        self.assertEqual(checked["totals"]["coins"], 2)
        self.assertEqual(checked["totals"]["rows"], 4992 + 4990)
        self.assertEqual(checked["totals"]["complete"], 1)
        self.assertEqual(checked["totals"]["out_of_scope"], 1)


class MainTests(unittest.TestCase):
    def test_writes_the_expected_json_file_with_a_fake_orchestrator(self) -> None:
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "live_data.sqlite3"
            out_path = Path(tmp) / "evidence.json"
            t0_ms = 500 * 86_400_000
            orchestrator = FakeOrchestrator(
                {
                    "BTC": _coverage("BTC", 4992, FIFTEEN_MINUTE_MS),
                    "ETH": _coverage("ETH", 4000, FIFTEEN_MINUTE_MS + 1),
                }
            )
            sleep = RecordingSleep()
            logged: list[str] = []

            exit_code = main(
                [
                    "--db", str(db_path),
                    "--coins", "BTC,ETH",
                    "--t0-ms", str(t0_ms),
                    "--out", str(out_path),
                ],
                orchestrator_factory=lambda config, store: orchestrator,
                sleep=sleep,
                log=logged.append,
            )

            self.assertEqual(exit_code, 0)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            start_ms, end_ms = plan_window(t0_ms, 52)
            self.assertEqual(report["t0_ms"], t0_ms)
            self.assertEqual(report["interval"], "15m")
            self.assertEqual(report["days"], 52)
            self.assertEqual(report["window"], {"start_ms": start_ms, "end_ms": end_ms})
            self.assertEqual(report["out_of_scope"], ["ETH"])
            self.assertEqual(report["totals"]["coins"], 2)
            self.assertEqual(report["totals"]["complete"], 1)
            self.assertEqual([c["coin"] for c in report["per_coin"]], ["BTC", "ETH"])
            self.assertTrue(out_path.read_text(encoding="utf-8").endswith("\n"))
            self.assertEqual(sleep.calls, [2.5])

    def test_exit_code_is_nonzero_when_the_database_cannot_be_set_up(self) -> None:
        with TemporaryDirectory() as tmp:
            # A directory in place of the db file makes LiveDataStore's open fail.
            bad_db = Path(tmp) / "not_a_file"
            bad_db.mkdir()
            out_path = Path(tmp) / "evidence.json"

            exit_code = main(
                [
                    "--db", str(bad_db),
                    "--coins", "BTC",
                    "--t0-ms", "1000000",
                    "--out", str(out_path),
                ],
                orchestrator_factory=lambda config, store: FakeOrchestrator({}),
                sleep=lambda _seconds: None,
                log=lambda _msg: None,
            )

            self.assertNotEqual(exit_code, 0)
            self.assertFalse(out_path.exists())


if __name__ == "__main__":
    unittest.main()
