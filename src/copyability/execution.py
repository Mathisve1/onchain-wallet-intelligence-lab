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
from typing import Mapping, Sequence

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
    #: Copies dropped because no usable price existed at the copy moment.
    skipped_fills: int
    #: Entries the follower made at the start of the interval to stand in the
    #: positions the source already held when the window opened. Zero unless
    #: ``opening_positions`` was given.
    catch_up_fills: int
    #: Of those, copies dropped because the only price was older than the
    #: allowed age: a hole in the data, not a fault of the wallet.
    stale_price_skips: int
    #: Source fills after the decision cutoff, excluded for every latency alike.
    fills_after_cutoff: int
    decision_cutoff_ms: int
    #: Funding settlements a held position should have seen, and how many of
    #: them the schedule actually priced. Anything unpriced was charged as
    #: zero, so the funding cost is unknown in that proportion.
    funding_periods_expected: int
    funding_periods_priced: int
    capital: Decimal
    #: Largest capital committed to open positions at any action, at cost
    #: basis, summed over coins. This is what the copy actually put to work,
    #: and the only fair base for comparing it with a baseline that deploys
    #: everything it is given.
    peak_deployed_notional: Decimal


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
    decision_cutoff_ms: int | None = None,
    max_price_age_ms: int | None = None,
    opening_positions: Mapping[str, Decimal] | None = None,
) -> FollowerRun:
    """Copy every source fill up to the cutoff after ``latency_ms``, at full cost.

    ``decision_cutoff_ms`` is the last source-fill time any latency may copy.
    A study runs every latency on the grid against the same cutoff, chosen as
    the interval end minus the largest latency, so each latency scores the
    same fills and a slower copy is not also a copy of fewer trades. Without
    it, the cutoff is the interval end minus this latency.

    ``max_price_age_ms`` bounds how old a price may be to execute or mark
    against. Older means no price: the copy is skipped and counted as stale.

    ``opening_positions`` is the signed size per coin the source already held
    when the window opened. The follower catches up to each of them at the
    first quote at or after the interval start, paying the full taker cost.
    Without it a source fill that closes a position opened before the window
    would open an inverted position for the follower instead of closing one,
    and the copy would be scored on a trade the wallet never made (code-review
    finding, 2026-09-04). The catch-up entry is priced at its own quote's time,
    so ``max_price_age_ms`` does not apply to it; a coin whose first quote
    falls after the interval end is skipped and counted in ``skipped_fills``.
    """
    _require_known(interval)
    if latency_ms < 0:
        raise InputError("latency cannot be negative")
    if decision_cutoff_ms is None:
        decision_cutoff_ms = interval.end_ms - latency_ms
    if decision_cutoff_ms + latency_ms > interval.end_ms:
        raise InputError("decision cutoff plus latency would land copies after the interval end")
    model = require_complete_model(cost_model)
    view = PointInTimeView(market, fills, horizon_ms=interval.end_ms)
    all_source = _fills_in(interval, fills)
    source = [f for f in all_source if f.time_ms <= decision_cutoff_ms]
    fills_after_cutoff = len(all_source) - len(source)

    positions: dict[str, _Position] = {}
    funding_checked: dict[str, int] = {}
    costs = CostBreakdown.zero()
    realized = Decimal(0)
    traded = Decimal(0)
    skipped = 0
    stale = 0
    trades = 0
    periods_expected = 0
    periods_priced = 0
    peak_deployed = Decimal(0)
    catch_up = 0
    curve: list[EquityPoint] = [EquityPoint(interval.start_ms, config.capital)]

    for coin in sorted(opening_positions or {}):
        size = _decimal(opening_positions[coin], "opening position") * config.size_scale
        if size == 0:
            continue
        series, liquidity = market.require_coin(coin)
        point = series.at_or_after(interval.start_ms)
        if point is None or point.time_ms > interval.end_ms:
            skipped += 1
            continue
        position = positions.setdefault(coin, _Position())
        notional = abs(size) * point.price
        costs += model.taker_execution(notional=notional, liquidity=liquidity)
        position.apply(size, point.price)
        traded += notional
        trades += 1
        catch_up += 1
        # Funding on a caught-up position accrues from its entry, not from the
        # interval start: the follower did not hold it before it bought it.
        funding_checked[coin] = point.time_ms
        _, deployed = _mark(config, realized, costs, positions, view, point.time_ms)
        peak_deployed = max(peak_deployed, deployed)

    actions = sorted(
        ((f.time_ms + latency_ms, f) for f in source), key=lambda pair: (pair[0], pair[1].trade_id)
    )
    for action_time, fill in actions:
        position = positions.setdefault(fill.coin, _Position())
        charge, expected, priced = _accrue_funding(
            view, fill.coin, position, funding_checked, until_ms=action_time,
            default_from_ms=interval.start_ms, model=model, max_price_age_ms=max_price_age_ms,
        )
        costs += charge
        periods_expected += expected
        periods_priced += priced
        point = view.price_at(fill.coin, action_time, max_age_ms=max_price_age_ms)
        if point is None:
            skipped += 1
            if view.price_at(fill.coin, action_time) is not None:
                stale += 1
            continue
        _, liquidity = market.require_coin(fill.coin)
        size = fill.size * config.size_scale
        notional = point.price * size
        costs += model.taker_execution(notional=notional, liquidity=liquidity)
        realized += position.apply(fill.signed_size * config.size_scale, point.price)
        traded += notional
        trades += 1
        equity, deployed = _mark(config, realized, costs, positions, view, action_time)
        peak_deployed = max(peak_deployed, deployed)
        curve.append(EquityPoint(action_time, equity))

    unrealized = Decimal(0)
    for coin, position in positions.items():
        charge, expected, priced = _accrue_funding(
            view, coin, position, funding_checked, until_ms=interval.end_ms,
            default_from_ms=interval.start_ms, model=model, max_price_age_ms=max_price_age_ms,
        )
        costs += charge
        periods_expected += expected
        periods_priced += priced
        if position.size != 0:
            # The final mark uses the last price whatever its age: an open
            # position has to be valued at something. A stale mark is counted
            # so the outcome can say the valuation rests on an old quote.
            point = view.price_at(coin, interval.end_ms)
            if point is None:
                raise InputError(f"no price to mark {coin} at the end of the interval")
            if max_price_age_ms is not None and interval.end_ms - point.time_ms > max_price_age_ms:
                stale += 1
            unrealized += (point.price - position.avg_price) * position.size
    curve.append(EquityPoint(interval.end_ms, config.capital + realized + unrealized - costs.total))

    pnl = FollowerPnl(
        wallet=interval.wallet, latency_ms=latency_ms, gross=realized + unrealized,
        costs=costs, trade_count=trades,
    )
    return FollowerRun(
        interval=interval, pnl=pnl, equity_curve=tuple(curve), traded_notional=traded,
        skipped_fills=skipped, catch_up_fills=catch_up, stale_price_skips=stale,
        fills_after_cutoff=fills_after_cutoff,
        decision_cutoff_ms=decision_cutoff_ms, funding_periods_expected=periods_expected,
        funding_periods_priced=periods_priced, capital=config.capital,
        peak_deployed_notional=peak_deployed,
    )


