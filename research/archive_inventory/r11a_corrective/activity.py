from __future__ import annotations

import dataclasses
import re
from types import MappingProxyType
from typing import Final

_WALLET_RE: Final[re.Pattern[str]] = re.compile(r"0x[0-9a-f]{40}\Z")
_DAY_RE: Final[re.Pattern[str]] = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_HOUR_RE: Final[re.Pattern[str]] = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:00:00Z\Z")


class ActivityError(ValueError):
    pass


@dataclasses.dataclass(frozen=True, slots=True)
class ActivitySnapshot:
    wallet: str
    active_hours: tuple[str, ...]
    active_days: tuple[str, ...]

    @property
    def active_hour_count(self) -> int:
        return len(self.active_hours)

    @property
    def active_day_count(self) -> int:
        return len(self.active_days)


class PureActivityTracker:
    """Read methods are observational only; `record` is the only mutation path."""

    __slots__ = ("_hours", "_days")

    def __init__(self) -> None:
        self._hours: dict[str, set[str]] = {}
        self._days: dict[str, set[str]] = {}

    def record(self, wallet: str, source_path_hour_utc: str) -> None:
        if _WALLET_RE.fullmatch(wallet) is None:
            raise ActivityError("wallet must be canonical lowercase address")
        if _HOUR_RE.fullmatch(source_path_hour_utc) is None:
            raise ActivityError("source path hour must be exact UTC hour text")
        day = source_path_hour_utc[:10]
        if _DAY_RE.fullmatch(day) is None:
            raise ActivityError("derived UTC day is invalid")
        # Validate all inputs before creating either set so failed writes are atomic.
        self._hours.setdefault(wallet, set()).add(source_path_hour_utc)
        self._days.setdefault(wallet, set()).add(day)

    def contains(self, wallet: str) -> bool:
        return wallet in self._hours

    def wallet_count(self) -> int:
        return len(self._hours)

    def snapshot(self, wallet: str) -> ActivitySnapshot | None:
        hours = self._hours.get(wallet)
        days = self._days.get(wallet)
        if hours is None or days is None:
            return None
        return ActivitySnapshot(wallet, tuple(sorted(hours)), tuple(sorted(days)))

    def snapshots(self) -> tuple[ActivitySnapshot, ...]:
        return tuple(
            ActivitySnapshot(
                wallet,
                tuple(sorted(self._hours[wallet])),
                tuple(sorted(self._days[wallet])),
            )
            for wallet in sorted(self._hours)
        )

    def immutable_mapping(self) -> MappingProxyType[str, ActivitySnapshot]:
        return MappingProxyType({row.wallet: row for row in self.snapshots()})
