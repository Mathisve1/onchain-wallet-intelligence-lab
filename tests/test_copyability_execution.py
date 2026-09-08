from __future__ import annotations

import unittest
from decimal import Decimal

from src.copyability import baselines
from src.copyability.costs import CostModel, FeeSchedule
from src.copyability.coverage import CoverageLedger, ObservedInterval, UnknownIntervalError
from src.copyability.execution import (
    LATENCY_GRID_MS,
    FollowerConfig,
    simulate_follower,
    source_pnl,
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
from src.copyability.metrics import as_row, max_drawdown, outcome_for
from src.copyability.execution import EquityPoint
from src.copyability.pit import LookAheadError
from src.copyability.simulate import StudyConfig, run_study

D = Decimal
W = "0x" + "ab" * 20
PEER = "0x" + "cd" * 20
FEES = FeeSchedule(taker_bps=D("4.5"), maker_bps=D("1.5"))
MODEL = CostModel(FEES)
CONFIG = FollowerConfig(capital=D("10000"), size_scale=D("1"))
LIQ = {"BTC": LiquidityProfile("BTC", D("1"), D("1000000"), D("10"))}


def fill(wallet, t, tid, side, price, size="1", closed_pnl="0", fee="0.05") -> SourceFill:
    return SourceFill(wallet, "BTC", t, side, D(price), D(size), D(fee), D(closed_pnl), tid)


def market(points, funding=()) -> MarketData:
    return MarketData(
        prices={"BTC": PriceSeries("BTC", points)}, funding=FundingSchedule(funding), liquidity=LIQ
    )


def certified(wallet=W, start=1_000, end=100_000):
    return CoverageLedger([ObservedInterval(wallet, start, end, True, "test")]).certify(wallet, start, end)


# A flat price path so gross is zero and every number left is a cost, then a
# rising path so a long earns exactly what the arithmetic says.
FLAT = [(t, "100") for t in range(1_000, 100_001, 1_000)]
RISING = [(t, str(100 + (t - 1_000) // 1_000)) for t in range(1_000, 100_001, 1_000)]


class SimulatorRefusesUnknownIntervalsTests(unittest.TestCase):
    def test_a_plain_tuple_or_hand_built_interval_is_refused(self) -> None:
        with self.assertRaises(UnknownIntervalError):
            simulate_follower((1_000, 100_000), latency_ms=0, fills=(), market=market(FLAT),  # type: ignore[arg-type]
                              cost_model=MODEL, config=CONFIG)

    def test_the_study_refuses_a_wallet_with_a_gap_instead_of_scoring_zero(self) -> None:
        ledger = CoverageLedger([
            ObservedInterval(W, 1_000, 50_000, True, "a"),
            ObservedInterval(W, 50_001, 100_000, True, "b"),
        ])
        fills = {W: [fill(W, 60_000, 1, "B", "100")]}
        config = StudyConfig(CONFIG, MODEL, "BTC", 5_000, 1_000, 7, 2, latencies_ms=(0,))
        (study,) = run_study(fills_by_wallet=fills, market=market(FLAT), ledger=ledger,
                             config=config, funding_truncated={W: False}, window=(1_000, 100_000))
        self.assertIsNone(study.interval)
        self.assertEqual(study.outcomes, ())
        self.assertIn("not fully observed", study.refusal)

    def test_a_certified_window_scores_and_carries_both_labels(self) -> None:
        ledger = CoverageLedger([ObservedInterval(W, 1_000, 100_000, True, "a")])
        fills = {W: [fill(W, 10_000, 1, "B", "100"), fill(W, 20_000, 2, "A", "100")]}
        config = StudyConfig(CONFIG, MODEL, "BTC", 5_000, 1_000, 7, 2, latencies_ms=(0, 1_000))
        (study,) = run_study(fills_by_wallet=fills, market=market(FLAT), ledger=ledger, config=config,
                             funding_truncated={W: True})
        self.assertIsNone(study.refusal)
        self.assertEqual([o.latency_ms for o in study.outcomes], [0, 1_000])
        self.assertEqual(study.profile.classification, "INSUFFICIENT_FILLS")
        for outcome in study.outcomes:
            self.assertTrue(outcome.source_funding_truncated)
            self.assertTrue(outcome.liquidity_assumed)  # LIQ carries the default ASSUMED source
            self.assertEqual(outcome.classification, "INSUFFICIENT_FILLS")
            row = as_row(outcome)
            self.assertTrue(row["source_funding_truncated"])
            self.assertTrue(row["liquidity_assumed"])
            self.assertIn("funding", row["net_certainty"])

    def test_the_study_refuses_a_wallet_whose_funding_status_is_unknown(self) -> None:
        ledger = CoverageLedger([ObservedInterval(W, 1_000, 100_000, True, "a")])
        config = StudyConfig(CONFIG, MODEL, "BTC", 5_000, 1_000, 7, 2, latencies_ms=(0,))
        (study,) = run_study(fills_by_wallet={W: []}, market=market(FLAT), ledger=ledger, config=config,
                             funding_truncated={})
        self.assertEqual(study.outcomes, ())
        self.assertIn("funding truncation status unknown", study.refusal)

    def test_baselines_are_compared_on_the_capital_the_copy_deployed(self) -> None:
        # The copy holds 1 BTC (~100 notional) on a rising market; buy-and-hold
        # on the same 100 earns the same move, so in return space they tie
        # before costs and the versus is a small cost difference, not -4834.
        ledger = CoverageLedger([ObservedInterval(W, 1_000, 100_000, True, "a")])
        fills = {W: [fill(W, 1_000, 1, "B", "100")]}
        config = StudyConfig(CONFIG, MODEL, "BTC", 5_000, 1_000, 7, 2, latencies_ms=(0,))
        (study,) = run_study(fills_by_wallet=fills, market=market(RISING), ledger=ledger, config=config,
                             funding_truncated={W: False})
        (outcome,) = study.outcomes
        self.assertEqual(outcome.deployed_capital, D("100"))  # cost basis, not the end mark
        self.assertIsNotNone(outcome.return_on_deployed)
        self.assertIn("buy_and_hold", outcome.versus)
        self.assertLess(abs(outcome.versus["buy_and_hold"]), D("0.01"))
        self.assertEqual(outcome.versus["no_trade"], outcome.return_on_deployed)


class FollowerExecutionTests(unittest.TestCase):
    def test_a_round_trip_on_a_flat_market_loses_exactly_its_costs(self) -> None:
        fills = [fill(W, 10_000, 1, "B", "100"), fill(W, 20_000, 2, "A", "100")]
        run = simulate_follower(certified(), latency_ms=0, fills=fills, market=market(FLAT),
                                cost_model=MODEL, config=CONFIG)
        self.assertEqual(run.pnl.gross, D("0"))
        self.assertEqual(run.pnl.trade_count, 2)
        # Two taker fills of 100 notional each: fee 0.045 + spread 0.01 + slippage 10bps*(100/1e6)
        per_fill = D("100") * (D("4.5") + D("1") + D("10") * D("100") / D("1000000")) / D(10_000)
        self.assertEqual(run.pnl.costs.total, per_fill * 2)
        self.assertEqual(run.pnl.net, -per_fill * 2)
        self.assertEqual(run.traded_notional, D("200"))
        self.assertEqual(run.equity_curve[-1].equity, CONFIG.capital + run.pnl.net)

    def test_latency_moves_the_execution_price(self) -> None:
        # Source buys at t=10000 (price 109) and sells at t=20000 (price 119).
        fills = [fill(W, 10_000, 1, "B", "109"), fill(W, 20_000, 2, "A", "119")]
        instant = simulate_follower(certified(), latency_ms=0, fills=fills, market=market(RISING),
                                    cost_model=MODEL, config=CONFIG)
        late = simulate_follower(certified(), latency_ms=5_000, fills=fills, market=market(RISING),
                                 cost_model=MODEL, config=CONFIG)
        self.assertEqual(instant.pnl.gross, D("10"))  # 119 - 109 on 1 unit
        self.assertEqual(late.pnl.gross, D("10"))  # 124 - 114: the follower still catches the drift
        self.assertGreater(late.pnl.costs.total, instant.pnl.costs.total)  # bigger notional, bigger cost

    def test_a_fill_after_the_decision_cutoff_is_excluded_not_skipped(self) -> None:
        fills = [fill(W, 99_500, 1, "B", "100")]
        run = simulate_follower(certified(), latency_ms=1_000, fills=fills, market=market(FLAT),
                                cost_model=MODEL, config=CONFIG)
        # Without an explicit cutoff it is end - latency, so this fill is out.
        self.assertEqual(run.decision_cutoff_ms, 99_000)
        self.assertEqual(run.fills_after_cutoff, 1)
        self.assertEqual(run.skipped_fills, 0)
        self.assertEqual(run.pnl.trade_count, 0)
        self.assertEqual(run.pnl.net, D("0"))
        with self.assertRaises(Exception):
            simulate_follower(certified(), latency_ms=1_000, fills=fills, market=market(FLAT),
                              cost_model=MODEL, config=CONFIG, decision_cutoff_ms=99_500)

    def test_funding_accrues_on_held_notional_between_actions(self) -> None:
        funding = [FundingEvent("BTC", 15_000, D("0.001"))]  # 10 bps on 100 notional = 0.1 paid by a long
        fills = [fill(W, 10_000, 1, "B", "100"), fill(W, 20_000, 2, "A", "100")]
        run = simulate_follower(certified(), latency_ms=0, fills=fills, market=market(FLAT, funding),
                                cost_model=MODEL, config=CONFIG)
        self.assertEqual(run.pnl.costs.funding, D("0.1"))
        short = [fill(W, 10_000, 1, "A", "100"), fill(W, 20_000, 2, "B", "100")]
        run_short = simulate_follower(certified(), latency_ms=0, fills=short, market=market(FLAT, funding),
                                      cost_model=MODEL, config=CONFIG)
        self.assertEqual(run_short.pnl.costs.funding, D("-0.1"))  # a short receives it

    def test_an_open_position_is_marked_at_the_last_known_price(self) -> None:
        fills = [fill(W, 10_000, 1, "B", "109")]
        run = simulate_follower(certified(), latency_ms=0, fills=fills, market=market(RISING),
                                cost_model=MODEL, config=CONFIG)
        self.assertEqual(run.pnl.gross, D("199") - D("109"))

    def test_source_pnl_uses_only_the_wallets_own_economics(self) -> None:
        fills = [fill(W, 10_000, 1, "B", "100", closed_pnl="5", fee="1"),
                 fill(W, 20_000, 2, "A", "100", closed_pnl="7", fee="1")]
        source = source_pnl(certified(), fills)
        self.assertEqual((source.closed_pnl, source.fees_paid, source.net, source.fill_count),
                         (D("12"), D("2"), D("10"), 2))

    def test_an_injected_look_ahead_series_fails_the_simulation(self) -> None:
        class Leaky(PriceSeries):
            def at_or_before(self, time_ms):
                return PricePoint(time_ms + 1, D("100"))

        leaky = MarketData(prices={"BTC": Leaky("BTC", FLAT)}, funding=FundingSchedule(()), liquidity=LIQ)
        with self.assertRaises(LookAheadError):
            simulate_follower(certified(), latency_ms=0, fills=[fill(W, 10_000, 1, "B", "100")],
                              market=leaky, cost_model=MODEL, config=CONFIG)

    def test_the_latency_grid_is_the_preregistered_one(self) -> None:
        self.assertEqual(LATENCY_GRID_MS, (1_000, 5_000, 30_000, 120_000, 300_000, 900_000))


class BaselineTests(unittest.TestCase):
    def test_no_trade_is_exactly_zero(self) -> None:
        self.assertEqual(baselines.no_trade(certified()), D("0"))

    def test_buy_and_hold_earns_the_move_minus_two_crossings(self) -> None:
        run = baselines.buy_and_hold(certified(), coin="BTC", market=market(RISING), cost_model=MODEL, config=CONFIG)
        # capital 10000 at 100 -> 100 units; exit at 199 -> gross 9900
        self.assertEqual(run.pnl.gross, D("9900"))
        self.assertEqual(run.pnl.trade_count, 2)
        self.assertGreater(run.pnl.costs.total, 0)
        self.assertLess(run.pnl.net, run.pnl.gross)

    def test_buy_and_hold_enters_on_the_first_quote_when_prices_start_late(self) -> None:
        # Real coverage windows begin before the first observed price: the
        # backfill window opened 12 hours before the first BTC fill in L1.
        late = [(t, "100") for t in range(50_000, 100_001, 1_000)]
        run = baselines.buy_and_hold(certified(), coin="BTC", market=market(late), cost_model=MODEL, config=CONFIG)
        self.assertEqual(run.pnl.trade_count, 2)
        self.assertEqual(run.equity_curve[1].time_ms, 50_000)  # entered at the first quote, not at 1_000
        with self.assertRaises(Exception):
            baselines.buy_and_hold(certified(), coin="BTC", market=market([(200_000, "1")]), cost_model=MODEL, config=CONFIG)

    def test_momentum_is_flat_on_a_flat_market_and_long_on_a_rising_one(self) -> None:
        flat = baselines.momentum(certified(), coin="BTC", market=market(FLAT), cost_model=MODEL,
                                  config=CONFIG, lookback_ms=5_000, step_ms=1_000)
        self.assertEqual(flat.pnl.trade_count, 0)
        rising = baselines.momentum(certified(), coin="BTC", market=market(RISING), cost_model=MODEL,
                                    config=CONFIG, lookback_ms=5_000, step_ms=1_000)
        self.assertEqual(rising.pnl.trade_count, 2)  # one entry, one exit at the end
        self.assertGreater(rising.pnl.gross, 0)

    def test_matched_random_only_uses_peers_with_similar_activity_and_full_coverage(self) -> None:
        ledger = CoverageLedger([
            ObservedInterval(W, 1_000, 100_000, True, "a"),
            ObservedInterval(PEER, 1_000, 100_000, True, "b"),
            ObservedInterval("0x" + "ef" * 20, 1_000, 50_000, True, "c"),  # gap: ineligible
        ])
        pool = {
            W: [fill(W, 10_000, 1, "B", "100"), fill(W, 20_000, 2, "A", "100")],
            PEER: [fill(PEER, 30_000, 1, "B", "100"), fill(PEER, 40_000, 2, "A", "100")],
            "0x" + "ef" * 20: [fill("0x" + "ef" * 20, 30_000, 1, "B", "100"), fill("0x" + "ef" * 20, 40_000, 2, "A", "100")],
        }
        interval = ledger.certify(W, 1_000, 100_000)
        mean, chosen = baselines.matched_random(
            interval, latency_ms=0, target_fill_count=2, pool=pool, market=market(FLAT), cost_model=MODEL,
            config=CONFIG, certify=ledger.certify, seed=1, sample_size=5,
        )
        self.assertEqual(chosen, (PEER,))
        self.assertLess(mean, 0)  # flat market: a peer round trip costs money too

    def test_matched_random_reports_none_rather_than_zero_when_no_peer_exists(self) -> None:
        ledger = CoverageLedger([ObservedInterval(W, 1_000, 100_000, True, "a")])
        interval = ledger.certify(W, 1_000, 100_000)
        mean, chosen = baselines.matched_random(
            interval, latency_ms=0, target_fill_count=2, pool={W: []}, market=market(FLAT), cost_model=MODEL,
            config=CONFIG, certify=ledger.certify, seed=1, sample_size=5,
        )
        self.assertIsNone(mean)
        self.assertEqual(chosen, ())


class MetricsTests(unittest.TestCase):
    def test_max_drawdown_finds_the_deepest_peak_to_trough(self) -> None:
        curve = [EquityPoint(1, D("100")), EquityPoint(2, D("120")), EquityPoint(3, D("90")),
                 EquityPoint(4, D("130")), EquityPoint(5, D("125"))]
        dd = max_drawdown(curve)
        self.assertEqual(dd.absolute, D("30"))
        self.assertEqual(dd.fraction_of_peak, D("30") / D("120"))
        self.assertEqual((dd.peak_time_ms, dd.trough_time_ms), (2, 3))

    def test_an_outcome_reports_return_versus_every_baseline_on_equal_capital(self) -> None:
        from src.copyability.classify import profile_wallet

        fills = [fill(W, 10_000, 1, "B", "100"), fill(W, 20_000, 2, "A", "100")]
        run = simulate_follower(certified(), latency_ms=0, fills=fills, market=market(FLAT),
                                cost_model=MODEL, config=CONFIG)
        profile = profile_wallet(certified(), fills)
        outcome = outcome_for(
            run, source_pnl(certified(), fills), {"no_trade": D("0"), "buy_and_hold": D("-0.01")},
            profile=profile, funding_truncated=False, liquidity_assumed=True,
        )
        self.assertTrue(outcome.liquidity_assumed)
        self.assertTrue(as_row(outcome)["liquidity_assumed"])
        self.assertEqual(outcome.deployed_capital, D("100"))
        self.assertEqual(outcome.return_on_deployed, outcome.net / D("100"))
        self.assertEqual(outcome.versus["no_trade"], outcome.return_on_deployed)
        self.assertEqual(outcome.versus["buy_and_hold"], outcome.return_on_deployed + D("0.01"))
        self.assertEqual(outcome.turnover, D("200") / D("100"))
        self.assertEqual(outcome.net_per_trade, outcome.net / 2)
        self.assertFalse(outcome.source_funding_truncated)
        row = as_row(outcome)
        self.assertEqual(row["trade_count"], 2)
        self.assertIn("versus_buy_and_hold", row)
        self.assertEqual(row["cost_total"], str(outcome.cost_total.quantize(D("0.0001"))))
        self.assertEqual(row["net"], str(outcome.net.quantize(D("0.0001"))))

    def test_a_copy_that_deployed_nothing_has_no_return_and_no_comparison(self) -> None:
        from src.copyability.classify import profile_wallet

        run = simulate_follower(certified(), latency_ms=0, fills=[], market=market(FLAT),
                                cost_model=MODEL, config=CONFIG)
        outcome = outcome_for(run, source_pnl(certified(), []), {"no_trade": D("0")},
                              profile=profile_wallet(certified(), []), funding_truncated=False,
                              liquidity_assumed=True)
        self.assertIsNone(outcome.funding_coverage)  # nothing held, nothing to price
        self.assertFalse(outcome.funding_incomplete)
        self.assertEqual(outcome.deployed_capital, D("0"))
        self.assertIsNone(outcome.return_on_deployed)
        self.assertIsNone(outcome.turnover)
        self.assertEqual(outcome.versus, {})
        self.assertEqual(outcome.baseline_returns, {})


if __name__ == "__main__":
    unittest.main()
