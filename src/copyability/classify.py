"""Characterise a wallet before it is scored: market maker or directional.

A market maker that scores well is not a discovery. Its edge is the spread
it earns by resting orders, which a follower crossing that same spread
cannot copy; scoring it as if it were directional would manufacture a false
positive. So every wallet is classified first, from its own fills, and the
label travels with every outcome.

Three measurements, each stated plainly so the thresholds can be argued:

* ``maker_share``: fraction of fills that rested rather than crossed, when
  the venue said which. Market makers rest.
* ``two_sided_share``: fraction of fills with an opposite-side fill in the
  same coin within a short window. Market makers buy and sell the same coin
  continuously.
* ``median_holding_ms``: median time from opening a position in a coin to
  being flat in it again. Market makers hold inventory briefly.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from decimal import Decimal
from statistics import median
from typing import Sequence

from .coverage import KnownInterval
from .inputs import SIDE_BUY, SourceFill

PROBABLE_MARKET_MAKER = "PROBABLE_MARKET_MAKER"
DIRECTIONAL = "DIRECTIONAL"
INSUFFICIENT_FILLS = "INSUFFICIENT_FILLS"

MS_PER_DAY = Decimal(86_400_000)


@dataclass(frozen=True, slots=True)
class ClassifierThresholds:
    """Every knob the label depends on, in one place, with its default."""

    min_fills: int = 20
    two_sided_window_ms: int = 60_000
    maker_share_threshold: Decimal = Decimal("0.6")
    two_sided_threshold: Decimal = Decimal("0.5")
    short_holding_ms: int = 300_000


DEFAULT_THRESHOLDS = ClassifierThresholds()


@dataclass(frozen=True, slots=True)
class WalletProfile:
    wallet: str
    fill_count: int
    coins_traded: int
    maker_share: Decimal | None
    two_sided_share: Decimal
    median_holding_ms: int | None
    round_trips: int
    flat_returns_per_day: Decimal
    classification: str
    reasons: tuple[str, ...]


def profile_wallet(
    interval: KnownInterval,
    fills: Sequence[SourceFill],
    thresholds: ClassifierThresholds = DEFAULT_THRESHOLDS,
) -> WalletProfile:
    rows = sorted(
        (f for f in fills if f.wallet == interval.wallet and interval.start_ms <= f.time_ms <= interval.end_ms),
        key=lambda f: (f.time_ms, f.trade_id),
    )
    coins = {f.coin for f in rows}
    maker_share = _maker_share(rows)
    two_sided = _two_sided_share(rows, thresholds.two_sided_window_ms)
    holdings = _round_trip_durations(rows)
    median_holding = int(median(holdings)) if holdings else None
    days = Decimal(interval.duration_ms) / MS_PER_DAY
    flat_per_day = (Decimal(len(holdings)) / days) if days > 0 else Decimal(0)

    reasons: list[str] = []
    if len(rows) < thresholds.min_fills:
        label = INSUFFICIENT_FILLS
        reasons.append(f"{len(rows)} fills < {thresholds.min_fills}")
    else:
        maker_says_mm = maker_share is not None and maker_share >= thresholds.maker_share_threshold
        churn_says_mm = (
            two_sided >= thresholds.two_sided_threshold
            and median_holding is not None
            and median_holding <= thresholds.short_holding_ms
        )
        if maker_says_mm:
            reasons.append(f"maker share {maker_share:.2f} >= {thresholds.maker_share_threshold}")
        if churn_says_mm:
            reasons.append(
                f"two-sided share {two_sided:.2f} >= {thresholds.two_sided_threshold} and "
                f"median holding {median_holding} ms <= {thresholds.short_holding_ms} ms"
            )
        label = PROBABLE_MARKET_MAKER if (maker_says_mm or churn_says_mm) else DIRECTIONAL
        if label == DIRECTIONAL:
            reasons.append(
                f"maker share {'n/a' if maker_share is None else f'{maker_share:.2f}'}, "
                f"two-sided share {two_sided:.2f}, median holding "
                f"{'n/a' if median_holding is None else median_holding} ms"
            )
    return WalletProfile(
        wallet=interval.wallet, fill_count=len(rows), coins_traded=len(coins), maker_share=maker_share,
        two_sided_share=two_sided, median_holding_ms=median_holding, round_trips=len(holdings),
        flat_returns_per_day=flat_per_day, classification=label, reasons=tuple(reasons),
    )


def _maker_share(rows: Sequence[SourceFill]) -> Decimal | None:
    known = [f for f in rows if f.crossed is not None]
    if not known:
        return None
    return Decimal(sum(1 for f in known if not f.crossed)) / Decimal(len(known))


def _two_sided_share(rows: Sequence[SourceFill], window_ms: int) -> Decimal:
    if not rows:
        return Decimal(0)
    by_coin_side: dict[tuple[str, str], list[int]] = {}
    for f in rows:
        by_coin_side.setdefault((f.coin, f.side), []).append(f.time_ms)
    hits = 0
    for f in rows:
        opposite = SIDE_BUY if f.side != SIDE_BUY else "A"
        times = by_coin_side.get((f.coin, opposite), [])
        lo = bisect_left(times, f.time_ms - window_ms)
        hi = bisect_right(times, f.time_ms + window_ms)
        if hi > lo:
            hits += 1
    return Decimal(hits) / Decimal(len(rows))


def _round_trip_durations(rows: Sequence[SourceFill]) -> list[int]:
    """Milliseconds from a coin's position leaving zero to returning to it."""
    position: dict[str, Decimal] = {}
    opened_at: dict[str, int] = {}
    durations: list[int] = []
    for f in rows:
        before = position.get(f.coin, Decimal(0))
        after = before + f.signed_size
        position[f.coin] = after
        if before == 0 and after != 0:
            opened_at[f.coin] = f.time_ms
        elif before != 0 and (after == 0 or (after > 0) != (before > 0)):
            start = opened_at.pop(f.coin, None)
            if start is not None:
                durations.append(f.time_ms - start)
            if after != 0:
                opened_at[f.coin] = f.time_ms
    return durations
