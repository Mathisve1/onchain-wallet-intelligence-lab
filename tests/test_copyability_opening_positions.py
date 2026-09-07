"""The follower stands in the positions the source already held.

A source fill that closes a position opened before the certified window is a
real close for the follower too. Without an opening position the simulator
read that close as an open in the opposite direction and scored a trade the
wallet never made. These tests pin the catch-up entry, the cost it pays, the
position replay that produces it, and the candle price source that makes an
entry at the start of the window priceable.
"""

from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from src.copyability.costs import CostModel, FeeSchedule
from src.copyability.coverage import CoverageLedger, ObservedInterval
from src.copyability.execution import (
    FollowerConfig,
    opening_positions_for,
    simulate_follower,
    source_pnl,
)
from src.copyability.simulate import StudyConfig, run_study
from src.copyability.classify import profile_wallet
from src.copyability.inputs import (
    FundingEvent,
    FundingSchedule,
    LiquidityProfile,
    MarketData,
    PriceSeries,
    SourceFill,
)
from src.copyability.loader import build_market, load_candle_prices, replay_positions
from src.copyability.metrics import as_row, outcome_for
from src.live_data.storage import LiveDataStore

D = Decimal
W = "0x" + "ab" * 20
MODEL = CostModel(FeeSchedule(taker_bps=D("4.5"), maker_bps=D("1.5")))
CONFIG = FollowerConfig(capital=D("10000"), size_scale=D("1"))
LIQ = {"BTC": LiquidityProfile("BTC", D("1"), D("1000000"), D("10"))}

