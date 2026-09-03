"""Tests for the defects the code review of src/copyability surfaced.

Each test pins the behaviour that was wrong before: latency-dependent fill
sets, silent zero funding, stale prices treated as live, an assumed depth
printed as a fact, a whole study aborted by one wallet, and the scored
wallet's own fills pricing its own copies.
"""

from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from src.copyability.classify import profile_wallet
from src.copyability.costs import CostModel, FeeSchedule
from src.copyability.coverage import CoverageLedger, ObservedInterval
from src.copyability.execution import FollowerConfig, simulate_follower, source_pnl
from src.copyability.metrics import as_row, outcome_for
from src.copyability.inputs import (
    FundingEvent,
    FundingSchedule,
    InputError,
    LiquidityProfile,
    MarketData,
    PriceSeries,
    SourceFill,
)
from src.copyability.pit import PointInTimeView
from src.copyability.simulate import StudyConfig, run_study

D = Decimal
W = "0x" + "ab" * 20
OTHER = "0x" + "cd" * 20
MODEL = CostModel(FeeSchedule(D("4.5"), D("1.5")))
CONFIG = FollowerConfig(capital=D("10000"), size_scale=D("1"))
LIQ = {"BTC": LiquidityProfile("BTC", D("1"), D("1000000"), D("10"))}
HOUR = 3_600_000


def fill(wallet, t, tid, side, price="100", size="1") -> SourceFill:
    return SourceFill(wallet, "BTC", t, side, D(price), D(size), D("0.05"), D("0"), tid)


def market(points, funding=()) -> MarketData:
    return MarketData(prices={"BTC": PriceSeries("BTC", points)}, funding=FundingSchedule(funding), liquidity=LIQ)


def certified(start, end, wallet=W):
    return CoverageLedger([ObservedInterval(wallet, start, end, True, "t")]).certify(wallet, start, end)


class CommonDecisionWindowTests(unittest.TestCase):
    def test_every_latency_scores_the_same_fills_under_one_cutoff(self) -> None:
        # Fills through the whole interval; the last one sits in the final 15 min.
        end = 20 * HOUR
        prices = [(t, "100") for t in range(1_000, end + 1, 60_000)]
        fills = [fill(W, 1_000 + i * HOUR, i, "B" if i % 2 == 0 else "A") for i in range(19)]
        fills.append(fill(W, end - 600_000, 99, "A"))  # ten minutes before the end
        interval = certified(1_000, end)
        cutoff = end - 900_000
        runs = {L: simulate_follower(interval, latency_ms=L, fills=fills, market=market(prices),
                                     cost_model=MODEL, config=CONFIG, decision_cutoff_ms=cutoff)
                for L in (1_000, 900_000)}
        self.assertEqual(runs[1_000].pnl.trade_count, runs[900_000].pnl.trade_count)
        self.assertEqual(runs[1_000].fills_after_cutoff, runs[900_000].fills_after_cutoff)
        self.assertEqual(runs[1_000].fills_after_cutoff, 1)
        self.assertEqual(runs[1_000].skipped_fills, 0)

    def test_the_study_sets_the_cutoff_from_the_largest_latency(self) -> None:
        end = 20 * HOUR
        prices = [(t, "100") for t in range(1_000, end + 1, 60_000)]
        rows = [fill(W, 1_000 + i * HOUR, i, "B" if i % 2 == 0 else "A") for i in range(19)]
        rows.append(fill(W, end - 600_000, 99, "A"))
        fills = {W: rows}
        ledger = CoverageLedger([ObservedInterval(W, 1_000, end, True, "t")])
        config = StudyConfig(CONFIG, MODEL, "BTC", HOUR, 600_000, 7, 2, latencies_ms=(1_000, 900_000))
        (study,) = run_study(fills_by_wallet=fills, market=market(prices), ledger=ledger, config=config,
                             funding_truncated={W: False})
        counts = {o.latency_ms: o.trade_count for o in study.outcomes}
        self.assertEqual(counts[1_000], counts[900_000])
        self.assertEqual({o.fills_after_cutoff for o in study.outcomes}, {1})


