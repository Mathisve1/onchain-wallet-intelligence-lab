"""Study orchestration: every wallet, every latency, against every baseline.

This is the one place the pieces meet. It takes certified intervals from the
coverage ledger, classifies the wallet before anything is scored, runs the
follower at each latency on the grid against one common decision cutoff,
measures how much capital the copy actually deployed, runs every baseline
on exactly that capital through the same simulator, and assembles an
:class:`Outcome` per wallet per latency carrying every disclosure.

It refuses, by construction, to score a wallet whose interval the ledger
will not certify, and it turns any other wallet-level failure into a named
refusal rather than a zero or an aborted study.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Mapping, Sequence

from . import baselines
from .classify import DEFAULT_THRESHOLDS, ClassifierThresholds, WalletProfile, profile_wallet
from .costs import CostModel
from .coverage import CoverageLedger, KnownInterval, UnknownIntervalError
from .execution import (
    LATENCY_GRID_MS,
    FollowerConfig,
    FollowerRun,
    opening_positions_for,
    simulate_follower,
    source_pnl,
)
from .inputs import InputError, MarketData, SourceFill
from .metrics import Outcome, outcome_for

#: Default bound on how old a price may be to execute or mark against: a
#: quarter of an hour, the largest latency on the grid.
DEFAULT_MAX_PRICE_AGE_MS = 900_000


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
    max_price_age_ms: int | None = DEFAULT_MAX_PRICE_AGE_MS
    #: Activity band for matched-random peers: a peer's fill count over the
    #: window must lie within this fraction either side of the target's.
    random_tolerance: Decimal = Decimal("0.5")

    def __post_init__(self) -> None:
        if not self.benchmark_coin:
            raise InputError("a benchmark coin is required for buy-and-hold and momentum")
        # Decimal arithmetic downstream: a float here would raise inside the
        # baseline, after every wallet's copy has been simulated.
        object.__setattr__(self, "random_tolerance", Decimal(str(self.random_tolerance)))
        if not (0 <= self.random_tolerance < 1):
            raise InputError("random_tolerance must lie in [0, 1)")
        if not self.latencies_ms or any(latency < 0 for latency in self.latencies_ms):
            raise InputError("latencies must be nonnegative and nonempty")
        if self.max_price_age_ms is not None and self.max_price_age_ms <= 0:
            raise InputError("max_price_age_ms must be positive or None")


@dataclass(frozen=True, slots=True)
class WalletStudy:
    """All outcomes for one wallet plus what could not be scored and why."""

    wallet: str
    interval: KnownInterval | None
    profile: WalletProfile | None
    funding_truncated: bool
    outcomes: tuple[Outcome, ...]
    refusal: str | None
    #: The peers that actually entered the matched-random mean at the last
    #: latency with a sample, and the sampled peers that dropped out, by
    #: reason. A reporter that names the peers behind one latency's baseline
    #: reads ``matched_by_latency`` for that latency instead: the contributing
    #: set can differ from one latency to the next.
    matched_peers: tuple[str, ...]
    matched_peers_dropped: dict[str, str] = field(default_factory=dict)
    matched_by_latency: dict[int, baselines.MatchedRandom] = field(default_factory=dict)


MarketFor = Callable[[str], MarketData]


def run_study(
    *,
    fills_by_wallet: Mapping[str, Sequence[SourceFill]],
    market: MarketData | None,
    ledger: CoverageLedger,
    config: StudyConfig,
    funding_truncated: Mapping[str, bool],
    wallets: Sequence[str] | None = None,
    window: tuple[int, int] | None = None,
    market_for: MarketFor | None = None,
) -> tuple[WalletStudy, ...]:
    """Score each wallet over its certified interval at every latency.

    ``funding_truncated`` is required, not optional: a caller that does not
    know whether a wallet's funding history is complete has no business
    reporting its net. ``market_for(wallet)`` supplies a per-wallet market
    (for a price series that excludes the wallet's own fills); ``market`` is
    the shared fallback. ``window`` narrows every wallet to the same
    ``[start, end]``; without it each wallet uses its largest certified
    interval. Every latency copies the same source fills: the decision cutoff
    is the interval end minus the largest latency on the grid.

    A wallet the ledger cannot certify, or whose inputs are missing something
    the simulator needs, is returned with a refusal, never with a zero, and
    never takes the other wallets down with it.
    """
    if market is None and market_for is None:
        raise InputError("run_study needs a market or a market_for callable")
    selected = list(wallets) if wallets is not None else sorted(fills_by_wallet)
    horizon = max(config.latencies_ms)
    results: list[WalletStudy] = []
    for wallet in selected:
        truncated = bool(funding_truncated.get(wallet, False))
        if wallet not in funding_truncated:
            results.append(WalletStudy(wallet, None, None, False, (),
                                       "funding truncation status unknown; refusing to score", ()))
            continue
        try:
            interval = _certify(ledger, wallet, window)
            wallet_market = market_for(wallet) if market_for is not None else market
            assert wallet_market is not None
            fills = fills_by_wallet.get(wallet, ())
            profile = profile_wallet(interval, fills, config.thresholds)
            source = source_pnl(interval, fills)
            cutoff = interval.end_ms - horizon
            if cutoff < interval.start_ms:
                raise InputError("interval shorter than the largest latency on the grid")
            assumed = any(p.assumed for p in wallet_market.liquidity.values())
            opening = opening_positions_for(interval, fills)
            outcomes: list[Outcome] = []
            peers_seen: tuple[str, ...] = ()
            dropped_seen: dict[str, str] = {}
            by_latency: dict[int, baselines.MatchedRandom] = {}
            for latency in config.latencies_ms:
                run = _follower_on_deployed_capital(
                    interval, latency, fills, wallet_market, config, cutoff, opening
                )
                returns, matched = _baseline_returns(
                    interval, latency, run, source.fill_count, fills_by_wallet, wallet_market,
                    ledger, config, cutoff,
                )
                if matched is not None:
                    by_latency[latency] = matched
                    if matched.chosen:
                        peers_seen, dropped_seen = matched.contributed, dict(matched.dropped)
                outcomes.append(outcome_for(
                    run, source, returns, profile=profile, funding_truncated=truncated,
                    liquidity_assumed=assumed,
                ))
        except (UnknownIntervalError, InputError) as exc:
            results.append(WalletStudy(wallet, None, None, truncated, (), f"{type(exc).__name__}: {exc}", ()))
            continue
        results.append(WalletStudy(wallet, interval, profile, truncated, tuple(outcomes), None,
                                   peers_seen, dropped_seen, by_latency))
    return tuple(results)


def _follower_on_deployed_capital(
    interval: KnownInterval, latency_ms: int, fills: Sequence[SourceFill], market: MarketData,
    config: StudyConfig, cutoff_ms: int, opening: Mapping[str, Decimal],
) -> FollowerRun:
    """Run once to measure deployed capital, then again with that as the base.

    The first pass uses whatever nominal capital the config carries; only the
    copy's positions determine how much notional it actually holds. The
    second pass restarts the equity curve from that amount so drawdown is a
    fraction of capital that was really at work, not of an arbitrary number.

    ``opening`` is what the source already held when the interval opened. It
    has to reach the simulator on both passes: without it a source fill that
    closes a pre-window position opens an inverted one for the follower, and
    the copy is scored on a trade the wallet never made.
    """
    first = simulate_follower(
        interval, latency_ms=latency_ms, fills=fills, market=market, cost_model=config.cost_model,
        config=config.follower, decision_cutoff_ms=cutoff_ms, max_price_age_ms=config.max_price_age_ms,
        opening_positions=opening,
    )
    deployed = first.peak_deployed_notional
    if deployed <= 0:
        return first
    sized = FollowerConfig(capital=deployed, size_scale=config.follower.size_scale)
    return simulate_follower(
        interval, latency_ms=latency_ms, fills=fills, market=market, cost_model=config.cost_model,
        config=sized, decision_cutoff_ms=cutoff_ms, max_price_age_ms=config.max_price_age_ms,
        opening_positions=opening,
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
    ledger: CoverageLedger, config: StudyConfig, cutoff_ms: int,
) -> tuple[dict[str, Decimal], baselines.MatchedRandom | None]:
    """Every baseline's return on exactly the capital the follower deployed."""
    capital = run.peak_deployed_notional
    if capital <= 0:
        # Nothing deployed at this latency: no baseline is computable and no
        # peer was sampled. ``None``, not an empty sample, so the caller can
        # tell "no baseline" from "a baseline nobody entered".
        return {}, None
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
    # Peers are copied under exactly the target's convention: the same common
    # decision cutoff and the same price-age bound. Without both, a peer fill
    # after the cutoff, or a peer priced on a quote the target would have
    # refused as stale, enters M_i while R_i excludes it, and "the same
    # measure" the plan promises is not what gets subtracted.
    matched = baselines.matched_random(
        interval, latency_ms=latency_ms, target_fill_count=target_fill_count, pool=fills_by_wallet,
        market=market, cost_model=config.cost_model, config=config.follower, certify=ledger.certify,
        seed=config.random_seed, sample_size=config.random_sample_size, tolerance=config.random_tolerance,
        decision_cutoff_ms=cutoff_ms, max_price_age_ms=config.max_price_age_ms,
    )
    if matched.mean is not None:
        returns["matched_random"] = matched.mean
    return returns, matched
