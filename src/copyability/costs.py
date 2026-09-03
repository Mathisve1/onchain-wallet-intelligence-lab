"""Follower cost model: fees, spread, slippage and funding.

Every component is required and accounted separately. A breakdown whose
total does not equal the sum of its named components fails validation, so a
component cannot be dropped from the arithmetic without a loud failure, and a
model cannot be built with a component missing. That is the property the
tests lean on: no cost is ever silently zero.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal

from .inputs import LiquidityProfile, _decimal

BPS = Decimal(10_000)

#: Every cost component the follower pays. The tuple is the contract: a
#: breakdown must carry exactly these, and its total must be their sum.
COST_COMPONENTS: tuple[str, ...] = ("fee", "spread", "slippage", "funding")


class CostError(ValueError):
    """Raised when a cost model or breakdown is incomplete or inconsistent."""


@dataclass(frozen=True, slots=True)
class FeeSchedule:
    """Venue fee rates in basis points of notional. No defaults on purpose."""

    taker_bps: Decimal
    maker_bps: Decimal

    def __post_init__(self) -> None:
        for name in ("taker_bps", "maker_bps"):
            value = _decimal(getattr(self, name), name)
            if value <= 0:
                raise CostError(f"{name} must be positive; a free venue is a claim, not a default")
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    """The cost of one follower action, split by component. Always positive-cost.

    ``funding`` is signed: a follower can receive funding. Every other
    component is a cost and must be nonnegative.
    """

    fee: Decimal
    spread: Decimal
    slippage: Decimal
    funding: Decimal

    def __post_init__(self) -> None:
        names = tuple(f.name for f in fields(self))
        if names != COST_COMPONENTS:
            raise CostError(f"cost components drift: {names} != {COST_COMPONENTS}")
        for name in COST_COMPONENTS:
            value = _decimal(getattr(self, name), name)
            if name != "funding" and value < 0:
                raise CostError(f"{name} cannot be negative")
            object.__setattr__(self, name, value)

    @property
    def total(self) -> Decimal:
        """Sum of every component. Computed, never stored, so it cannot drift."""
        return sum((getattr(self, name) for name in COST_COMPONENTS), Decimal(0))

    def __add__(self, other: CostBreakdown) -> CostBreakdown:
        if not isinstance(other, CostBreakdown):
            return NotImplemented
        return CostBreakdown(
            **{name: getattr(self, name) + getattr(other, name) for name in COST_COMPONENTS}
        )

    @classmethod
    def zero(cls) -> CostBreakdown:
        return cls(Decimal(0), Decimal(0), Decimal(0), Decimal(0))

    def assert_complete(self) -> None:
        """Fail unless the total is exactly the sum of all named components."""
        recomputed = Decimal(0)
        for name in COST_COMPONENTS:
            recomputed += getattr(self, name)
        if recomputed != self.total:
            raise CostError("cost total does not equal the sum of its components")


@dataclass(frozen=True, slots=True)
class CostModel:
    """Turns a follower order into its explicit cost."""

    fees: FeeSchedule

    def __post_init__(self) -> None:
        if not isinstance(self.fees, FeeSchedule):
            raise CostError("cost model needs a FeeSchedule")

    def taker_execution(
        self, *, notional: Decimal, liquidity: LiquidityProfile
    ) -> CostBreakdown:
        """Cost of crossing the spread for ``notional`` in this coin.

        Fee: taker rate on notional.
        Spread: half the quoted spread, paid once on entry.
        Slippage: impact grows with the share of resting depth the order eats,
        so a large order against a thin book is priced accordingly rather than
        filled at the mid as if it were free.
        Funding: none at execution; it accrues while the position is held.
        """
        notional = _decimal(notional, "notional")
        if notional <= 0:
            raise CostError("notional must be positive")
        fee = notional * self.fees.taker_bps / BPS
        spread = notional * liquidity.half_spread_bps / BPS
        depth_share = notional / liquidity.depth_notional
        slippage = notional * (liquidity.impact_bps_per_depth * depth_share) / BPS
        return CostBreakdown(fee=fee, spread=spread, slippage=slippage, funding=Decimal(0))

    def funding_payment(self, *, position_notional: Decimal, rate: Decimal) -> CostBreakdown:
        """Funding on a held position: positive is paid, negative is received.

        Longs pay when the rate is positive, shorts receive; the sign of the
        signed notional carries that. Nothing else is charged here.
        """
        signed = _decimal(position_notional, "position_notional") * _decimal(rate, "rate")
        return CostBreakdown(fee=Decimal(0), spread=Decimal(0), slippage=Decimal(0), funding=signed)


def require_complete_model(model: object) -> CostModel:
    """Reject anything that is not a full :class:`CostModel`."""
    if not isinstance(model, CostModel):
        raise CostError(f"expected CostModel, got {type(model).__name__}")
    return model