class StalePriceTests(unittest.TestCase):
    def test_price_at_treats_a_quote_older_than_the_bound_as_no_price(self) -> None:
        view = PointInTimeView(market([(1_000, "100")]), (), horizon_ms=10 * HOUR)
        self.assertIsNotNone(view.price_at("BTC", 1_000 + HOUR, max_age_ms=2 * HOUR))
        self.assertIsNone(view.price_at("BTC", 1_000 + 3 * HOUR, max_age_ms=2 * HOUR))
        self.assertIsNotNone(view.price_at("BTC", 1_000 + 3 * HOUR))  # unbounded still answers

    def test_a_copy_against_a_stale_quote_is_skipped_and_counted_as_stale(self) -> None:
        # One price at the start, then a 5-hour hole; the copy at hour 4 has only a 4-hour-old quote.
        interval = certified(1_000, 6 * HOUR)
        prices = [(1_000, "100"), (5 * HOUR + 1_000, "100")]
        fills = [fill(W, 4 * HOUR, 1, "B")]
        run = simulate_follower(interval, latency_ms=0, fills=fills, market=market(prices),
                                cost_model=MODEL, config=CONFIG, max_price_age_ms=HOUR)
        self.assertEqual(run.pnl.trade_count, 0)
        self.assertEqual(run.skipped_fills, 1)
        self.assertEqual(run.stale_price_skips, 1)
        unbounded = simulate_follower(interval, latency_ms=0, fills=fills, market=market(prices),
                                      cost_model=MODEL, config=CONFIG)
        self.assertEqual(unbounded.pnl.trade_count, 1)


class FundingCoverageTests(unittest.TestCase):
    def test_a_held_position_with_no_funding_events_is_reported_as_unpriced(self) -> None:
        interval = certified(1_000, 10 * HOUR)
        prices = [(t, "100") for t in range(1_000, 10 * HOUR + 1, 60_000)]
        fills = [fill(W, 1_000, 1, "B")]  # held to the end: hour marks 1h..10h fall inside
        run = simulate_follower(interval, latency_ms=0, fills=fills, market=market(prices),
                                cost_model=MODEL, config=CONFIG)
        self.assertEqual(run.funding_periods_expected, 10)
        self.assertEqual(run.funding_periods_priced, 0)
        self.assertEqual(run.pnl.costs.funding, D("0"))  # charged nothing, and says so

    def test_a_fully_priced_schedule_covers_every_expected_period(self) -> None:
        interval = certified(1_000, 10 * HOUR)
        prices = [(t, "100") for t in range(1_000, 10 * HOUR + 1, 60_000)]
        funding = [FundingEvent("BTC", h * HOUR, D("0.0001")) for h in range(1, 11)]
        fills = [fill(W, 1_000, 1, "B")]
        run = simulate_follower(interval, latency_ms=0, fills=fills, market=market(prices, funding),
                                cost_model=MODEL, config=CONFIG)
        self.assertEqual((run.funding_periods_expected, run.funding_periods_priced), (10, 10))
        self.assertEqual(run.pnl.costs.funding, D("100") * D("0.0001") * 10)

    def test_a_sub_hour_position_expects_only_the_boundaries_it_straddles(self) -> None:
        interval = certified(1_000, 10 * HOUR)
        prices = [(t, "100") for t in range(1_000, 10 * HOUR + 1, 60_000)]
        funding = [FundingEvent("BTC", h * HOUR, D("0.0001")) for h in range(1, 11)]
        # Open at 1:59, close at 2:01: straddles the 2:00 settlement and nothing else.
        fills = [fill(W, 2 * HOUR - 60_000, 1, "B"), fill(W, 2 * HOUR + 60_000, 2, "A")]
        run = simulate_follower(interval, latency_ms=0, fills=fills, market=market(prices, funding),
                                cost_model=MODEL, config=CONFIG)
        self.assertEqual((run.funding_periods_expected, run.funding_periods_priced), (1, 1))
        # Never more priced than expected, whatever the timestamps do.
        self.assertLessEqual(run.funding_periods_priced, run.funding_periods_expected)

    def test_the_outcome_carries_coverage_as_a_share_not_a_bound(self) -> None:
        interval = certified(1_000, 10 * HOUR)
        prices = [(t, "100") for t in range(1_000, 10 * HOUR + 1, 60_000)]
        funding = [FundingEvent("BTC", h * HOUR, D("0.0001")) for h in range(1, 4)]  # 3 of 10
        fills = [fill(W, 1_000, 1, "B")]
        run = simulate_follower(interval, latency_ms=0, fills=fills, market=market(prices, funding),
                                cost_model=MODEL, config=CONFIG)
        outcome = outcome_for(run, source_pnl(interval, fills), {}, profile=profile_wallet(interval, fills),
                              funding_truncated=False, liquidity_assumed=True)
        self.assertEqual(outcome.funding_coverage, D(3) / D(10))
        self.assertTrue(outcome.funding_incomplete)
        row = as_row(outcome)
        self.assertEqual(row["net_certainty"], "funding partly unpriced")
        self.assertNotIn("<=", str(row["net"]))


