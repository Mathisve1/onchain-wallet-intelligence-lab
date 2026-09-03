"""Study orchestration: every wallet, every latency, against every baseline.

This is the one place the pieces meet. It takes certified intervals from the
coverage ledger, runs the follower at each latency on the grid, builds each
baseline through the same simulator, and assembles an :class:`Outcome` per
wallet per latency. It refuses, by construction, to score a wallet whose
interval the ledger will not certify.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence

from . import baselines
from .costs import CostModel
from .coverage import CoverageLedger, KnownInterval, UnknownIntervalError
from .execution import LATENCY_GRID_MS, FollowerConfig, simulate_follower, source_pnl
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
    outcomes: tuple[Outcome, ...]
    refusal: str | None
    matched_peers: tuple[str, ...]


def run_study(
    *,
    fills_by_wallet: Mapping[str, Sequence[SourceFill]],
    market: MarketData,
    ledger: CoverageLedger,
    config: StudyConfig,
    wallets: Sequence[str] | None = None,
    window: tuple[int, int] | None = None,
) -> tuple[WalletStudy, ...]:
    """Score each wallet over its certified interval at every latency.

    ``window`` narrows every wallet to the same ``[start, end]``; without it
    each wallet uses its largest certified interval. A wallet the ledger
    cannot certify is returned with a refusal, never with a zero.
    """
    selected = list(wallets) if wallets is not None else sorted(fills_by_wallet)
    results: list[WalletStudy] = []
    for wallet in selected:
        try:
            interval = _certify(ledger, wallet, window)
        except UnknownIntervalError as exc:
            results.append(WalletStudy(wallet, None, (), str(exc), ()))
            continue
        fills = fills_by_wallet.get(wallet, ())
        source = source_pnl(interval, fills)
        outcomes: list[Outcome] = []
        peers_seen: tuple[str, ...] = ()
        for latency in config.latencies_ms:
            run = simulate_follower(
                interval, latency_ms=latency, fills=fills, market=market,
                cost_model=config.cost_model, config=config.follower,
            )
            scores, peers = _baseline_nets(
                interval, latency, source.fill_count, fills_by_wallet, market, ledger, config
            )
            peers_seen = peers or peers_seen
            outcomes.append(outcome_for(run, source, scores))
        results.append(WalletStudy(wallet, interval, tuple(outcomes), None, peers_seen))
    return tuple(results)


def _certify(ledger: CoverageLedger, wallet: str, window: tuple[int, int] | None) -> KnownInterval:
    if window is not None:
        return ledger.certify(wallet, window[0], window[1])
    interval = ledger.largest_known(wallet)
    if interval is None:
        raise UnknownIntervalError(f"{wallet} has no complete observed interval")
    return interval


def _baseline_nets(
    interval: KnownInterval, latency_ms: int, target_fill_count: int,
    fills_by_wallet: Mapping[str, Sequence[SourceFill]], market: MarketData,
    ledger: CoverageLedger, config: StudyConfig,
) -> tuple[dict[str, Decimal], tuple[str, ...]]:
    scores: dict[str, Decimal] = {"no_trade": baselines.no_trade(interval)}
    scores["buy_and_hold"] = baselines.buy_and_hold(
        interval, coin=config.benchmark_coin, market=market,
        cost_model=config.cost_model, config=config.follower,
    ).pnl.net
    scores["momentum"] = baselines.momentum(
        interval, coin=config.benchmark_coin, market=market, cost_model=config.cost_model,
        config=config.follower, lookback_ms=config.momentum_lookback_ms,
        step_ms=config.momentum_step_ms,
    ).pnl.net
    matched, peers = baselines.matched_random(
        interval, latency_ms=latency_ms, target_fill_count=target_fill_count,
        pool=fills_by_wallet, market=market, cost_model=config.cost_model,
        config=config.follower, certify=ledger.certify, seed=config.random_seed,
        sample_size=config.random_sample_size,
    )
    if matched is not None:
        scores["matched_random"] = matched
    return scores, peers
