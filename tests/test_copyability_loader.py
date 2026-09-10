from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from src.copyability.coverage import UnknownIntervalError
from src.copyability.loader import (
    coverage_snapshot,
    load_coverage,
    load_fill_prices,
    load_fills,
    load_funding_rates,
    load_trade_prices,
)
from src.live_data.models import ClearinghouseState, Fill, FundingDelta
from src.live_data.storage import (
    COVERAGE_FILLS_BOUND_RULE,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    LiveDataStore,
)
from src.live_data.trades import Trade

W = "0x" + "ab" * 20
GAPPED = "0x" + "cd" * 20
TRUNCATED = "0x" + "ef" * 20
FAILED = "0x" + "12" * 20
D = Decimal


def fill_row(wallet: str, tid: int, t: int, price: str = "100", coin: str = "BTC") -> tuple[Fill, dict]:
    payload = {
        "coin": coin, "px": price, "sz": "1", "side": "B", "time": t, "startPosition": "0",
        "dir": "Open Long", "closedPnl": "0.5", "hash": "0x" + "cd" * 32, "oid": tid, "crossed": True,
        "fee": "0.05", "tid": tid, "feeToken": "USDC",
    }
    return Fill.parse(payload, wallet), payload


def funding_row(wallet: str, t: int, rate: str = "0.0001") -> tuple[FundingDelta, dict]:
    payload = {"time": t, "delta": {"type": "funding", "coin": "BTC", "usdc": "-0.1", "szi": "1", "fundingRate": rate}}
    (delta,) = __import__("src.live_data.models", fromlist=["parse_funding"]).parse_funding([payload], wallet)
    return delta, payload


def trade_row(tid: int, t: int, price: str) -> tuple[Trade, dict]:
    payload = {"coin": "BTC", "side": "B", "px": price, "sz": "1", "hash": "0x" + "1" * 64, "time": t,
               "tid": tid, "users": [W, GAPPED]}
    return Trade.parse(payload), payload


def clearinghouse(wallet: str, t: int) -> tuple[ClearinghouseState, dict]:
    summary = {"accountValue": "100", "totalNtlPos": "0", "totalRawUsd": "100", "totalMarginUsed": "0"}
    payload = {"marginSummary": summary, "crossMarginSummary": summary, "crossMaintenanceMarginUsed": "0",
               "withdrawable": "100", "assetPositions": [], "time": t}
    return ClearinghouseState.parse(payload, wallet), payload


def finish(store: LiveDataStore, run_id: str, *, mode: str, wallet: str | None, start: int, end: int,
           status: str = RUN_STATUS_COMPLETED, coverage: dict) -> None:
    store.start_run(run_id, mode=mode, started_at_ms=start, wallet_address=wallet)
    store.finish_run(run_id, finished_at_ms=end, status=status, records_seen=0, records_written=0, coverage=coverage)


def backfill_coverage(start: int, end: int, *, completed: bool, covered_until: int | None = None) -> dict:
    return {
        "window": {"start_time_ms": start, "end_time_ms": end, "days": 7},
        "fills": {"attempted": True, "completed": completed, "truncated_at_page_cap": not completed,
                  "covered_until_ms": covered_until if covered_until is not None else end},
        "funding": {"attempted": True, "completed": True},
        "positions": {"attempted": True, "completed": True},
    }


class LoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self.store = LiveDataStore(Path(tempdir.name) / "live.sqlite3")
        self.addCleanup(self.store.close)
        s = self.store
        # W: one complete backfill, then a watch that starts after a gap.
        finish(s, "bf-w", mode="backfill_wallet", wallet=W, start=1_000, end=1_100, coverage=backfill_coverage(1_000, 1_100, completed=True))
        # GAPPED: two backfills with a 1 ms hole between them.
        finish(s, "bf-g1", mode="backfill_wallet", wallet=GAPPED, start=1_000, end=1_050, coverage=backfill_coverage(1_000, 1_050, completed=True))
        finish(s, "bf-g2", mode="backfill_wallet", wallet=GAPPED, start=1_052, end=1_100, coverage=backfill_coverage(1_052, 1_100, completed=True))
        # TRUNCATED: page cap hit; covered only to 1_080.
        finish(s, "bf-t", mode="backfill_wallet", wallet=TRUNCATED, start=1_000, end=1_100, coverage=backfill_coverage(1_000, 1_100, completed=False, covered_until=1_080))
        # FAILED: contributes nothing even though it wrote some fills.
        finish(s, "bf-f", mode="backfill_wallet", wallet=FAILED, start=1_000, end=1_100, status=RUN_STATUS_FAILED, coverage={"fills": {"attempted": True, "completed": False}})
        # A watch from 1_200 to 1_300 that tracked W (and only W). GAPPED's
        # backfill snapshot lands inside the same span and must not count.
        s.write_position_snapshot(*clearinghouse(W, 1_250), ingested_at_ms=1_250)
        s.write_position_snapshot(*clearinghouse(GAPPED, 1_260), ingested_at_ms=1_260)
        finish(s, "watch-1", mode="watch", wallet=None, start=1_200, end=1_300,
               coverage={"fills": {"attempted": True}, "positions": {"tracked_wallets": [W]}, "connection": {"reconnects": 0}})
        # A watch that reconnected: its span has untimed holes and certifies nothing.
        finish(s, "watch-2", mode="watch", wallet=None, start=1_400, end=1_500,
               coverage={"fills": {"attempted": True}, "positions": {"tracked_wallets": [W]}, "connection": {"reconnects": 2}})

        s.write_fills([fill_row(W, 1, 1_010, "100"), fill_row(W, 2, 1_020, "110")], source="rest", ingested_at_ms=1)
        s.write_fills([fill_row(FAILED, 3, 1_030, "120")], source="rest", ingested_at_ms=1)
        s.write_fills([fill_row(W, 4, 1_020, "111"), fill_row(W, 5, 1_040, "130", coin="ETH")], source="rest", ingested_at_ms=1)
        s.write_trades([trade_row(1, 1_210, "200"), trade_row(2, 1_210, "201"), trade_row(3, 1_220, "202")], ingested_at_ms=1)
        s.write_funding([funding_row(W, 1_015, "0.0001"), funding_row(FAILED, 1_015, "0.0001"), funding_row(W, 1_025, "0.0002")], ingested_at_ms=1)

    def test_coverage_merges_touching_runs_and_keeps_gaps(self) -> None:
        ledger = load_coverage(self.store)
        # gap 1_100..1_200 kept; the reconnected watch-2 span is not credited
        self.assertEqual(ledger.covered(W), [(1_000, 1_100), (1_200, 1_300)])
        # GAPPED's snapshot inside watch-1 does not buy it watch coverage
        self.assertEqual(ledger.covered(GAPPED), [(1_000, 1_050), (1_052, 1_100)])
        self.assertFalse(ledger.is_fully_known(GAPPED, 1_000, 1_100))

    def test_a_truncated_backfill_certifies_its_prefix_and_a_failed_run_nothing(self) -> None:
        ledger = load_coverage(self.store)
        # Every fill up to covered_until_ms was collected; that prefix is known.
        self.assertEqual(ledger.covered(TRUNCATED), [(1_000, 1_080)])
        self.assertTrue(ledger.is_fully_known(TRUNCATED, 1_000, 1_080))
        self.assertFalse(ledger.is_fully_known(TRUNCATED, 1_000, 1_081))
        self.assertEqual(ledger.covered(FAILED), [])
        with self.assertRaises(UnknownIntervalError):
            ledger.certify(FAILED, 1_000, 1_100)

    def test_the_ledger_can_be_bounded_by_mode_and_by_when_a_run_finished(self) -> None:
        # A study whose window closed at an instant reads only the rows that
        # had finished by then, so a rerun after later collection reads the
        # same ledger; the snapshot says which rows those were.
        late = "0x" + "77" * 20
        finish(self.store, "late-backfill", mode="backfill_wallet", wallet=late, start=9_000, end=9_100,
               coverage=backfill_coverage(1_000, 1_100, completed=True))
        self.assertIn(late, load_coverage(self.store).wallets())
        self.assertNotIn(late, load_coverage(self.store, finished_by_ms=1_500).wallets())
        bounded = coverage_snapshot(self.store, finished_by_ms=1_500)
        self.assertLessEqual(bounded["max_finished_at_ms"], 1_500)
        self.assertEqual(bounded["finished_by_ms"], 1_500)
        self.assertNotEqual(bounded["run_ids_sha256"], coverage_snapshot(self.store)["run_ids_sha256"])
        # Counting only rows that produced an interval: a snapshot of the same
        # rows hashes the same, one row more does not.
        self.assertEqual(bounded, coverage_snapshot(self.store, finished_by_ms=1_500))
        rest = coverage_snapshot(self.store, modes=("backfill_wallet", "sweep_wallet"))
        self.assertEqual(rest["modes"], ["backfill_wallet", "sweep_wallet"])
        self.assertLess(rest["runs_consulted"], coverage_snapshot(self.store)["runs_consulted"])

    def test_a_forced_cursor_advance_is_trusted_only_where_the_bound_says_it_was_applied(self) -> None:
        marked, unmarked = "0x" + "88" * 20, "0x" + "99" * 20
        for wallet, extra in ((marked, {"bound_rule": COVERAGE_FILLS_BOUND_RULE}), (unmarked, {})):
            coverage = backfill_coverage(1_000, 1_100, completed=True)
            coverage["fills"].update(forced_cursor_advances=1, covered_until_ms=1_080, **extra)
            finish(self.store, f"forced-{wallet[:6]}", mode="backfill_wallet", wallet=wallet,
                   start=1_000, end=1_100, coverage=coverage)
        ledger = load_coverage(self.store)
        # The marked row's bound already stops before the skipped millisecond.
        self.assertEqual(ledger.covered(marked), [(1_000, 1_080)])
        # The unmarked row predates that rule, so its bound over-claims and
        # proves nothing, whether or not the walk said it completed.
        self.assertEqual(ledger.covered(unmarked), [])

    def test_fills_load_per_wallet_in_time_order(self) -> None:
        fills = load_fills(self.store, [W])
        self.assertEqual(sorted(fills), [W])
        self.assertEqual([f.trade_id for f in fills[W]], [1, 2, 4, 5])
        self.assertEqual(fills[W][0].closed_pnl, D("0.5"))

    def test_fill_prices_pool_every_wallet_and_take_the_last_per_millisecond(self) -> None:
        prices = load_fill_prices(self.store, ["BTC"])
        btc = prices["BTC"]
        self.assertEqual(len(btc), 3)  # 1_010, 1_020, 1_030
        self.assertEqual(btc.at_or_before(1_020).price, D("111"))  # trade 4 beats trade 2 in the same ms
        self.assertEqual(btc.at_or_before(1_035).price, D("120"))  # the failed wallet's fill still prices the market

    def test_trade_prices_take_the_last_trade_per_millisecond(self) -> None:
        tape = load_trade_prices(self.store, ["BTC"])["BTC"]
        self.assertEqual(len(tape), 2)
        self.assertEqual(tape.at_or_before(1_210).price, D("201"))

    def test_funding_truncation_is_read_from_either_flag_or_a_full_response(self) -> None:
        from src.copyability.loader import load_funding_truncation

        s = self.store
        # A record that predates the flag but received exactly the cap.
        finish(s, "bf-old", mode="backfill_wallet", wallet="0x" + "34" * 20, start=1, end=2,
               coverage={"window": {"start_time_ms": 1, "end_time_ms": 2}, "fills": {"attempted": True, "completed": True, "covered_until_ms": 2},
                         "funding": {"attempted": True, "completed": True, "seen": 500}, "positions": {"attempted": True}})
        # A record with the flag set.
        finish(s, "bf-new", mode="backfill_wallet", wallet="0x" + "56" * 20, start=1, end=2,
               coverage={"window": {"start_time_ms": 1, "end_time_ms": 2}, "fills": {"attempted": True, "completed": True, "covered_until_ms": 2},
                         "funding": {"attempted": True, "completed": False, "truncated_at_response_cap": True, "seen": 500}, "positions": {"attempted": True}})
        truncated = load_funding_truncation(s)
        self.assertTrue(truncated["0x" + "34" * 20])
        self.assertTrue(truncated["0x" + "56" * 20])
        self.assertFalse(truncated[W])  # setUp's backfill_coverage says funding completed, no count
        self.assertNotIn(FAILED, truncated)  # failed runs say nothing either way

    def test_a_fully_paged_wallet_is_not_reported_as_funding_truncated(self) -> None:
        """Regression: ``seen`` is the sum across pages now that funding pages.

        Before pagination, a ``seen`` at the response cap was the only sign of
        truncation. Afterwards any wallet with 500 or more funding rows
        collected *completely* tripped the same test, so every result it
        appeared in carried a truncation caveat it had not earned.
        """
        from src.copyability.loader import load_funding_truncation

        paged = "0x" + "78" * 20
        finish(self.store, "bf-paged", mode="backfill_wallet", wallet=paged, start=1, end=2,
               coverage={"window": {"start_time_ms": 1, "end_time_ms": 2},
                         "fills": {"attempted": True, "completed": True, "covered_until_ms": 2},
                         "funding": {"attempted": True, "completed": True,
                                     "truncated_at_response_cap": False,
                                     "seen": 1500, "pages": 3},
                         "positions": {"attempted": True}})
        self.assertFalse(load_funding_truncation(self.store)[paged])

    def test_a_sweep_that_hit_the_funding_cap_truncates_the_wallet(self) -> None:
        """A sweep_wallet row is read like a backfill: its funding cap counts."""
        from src.copyability.loader import load_funding_truncation

        swept = "0x" + "9a" * 20
        finish(self.store, "sw-1", mode="sweep_wallet", wallet=swept, start=1, end=2,
               coverage={"window": {"start_time_ms": 1, "end_time_ms": 2},
                         "fills": {"attempted": True, "completed": True, "covered_until_ms": 2},
                         "funding": {"attempted": True, "completed": False,
                                     "truncated_at_response_cap": True, "seen": 500, "pages": 1}})
        self.assertTrue(load_funding_truncation(self.store)[swept])

    def test_fills_carry_the_crossed_flag(self) -> None:
        fills = load_fills(self.store, [W])
        self.assertTrue(all(f.crossed is True for f in fills[W]))

    def test_funding_rates_are_venue_facts_deduplicated_across_wallets(self) -> None:
        schedule = load_funding_rates(self.store, ["BTC"])
        events = schedule.between("BTC", 0, 2_000)
        self.assertEqual([(e.time_ms, e.rate) for e in events], [(1_015, D("0.0001")), (1_025, D("0.0002"))])


if __name__ == "__main__":
    unittest.main()
