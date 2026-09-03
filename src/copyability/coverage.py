"""Coverage ledger: which wallet-intervals are fully known.

The simulator must never score a period it did not fully observe. "The wallet
did nothing" and "we were not looking" are different facts, and a scorer that
cannot tell them apart will award a clean zero to a gap in the data. The
mechanism here makes that confusion structural rather than a convention:

* the only way to obtain a :class:`KnownInterval` is to ask a ledger to
  certify one, and
* the scorer refuses anything else.

A ``KnownInterval`` built by hand raises at construction. That is the whole
point of the private token below.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

_CERTIFICATION_TOKEN = object()


class UnknownIntervalError(ValueError):
    """Raised when a wallet-interval is not fully covered by observations."""


@dataclass(frozen=True, slots=True)
class ObservedInterval:
    """One interval a run actually covered for one wallet.

    ``complete`` is False when the run itself says it stopped early (for
    instance a backfill truncated at its page cap). An incomplete interval
    contributes nothing to certification, on purpose.
    """

    wallet: str
    start_ms: int
    end_ms: int
    complete: bool
    source: str

    def __post_init__(self) -> None:
        if not self.wallet:
            raise ValueError("observed interval needs a wallet")
        if self.end_ms < self.start_ms:
            raise ValueError("observed interval ends before it starts")


@dataclass(frozen=True, slots=True)
class KnownInterval:
    """A wallet-interval the ledger certified as fully observed.

    Cannot be constructed directly: the certifying ledger passes a private
    token, and any other constructor call fails. Tests exercise exactly this.
    """

    wallet: str
    start_ms: int
    end_ms: int
    certified_by: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.certified_by is not _CERTIFICATION_TOKEN:
            raise UnknownIntervalError(
                "a KnownInterval can only be issued by CoverageLedger.certify(); "
                "constructing one by hand would let an unobserved gap be scored"
            )
        if self.end_ms < self.start_ms:
            raise UnknownIntervalError("interval ends before it starts")

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


class CoverageLedger:
    """Union of complete observed intervals per wallet, queried for full cover."""

    __slots__ = ("_intervals",)

    def __init__(self, observed: Iterable[ObservedInterval]) -> None:
        by_wallet: dict[str, list[tuple[int, int]]] = {}
        for interval in observed:
            if not isinstance(interval, ObservedInterval):
                raise TypeError(f"expected ObservedInterval, got {type(interval).__name__}")
            if not interval.complete:
                continue
            by_wallet.setdefault(interval.wallet, []).append((interval.start_ms, interval.end_ms))
        self._intervals = {wallet: _merge(rows) for wallet, rows in by_wallet.items()}

    def wallets(self) -> frozenset[str]:
        return frozenset(self._intervals)

    def covered(self, wallet: str) -> list[tuple[int, int]]:
        return list(self._intervals.get(wallet, []))

    def is_fully_known(self, wallet: str, start_ms: int, end_ms: int) -> bool:
        """True only if one merged complete interval contains ``[start, end]``.

        Two adjacent runs that merge into one interval count. Two runs with a
        gap between them, however small, do not: the gap is exactly the period
        nobody observed.
        """
        if end_ms < start_ms:
            raise UnknownIntervalError("query interval ends before it starts")
        for lo, hi in self._intervals.get(wallet, []):
            if lo <= start_ms and end_ms <= hi:
                return True
        return False

    def certify(self, wallet: str, start_ms: int, end_ms: int) -> KnownInterval:
        """Issue a :class:`KnownInterval`, or refuse with the reason."""
        if not self.is_fully_known(wallet, start_ms, end_ms):
            covered = self.covered(wallet)
            raise UnknownIntervalError(
                f"{wallet} is not fully observed over [{start_ms}, {end_ms}]; "
                f"complete coverage is {covered or 'empty'}"
            )
        return KnownInterval(wallet, start_ms, end_ms, certified_by=_CERTIFICATION_TOKEN)

    def largest_known(self, wallet: str) -> KnownInterval | None:
        """The longest certified interval for a wallet, if any."""
        rows = self._intervals.get(wallet)
        if not rows:
            return None
        lo, hi = max(rows, key=lambda r: r[1] - r[0])
        return KnownInterval(wallet, lo, hi, certified_by=_CERTIFICATION_TOKEN)


def _merge(rows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping or touching intervals; leave gaps as gaps."""
    merged: list[tuple[int, int]] = []
    for lo, hi in sorted(rows):
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return merged
