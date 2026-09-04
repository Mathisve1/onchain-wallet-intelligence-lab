"""Tests for the arm B operational-health script.

Populates a temp :class:`LiveDataStore` through its own write methods only,
the way a real ingest run would, and asserts on the health module's counts and
gap sizes -- never on a price or a return, which the health script must never
compute in the first place.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from research.wallet_copyability.live_data_collector import health
from src.live_data.models import Candle, Fill, FundingDelta
from src.live_data.storage import LiveDataStore

WALLET_A = "0x" + "aa" * 20
WALLET_B = "0x" + "bb" * 20
T0_MS = 1_700_000_000_000
FIFTEEN_MIN_MS = 900_000


def _fill(wallet: str, coin: str, trade_id: int, event_time_ms: int) -> tuple[Fill, dict]:
    fill = Fill(
        wallet_address=wallet,
        coin=coin,
        trade_id=trade_id,
        event_time_ms=event_time_ms,
        side="B",
        price=Decimal("100"),
        size=Decimal("1"),
        fee=Decimal("0.01"),
        closed_pnl=Decimal("0"),
        start_position=Decimal("0"),
        direction="Open Long",
        order_id=trade_id,
        crossed=True,
        tx_hash="0x" + "11" * 32,
        fee_token=None,
    )
    return fill, {"raw": "fill"}


def _funding(wallet: str, coin: str, event_time_ms: int) -> tuple[FundingDelta, dict]:
    delta = FundingDelta(
        wallet_address=wallet,
        coin=coin,
        event_time_ms=event_time_ms,
        usdc=Decimal("-0.1"),
        funding_rate=Decimal("0.0000125"),
        signed_size=Decimal("1"),
    )
    return delta, {"raw": "funding"}


def _candle(coin: str, open_time_ms: int, interval: str = "15m") -> tuple[Candle, dict]:
    candle = Candle(
        coin=coin,
        interval=interval,
        open_time_ms=open_time_ms,
        close_time_ms=open_time_ms + FIFTEEN_MIN_MS,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100.5"),
        volume=Decimal("10"),
        trade_count=5,
    )
    return candle, {"raw": "candle"}


class HealthTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.store = LiveDataStore(Path(self._tempdir.name) / "live.sqlite3")
        self.addCleanup(self.store.close)


class WalletHealthTests(HealthTestCase):
    def test_a_wallet_with_no_fills_since_t0_is_reported_as_such(self) -> None:
        self.store.write_fills(
            [_fill(WALLET_A, "BTC", 1, T0_MS - 1_000)], source="test", ingested_at_ms=1
        )
        rows = health.wallet_health(self.store, [WALLET_A], t0_ms=T0_MS)
        self.assertEqual(rows[0]["fills_since_t0"], 0)
        self.assertEqual(rows[0]["last_fill_ms"], T0_MS - 1_000)

    def test_fills_after_t0_are_counted(self) -> None:
        self.store.write_fills(
            [
                _fill(WALLET_A, "BTC", 1, T0_MS - 1_000),
                _fill(WALLET_A, "BTC", 2, T0_MS + 1_000),
                _fill(WALLET_A, "BTC", 3, T0_MS + 2_000),
            ],
            source="test",
            ingested_at_ms=1,
        )
        rows = health.wallet_health(self.store, [WALLET_A], t0_ms=T0_MS)
        self.assertEqual(rows[0]["fills_since_t0"], 2)
        self.assertEqual(rows[0]["last_fill_ms"], T0_MS + 2_000)

    def test_a_wallet_with_no_data_at_all_reports_nulls_and_zeros(self) -> None:
        rows = health.wallet_health(self.store, [WALLET_A], t0_ms=T0_MS)
        row = rows[0]
        self.assertIsNone(row["last_fill_ms"])
        self.assertEqual(row["fills_since_t0"], 0)
        self.assertIsNone(row["last_funding_ms"])
        self.assertEqual(row["funding_rows_since_t0"], 0)
        self.assertIsNone(row["last_sweep_ms"])
        self.assertEqual(row["sweep_failures"], 0)
        self.assertEqual(row["coverage_gap_ms"], 0)

    def test_funding_rows_since_t0_and_last_funding_ms(self) -> None:
        self.store.write_funding(
            [
                _funding(WALLET_A, "BTC", T0_MS - 500),
                _funding(WALLET_A, "BTC", T0_MS + 500),
            ],
            ingested_at_ms=1,
        )
        rows = health.wallet_health(self.store, [WALLET_A], t0_ms=T0_MS)
        self.assertEqual(rows[0]["funding_rows_since_t0"], 1)
        self.assertEqual(rows[0]["last_funding_ms"], T0_MS + 500)

    def test_a_failed_run_is_counted_as_a_sweep_failure(self) -> None:
        self.store.start_run(
            "run-failed", mode="backfill_wallet", started_at_ms=1, wallet_address=WALLET_A
        )
        self.store.finish_run(
            "run-failed",
            finished_at_ms=2,
            status="failed",
            records_seen=0,
            records_written=0,
            error_count=1,
        )
        rows = health.wallet_health(self.store, [WALLET_A], t0_ms=T0_MS)
        self.assertEqual(rows[0]["sweep_failures"], 1)

    def test_last_sweep_ms_ignores_incomplete_and_other_wallets_runs(self) -> None:
        self.store.start_run(
            "run-a", mode="sweep", started_at_ms=1, wallet_address=WALLET_A
        )
        self.store.finish_run(
            "run-a", finished_at_ms=1_000, status="completed",
            records_seen=1, records_written=1,
        )
        self.store.start_run(
            "run-b", mode="sweep", started_at_ms=1, wallet_address=WALLET_A
        )
        self.store.finish_run(
            "run-b", finished_at_ms=5_000, status="completed",
            records_seen=1, records_written=1,
        )
        self.store.start_run(
            "run-other", mode="sweep", started_at_ms=1, wallet_address=WALLET_B
        )
        self.store.finish_run(
            "run-other", finished_at_ms=999_999, status="completed",
            records_seen=1, records_written=1,
        )
        rows = health.wallet_health(self.store, [WALLET_A], t0_ms=T0_MS)
        self.assertEqual(rows[0]["last_sweep_ms"], 5_000)

    def test_coverage_gap_ms_is_the_largest_gap_between_completed_windows(self) -> None:
        self.store.start_run(
            "run-1", mode="backfill_wallet", started_at_ms=1, wallet_address=WALLET_A
        )
        self.store.finish_run(
            "run-1", finished_at_ms=2, status="completed", records_seen=1, records_written=1,
            coverage={"window": {"start_time_ms": 0, "end_time_ms": 1_000}},
        )
        self.store.start_run(
            "run-2", mode="sweep", started_at_ms=1, wallet_address=WALLET_A
        )
        self.store.finish_run(
            "run-2", finished_at_ms=2, status="completed", records_seen=1, records_written=1,
            coverage={"window": {"start_time_ms": 4_000, "end_time_ms": 5_000}},
        )
        rows = health.wallet_health(self.store, [WALLET_A], t0_ms=T0_MS)
        self.assertEqual(rows[0]["coverage_gap_ms"], 3_000)


class CoinHealthTests(HealthTestCase):
    def test_mids_gap_at_exactly_fifteen_minutes_is_not_flagged(self) -> None:
        self.store.write_mids(
            {"BTC": "100"}, {}, observed_at_ms=T0_MS + 1, ingested_at_ms=1
        )
        self.store.write_mids(
            {"BTC": "101"}, {}, observed_at_ms=T0_MS + 1 + FIFTEEN_MIN_MS, ingested_at_ms=1
        )
        rows = health.coin_health(self.store, ["BTC"], since_ms=T0_MS)
        self.assertEqual(rows[0]["mids_max_gap_ms"], FIFTEEN_MIN_MS)
        totals = health.summary([], rows, stale_after_ms=1, now_ms=T0_MS)
        self.assertEqual(totals["coins_mids_gap_over_15m"], 0)

    def test_mids_gap_one_ms_over_fifteen_minutes_is_flagged(self) -> None:
        self.store.write_mids(
            {"BTC": "100"}, {}, observed_at_ms=T0_MS + 1, ingested_at_ms=1
        )
        self.store.write_mids(
            {"BTC": "101"}, {}, observed_at_ms=T0_MS + 1 + FIFTEEN_MIN_MS + 1, ingested_at_ms=1
        )
        rows = health.coin_health(self.store, ["BTC"], since_ms=T0_MS)
        self.assertEqual(rows[0]["mids_max_gap_ms"], FIFTEEN_MIN_MS + 1)
        totals = health.summary([], rows, stale_after_ms=1, now_ms=T0_MS)
        self.assertEqual(totals["coins_mids_gap_over_15m"], 1)

    def test_mids_observed_at_or_before_since_ms_do_not_count_toward_the_gap(self) -> None:
        self.store.write_mids({"BTC": "100"}, {}, observed_at_ms=T0_MS - 5, ingested_at_ms=1)
        self.store.write_mids({"BTC": "101"}, {}, observed_at_ms=T0_MS + 1, ingested_at_ms=1)
        rows = health.coin_health(self.store, ["BTC"], since_ms=T0_MS)
        self.assertIsNone(rows[0]["mids_max_gap_ms"])
        self.assertEqual(rows[0]["mids_last_ms"], T0_MS + 1)

    def test_candle_gap_is_measured_over_open_time(self) -> None:
        self.store.write_candles(
            [
                _candle("BTC", T0_MS + 1),
                _candle("BTC", T0_MS + 1 + FIFTEEN_MIN_MS),
                _candle("BTC", T0_MS + 1 + 3 * FIFTEEN_MIN_MS),
            ],
            ingested_at_ms=1,
        )
        rows = health.coin_health(self.store, ["BTC"], since_ms=T0_MS)
        self.assertEqual(rows[0]["candle_max_gap_ms"], 2 * FIFTEEN_MIN_MS)
        self.assertEqual(rows[0]["candle_rows"], 3)
        self.assertEqual(rows[0]["candle_last_open_ms"], T0_MS + 1 + 3 * FIFTEEN_MIN_MS)
        totals = health.summary([], rows, stale_after_ms=1, now_ms=T0_MS)
        self.assertEqual(totals["coins_candle_gap_over_15m"], 1)

    def test_a_coin_with_no_mids_at_all_is_flagged(self) -> None:
        self.store.write_candles([_candle("ETH", T0_MS + 1)], ingested_at_ms=1)
        rows = health.coin_health(self.store, ["ETH"], since_ms=T0_MS)
        self.assertEqual(rows[0]["mids_rows"], 0)
        self.assertIsNone(rows[0]["mids_last_ms"])
        totals = health.summary([], rows, stale_after_ms=1, now_ms=T0_MS)
        self.assertEqual(totals["coins_no_mids"], 1)


class SummaryTests(HealthTestCase):
    def test_a_stale_sweep_is_flagged_and_a_fresh_one_is_not(self) -> None:
        self.store.start_run(
            "run-stale", mode="sweep", started_at_ms=1, wallet_address=WALLET_A
        )
        self.store.finish_run(
            "run-stale", finished_at_ms=T0_MS - 30 * FIFTEEN_MIN_MS, status="completed",
            records_seen=1, records_written=1,
        )
        self.store.start_run(
            "run-fresh", mode="sweep", started_at_ms=1, wallet_address=WALLET_B
        )
        self.store.finish_run(
            "run-fresh", finished_at_ms=T0_MS - 1, status="completed",
            records_seen=1, records_written=1,
        )
        rows = health.wallet_health(self.store, [WALLET_A, WALLET_B], t0_ms=T0_MS)
        totals = health.summary(
            rows, [], stale_after_ms=6 * 3_600_000, now_ms=T0_MS
        )
        self.assertEqual(totals["wallets_total"], 2)
        self.assertEqual(totals["wallets_stale_sweep"], 1)

    def test_a_wallet_with_a_failure_is_counted_once_regardless_of_run_count(self) -> None:
        for run_id in ("run-1", "run-2"):
            self.store.start_run(run_id, mode="sweep", started_at_ms=1, wallet_address=WALLET_A)
            self.store.finish_run(
                run_id, finished_at_ms=2, status="failed", records_seen=0, records_written=0,
            )
        rows = health.wallet_health(self.store, [WALLET_A], t0_ms=T0_MS)
        totals = health.summary(rows, [], stale_after_ms=1, now_ms=T0_MS)
        self.assertEqual(totals["wallets_with_failure"], 1)


class MainCohortFileTests(HealthTestCase):
    def test_main_reads_the_cohort_file_and_writes_the_json_report(self) -> None:
        self.store.write_fills(
            [_fill(WALLET_A, "BTC", 1, T0_MS + 1_000)], source="test", ingested_at_ms=1
        )
        self.store.write_mids({"BTC": "100"}, {}, observed_at_ms=T0_MS + 1, ingested_at_ms=1)
        self.store.close()

        cohort_path = Path(self._tempdir.name) / "cohort.json"
        cohort_path.write_text(
            json.dumps(
                {
                    "t0_ms": T0_MS,
                    "t0_utc": "2026-09-04T00:00:00Z",
                    "plan_commit": "1833f34",
                    "cohort": [WALLET_A],
                    "cohort_sha256": "deadbeef",
                    "stage_counts": {},
                    "evaluable_count": 1,
                    "hard_stop": False,
                    "attempted_count": 1,
                    "attempted_sha256": "deadbeef",
                }
            ),
            encoding="utf-8",
        )
        json_out = Path(self._tempdir.name) / "health.json"
        db_path = Path(self._tempdir.name) / "live.sqlite3"

        logged: list[str] = []
        exit_code = health.main(
            [
                "--db", str(db_path),
                "--cohort", str(cohort_path),
                "--json", str(json_out),
            ],
            log=logged.append,
        )

        self.assertEqual(exit_code, 0)
        report = json.loads(json_out.read_text(encoding="utf-8"))
        self.assertEqual(report["summary"]["wallets_total"], 1)
        self.assertEqual(report["wallets"][0]["wallet_address"], WALLET_A)
        self.assertEqual(report["coins"][0]["coin"], "BTC")
        self.assertTrue(logged, "main did not print anything")

    def test_main_derives_coins_from_cohort_fills_when_coins_flag_is_omitted(self) -> None:
        self.store.write_fills(
            [_fill(WALLET_A, "ETH", 1, T0_MS + 1_000)], source="test", ingested_at_ms=1
        )
        self.store.close()

        cohort_path = Path(self._tempdir.name) / "cohort.json"
        cohort_path.write_text(json.dumps({"t0_ms": T0_MS, "cohort": [WALLET_A]}), encoding="utf-8")
        json_out = Path(self._tempdir.name) / "health.json"
        db_path = Path(self._tempdir.name) / "live.sqlite3"

        exit_code = health.main(
            ["--db", str(db_path), "--cohort", str(cohort_path), "--json", str(json_out)],
            log=lambda *_: None,
        )
        self.assertEqual(exit_code, 0)
        report = json.loads(json_out.read_text(encoding="utf-8"))
        self.assertEqual([row["coin"] for row in report["coins"]], ["ETH"])


class NoPnlTokenTests(unittest.TestCase):
    def test_the_module_source_never_mentions_a_pnl_or_return_token(self) -> None:
        source_path = (
            Path(__file__).resolve().parents[1]
            / "research" / "wallet_copyability" / "live_data_collector" / "health.py"
        )
        forbidden = ("pnl", "return_on", "closed_pnl")
        for line_number, line in enumerate(
            source_path.read_text(encoding="utf-8").splitlines(), 1
        ):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            lowered = line.lower()
            for token in forbidden:
                with self.subTest(line=line_number, token=token):
                    self.assertNotIn(token, lowered)


if __name__ == "__main__":
    unittest.main()
