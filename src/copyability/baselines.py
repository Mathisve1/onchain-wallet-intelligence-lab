"""Baselines a copied wallet has to beat before a positive number means anything.

Every baseline is expressed as a stream of synthetic source fills and run
through the very same follower simulator, at the same costs, over the same
certified interval. That is deliberate: a baseline computed by a different
code path with different costs would not be a comparison.

* ``no_trade``: hold cash. Net is exactly zero.
* ``buy_and_hold``: buy the coin with the follower's capital at the start of
  the interval, sell at the end.
* ``momentum``: at each step, be long if the price rose over the lookback,
  flat otherwise.
* ``matched_random``: copy other wallets of similar activity, chosen with a
  seeded generator, and average their nets.
"""

from __future__ import annotations

import random
from decimal import Decimal
from typing import Mapping, Sequence

from .costs import CostModel
from .coverage import KnownInterval
from .execution import FollowerConfig, FollowerRun, simulate_follower
from .inputs import SIDE_BUY, SIDE_SELL, InputError, MarketData, SourceFill
from .pit import PointInTimeView

BASELINE_NAMES: tuple[str, ...] = ("no_trade", "buy_and_hold", "momentum", "matched_random")


def no_trade(interval: KnownInterval) -> Decimal:
    """Cash. Nothing bought, nothing paid, nothing earned."""
    if not isinstance(interval, KnownInterval):
        raise InputError("baselines score only a certified interval")
    return Decimal(0)


def buy_and_hold(
    interval: KnownInterval, *, coin: str, market: MarketData, cost_model: CostModel,
    config: FollowerConfig,
) -> FollowerRun:
    view = PointInTimeView(market, (), horizon_ms=interval.end_ms)
    entry = view.price_at(coin, interval.start_ms)
    if entry is None:
        raise InputError(f"no {coin} price at the start of the interval")
    size = config.capital / entry.price / config.size_scale
    fills = (
        _synthetic(interval.wallet, coin, interval.start_ms, SIDE_BUY, entry.price, size, 1),
    )
    exit_point = view.price_at(coin, interval.end_ms)
    if exit_point is None:
        raise InputError(f"no {coin} price at the end of the interval")
    fills += (
        _synthetic(interval.wallet, coin, interval.end_ms, SIDE_SELL, exit_point.price, size, 2),
    )
    return simulate_follower(
        interval, latency_ms=0, fills=fills, market=market, cost_model=cost_model, config=config
    )


def momentum(
    interval: KnownInterval, *, coin: str, market: MarketData, cost_model: CostModel,
    config: FollowerConfig, lookback_ms: int, step_ms: int,
) -> FollowerRun:
    """Long when price rose over ``lookback_ms``, flat otherwise, every ``step_ms``."""
    if lookback_ms <= 0 or step_ms <= 0:
        raise InputError("lookback and step must be positive")
    view = PointInTimeView(market, (), horizon_ms=interval.end_ms)
    fills: list[SourceFill] = []
    held = Decimal(0)  # size currently long, in source units; sold in full when flat
    trade_id = 0
    t = interval.start_ms + lookback_ms
    while t <= interval.end_ms:
        now = view.price_at(coin, t)
        then = view.price_at(coin, t - lookback_ms)
        if now is not None and then is not None:
            want_long = now.price > then.price
            if want_long and held == 0:
                trade_id += 1
                held = config.capital / now.price / config.size_scale
                fills.append(_synthetic(interval.wallet, coin, t, SIDE_BUY, now.price, held, trade_id))
            elif not want_long and held != 0:
                trade_id += 1
                fills.append(_synthetic(interval.wallet, coin, t, SIDE_SELL, now.price, held, trade_id))
                held = Decimal(0)
        t += step_ms
    if held != 0:
        exit_point = view.price_at(coin, interval.end_ms)
        if exit_point is not None:
            trade_id += 1
            fills.append(_synthetic(
                interval.wallet, coin, interval.end_ms, SIDE_SELL, exit_point.price, held, trade_id,
            ))
    return simulate_follower(
        interval, latency_ms=0, fills=tuple(fills), market=market, cost_model=cost_model, config=config
    )


def matched_random(
    interval: KnownInterval, *, latency_ms: int, target_fill_count: int,
    pool: Mapping[str, Sequence[SourceFill]], market: MarketData, cost_model: CostModel,
    config: FollowerConfig, certify, seed: int, sample_size: int, tolerance: Decimal = Decimal("0.5"),
) -> tuple[Decimal | None, tuple[str, ...]]:
    """Mean follower net over wallets of similar activity, chosen by a seeded RNG.

    ``certify(wallet, start, end)`` must return a :class:`KnownInterval` or
    raise; wallets whose coverage does not certify the same window are not
    eligible, since scoring them would be scoring a gap. Returns ``None`` and
    an empty tuple when no eligible peer exists, which the caller must report
    rather than treat as zero.
    """
    if sample_size <= 0:
        raise InputError("sample_size must be positive")
    lo = Decimal(target_fill_count) * (1 - tolerance)
    hi = Decimal(target_fill_count) * (1 + tolerance)
    candidates: list[str] = []
    for wallet in sorted(pool):
        if wallet == interval.wallet:
            continue
        count = sum(1 for f in pool[wallet] if interval.start_ms <= f.time_ms <= interval.end_ms)
        if count == 0 or not (lo <= count <= hi):
            continue
        try:
            certify(wallet, interval.start_ms, interval.end_ms)
        except Exception:
            continue
        candidates.append(wallet)
    if not candidates:
        return None, ()
    chosen = tuple(random.Random(seed).sample(candidates, min(sample_size, len(candidates))))
    nets: list[Decimal] = []
    for wallet in chosen:
        peer_interval = certify(wallet, interval.start_ms, interval.end_ms)
        run = simulate_follower(
            peer_interval, latency_ms=latency_ms, fills=pool[wallet], market=market,
            cost_model=cost_model, config=config,
        )
        nets.append(run.pnl.net)
    return sum(nets, Decimal(0)) / len(nets), chosen


def _synthetic(
    wallet: str, coin: str, time_ms: int, side: str, price: Decimal, size: Decimal, trade_id: int
) -> SourceFill:
    # Baseline fills carry no source economics: the strategy is not a wallet.
    return SourceFill(
        wallet=wallet, coin=coin, time_ms=time_ms, side=side, price=price, size=size,
        fee=Decimal(0), closed_pnl=Decimal(0), trade_id=trade_id,
    )
