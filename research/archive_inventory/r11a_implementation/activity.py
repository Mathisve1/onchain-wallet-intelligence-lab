from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping


class ActivityError(ValueError):
    """Raised when an activity write is malformed."""


@dataclass(frozen=True, slots=True)
class ActivitySnapshot:
    wallet_address: str
    path_hours: tuple[str, ...]
    path_days: tuple[str, ...]
    block_times: tuple[str, ...]
    fill_times_ms: tuple[int, ...]


@dataclass(slots=True)
class _MutableActivity:
    path_hours: set[str]
    path_days: set[str]
    block_times: set[str]
    fill_times_ms: set[int]

    @classmethod
    def empty(cls) -> "_MutableActivity":
        return cls(set(), set(), set(), set())


class ActivityTracker:
    """Explicit-write activity state with pure reads.

    There is deliberately no ``__getitem__`` and no ``defaultdict``. A wallet
    enters state only through ``record``. This prevents the historical R11 bug
    where rendering added the ambient final day during a read.
    """

    def __init__(self) -> None:
        self._states: dict[str, _MutableActivity] = {}

    @staticmethod
    def _validate_wallet(wallet: str) -> None:
        if (
            type(wallet) is not str
            or len(wallet) != 42
            or not wallet.startswith("0x")
            or any(ch not in "0123456789abcdef" for ch in wallet[2:])
        ):
            raise ActivityError("wallet must be exact lowercase 0x plus 40 hex")

    @staticmethod
    def _validate_path_hour(path_hour_utc: str) -> None:
        if (
            type(path_hour_utc) is not str
            or len(path_hour_utc) != 20
            or path_hour_utc[4] != "-"
            or path_hour_utc[7] != "-"
            or path_hour_utc[10] != "T"
            or path_hour_utc[13:] != ":00:00Z"
        ):
            raise ActivityError("path hour must be exact YYYY-MM-DDTHH:00:00Z")

    def record(
        self,
        wallet: str,
        *,
        path_hour_utc: str,
        block_time_exact: str,
        fill_time_ms: int,
    ) -> None:
        self._validate_wallet(wallet)
        self._validate_path_hour(path_hour_utc)
        if type(block_time_exact) is not str or not block_time_exact:
            raise ActivityError("block_time_exact must be nonempty exact source string")
        if type(fill_time_ms) is not int or fill_time_ms < 0:
            raise ActivityError("fill_time_ms must be nonnegative exact integer")
        state = self._states.get(wallet)
        if state is None:
            state = _MutableActivity.empty()
            self._states[wallet] = state
        state.path_hours.add(path_hour_utc)
        state.path_days.add(path_hour_utc[:10])
        state.block_times.add(block_time_exact)
        state.fill_times_ms.add(fill_time_ms)

    def contains(self, wallet: str) -> bool:
        return wallet in self._states

    def wallet_count(self) -> int:
        return len(self._states)

    def snapshot(self, wallet: str) -> ActivitySnapshot | None:
        state = self._states.get(wallet)
        if state is None:
            return None
        return ActivitySnapshot(
            wallet_address=wallet,
            path_hours=tuple(sorted(state.path_hours)),
            path_days=tuple(sorted(state.path_days)),
            block_times=tuple(sorted(state.block_times)),
            fill_times_ms=tuple(sorted(state.fill_times_ms)),
        )

    def snapshots(self) -> tuple[ActivitySnapshot, ...]:
        rows: list[ActivitySnapshot] = []
        for wallet in sorted(self._states):
            snapshot = self.snapshot(wallet)
            if snapshot is not None:
                rows.append(snapshot)
        return tuple(rows)

    def immutable_mapping(self) -> Mapping[str, ActivitySnapshot]:
        return MappingProxyType({row.wallet_address: row for row in self.snapshots()})

    def record_many(self, rows: Iterable[tuple[str, str, str, int]]) -> None:
        for wallet, path_hour, block_time, fill_time in rows:
            self.record(
                wallet,
                path_hour_utc=path_hour,
                block_time_exact=block_time,
                fill_time_ms=fill_time,
            )
