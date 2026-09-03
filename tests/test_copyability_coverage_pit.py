from __future__ import annotations

import unittest
from decimal import Decimal

from src.copyability.coverage import (
    CoverageLedger,
    KnownInterval,
    ObservedInterval,
    UnknownIntervalError,
)
from src.copyability.inputs import (
    FundingEvent,
    FundingSchedule,
    LiquidityProfile,
    MarketData,
    PricePoint,
    PriceSeries,
    SourceFill,
)
from src.copyability.pit import LookAheadError, PointInTimeView, assert_point_in_time

D = Decimal
W = "0x" + "ab" * 20


def fill(t: int, tid: int, side: str = "B", price: str = "100", size: str = "1") -> SourceFill:
    return SourceFill(W, "BTC", t, side, D(price), D(size), D("0.01"), D("0"), tid)


def market(points, funding=()) -> MarketData:
    return MarketData(
        prices={"BTC": PriceSeries("BTC", points)},
        funding=FundingSchedule(funding),
        liquidity={"BTC": LiquidityProfile("BTC", D("1"), D("1000000"), D("10"))},
    )


class CoverageLedgerTests(unittest.TestCase):
    def test_a_known_interval_cannot_be_built_by_hand(self) -> None:
        with self.assertRaises(UnknownIntervalError):
            KnownInterval(W, 1, 2, certified_by=object())
        with self.assertRaises(UnknownIntervalError):
            KnownInterval(W, 1, 2, certified_by=None)

    def test_the_ledger_certifies_only_fully_covered_queries(self) -> None:
        ledger = CoverageLedger([ObservedInterval(W, 100, 200, True, "backfill:a")])
        self.assertTrue(ledger.is_fully_known(W, 100, 200))
        self.assertTrue(ledger.is_fully_known(W, 120, 180))
        self.assertFalse(ledger.is_fully_known(W, 90, 150))
        self.assertFalse(ledger.is_fully_known(W, 150, 201))
        self.assertIsInstance(ledger.certify(W, 120, 180), KnownInterval)
        with self.assertRaises(UnknownIntervalError):
            ledger.certify(W, 150, 201)

    def test_a_gap_between_two_runs_is_a_gap_however_small(self) -> None:
        ledger = CoverageLedger([
            ObservedInterval(W, 100, 200, True, "a"),
            ObservedInterval(W, 201, 300, True, "b"),  # 1 ms nobody observed
        ])
        self.assertTrue(ledger.is_fully_known(W, 100, 200))
        self.assertTrue(ledger.is_fully_known(W, 201, 300))
        self.assertFalse(ledger.is_fully_known(W, 100, 300))
        self.assertEqual(ledger.covered(W), [(100, 200), (201, 300)])

    def test_touching_runs_merge_into_one_interval(self) -> None:
        ledger = CoverageLedger([
            ObservedInterval(W, 100, 200, True, "a"),
            ObservedInterval(W, 200, 300, True, "b"),
        ])
        self.assertTrue(ledger.is_fully_known(W, 100, 300))
        self.assertEqual(ledger.largest_known(W).duration_ms, 200)

    def test_an_incomplete_run_contributes_nothing(self) -> None:
        ledger = CoverageLedger([ObservedInterval(W, 100, 200, False, "truncated backfill")])
        self.assertFalse(ledger.is_fully_known(W, 100, 200))
        self.assertIsNone(ledger.largest_known(W))
        self.assertEqual(ledger.wallets(), frozenset())

    def test_coverage_is_per_wallet(self) -> None:
        other = "0x" + "cd" * 20
        ledger = CoverageLedger([ObservedInterval(other, 100, 200, True, "a")])
        self.assertFalse(ledger.is_fully_known(W, 100, 200))


