"""Outcome metrics for one follower run and its comparison with baselines.

Net expectancy, drawdown and turnover are what the risk policy says research
optimises for. Each is computed from the follower run alone; the source
wallet's own result is reported beside it under its own name and never
folded in.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence

from .execution import EquityPoint, FollowerRun
from .pnl import PnlComparison, SourcePnl

MS_PER_DAY = Decimal(86_400_000)


@dataclass(frozen=True, slots=True)
class Drawdown:
    """Largest peak-to-trough equity decline over the curve."""

    absolute: Decimal
    fraction_of_peak: Decimal
    peak_time_ms: int | None
    trough_time_ms: int | None


def max_drawdown(curve: Sequence[EquityPoint]) -> Drawdown:
    if not curve:
        return Drawdown(Decimal(0), Decimal(0), None, None)
    peak = curve[0]
    worst = Drawdown(Decimal(0), Decimal(0), peak.time_ms, peak.time_ms)
    for point in curve:
        if point.equity > peak.equity:
            peak = point
            continue
        decline = peak.equity - point.equity
        if decline > worst.absolute:
            fraction = decline / peak.equity if peak.equity > 0 else Decimal(0)
            worst = Drawdown(decline, fraction, peak.time_ms, point.time_ms)
    return worst


@dataclass(frozen=True, slots=True)
class Outcome:
    """Everything reported for one wallet at one latency.

    ``versus`` holds ``net - baseline_net`` per baseline. A positive ``net``
    with a negative entry here means the copy lost to something that needed
    no wallet at all, which is the comparison the study exists to make.
    """

    wallet: str
    latency_ms: int
    net: Decimal
    gross: Decimal
    cost_total: Decimal
    cost_fee: Decimal
    cost_spread: Decimal
    cost_slippage: Decimal
    cost_funding: Decimal
    net_per_trade: Decimal | None
    net_per_day: Decimal | None
    drawdown: Drawdown
    turnover: Decimal
    trade_count: int
    skipped_fills: int
    interval_days: Decimal
    source_net: Decimal
    source_fill_count: int
    baselines: Mapping[str, Decimal]
    versus: Mapping[str, Decimal]


def outcome_for(
    run: FollowerRun, source: SourcePnl, baselines: Mapping[str, Decimal]
) -> Outcome:
    """Assemble the outcome; the comparison type keeps the two P&Ls apart."""
    comparison = PnlComparison(source=source, follower=run.pnl)
    follower = comparison.follower
    days = Decimal(run.interval.duration_ms) / MS_PER_DAY
    net = follower.net
    return Outcome(
        wallet=run.interval.wallet,
        latency_ms=follower.latency_ms,
        net=net,
        gross=follower.gross,
        cost_total=follower.costs.total,
        cost_fee=follower.costs.fee,
        cost_spread=follower.costs.spread,
        cost_slippage=follower.costs.slippage,
        cost_funding=follower.costs.funding,
        net_per_trade=(net / follower.trade_count) if follower.trade_count else None,
        net_per_day=(net / days) if days > 0 else None,
        drawdown=max_drawdown(run.equity_curve),
        turnover=run.traded_notional / run.capital,
        trade_count=follower.trade_count,
        skipped_fills=run.skipped_fills,
        interval_days=days,
        source_net=comparison.source.net,
        source_fill_count=comparison.source.fill_count,
        baselines=dict(baselines),
        versus={name: net - value for name, value in baselines.items()},
    )


def as_row(outcome: Outcome, *, places: int = 4) -> dict[str, object]:
    """A flat, JSON-ready view with decimals rendered as strings."""
    q = Decimal(1).scaleb(-places)

    def fmt(value: Decimal | None) -> str | None:
        return None if value is None else str(value.quantize(q))

    row: dict[str, object] = {
        "wallet": outcome.wallet,
        "latency_ms": outcome.latency_ms,
        "net": fmt(outcome.net),
        "gross": fmt(outcome.gross),
        "cost_total": fmt(outcome.cost_total),
        "cost_fee": fmt(outcome.cost_fee),
        "cost_spread": fmt(outcome.cost_spread),
        "cost_slippage": fmt(outcome.cost_slippage),
        "cost_funding": fmt(outcome.cost_funding),
        "net_per_trade": fmt(outcome.net_per_trade),
        "net_per_day": fmt(outcome.net_per_day),
        "max_drawdown": fmt(outcome.drawdown.absolute),
        "max_drawdown_fraction": fmt(outcome.drawdown.fraction_of_peak),
        "turnover": fmt(outcome.turnover),
        "trade_count": outcome.trade_count,
        "skipped_fills": outcome.skipped_fills,
        "interval_days": fmt(outcome.interval_days),
        "source_net": fmt(outcome.source_net),
        "source_fill_count": outcome.source_fill_count,
    }
    for name in sorted(outcome.baselines):
        row[f"baseline_{name}"] = fmt(outcome.baselines[name])
        row[f"versus_{name}"] = fmt(outcome.versus[name])
    return row
