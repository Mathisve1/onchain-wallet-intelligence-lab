from __future__ import annotations

import unittest
from decimal import Decimal

from src.copyability.classify import (
    DIRECTIONAL,
    INSUFFICIENT_FILLS,
    PROBABLE_MARKET_MAKER,
    ClassifierThresholds,
    profile_wallet,
)
from src.copyability.coverage import CoverageLedger, ObservedInterval
from src.copyability.inputs import SourceFill

D = Decimal
W = "0x" + "ab" * 20
DAY = 86_400_000
INTERVAL = CoverageLedger([ObservedInterval(W, 1_000, 1_000 + DAY, True, "t")]).certify(W, 1_000, 1_000 + DAY)


def fill(t: int, tid: int, side: str, *, coin: str = "BTC", crossed: bool | None = None, size: str = "1") -> SourceFill:
    return SourceFill(W, coin, t, side, D("100"), D(size), D("0.01"), D("0"), tid, crossed=crossed)


class ClassifierTests(unittest.TestCase):
    def test_too_few_fills_is_insufficient_not_directional(self) -> None:
        profile = profile_wallet(INTERVAL, [fill(2_000 + i, i, "B") for i in range(5)])
        self.assertEqual(profile.classification, INSUFFICIENT_FILLS)
        self.assertEqual(profile.fill_count, 5)

    def test_resting_two_sided_short_hold_activity_is_a_probable_market_maker(self) -> None:
        # Buy and sell 1 BTC within 10 s, twenty times, every fill a maker fill.
        fills = []
        for i in range(20):
            base = 2_000 + i * 60_000
            fills.append(fill(base, 2 * i, "B", crossed=False))
            fills.append(fill(base + 10_000, 2 * i + 1, "A", crossed=False))
        profile = profile_wallet(INTERVAL, fills)
        self.assertEqual(profile.classification, PROBABLE_MARKET_MAKER)
        self.assertEqual(profile.maker_share, D(1))
        self.assertEqual(profile.two_sided_share, D(1))
        self.assertEqual(profile.median_holding_ms, 10_000)
        self.assertEqual(profile.round_trips, 20)
        self.assertTrue(any("maker share" in r for r in profile.reasons))

    def test_churn_alone_classifies_when_the_venue_did_not_say_who_rested(self) -> None:
        fills = []
        for i in range(20):
            base = 2_000 + i * 60_000
            fills.append(fill(base, 2 * i, "B"))
            fills.append(fill(base + 10_000, 2 * i + 1, "A"))
        profile = profile_wallet(INTERVAL, fills)
        self.assertIsNone(profile.maker_share)
        self.assertEqual(profile.classification, PROBABLE_MARKET_MAKER)
        self.assertTrue(any("two-sided" in r for r in profile.reasons))

    def test_taker_fills_held_for_hours_are_directional(self) -> None:
        fills = []
        for i in range(20):
            base = 2_000 + i * 3_600_000  # one entry per hour
            fills.append(fill(base, 2 * i, "B", crossed=True))
            fills.append(fill(base + 1_800_000, 2 * i + 1, "A", crossed=True))  # held 30 min
        profile = profile_wallet(INTERVAL, fills)
        self.assertEqual(profile.classification, DIRECTIONAL)
        self.assertEqual(profile.maker_share, D(0))
        self.assertEqual(profile.two_sided_share, D(0))  # nothing opposite within 60 s
        self.assertEqual(profile.median_holding_ms, 1_800_000)

    def test_a_position_that_flips_through_zero_closes_one_round_trip_and_opens_another(self) -> None:
        fills = [fill(2_000, 1, "B", crossed=True), fill(12_000, 2, "A", crossed=True, size="2"),
                 fill(22_000, 3, "B", crossed=True)]
        profile = profile_wallet(INTERVAL, fills, ClassifierThresholds(min_fills=1))
        self.assertEqual(profile.round_trips, 2)
        self.assertEqual(profile.median_holding_ms, 10_000)

    def test_thresholds_are_explicit_and_change_the_label(self) -> None:
        fills = []
        for i in range(20):
            base = 2_000 + i * 60_000
            fills.append(fill(base, 2 * i, "B", crossed=False))
            fills.append(fill(base + 10_000, 2 * i + 1, "A", crossed=True))  # half maker
        default = profile_wallet(INTERVAL, fills)
        self.assertEqual(default.maker_share, D("0.5"))
        self.assertEqual(default.classification, PROBABLE_MARKET_MAKER)  # churn rule still fires
        strict = profile_wallet(INTERVAL, fills, ClassifierThresholds(two_sided_threshold=D("1.1"), short_holding_ms=1))
        self.assertEqual(strict.classification, DIRECTIONAL)

    def test_only_fills_inside_the_certified_interval_count(self) -> None:
        inside = [fill(2_000 + i * 1_000, i, "B", crossed=True) for i in range(20)]
        outside = [fill(1_000 + DAY + 5_000 + i, 100 + i, "A", crossed=False) for i in range(50)]
        profile = profile_wallet(INTERVAL, inside + outside)
        self.assertEqual(profile.fill_count, 20)
        self.assertEqual(profile.maker_share, D(0))


if __name__ == "__main__":
    unittest.main()