class PointInTimeViewTests(unittest.TestCase):
    def test_price_lookup_never_returns_a_later_point(self) -> None:
        view = PointInTimeView(market([(100, "1"), (200, "2"), (300, "3")]), (), horizon_ms=300)
        self.assertEqual(view.price_at("BTC", 250), PricePoint(200, D("2")))
        self.assertEqual(view.price_at("BTC", 200), PricePoint(200, D("2")))
        self.assertIsNone(view.price_at("BTC", 50))

    def test_a_query_beyond_the_horizon_is_refused(self) -> None:
        view = PointInTimeView(market([(100, "1")]), (), horizon_ms=200)
        with self.assertRaises(LookAheadError):
            view.price_at("BTC", 201)
        with self.assertRaises(LookAheadError):
            view.fills_until(201)
        with self.assertRaises(LookAheadError):
            view.funding_between("BTC", 0, 201)
        with self.assertRaises(LookAheadError):
            view.narrowed(300)

    def test_an_injected_look_ahead_price_series_is_caught_at_the_boundary(self) -> None:
        class Leaky(PriceSeries):
            def at_or_before(self, time_ms: int):  # returns the future
                return PricePoint(time_ms + 1, D("999"))

        leaky = MarketData(
            prices={"BTC": Leaky("BTC", [(100, "1")])},
            funding=FundingSchedule(()),
            liquidity={"BTC": LiquidityProfile("BTC", D("1"), D("1"), D("1"))},
        )
        view = PointInTimeView(leaky, (), horizon_ms=1000)
        with self.assertRaises(LookAheadError):
            view.price_at("BTC", 500)

    def test_an_injected_look_ahead_funding_schedule_is_caught(self) -> None:
        class Leaky(FundingSchedule):
            def between(self, coin, start_ms, end_ms):
                return [FundingEvent(coin, end_ms + 1, D("0.01"))]

        leaky = MarketData(
            prices={"BTC": PriceSeries("BTC", [(100, "1")])},
            funding=Leaky(()),
            liquidity={"BTC": LiquidityProfile("BTC", D("1"), D("1"), D("1"))},
        )
        view = PointInTimeView(leaky, (), horizon_ms=1000)
        with self.assertRaises(LookAheadError):
            view.funding_between("BTC", 0, 500)

    def test_fills_until_only_returns_the_past(self) -> None:
        fills = (fill(100, 1), fill(200, 2), fill(300, 3))
        view = PointInTimeView(market([(100, "1")]), fills, horizon_ms=300)
        self.assertEqual([f.trade_id for f in view.fills_until(200)], [1, 2])


class LookAheadProbeTests(unittest.TestCase):
    """The probe must pass a correct selector and fail a peeking one."""

    AS_OF = (fill(100, 1, price="100"), fill(200, 2, price="110"))
    FUTURE = (fill(400, 3, price="10"),)

    @staticmethod
    def honest_selector(fills):
        # Eligible if the wallet traded at least twice by the horizon.
        return sum(1 for f in fills if f.time_ms <= 300) >= 2

    @staticmethod
    def peeking_selector(fills):
        # Uses every fill it is handed, including ones after the horizon:
        # mean price 105 as of the horizon, 73 once the future fill leaks in.
        return sum(f.price for f in fills) / len(fills) > 100

    def test_an_honest_selector_passes(self) -> None:
        self.assertTrue(assert_point_in_time(self.honest_selector, self.AS_OF, self.FUTURE, horizon_ms=300))

    def test_a_selector_that_peeks_fails(self) -> None:
        with self.assertRaises(LookAheadError):
            assert_point_in_time(self.peeking_selector, self.AS_OF, self.FUTURE, horizon_ms=300)

    def test_the_probe_refuses_a_vacuous_fixture(self) -> None:
        with self.assertRaises(Exception):
            assert_point_in_time(self.honest_selector, self.AS_OF, (), horizon_ms=300)
        with self.assertRaises(Exception):
            assert_point_in_time(self.honest_selector, self.AS_OF, (fill(250, 9),), horizon_ms=300)
        with self.assertRaises(Exception):
            assert_point_in_time(self.honest_selector, self.AS_OF + self.FUTURE, self.FUTURE, horizon_ms=300)


if __name__ == "__main__":
    unittest.main()