class LiquidityDisclosureTests(unittest.TestCase):
    def test_a_profile_is_assumed_unless_declared_measured(self) -> None:
        self.assertTrue(LiquidityProfile("BTC", D("1"), D("1"), D("1")).assumed)
        self.assertFalse(LiquidityProfile("BTC", D("1"), D("1"), D("1"), source="MEASURED").assumed)
        with self.assertRaises(InputError):
            LiquidityProfile("BTC", D("1"), D("1"), D("1"), source="GUESSED")


class StudyRefusalTests(unittest.TestCase):
    def test_a_wallet_missing_a_liquidity_profile_is_refused_not_fatal(self) -> None:
        end = 5 * HOUR
        prices = [(t, "100") for t in range(1_000, end + 1, 60_000)]
        eth_fill = SourceFill(OTHER, "ETH", 2 * HOUR, "B", D("10"), D("1"), D("0"), D("0"), 1)
        fills = {W: [fill(W, HOUR, 1, "B"), fill(W, 2 * HOUR, 2, "A")], OTHER: [eth_fill]}
        ledger = CoverageLedger([ObservedInterval(W, 1_000, end, True, "t"), ObservedInterval(OTHER, 1_000, end, True, "t")])
        config = StudyConfig(CONFIG, MODEL, "BTC", HOUR, 600_000, 7, 2, latencies_ms=(0,))
        studies = run_study(fills_by_wallet=fills, market=market(prices), ledger=ledger, config=config,
                            funding_truncated={W: False, OTHER: False})
        by = {s.wallet: s for s in studies}
        self.assertIsNone(by[W].refusal)
        self.assertEqual(len(by[W].outcomes), 1)
        self.assertIn("InputError", by[OTHER].refusal)
        self.assertEqual(by[OTHER].outcomes, ())

    def test_market_for_gives_each_wallet_its_own_price_series(self) -> None:
        end = 5 * HOUR
        own = market([(t, "100") for t in range(1_000, end + 1, 60_000)])
        other = market([(t, "200") for t in range(1_000, end + 1, 60_000)])
        fills = {W: [fill(W, HOUR, 1, "B")]}
        ledger = CoverageLedger([ObservedInterval(W, 1_000, end, True, "t")])
        config = StudyConfig(CONFIG, MODEL, "BTC", HOUR, 600_000, 7, 2, latencies_ms=(0,))
        (study,) = run_study(fills_by_wallet=fills, market=own, ledger=ledger, config=config,
                             funding_truncated={W: False}, market_for=lambda w: other)
        self.assertEqual(study.outcomes[0].deployed_capital, D("200"))


class OwnFillsExcludedFromPricesTests(unittest.TestCase):
    def test_the_loader_can_leave_the_scored_wallets_fills_out_of_its_prices(self) -> None:
        from src.copyability.loader import load_fill_prices
        from src.live_data.models import Fill
        from src.live_data.storage import LiveDataStore

        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        store = LiveDataStore(Path(tempdir.name) / "live.sqlite3")
        self.addCleanup(store.close)

        def row(wallet, tid, t, px):
            payload = {"coin": "BTC", "px": px, "sz": "1", "side": "B", "time": t, "startPosition": "0",
                       "dir": "Open Long", "closedPnl": "0", "hash": "0x" + "cd" * 32, "oid": tid,
                       "crossed": True, "fee": "0.05", "tid": tid, "feeToken": "USDC"}
            return Fill.parse(payload, wallet), payload

        store.write_fills([row(W, 1, 1_000, "100"), row(OTHER, 2, 2_000, "110")], source="rest", ingested_at_ms=1)
        pooled = load_fill_prices(store, ["BTC"])["BTC"]
        without = load_fill_prices(store, ["BTC"], exclude_wallet=W)["BTC"]
        self.assertEqual(len(pooled), 2)
        self.assertEqual(len(without), 1)
        self.assertIsNone(without.at_or_before(1_500))  # W's own fill no longer prices the market


if __name__ == "__main__":
    unittest.main()
