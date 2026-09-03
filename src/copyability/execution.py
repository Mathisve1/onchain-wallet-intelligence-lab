"""Follower execution simulation at a fixed copy latency.

A follower sees each source fill ``latency_ms`` after it happened, and then
crosses the spread at whatever the mid is at that moment, paying the full
cost model. Positions are tracked per coin with average-entry accounting,
funding accrues on what is held between actions, and open positions are
marked at the last price inside the certified interval. Everything the
follower reads passes through a :class:`~.pit.PointInTimeView` fixed to that
interval's end, so nothing after it can leak in.

The result is a :class:`~.pnl.FollowerPnl`. The source wallet's own economics
are summarised separately by :func:`source_pnl` and never enter this ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from .costs import CostBreakdown, CostModel, require_complete_model
from .coverage import KnownInterval, UnknownIntervalError
from .inputs import InputError, MarketData, SourceFill, _decimal
from .pit import PointInTimeView
from .pnl import FollowerPnl, SourcePnl

#: Copy latencies the study preregistered: 1 s, 5 s, 30 s, 2 min, 5 min, 15 min.
LATENCY_GRID_MS: tuple[int, ...] = (1_000, 5_000, 30_000, 120_000, 300_000, 900_000)


@dataclass(frozen=True, slots=True)
class FollowerConfig:
    """How much the follower puts behind the copy.

    ``capital`` is the equity the curve starts from and turnover is measured
    against. ``size_scale`` multiplies the source's fill size: a follower with
    a tenth of the wallet's capital copies at 0.1.
    """

    capital: Decimal
    size_scale: Decimal

    def __post_init__(self) -> None:
        for name in ("capital", "size_scale"):
            value = _decimal(getattr(self, name), name)
            if value <= 0:
                raise InputError(f"{name} must be positive")
            object.__setattr__(self, name, value)


@dataclass(slots=True)
class _Position:
    size: Decimal = Decimal(0)
    avg_price: Decimal = Decimal(0)

    def apply(self, delta: Decimal, price: Decimal) -> Decimal:
        """Apply a signed size change at ``price``; return realized gross P&L."""
        if self.size == 0 or (self.size > 0) == (delta > 0):
            total = self.size + delta
            self.avg_price = (self.size * self.avg_price + delta * price) / total
            self.size = total
            return Decimal(0)
        closing = min(abs(delta), abs(self.size))
        direction = Decimal(1) if self.size > 0 else Decimal(-1)
        realized = (price - self.avg_price) * closing * direction
        remaining = self.size + delta
        if remaining == 0 or (remaining > 0) != (self.size > 0):
            # Flat, or flipped through zero: what is left was opened here.
            self.avg_price = price if remaining != 0 else Decimal(0)
        self.size = remaining
        return realized

    def notional_at(self, price: Decimal) -> Decimal:
        return self.size * price


@dataclass(frozen=True, slots=True)
class EquityPoint:
    time_ms: int
    equity: Decimal


@dataclass(frozen=True, slots=True)
class FollowerRun:
    """One follower simulation over one certified interval at one latency."""

    interval: KnownInterval
    pnl: FollowerPnl
    equity_curve: tuple[EquityPoint, ...]
    traded_notional: Decimal
    skipped_fills: int
    capital: Decimal


def source_pnl(interval: KnownInterval, fills: Sequence[SourceFill]) -> SourcePnl:
    """The copied wallet's own reported economics inside the interval."""
    _require_known(interval)
    rows = _fills_in(interval, fills)
    return SourcePnl(
        wallet=interval.wallet,
        closed_pnl=sum((f.closed_pnl for f in rows), Decimal(0)),
        fees_paid=sum((f.fee for f in rows), Decimal(0)),
        fill_count=len(rows),
    )


