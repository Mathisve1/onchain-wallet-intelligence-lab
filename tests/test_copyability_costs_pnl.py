from __future__ import annotations

import dataclasses
import unittest
from decimal import Decimal

from src.copyability.costs import COST_COMPONENTS, CostBreakdown, CostError, CostModel, FeeSchedule
from src.copyability.inputs import LiquidityProfile
from src.copyability.pnl import FollowerPnl, PnlComparison, PnlMixingError, SourcePnl

D = Decimal
BTC = LiquidityProfile("BTC", half_spread_bps=D("0.5"), depth_notional=D("1000000"), impact_bps_per_depth=D("10"))
FEES = FeeSchedule(taker_bps=D("4.5"), maker_bps=D("1.5"))


class NoCostIsSilentlyZeroTests(unittest.TestCase):
    """Every cost component is required, and the total is their sum, always."""

    def test_a_fee_schedule_cannot_be_built_without_both_rates(self) -> None:
        with self.assertRaises(TypeError):
            FeeSchedule(taker_bps=D("4.5"))  # type: ignore[call-arg]
        with self.assertRaises(CostError):
            FeeSchedule(taker_bps=D("0"), maker_bps=D("1.5"))

    def test_a_liquidity_profile_cannot_omit_spread_or_depth(self) -> None:
        with self.assertRaises(TypeError):
            LiquidityProfile("BTC", half_spread_bps=D("0.5"), depth_notional=D("1"))  # type: ignore[call-arg]
        for zeroed in ("half_spread_bps", "depth_notional", "impact_bps_per_depth"):
            kwargs = {"half_spread_bps": D("0.5"), "depth_notional": D("1"), "impact_bps_per_depth": D("1")}
            kwargs[zeroed] = D("0")
            with self.assertRaises(Exception, msg=zeroed):
                LiquidityProfile("BTC", **kwargs)

    def test_a_breakdown_cannot_be_built_with_a_component_missing(self) -> None:
        for dropped in COST_COMPONENTS:
            kwargs = {name: D("1") for name in COST_COMPONENTS}
            del kwargs[dropped]
            with self.assertRaises(TypeError, msg=dropped):
                CostBreakdown(**kwargs)  # type: ignore[arg-type]

    def test_the_total_equals_the_sum_of_every_named_component(self) -> None:
        # Distinct primes: dropping any one changes the sum detectably.
        breakdown = CostBreakdown(fee=D("2"), spread=D("3"), slippage=D("5"), funding=D("7"))
        self.assertEqual(breakdown.total, D("17"))
        for name in COST_COMPONENTS:
            self.assertNotEqual(breakdown.total - getattr(breakdown, name), breakdown.total, name)
        breakdown.assert_complete()

    def test_the_component_contract_is_pinned(self) -> None:
        self.assertEqual(COST_COMPONENTS, ("fee", "spread", "slippage", "funding"))
        self.assertEqual(tuple(f.name for f in dataclasses.fields(CostBreakdown)), COST_COMPONENTS)

    def test_taker_execution_charges_fee_spread_and_slippage_all_nonzero(self) -> None:
        model = CostModel(FEES)
        cost = model.taker_execution(notional=D("10000"), liquidity=BTC)
        self.assertEqual(cost.fee, D("4.5"))  # 4.5 bps of 10k
        self.assertEqual(cost.spread, D("0.5"))  # 0.5 bps of 10k
        # 10k eats 1% of 1M depth -> 10 bps * 0.01 = 0.1 bps of 10k
        self.assertEqual(cost.slippage, D("0.1"))
        self.assertEqual(cost.funding, D("0"))
        self.assertEqual(cost.total, D("5.1"))
        for name in ("fee", "spread", "slippage"):
            self.assertGreater(getattr(cost, name), 0, name)

    def test_slippage_grows_with_order_size_against_depth(self) -> None:
        model = CostModel(FEES)
        small = model.taker_execution(notional=D("10000"), liquidity=BTC)
        large = model.taker_execution(notional=D("100000"), liquidity=BTC)
        # Ten times the notional: fee and spread scale 10x, slippage 100x.
        self.assertEqual(large.fee, small.fee * 10)
        self.assertEqual(large.spread, small.spread * 10)
        self.assertEqual(large.slippage, small.slippage * 100)

    def test_funding_is_signed_by_position_direction(self) -> None:
        model = CostModel(FEES)
        long = model.funding_payment(position_notional=D("10000"), rate=D("0.0001"))
        short = model.funding_payment(position_notional=D("-10000"), rate=D("0.0001"))
        self.assertEqual(long.funding, D("1"))
        self.assertEqual(short.funding, D("-1"))

    def test_a_cost_model_needs_a_fee_schedule(self) -> None:
        with self.assertRaises(CostError):
            CostModel(fees=None)  # type: ignore[arg-type]


class PnlSeparationTests(unittest.TestCase):
    """Source and follower P&L are different types and refuse to mix."""

    def setUp(self) -> None:
        self.source = SourcePnl("0xw", closed_pnl=D("100"), fees_paid=D("10"), fill_count=3)
        self.follower = FollowerPnl(
            "0xw", latency_ms=1000, gross=D("80"),
            costs=CostBreakdown(D("2"), D("3"), D("5"), D("7")), trade_count=3,
        )

    def test_each_side_reports_its_own_net(self) -> None:
        self.assertEqual(self.source.net, D("90"))
        self.assertEqual(self.follower.net, D("63"))

    def test_adding_source_to_follower_raises_in_both_directions(self) -> None:
        with self.assertRaises(PnlMixingError):
            _ = self.source + self.follower
        with self.assertRaises(PnlMixingError):
            _ = self.follower + self.source

    def test_comparing_source_with_follower_raises(self) -> None:
        with self.assertRaises(PnlMixingError):
            _ = self.source < self.follower
        with self.assertRaises(PnlMixingError):
            _ = self.follower < self.source

    def test_the_comparison_holds_both_by_name_and_never_sums(self) -> None:
        comparison = PnlComparison(source=self.source, follower=self.follower)
        self.assertEqual(comparison.source.net, D("90"))
        self.assertEqual(comparison.follower.net, D("63"))
        self.assertEqual(comparison.follower_captures, D("63") / D("90"))
        self.assertFalse(hasattr(comparison, "net"))
        self.assertFalse(hasattr(comparison, "total"))

    def test_a_comparison_rejects_swapped_arguments(self) -> None:
        with self.assertRaises(PnlMixingError):
            PnlComparison(source=self.follower, follower=self.source)  # type: ignore[arg-type]

    def test_follower_pnl_requires_a_complete_cost_breakdown(self) -> None:
        with self.assertRaises(TypeError):
            FollowerPnl("0xw", latency_ms=0, gross=D("1"), costs=D("1"), trade_count=1)  # type: ignore[arg-type]

    def test_no_function_in_the_package_converts_one_into_the_other(self) -> None:
        import src.copyability as package

        for name in package.__all__:
            obj = getattr(package, name)
            annotations = getattr(obj, "__annotations__", {}) if callable(obj) else {}
            returns = annotations.get("return")
            args = {k: v for k, v in annotations.items() if k != "return"}
            if returns in ("FollowerPnl", FollowerPnl):
                self.assertNotIn("SourcePnl", str(args), name)
            if returns in ("SourcePnl", SourcePnl):
                self.assertNotIn("FollowerPnl", str(args), name)


if __name__ == "__main__":
    unittest.main()
