"""Point-in-time discipline: nothing after the decision moment is visible.

Two mechanisms, used together.

:class:`PointInTimeView` is the only window through which the simulator reads
market data and source fills. It is fixed to a horizon and refuses to hand out
anything observed after it. A price series or fill source that returns a
later point anyway is caught at the boundary and raises :class:`LookAheadError`.

:func:`assert_point_in_time` is the probe for the other direction. It runs a
decision function twice, once on the data as of the horizon and once with
future observations appended, and fails if the two decisions differ. A
selector that peeks at the future cannot pass it, and a test that passes
future data to a correct selector proves the selector ignores it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence, TypeVar

from .inputs import FundingEvent, InputError, MarketData, PricePoint, SourceFill

T = TypeVar("T")


class LookAheadError(RuntimeError):
    """Raised when a decision could see information from after its horizon."""


@dataclass(frozen=True, slots=True)
class PointInTimeView:
    """Market and fill data truncated at ``horizon_ms``, enforced on every read."""

    market: MarketData
    fills: Sequence[SourceFill]
    horizon_ms: int

    def __post_init__(self) -> None:
        if self.horizon_ms <= 0:
            raise InputError("horizon must be a positive millisecond timestamp")

    def price_at(self, coin: str, time_ms: int) -> PricePoint | None:
        """Latest price at or before ``time_ms``, which must not exceed the horizon."""
        if time_ms > self.horizon_ms:
            raise LookAheadError(
                f"price requested at {time_ms} beyond horizon {self.horizon_ms} for {coin}"
            )
        series, _ = self.market.require_coin(coin)
        point = series.at_or_before(time_ms)
        if point is not None and point.time_ms > time_ms:
            # A series that answers with a later point is lying about the
            # past. Catching it here means no simulation step can consume it.
            raise LookAheadError(
                f"{coin} price series returned {point.time_ms} for a query at {time_ms}"
            )
        return point

    def fills_until(self, time_ms: int) -> list[SourceFill]:
        """Source fills with ``fill.time_ms <= time_ms``, within the horizon."""
        if time_ms > self.horizon_ms:
            raise LookAheadError(f"fills requested at {time_ms} beyond horizon {self.horizon_ms}")
        visible = [fill for fill in self.fills if fill.time_ms <= time_ms]
        for fill in visible:
            if fill.time_ms > time_ms:  # pragma: no cover - defensive, filtered above
                raise LookAheadError("fill after query time leaked through")
        return visible

    def funding_between(self, coin: str, start_ms: int, end_ms: int) -> list[FundingEvent]:
        if end_ms > self.horizon_ms:
            raise LookAheadError(f"funding requested to {end_ms} beyond horizon {self.horizon_ms}")
        events = self.market.funding.between(coin, start_ms, end_ms)
        for event in events:
            if event.time_ms > end_ms:
                raise LookAheadError("funding schedule returned an event after the query window")
        return events

    def narrowed(self, horizon_ms: int) -> PointInTimeView:
        """A view with an earlier horizon. Widening is not offered."""
        if horizon_ms > self.horizon_ms:
            raise LookAheadError("a view cannot be widened past its horizon")
        return PointInTimeView(self.market, self.fills, horizon_ms)


def assert_point_in_time(
    decide: Callable[[Sequence[SourceFill]], T],
    fills_as_of: Sequence[SourceFill],
    future_fills: Iterable[SourceFill],
    *,
    horizon_ms: int,
) -> T:
    """Run ``decide`` with and without future fills; fail if the answer moves.

    ``fills_as_of`` must all be at or before the horizon and ``future_fills``
    all after it; the probe checks both so a mislabelled fixture cannot make
    the test vacuous. Returns the as-of decision so callers can use it.
    """
    as_of = list(fills_as_of)
    future = list(future_fills)
    if any(fill.time_ms > horizon_ms for fill in as_of):
        raise InputError("fills_as_of contains a fill after the horizon")
    if not future:
        raise InputError("the probe needs at least one future fill to be meaningful")
    if any(fill.time_ms <= horizon_ms for fill in future):
        raise InputError("future_fills contains a fill at or before the horizon")

    baseline = decide(as_of)
    with_future = decide(as_of + future)
    if baseline != with_future:
        raise LookAheadError(
            f"decision changed when future fills were appended: {baseline!r} -> {with_future!r}"
        )
    return baseline