def simulate_follower(
    interval: KnownInterval,
    *,
    latency_ms: int,
    fills: Sequence[SourceFill],
    market: MarketData,
    cost_model: CostModel,
    config: FollowerConfig,
) -> FollowerRun:
    """Copy every source fill in the interval after ``latency_ms``, at full cost."""
    _require_known(interval)
    if latency_ms < 0:
        raise InputError("latency cannot be negative")
    model = require_complete_model(cost_model)
    view = PointInTimeView(market, fills, horizon_ms=interval.end_ms)
    source = _fills_in(interval, fills)

    positions: dict[str, _Position] = {}
    funding_checked: dict[str, int] = {}
    costs = CostBreakdown.zero()
    realized = Decimal(0)
    traded = Decimal(0)
    skipped = 0
    trades = 0
    curve: list[EquityPoint] = [EquityPoint(interval.start_ms, config.capital)]

    actions = sorted(
        ((f.time_ms + latency_ms, f) for f in source), key=lambda pair: (pair[0], pair[1].trade_id)
    )
    for action_time, fill in actions:
        if action_time > interval.end_ms:
            # The copy would land after the last observed moment. That is not
            # a fill we can price honestly, so it is skipped and counted.
            skipped += 1
            continue
        position = positions.setdefault(fill.coin, _Position())
        costs += _accrue_funding(view, fill.coin, position, funding_checked, until_ms=action_time,
                                 default_from_ms=interval.start_ms, model=model)
        point = view.price_at(fill.coin, action_time)
        if point is None:
            skipped += 1
            continue
        _, liquidity = market.require_coin(fill.coin)
        size = fill.size * config.size_scale
        notional = point.price * size
        costs += model.taker_execution(notional=notional, liquidity=liquidity)
        realized += position.apply(fill.signed_size * config.size_scale, point.price)
        traded += notional
        trades += 1
        curve.append(EquityPoint(action_time, _equity(config, realized, costs, positions, view, action_time)))

    unrealized = Decimal(0)
    for coin, position in positions.items():
        costs += _accrue_funding(view, coin, position, funding_checked, until_ms=interval.end_ms,
                                 default_from_ms=interval.start_ms, model=model)
        if position.size != 0:
            point = view.price_at(coin, interval.end_ms)
            if point is None:
                raise InputError(f"no price to mark {coin} at the end of the interval")
            unrealized += (point.price - position.avg_price) * position.size
    curve.append(EquityPoint(interval.end_ms, config.capital + realized + unrealized - costs.total))

    pnl = FollowerPnl(
        wallet=interval.wallet, latency_ms=latency_ms, gross=realized + unrealized,
        costs=costs, trade_count=trades,
    )
    return FollowerRun(
        interval=interval, pnl=pnl, equity_curve=tuple(curve), traded_notional=traded,
        skipped_fills=skipped, capital=config.capital,
    )


def _accrue_funding(
    view: PointInTimeView, coin: str, position: _Position, checked: dict[str, int], *,
    until_ms: int, default_from_ms: int, model: CostModel,
) -> CostBreakdown:
    """Charge every funding event since the last check on the held notional."""
    since = checked.get(coin, default_from_ms)
    total = CostBreakdown.zero()
    if position.size != 0:
        for event in view.funding_between(coin, since, until_ms):
            point = view.price_at(coin, event.time_ms)
            price = point.price if point is not None else position.avg_price
            total += model.funding_payment(position_notional=position.notional_at(price), rate=event.rate)
    checked[coin] = until_ms
    return total


def _equity(
    config: FollowerConfig, realized: Decimal, costs: CostBreakdown,
    positions: dict[str, _Position], view: PointInTimeView, time_ms: int,
) -> Decimal:
    unrealized = Decimal(0)
    for coin, position in positions.items():
        if position.size == 0:
            continue
        point = view.price_at(coin, time_ms)
        if point is not None:
            unrealized += (point.price - position.avg_price) * position.size
    return config.capital + realized + unrealized - costs.total


def _require_known(interval: object) -> None:
    if not isinstance(interval, KnownInterval):
        raise UnknownIntervalError(
            "the simulator scores only a KnownInterval issued by CoverageLedger.certify(); "
            f"got {type(interval).__name__}"
        )


def _fills_in(interval: KnownInterval, fills: Sequence[SourceFill]) -> list[SourceFill]:
    rows = [
        f for f in fills
        if f.wallet == interval.wallet and interval.start_ms <= f.time_ms <= interval.end_ms
    ]
    return sorted(rows, key=lambda f: (f.time_ms, f.trade_id))
