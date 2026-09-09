"""Matched-random peers are scored under the target's own convention.

Regression for a finding of the arm A runner verification (2026-09-09): the
study fixes one decision cutoff for every latency and one price-age bound, and
applied both to the target, but the peers behind ``M_i`` were simulated with
neither. A peer fill after the common cutoff, or a peer copy priced on a quote
the target would have refused as stale, then moved the primary mean while the
target's own ``R_i`` excluded it.
"""

from __future__ import annotations

import unittest
from decimal import Decimal as D

from src.copyability import baselines
from src.copyability.costs import CostModel, FeeSchedule
from src.copyability.coverage import CoverageLedger, ObservedInterval
from src.copyability.execution import FollowerConfig
from src.copyability.inputs import (
    FundingSchedule,
    LiquidityProfile,
    MarketData,
    PriceSeries,
    SourceFill,
)
from src.copyability.simulate import StudyConfig, run_study

TARGET = "0x" + "aa" * 20
PEER = "0x" + "bb" * 20
MODEL = CostModel(FeeSchedule(taker_bps=D("4.5"), maker_bps=D("1.5")))
CONFIG = FollowerConfig(capital=D("10000"), size_scale=D("1"))
LIQ = {"BTC": LiquidityProfile("BTC", D("1"), D("1000000"), D("10"))}
START, END = 1_000, 1_000_000


def fill(wallet: str, t: int, tid: int, side: str, price: str = "100") -> SourceFill:
    return SourceFill(wallet, "BTC", t, side, D(price), D("1"), D("0"), D("0"), tid)


def market(points) -> MarketData:
    return MarketData(prices={"BTC": PriceSeries("BTC", points)}, funding=FundingSchedule(()), liquidity=LIQ)


def ledger() -> CoverageLedger:
    return CoverageLedger([ObservedInterval(w, START, END, True, "t") for w in (TARGET, PEER)])


def study(latencies=(0,), max_price_age_ms=None) -> StudyConfig:
    return StudyConfig(CONFIG, MODEL, "BTC", 5_000, 1_000, 7, 5, latencies_ms=latencies,
                       max_price_age_ms=max_price_age_ms)


class PeerConventionTests(unittest.TestCase):
    def _run(self, peer_fills, **kwargs):
        rising = [(t, str(100 + t // 10_000)) for t in range(START, END + 1, 1_000)]
        target_fills = [fill(TARGET, 100_000, 1, "B"), fill(TARGET, 500_000, 2, "A")]
        studies = run_study(
            fills_by_wallet={TARGET: target_fills, PEER: peer_fills},
            market=market(rising), ledger=ledger(), config=study(**kwargs),
            funding_truncated={TARGET: False, PEER: False}, wallets=[TARGET], window=(START, END),
        )
        (s,) = studies
        self.assertIsNone(s.refusal, s.refusal)
        return s.outcomes[0]

    def test_a_peer_fill_after_the_common_cutoff_does_not_enter_the_baseline(self) -> None:
        # Two latencies: the common cutoff is END - 900_000 = 100_000, so every
        # copy after that is excluded for the target. The peer's second fill
        # sits after the cutoff; before the fix it was copied for the peer.
        latencies = (0, 900_000)
        base = [fill(PEER, 50_000, 1, "B"), fill(PEER, 90_000, 2, "A")]
        late = base + [fill(PEER, 600_000, 3, "B")]
        without = self._run(base, latencies=latencies).baseline_returns["matched_random"]
        with_late = self._run(late, latencies=latencies).baseline_returns["matched_random"]
        self.assertEqual(without, with_late)

    def test_a_peer_copy_on_a_stale_quote_is_skipped_like_the_targets(self) -> None:
        # No price between 200_000 and 400_000: a peer fill at 300_000 has only
        # a 100-second-old quote. With a 60-second bound the target would skip
        # it, and so must the peer.
        gappy = [(t, str(100 + t // 10_000)) for t in range(START, END + 1, 1_000)
                 if not 200_000 < t < 400_000]
        peer_fills = [fill(PEER, 150_000, 1, "B"), fill(PEER, 300_000, 2, "A"), fill(PEER, 450_000, 3, "B"),
                      fill(PEER, 480_000, 4, "A")]
        # Four target fills too, so the peer sits inside the +/-50% activity
        # band and is eligible at all; otherwise both runs return None.
        target_fills = [fill(TARGET, 100_000, 1, "B"), fill(TARGET, 120_000, 2, "A"),
                        fill(TARGET, 500_000, 3, "B"), fill(TARGET, 520_000, 4, "A")]
        for bound in (None, 60_000):
            (s,) = run_study(
                fills_by_wallet={TARGET: target_fills, PEER: peer_fills},
                market=market(gappy), ledger=ledger(), config=study(max_price_age_ms=bound),
                funding_truncated={TARGET: False, PEER: False}, wallets=[TARGET], window=(START, END),
            )
            self.assertIsNone(s.refusal)
            if bound is None:
                unbounded = s.outcomes[0].baseline_returns["matched_random"]
            else:
                bounded = s.outcomes[0].baseline_returns["matched_random"]
        self.assertNotEqual(unbounded, bounded, "the bound must reach the peer's copy at 300_000")

    def test_matched_random_accepts_and_forwards_both_conventions(self) -> None:
        interval = ledger().certify(TARGET, START, END)
        rising = [(t, str(100 + t // 10_000)) for t in range(START, END + 1, 1_000)]
        seen = {}
        original = baselines.simulate_follower

        def spy(*args, **kwargs):
            seen.update(kwargs)
            return original(*args, **kwargs)

        baselines.simulate_follower = spy
        try:
            baselines.matched_random(
                interval, latency_ms=0, target_fill_count=2,
                pool={TARGET: [], PEER: [fill(PEER, 50_000, 1, "B"), fill(PEER, 90_000, 2, "A")]},
                market=market(rising), cost_model=MODEL, config=CONFIG, certify=ledger().certify,
                seed=1, sample_size=5, decision_cutoff_ms=123_456, max_price_age_ms=7_000,
            )
        finally:
            baselines.simulate_follower = original
        self.assertEqual(seen["decision_cutoff_ms"], 123_456)
        self.assertEqual(seen["max_price_age_ms"], 7_000)


if __name__ == "__main__":
    unittest.main()