#: A price that rises one dollar a second, so a move is exactly readable.
RISING = [(t, str(100 + (t - 1_000) // 1_000)) for t in range(1_000, 100_001, 1_000)]


def fill(wallet, t, tid, side, price="100", size="1") -> SourceFill:
    return SourceFill(wallet, "BTC", t, side, D(price), D(size), D("0.05"), D("0"), tid)


def market(points, funding=()) -> MarketData:
    return MarketData(
        prices={"BTC": PriceSeries("BTC", points)}, funding=FundingSchedule(funding), liquidity=LIQ
    )


def certified(start=1_000, end=100_000, wallet=W):
    return CoverageLedger([ObservedInterval(wallet, start, end, True, "t")]).certify(wallet, start, end)


class RunStudyOpeningPositionTests(unittest.TestCase):
    """The orchestration path must supply opening positions, not just accept them.

    Regression: ``simulate_follower`` grew ``opening_positions`` and
    ``replay_positions`` was written to build the map, but ``run_study`` never
    passed either, so the only path a study actually runs still scored a
    pre-window close as an inverted open. The unit tests above passed
    throughout, because they call the simulator directly.
    """

    def _study(self):
        # Long 1 BTC opened before the window, sold inside it at 109.
        rows = [
            fill(W, 500, 0, "B", price="99"),
            fill(W, 10_000, 1, "A", price="109"),
        ]
        ledger = CoverageLedger([ObservedInterval(W, 1_000, 100_000, True, "t")])
        config = StudyConfig(
            follower=CONFIG,
            cost_model=MODEL,
            benchmark_coin="BTC",
            momentum_lookback_ms=5_000,
            momentum_step_ms=1_000,
            random_seed=1,
            random_sample_size=1,
            latencies_ms=(0,),
        )
        return run_study(
            fills_by_wallet={W: rows},
            market=market(RISING),
            ledger=ledger,
            config=config,
            funding_truncated={W: False},
            window=(1_000, 100_000),
        )

    def test_run_study_scores_a_pre_window_close_as_a_close(self) -> None:
        studies = self._study()
        self.assertEqual(len(studies), 1)
        study = studies[0]
        self.assertIsNone(study.refusal)
        outcome = study.outcomes[0]
        # Catch-up long at the first quote (100), closed at 109: +9.
        # Before the fix this was -90, a short the wallet never opened.
        self.assertEqual(outcome.gross, D("9"))

    def test_the_opening_map_excludes_a_fill_exactly_at_the_interval_start(self) -> None:
        """A fill at ``start_ms`` is inside the window, so it must not also
        count as inventory carried into it."""
        interval = certified()
        rows = [fill(W, 1_000, 1, "B", price="100")]
        self.assertEqual(opening_positions_for(interval, rows), {})
        earlier = [fill(W, 999, 1, "B", price="100")]
        self.assertEqual(opening_positions_for(interval, earlier), {"BTC": D("1")})

    def test_the_opening_map_ignores_another_wallets_fills(self) -> None:
        other = "0x" + "cd" * 20
        rows = [fill(other, 500, 1, "B", price="100")]
        self.assertEqual(opening_positions_for(certified(), rows), {})


class OpeningPositionTests(unittest.TestCase):
    def test_a_close_of_a_position_opened_before_the_window_is_copied_as_a_close(self) -> None:
        # The source is long 1 BTC from before the window and sells it inside.
        rows = [fill(W, 10_000, 1, "A", price="109")]
        interval = certified()
        run = simulate_follower(
            interval, latency_ms=0, fills=rows, market=market(RISING), cost_model=MODEL,
            config=CONFIG, opening_positions={"BTC": D(1)},
        )
        self.assertEqual(run.catch_up_fills, 1)
        self.assertEqual(run.pnl.trade_count, 2)  # the catch-up plus the close
        # Entry at the first quote at or after the start (100), close at 109.
        self.assertEqual(run.pnl.gross, D("9"))
        self.assertEqual(run.traded_notional, D("100") + D("109"))
        self.assertEqual(run.equity_curve[-1].equity, CONFIG.capital + D("9") - run.pnl.costs.total)

    def test_without_the_opening_position_the_same_fill_opens_a_short(self) -> None:
        rows = [fill(W, 10_000, 1, "A", price="109")]
        run = simulate_follower(
            certified(), latency_ms=0, fills=rows, market=market(RISING), cost_model=MODEL,
            config=CONFIG,
        )
        self.assertEqual(run.catch_up_fills, 0)
        self.assertEqual(run.pnl.trade_count, 1)
        # Short 1 at 109, marked at the last price of the interval (199).
        self.assertEqual(run.pnl.gross, D("-90"))
        self.assertEqual(run.traded_notional, D("109"))

    def test_the_catch_up_entry_pays_the_full_taker_cost(self) -> None:
        run = simulate_follower(
            certified(), latency_ms=0, fills=(), market=market(RISING), cost_model=MODEL,
            config=CONFIG, opening_positions={"BTC": D(1)},
        )
        expected = MODEL.taker_execution(notional=D("100"), liquidity=LIQ["BTC"])
        self.assertEqual(run.catch_up_fills, 1)
        self.assertEqual(run.pnl.costs.fee, expected.fee)
        self.assertEqual(run.pnl.costs.spread, expected.spread)
        self.assertEqual(run.pnl.costs.slippage, expected.slippage)
        self.assertEqual(run.pnl.costs.total, expected.total)
        self.assertEqual(run.traded_notional, D("100"))
        self.assertEqual(run.peak_deployed_notional, D("100"))

    def test_a_short_opening_position_is_scaled_and_marked(self) -> None:
        config = FollowerConfig(capital=D("10000"), size_scale=D("0.5"))
        run = simulate_follower(
            certified(), latency_ms=0, fills=(), market=market(RISING), cost_model=MODEL,
            config=config, opening_positions={"BTC": D(-2)},
        )
        # Short 1 (2 x 0.5) at 100, marked at 199 at the end of the interval.
        self.assertEqual(run.traded_notional, D("100"))
        self.assertEqual(run.pnl.gross, D("-99"))

    def test_a_coin_whose_first_quote_falls_after_the_interval_is_skipped(self) -> None:
        late = market([(t, "100") for t in range(200_000, 300_001, 1_000)])
        run = simulate_follower(
            certified(), latency_ms=0, fills=(), market=late, cost_model=MODEL, config=CONFIG,
            opening_positions={"BTC": D(1)},
        )
        self.assertEqual(run.catch_up_fills, 0)
        self.assertEqual(run.skipped_fills, 1)
        self.assertEqual(run.pnl.trade_count, 0)


class CatchUpFundingTests(unittest.TestCase):
    """Funding runs from the catch-up entry, and the watermark never rewinds.

    The catch-up entry sets the coin's funding watermark to its own quote's
    time. A source fill acted on before that time must not drag the watermark
    back, or the hours between the fill and the entry would be charged on a
    position the follower did not hold yet.
    """

    #: Quote at 5,000,000 only: the fill at 4,000,000 has no price at all.
    LATE_QUOTE = [(5_000_000, "100")]
    #: A rate that makes a 100-notional hour cost exactly 0.1.
    RATE = D("0.001")

    def test_a_fill_before_the_catch_up_entry_does_not_rewind_the_funding_mark(self) -> None:
        interval = certified(start=3_000_000, end=8_000_000)
        data = market(self.LATE_QUOTE, funding=[FundingEvent("BTC", 4_500_000, self.RATE)])
        early = [fill(W, 4_000_000, 1, "A", price="100")]
        run = simulate_follower(
            interval, latency_ms=0, fills=early, market=data, cost_model=MODEL, config=CONFIG,
            opening_positions={"BTC": D(1)},
        )
        # The fill had no price, so it was skipped; the entry stands alone.
        self.assertEqual(run.skipped_fills, 1)
        self.assertEqual(run.catch_up_fills, 1)
        self.assertEqual(run.pnl.trade_count, 1)
        # The settlement at 4,500,000 is before the entry at 5,000,000.
        self.assertEqual(run.pnl.costs.funding, D("0"))
        # And the same run without the early fill charges the same nothing.
        without = simulate_follower(
            interval, latency_ms=0, fills=(), market=data, cost_model=MODEL, config=CONFIG,
            opening_positions={"BTC": D(1)},
        )
        self.assertEqual(without.pnl.costs.funding, D("0"))
        self.assertEqual(run.pnl.costs.funding, without.pnl.costs.funding)

    def test_a_priced_fill_before_the_catch_up_quote_still_charges_no_earlier_funding(self) -> None:
        """A priced fill acted on before the catch-up entry changes nothing.

        The follower cannot really copy a fill on a coin it has not yet caught
        up on, at a price it does not yet have; here the copy is priced from a
        quote that predates the window while the entry waits for the first
        quote inside it, so the two are applied out of chronological order.
        Whichever order the code settles on, funding may only accrue from the
        moment a position was actually held: nothing was held at 4,500,000,
        so nothing is charged for it.
        """
        interval = certified(start=3_000_000, end=8_000_000)
        # A quote before the window prices the fill; the entry takes the first
        # quote at or after the start, which is the one at 5,000,000.
        data = market(
            [(2_000_000, "100"), (5_000_000, "100")],
            funding=[FundingEvent("BTC", 4_500_000, self.RATE)],
        )
        rows = [fill(W, 4_000_000, 1, "A", price="100")]
        run = simulate_follower(
            interval, latency_ms=0, fills=rows, market=data, cost_model=MODEL, config=CONFIG,
            opening_positions={"BTC": D(1)},
        )
        self.assertEqual(run.skipped_fills, 0)
        self.assertEqual(run.catch_up_fills, 1)
        self.assertEqual(run.pnl.trade_count, 2)
        self.assertEqual(run.pnl.costs.funding, D("0"))
        self.assertEqual(run.pnl.gross, D("0"))

    def test_funding_accrues_from_the_entry_not_from_the_interval_start(self) -> None:
        interval = certified(start=3_000_000, end=12_000_000)
        data = market(
            [(8_000_000, "100")],
            funding=[
                FundingEvent("BTC", 6_600_000, self.RATE),   # start + 1h, before the entry
                FundingEvent("BTC", 9_000_000, self.RATE),   # after the entry, charged
            ],
        )
        run = simulate_follower(
            interval, latency_ms=0, fills=(), market=data, cost_model=MODEL, config=CONFIG,
            opening_positions={"BTC": D(1)},
        )
        self.assertEqual(run.catch_up_fills, 1)
        # One settlement on 100 of notional at 0.001, not two.
        self.assertEqual(run.pnl.costs.funding, D("0.1"))
        self.assertEqual(run.funding_periods_expected, 1)
        self.assertEqual(run.funding_periods_priced, 1)


class CatchUpOutcomeTests(unittest.TestCase):
    def test_the_outcome_carries_the_catch_up_count(self) -> None:
        interval = certified()
        rows = [fill(W, 10_000, 1, "A", price="109")]
        run = simulate_follower(
            interval, latency_ms=0, fills=rows, market=market(RISING), cost_model=MODEL,
            config=CONFIG, opening_positions={"BTC": D(1)},
        )
        outcome = outcome_for(
            run, source_pnl(interval, rows), {}, profile=profile_wallet(interval, rows),
            funding_truncated=False, liquidity_assumed=True,
        )
        self.assertEqual(outcome.catch_up_fills, 1)
        self.assertEqual(as_row(outcome)["catch_up_fills"], 1)


class ReplayPositionsTests(unittest.TestCase):
    def test_it_sums_and_flips_and_omits_flat_coins_and_later_fills(self) -> None:
        eth = SourceFill(W, "ETH", 3_000, "B", D("10"), D("4"), D("0"), D("0"), 3)
        rows = [
            fill(W, 1_000, 1, "B", size="3"),   # long 3 BTC
            fill(W, 2_000, 2, "A", size="5"),   # flips to short 2 BTC
            eth,                                 # long 4 ETH
            SourceFill(W, "ETH", 4_000, "A", D("10"), D("4"), D("0"), D("0"), 4),  # ETH back to flat
            fill(W, 9_000, 5, "B", size="7"),   # after the cutoff, ignored
        ]
        self.assertEqual(replay_positions(rows, until_ms=5_000), {"BTC": D("-2")})
        self.assertEqual(replay_positions(rows, until_ms=1_000), {"BTC": D("3")})
        self.assertEqual(replay_positions(rows, until_ms=3_000), {"BTC": D("-2"), "ETH": D("4")})
        self.assertEqual(replay_positions(rows, until_ms=500), {})
        self.assertEqual(replay_positions(rows, until_ms=9_000), {"BTC": D("5")})


class CandlePriceTests(unittest.TestCase):
    def setUp(self) -> None:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self.store = LiveDataStore(Path(tempdir.name) / "live.sqlite3")
        self.addCleanup(self.store.close)
        # The candles table comes from the live-data schema itself: a fresh
        # store migrates to the version that holds it, and these rows go into
        # the real table the loader reads.
        self.store.connection.executemany(
            "INSERT INTO candles (coin, interval, open_time_ms, close_time_ms, open, high, low, "
            "close, volume, trade_count, raw_payload, ingested_at_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("BTC", "15m", 1_000, 901_000, "100", "110", "99", "105", "3", 7, "{}", 1),
                ("BTC", "15m", 901_000, 1_801_000, "105", "115", "104", "112", "4", 9, "{}", 1),
                ("BTC", "1h", 1_000, 3_601_000, "100", "120", "98", "118", "9", 20, "{}", 1),
                ("ETH", "15m", 1_000, 901_000, "10", "11", "9", "10.5", "2", 3, "{}", 1),
            ],
        )
        self.store.connection.commit()

    def test_a_candle_close_is_only_known_once_the_candle_has_closed(self) -> None:
        series = load_candle_prices(self.store, ["BTC"])["BTC"]
        self.assertEqual(len(series), 2)
        self.assertEqual(series.at_or_before(901_000).price, D("105"))
        self.assertEqual(series.at_or_before(901_000).time_ms, 901_000)
        self.assertIsNone(series.at_or_before(1_000))  # the open time sees nothing yet
        self.assertIsNone(series.at_or_before(900_999))
        self.assertEqual(series.at_or_before(1_801_000).price, D("112"))

    def test_the_interval_selects_which_candles_are_read(self) -> None:
        hourly = load_candle_prices(self.store, ["BTC"], interval="1h")["BTC"]
        self.assertEqual([(p.time_ms, p.price) for p in hourly.points()], [(3_601_000, D("118"))])
        self.assertEqual(len(load_candle_prices(self.store, ["BTC"], interval="4h")["BTC"]), 0)

    def test_build_market_accepts_the_candle_source(self) -> None:
        liquidity = {
            "BTC": LIQ["BTC"],
            "ETH": LiquidityProfile("ETH", D("1"), D("1000000"), D("10")),
        }
        data = build_market(
            self.store, ["BTC", "ETH"], liquidity, price_source="candles", exclude_wallet=W
        )
        self.assertEqual(sorted(data.prices), ["BTC", "ETH"])
        series, _ = data.require_coin("ETH")
        self.assertEqual(series.at_or_before(901_000).price, D("10.5"))
        self.assertEqual(data.require_coin("BTC")[0].at_or_before(1_801_000).price, D("112"))

    def test_build_market_forwards_the_candle_interval(self) -> None:
        liquidity = {"BTC": LIQ["BTC"]}
        hourly = build_market(
            self.store, ["BTC"], liquidity, price_source="candles", candle_interval="1h"
        )
        series, _ = hourly.require_coin("BTC")
        self.assertEqual([(p.time_ms, p.price) for p in series.points()], [(3_601_000, D("118"))])
        # The default is still the 15-minute series.
        default = build_market(self.store, ["BTC"], liquidity, price_source="candles")
        self.assertEqual(len(default.require_coin("BTC")[0]), 2)


if __name__ == "__main__":
    unittest.main()