def _accrue_funding(
    view: PointInTimeView, coin: str, position: _Position, checked: dict[str, int], *,
    until_ms: int, default_from_ms: int, model: CostModel, max_price_age_ms: int | None = None,
) -> tuple[CostBreakdown, int, int]:
    """Charge every funding event since the last check on the held notional.

    Returns ``(charge, periods_expected, periods_priced)``. A held position
    that saw fewer events than the venue's hourly settlement implies was
    charged nothing for the missing hours; the caller carries that count into
    the outcome so an unpriced funding hour is never mistaken for a free one.

    The watermark only ever moves forward. A catch-up entry sets it to its own
    quote's time, and a source fill acted on before that time must not drag it
    back: doing so would charge the hours between as if the position had been
    held before it was bought. Such a call accrues nothing and leaves the
    watermark where it was.
    """
    since = checked.get(coin, default_from_ms)
    total = CostBreakdown.zero()
    expected = 0
    priced = 0
    if until_ms <= since:
        return total, expected, priced
    if position.size != 0:
        expected = view.market.funding.expected_periods(since, until_ms)
        events = view.funding_between(coin, since, until_ms)
        # Never more priced than expected: a settlement timestamped a few
        # milliseconds past the hour still belongs to that hour's boundary.
        priced = min(len(events), expected)
        for event in events:
            point = view.price_at(coin, event.time_ms, max_age_ms=max_price_age_ms)
            price = point.price if point is not None else position.avg_price
            total += model.funding_payment(position_notional=position.notional_at(price), rate=event.rate)
    checked[coin] = until_ms
    return total, expected, priced


def _mark(
    config: FollowerConfig, realized: Decimal, costs: CostBreakdown,
    positions: dict[str, _Position], view: PointInTimeView, time_ms: int,
) -> tuple[Decimal, Decimal]:
    """Equity at ``time_ms`` and the capital committed to open positions.

    Deployed capital is taken at cost basis, ``|size| x average entry``: it is
    what the follower had to put up, and it does not drift with the mark. A
    mark-to-market figure would let an appreciating position inflate its own
    denominator and understate the return.
    """
    unrealized = Decimal(0)
    deployed = Decimal(0)
    for coin, position in positions.items():
        if position.size == 0:
            continue
        point = view.price_at(coin, time_ms)
        price = point.price if point is not None else position.avg_price
        unrealized += (price - position.avg_price) * position.size
        deployed += abs(position.size) * position.avg_price
    return config.capital + realized + unrealized - costs.total, deployed


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
