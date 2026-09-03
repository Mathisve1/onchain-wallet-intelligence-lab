"""Outcome metrics for one follower run and its comparison with baselines.

Net expectancy, drawdown and turnover are what the risk policy says research
optimises for. Comparisons with baselines are made on equal capital: the
follower's return on the capital it actually deployed against each
baseline's return on the same amount. An absolute difference between a copy
that deployed a few hundred and a hold that deployed a hundred thousand is
capital scale, not insight, and is not reported.

Four disclosures travel with every outcome and may never be dropped: the
wallet's classification; the share of the follower's own funding hours the
rate schedule actually priced (unpriced hours were charged as zero, in either
direction, so the net is uncertain by that much rather than bounded); whether
the source wallet's funding history was truncated at the venue's cap; and
whether the liquidity behind the slippage figure was assumed rather than
measured.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence

from .classify import WalletProfile
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

    ``baseline_returns`` and ``versus`` are in return space on equal capital:
    ``versus[name] = return_on_deployed - baseline_returns[name]``. When the
    follower deployed nothing there is no return and no comparison, and both
    are empty rather than zero.
    """

    wallet: str
    latency_ms: int
    classification: str
    #: Share of the follower's own funding settlements the schedule priced.
    #: 1 means every held hour was charged; less means the remainder was
    #: charged as zero and the net is uncertain, not bounded, by that much.
    funding_coverage: Decimal | None
    funding_incomplete: bool
    #: The source wallet's own funding history hit the venue's response cap.
    #: A fact about the source ledger, disclosed; it does not bound the
    #: follower's cost, which comes from the rate schedule.
    source_funding_truncated: bool
    liquidity_assumed: bool
    net: Decimal
    gross: Decimal
    cost_total: Decimal
    cost_fee: Decimal
    cost_spread: Decimal
    cost_slippage: Decimal
    cost_funding: Decimal
    deployed_capital: Decimal
    return_on_deployed: Decimal | None
    net_per_trade: Decimal | None
    net_per_day: Decimal | None
    drawdown: Drawdown
    turnover: Decimal | None
    trade_count: int
    skipped_fills: int
    stale_price_skips: int
    fills_after_cutoff: int
    interval_days: Decimal
    source_net: Decimal
    source_fill_count: int
    baseline_returns: Mapping[str, Decimal]
    versus: Mapping[str, Decimal]


def outcome_for(
    run: FollowerRun,
    source: SourcePnl,
    baseline_returns: Mapping[str, Decimal],
    *,
    profile: WalletProfile,
    funding_truncated: bool,
    liquidity_assumed: bool,
) -> Outcome:
    """Assemble the outcome; the comparison type keeps the two P&Ls apart."""
    comparison = PnlComparison(source=source, follower=run.pnl)
    follower = comparison.follower
    days = Decimal(run.interval.duration_ms) / MS_PER_DAY
    net = follower.net
    deployed = run.peak_deployed_notional
    ret = (net / deployed) if deployed > 0 else None
    versus = {name: ret - value for name, value in baseline_returns.items()} if ret is not None else {}
    expected = run.funding_periods_expected
    coverage = (Decimal(run.funding_periods_priced) / Decimal(expected)) if expected else None
    return Outcome(
        wallet=run.interval.wallet,
        latency_ms=follower.latency_ms,
        classification=profile.classification,
        funding_coverage=coverage,
        funding_incomplete=coverage is not None and coverage < 1,
        source_funding_truncated=funding_truncated,
        liquidity_assumed=liquidity_assumed,
        net=net,
        gross=follower.gross,
        cost_total=follower.costs.total,
        cost_fee=follower.costs.fee,
        cost_spread=follower.costs.spread,
        cost_slippage=follower.costs.slippage,
        cost_funding=follower.costs.funding,
        deployed_capital=deployed,
        return_on_deployed=ret,
        net_per_trade=(net / follower.trade_count) if follower.trade_count else None,
        net_per_day=(net / days) if days > 0 else None,
        drawdown=max_drawdown(run.equity_curve),
        turnover=(run.traded_notional / deployed) if deployed > 0 else None,
        trade_count=follower.trade_count,
        skipped_fills=run.skipped_fills,
        stale_price_skips=run.stale_price_skips,
        fills_after_cutoff=run.fills_after_cutoff,
        interval_days=days,
        source_net=comparison.source.net,
        source_fill_count=comparison.source.fill_count,
        baseline_returns=dict(baseline_returns) if ret is not None else {},
        versus=versus,
    )


def as_row(outcome: Outcome, *, places: int = 4) -> dict[str, object]:
    """A flat, JSON-ready view with decimals rendered as strings.

    The disclosures come first so they cannot be missed. An incomplete
    funding coverage is rendered as a share, never as a directional bound:
    funding can be paid or received, so a missing hour moves the net either way.
    """
    q = Decimal(1).scaleb(-places)

    def fmt(value: Decimal | None) -> str | None:
        return None if value is None else str(value.quantize(q))

    row: dict[str, object] = {
        "wallet": outcome.wallet,
        "latency_ms": outcome.latency_ms,
        "classification": outcome.classification,
        "funding_coverage": fmt(outcome.funding_coverage),
        "funding_incomplete": outcome.funding_incomplete,
        "source_funding_truncated": outcome.source_funding_truncated,
        "liquidity_assumed": outcome.liquidity_assumed,
        "net": fmt(outcome.net),
        "net_certainty": (
            "funding partly unpriced" if outcome.funding_incomplete else "all funding hours priced"
        ),
        "gross": fmt(outcome.gross),
        "cost_total": fmt(outcome.cost_total),
        "cost_fee": fmt(outcome.cost_fee),
        "cost_spread": fmt(outcome.cost_spread),
        "cost_slippage": fmt(outcome.cost_slippage),
        "cost_funding": fmt(outcome.cost_funding),
        "deployed_capital": fmt(outcome.deployed_capital),
        "return_on_deployed": fmt(outcome.return_on_deployed),
        "net_per_trade": fmt(outcome.net_per_trade),
        "net_per_day": fmt(outcome.net_per_day),
        "max_drawdown": fmt(outcome.drawdown.absolute),
        "max_drawdown_fraction": fmt(outcome.drawdown.fraction_of_peak),
        "turnover": fmt(outcome.turnover),
        "trade_count": outcome.trade_count,
        "skipped_fills": outcome.skipped_fills,
        "stale_price_skips": outcome.stale_price_skips,
        "fills_after_cutoff": outcome.fills_after_cutoff,
        "interval_days": fmt(outcome.interval_days),
        "source_net": fmt(outcome.source_net),
        "source_fill_count": outcome.source_fill_count,
    }
    for name in sorted(outcome.baseline_returns):
        row[f"baseline_return_{name}"] = fmt(outcome.baseline_returns[name])
        row[f"versus_{name}"] = fmt(outcome.versus[name])
    return row
