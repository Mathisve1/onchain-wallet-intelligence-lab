"""Study orchestration: every wallet, every latency, against every baseline.

This is the one place the pieces meet. It takes certified intervals from the
coverage ledger, classifies the wallet before anything is scored, runs the
follower at each latency on the grid, measures how much capital the copy
actually deployed, runs every baseline on exactly that capital through the
same simulator, and assembles an :class:`Outcome` per wallet per latency
carrying the classification and the funding-truncation label.

It refuses, by construction, to score a wallet whose interval the ledger
will not certify.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence

from . import baselines
from .classify import DEFAULT_THRESHOLDS, ClassifierThresholds, WalletProfile, profile_wallet
from .costs import CostModel
from .coverage import CoverageLedger, KnownInterval, UnknownIntervalError
from .execution import LATENCY_GRID_MS, FollowerConfig, FollowerRun, simulate_follower, source_pnl
from .inputs import InputError, MarketData, SourceFill
from .metrics import Outcome, outcome_for


@dataclass(frozen=True, slots=True)
class StudyConfig:
    """Parameters shared by every wallet in a study run."""

    follower: FollowerConfig
    cost_model: CostModel
    benchmark_coin: str
    momentum_lookback_ms: int
    momentum_step_ms: int
    random_seed: int
    random_sample_size: int
    latencies_ms: tuple[int, ...] = LATENCY_GRID_MS
    thresholds: ClassifierThresholds = DEFAULT_THRESHOLDS

    def __post_init__(self) -> None:
        if not self.benchmark_coin:
            raise InputError("a benchmark coin is required for buy-and-hold and momentum")
        if not self.latencies_ms or any(l < 0 for l in self.latencies_ms):
            raise InputError("latencies must be nonnegative and nonempty")


@dataclass(frozen=True, slots=True)
class WalletStudy:
    """All outcomes for one wallet plus what could not be scored and why."""

    wallet: str
    interval: KnownInterval | None
    profile: WalletProfile | None
    funding_truncated: bool
    outcomes: tuple[Outcome, ...]
    refusal: str | None
    matched_peers: tuple[str, ...]


def run_study(
    *,
    fills_by_wallet: Mapping[str, Sequence[SourceFill]],
    market: MarketData,
    ledger: CoverageLedger,
    config: StudyConfig,
    funding_truncated: Mapping[str, bool],
    wallets: Sequence[str] | None = None,
    window: tuple[int, int] | None = None,
) -> tuple[WalletStudy, ...]:
    """Score each wallet over its certified interval at every latency.

    ``funding_truncated`` is required, not optional: a caller that does not
    know whether a wallet's funding history is complete has no business
    reporting its net. ``window`` narrows every wallet to the same
    ``[start, end]``; without it each wallet uses its largest certified
    interval. A wallet the ledger cannot certify is returned with a refusal,
    never with a zero.
    """
    selected = list(wallets) if wallets is not None else sorted(fills_by_wallet)
    results: list[WalletStudy] = []
    for wallet in selected:
        if wallet not in funding_truncated:
            raise InputError(f"funding truncation status unknown for {wallet}; refusing to score")
        truncated = bool(funding_truncated[wallet])
        try:
            interval = _certify(ledger, wallet, window)
        except UnknownIntervalError as exc:
            results.append(WalletStudy(wallet, None, None, truncated, (), str(exc), ()))
            continue
        fills = fills_by_wallet.get(wallet, ())
        profile = profile_wallet(interval, fills, config.thresholds)
        source = source_pnl(interval, fills)
        outcomes: list[Outcome] = []
        peers_seen: tuple[str, ...] = ()
        for latency in config.latencies_ms:
            run = _follower_on_deployed_capital(interval, latency, fills, market, config)
            returns, peers = _baseline_returns(
                interval, latency, run, source.fill_count, fills_by_wallet, market, ledger, config
            )
            peers_seen = peers or peers_seen
            outcomes.append(outcome_for(run, source, returns, profile=profile, funding_truncated=truncated))
        results.append(WalletStudy(wallet, interval, profile, truncated, tuple(outcomes), None, peers_seen))
    return tuple(results)


def _follower_on_deployed_capital(
    interval: KnownInterval, latency_ms: int, fills: Sequence[SourceFill], market: MarketData,
    config: StudyConfig,
) -> FollowerRun:
    """Run once to measure deployed capital, then again with that as the base.

    The first pass uses whatever nominal capital the config carries; only the
    copy's positions determine how much notional it actually holds. The
    second pass restarts the equity curve from that amount so drawdown is a
    fraction of capital that was really at work, not of an arbitrary number.
    """
    first = simulate_follower(
        interval, latency_ms=latency_ms, fills=fills, market=market,
        cost_model=config.cost_model, config=config.follower,
    )
    deployed = first.peak_deployed_notional
    if deployed <= 0:
        return first
    sized = FollowerConfig(capital=deployed, size_scale=config.follower.size_scale)
    return simulate_follower(
        interval, latency_ms=latency_ms, fills=fills, market=market,
        cost_model=config.cost_model, config=sized,
    )


def _certify(ledger: CoverageLedger, wallet: str, window: tuple[int, int] | None) -> KnownInterval:
    if window is not None:
        return ledger.certify(wallet, window[0], window[1])
    interval = ledger.largest_known(wallet)
    if interval is None:
        raise UnknownIntervalError(f"{wallet} has no complete observed interval")
    return interval


def _baseline_returns(
    interval: KnownInterval, latency_ms: int, run: FollowerRun, target_fill_count: int,
    fills_by_wallet: Mapping[str, Sequence[SourceFill]], market: MarketData,
    ledger: CoverageLedger, config: StudyConfig,
) -> tuple[dict[str, Decimal], tuple[str, ...]]:
    """Every baseline's return on exactly the capital the follower deployed."""
    capital = run.peak_deployed_notional
    if capital <= 0:
        return {}, ()
    equal = FollowerConfig(capital=capital, size_scale=Decimal(1))
    returns: dict[str, Decimal] = {"no_trade": baselines.no_trade(interval) / capital}
    hold = baselines.buy_and_hold(
        interval, coin=config.benchmark_coin, market=market, cost_model=config.cost_model, config=equal,
    )
    returns["buy_and_hold"] = hold.pnl.net / capital
    mom = baselines.momentum(
        interval, coin=config.benchmark_coin, market=market, cost_model=config.cost_model,
        config=equal, lookback_ms=config.momentum_lookback_ms, step_ms=config.momentum_step_ms,
    )
    returns["momentum"] = mom.pnl.net / capital
    matched, peers = baselines.matched_random(
        interval, latency_ms=latency_ms, target_fill_count=target_fill_count, pool=fills_by_wallet,
        market=market, cost_model=config.cost_model, config=config.follower, certify=ledger.certify,
        seed=config.random_seed, sample_size=config.random_sample_size,
    )
    if matched is not None:
        returns["matched_random"] = matched
    return returns, peers
