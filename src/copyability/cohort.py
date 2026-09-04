"""Choosing the wallets a study is allowed to evaluate, and freezing the list.

A cohort picked after the outcomes are known is not a cohort, it is a result.
So the selection runs once, from facts observable before scoring, and the
frozen list is hashed: any later addition, removal or re-run against a
different set is visible by comparing one hex digest.

Three filters, in order, each answering a question that would otherwise
invalidate a copy result:

* **Classification.** Only ``DIRECTIONAL`` wallets survive. A market maker's
  edge is the spread it earns by resting, which a follower crossing that
  spread cannot copy, and a wallet with too few fills was never characterised
  at all. Both are excluded, and counted apart from each other.
* **Rebate dependence.** A wallet whose income is mostly negative fees is
  being paid to provide liquidity. The follower is a taker and is paid
  nothing, so that income does not travel.
* **Instrument scope.** A wallet that mostly trades instruments the study
  cannot price or fund would be scored on the fraction it happens to cover.
  Only wallets trading mostly in-scope coins are evaluable.

Everything here is deterministic and network-free: the same fills in, the
same cohort and the same digest out.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping, Sequence

from .classify import (
    DEFAULT_THRESHOLDS,
    DIRECTIONAL,
    INSUFFICIENT_FILLS,
    PROBABLE_MARKET_MAKER,
    ClassifierThresholds,
    WalletProfile,
    profile_wallet,
)
from .coverage import CoverageLedger, ObservedInterval
from .inputs import SourceFill

#: Prefixes the venue uses for instruments this study does not model.
SPOT_PREFIX = "@"
BUILDER_PREFIX = "xyz:"

EVALUABLE = "EVALUABLE"
REASON_REBATE = "REBATE_DEPENDENT"
REASON_SCOPE = "OUT_OF_SCOPE"

#: The stage counters, in the order a wallet meets them.
STAGE_NAMES = (
    "discovered",
    "prefiltered_directional",
    "probable_market_maker",
    "rebate_excluded",
    "scope_excluded",
    "insufficient_fills",
    "evaluable",
)


def characterise(
    wallet: str,
    fills: Sequence[SourceFill],
    *,
    start_ms: int,
    end_ms: int,
    thresholds: ClassifierThresholds = DEFAULT_THRESHOLDS,
) -> WalletProfile:
    """Label one wallet over a window the caller states it observed in full.

    The window is certified through a ledger rather than asserted, because
    :class:`~.coverage.KnownInterval` cannot be built by hand: the classifier
    refuses to characterise a period nobody claims to have watched.
    """
    interval = CoverageLedger(
        [ObservedInterval(wallet, start_ms, end_ms, True, "characterisation")]
    ).certify(wallet, start_ms, end_ms)
    return profile_wallet(interval, fills, thresholds)


def _in_window(fills: Sequence[SourceFill], start_ms: int, end_ms: int) -> list[SourceFill]:
    return [f for f in fills if start_ms <= f.time_ms <= end_ms]


def rebate_dependence(
    fills: Sequence[SourceFill], *, start_ms: int, end_ms: int
) -> Decimal | None:
    """Negative-fee income as a fraction of gross closed profit.

    ``None`` when the wallet closed nothing profitable in the window: a ratio
    against a zero denominator is not a small number, it is no measurement,
    and saying so keeps the caller from reading zero as "not rebate driven".
    """
    rows = _in_window(fills, start_ms, end_ms)
    rebates = sum((-f.fee for f in rows if f.fee < 0), Decimal(0))
    gross = sum((f.closed_pnl for f in rows if f.closed_pnl > 0), Decimal(0))
    if gross == 0:
        return None
    return rebates / gross


@dataclass(frozen=True, slots=True)
class InstrumentScope:
    """Which coins the study can actually price, fund and cost.

    The three sets are measured, not assumed: a coin is in scope only when
    funding was collected for it *and* its candle history is complete, and
    never when it was explicitly excluded. Anything unmeasured is out.
    """

    funding_coins: frozenset[str]
    candle_complete_coins: frozenset[str]
    excluded_coins: frozenset[str] = frozenset()

    def in_scope(self, coin: str) -> bool:
        if coin.startswith(SPOT_PREFIX) or coin.startswith(BUILDER_PREFIX):
            return False
        if coin in self.excluded_coins:
            return False
        return coin in self.funding_coins and coin in self.candle_complete_coins


def scope_share(
    fills: Sequence[SourceFill], scope: InstrumentScope, *, start_ms: int, end_ms: int
) -> Decimal:
    """Fraction of traded notional that falls on in-scope coins."""
    rows = _in_window(fills, start_ms, end_ms)
    total = sum((f.notional for f in rows), Decimal(0))
    if total == 0:
        return Decimal(0)
    inside = sum((f.notional for f in rows if scope.in_scope(f.coin)), Decimal(0))
    return inside / total


@dataclass(frozen=True, slots=True)
class CohortSelection:
    """The frozen outcome of one selection pass."""

    evaluable: tuple[str, ...]
    stage_counts: dict[str, int]
    per_wallet: dict[str, str]

    @property
    def count(self) -> int:
        return len(self.evaluable)


def select_cohort(
    candidates: Mapping[str, Sequence[SourceFill]],
    *,
    scope: InstrumentScope,
    characterisation_window: tuple[int, int],
    rebate_max: Decimal = Decimal("0.25"),
    scope_min: Decimal = Decimal("0.5"),
    thresholds: ClassifierThresholds = DEFAULT_THRESHOLDS,
) -> CohortSelection:
    """Apply the three filters in order and record why each wallet fell out."""
    start_ms, end_ms = characterisation_window
    counts = {name: 0 for name in STAGE_NAMES}
    counts["discovered"] = len(candidates)
    reasons: dict[str, str] = {}
    evaluable: list[str] = []

    for wallet in sorted(candidates):
        fills = candidates[wallet]
        profile = characterise(
            wallet, fills, start_ms=start_ms, end_ms=end_ms, thresholds=thresholds
        )
        if profile.classification != DIRECTIONAL:
            reasons[wallet] = profile.classification
            if profile.classification == INSUFFICIENT_FILLS:
                counts["insufficient_fills"] += 1
            elif profile.classification == PROBABLE_MARKET_MAKER:
                counts["probable_market_maker"] += 1
            continue
        counts["prefiltered_directional"] += 1

        rebate = rebate_dependence(fills, start_ms=start_ms, end_ms=end_ms)
        if rebate is not None and rebate >= rebate_max:
            reasons[wallet] = REASON_REBATE
            counts["rebate_excluded"] += 1
            continue

        if scope_share(fills, scope, start_ms=start_ms, end_ms=end_ms) < scope_min:
            reasons[wallet] = REASON_SCOPE
            counts["scope_excluded"] += 1
            continue

        reasons[wallet] = EVALUABLE
        evaluable.append(wallet)

    counts["evaluable"] = len(evaluable)
    return CohortSelection(tuple(sorted(evaluable)), counts, reasons)


def cohort_hash(wallets: Sequence[str]) -> str:
    """SHA-256 over the sorted, lowercase addresses, one per line.

    Case and order are normalised so the digest identifies the *set*, and the
    terminal newline makes the hashed text the same bytes a plain text file
    of the cohort would hold.
    """
    text = "".join(f"{w}\n" for w in sorted(w.lower() for w in wallets))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _iso_utc(t0_ms: int) -> str:
    seconds, millis = divmod(t0_ms, 1000)
    stamp = datetime.fromtimestamp(seconds, tz=timezone.utc)
    fraction = f".{millis:03d}" if millis else ""
    return stamp.strftime("%Y-%m-%dT%H:%M:%S") + fraction + "Z"


def freeze_record(
    *,
    t0_ms: int,
    wallets: Sequence[str],
    plan_commit: str,
    stage_counts: Mapping[str, int],
    minimum: int = 200,
) -> dict:
    """The JSON-ready freeze record, or the hard stop that refuses to write one.

    Below ``minimum`` evaluable wallets the study has no power worth spending
    a month on, so the record says ``hard_stop`` and carries an empty cohort:
    a short list is not written down, because a written list invites a run.

    ``cohort_sha256`` is always ``cohort_hash(cohort)``: the digest of the
    list actually written to the ``cohort`` field, which under a hard stop is
    empty. A reader must be able to verify the digest against the list in the
    same record without knowing which branch produced it. ``attempted_count``
    and ``attempted_sha256`` describe the wallets the caller passed in,
    before any hard stop discards them, so that information is not lost.
    """
    count = len(wallets)
    hard_stop = count < minimum
    cohort = [] if hard_stop else sorted(w.lower() for w in wallets)
    return {
        "t0_ms": t0_ms,
        "t0_utc": _iso_utc(t0_ms),
        "plan_commit": plan_commit,
        "cohort": cohort,
        "cohort_sha256": cohort_hash(cohort),
        "stage_counts": dict(stage_counts),
        "evaluable_count": count,
        "attempted_count": count,
        "attempted_sha256": cohort_hash(wallets),
        "hard_stop": hard_stop,
    }
