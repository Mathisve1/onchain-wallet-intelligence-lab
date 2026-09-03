"""Idempotent SQLite persistence with lossless provenance.

Every parsed row is stored next to the exact raw JSON it came from, and every
write is idempotent on a natural key. Re-running an ingest can therefore never
inflate a wallet's history, which is the property the downstream ledger and
performance work depend on.

Decimals are stored as TEXT. SQLite REAL is binary floating point and would
quietly change the venue's numbers.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from .models import ClearinghouseState, Fill, FundingDelta

SCHEMA_VERSION = 1

_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE schema_version (
        version INTEGER NOT NULL PRIMARY KEY,
        applied_at_ms INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE wallets (
        address TEXT NOT NULL PRIMARY KEY,
        label TEXT,
        first_seen_at_ms INTEGER NOT NULL,
        last_seen_at_ms INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE fills (
        wallet_address TEXT NOT NULL,
        coin TEXT NOT NULL,
        trade_id INTEGER NOT NULL,
        event_time_ms INTEGER NOT NULL,
        side TEXT NOT NULL,
        price TEXT NOT NULL,
        size TEXT NOT NULL,
        fee TEXT NOT NULL,
        closed_pnl TEXT NOT NULL,
        start_position TEXT NOT NULL,
        direction TEXT NOT NULL,
        order_id INTEGER NOT NULL,
        crossed INTEGER NOT NULL,
        tx_hash TEXT NOT NULL,
        fee_token TEXT,
        raw_payload TEXT NOT NULL,
        source TEXT NOT NULL,
        ingested_at_ms INTEGER NOT NULL,
        PRIMARY KEY (wallet_address, coin, trade_id, event_time_ms)
    )
    """,
    "CREATE INDEX fills_by_wallet_time ON fills (wallet_address, event_time_ms)",
    """
    CREATE TABLE positions_snapshot (
        wallet_address TEXT NOT NULL,
        snapshot_time_ms INTEGER NOT NULL,
        account_value TEXT NOT NULL,
        total_notional_position TEXT NOT NULL,
        total_margin_used TEXT NOT NULL,
        withdrawable TEXT NOT NULL,
        open_position_count INTEGER NOT NULL,
        raw_payload TEXT NOT NULL,
        ingested_at_ms INTEGER NOT NULL,
        PRIMARY KEY (wallet_address, snapshot_time_ms)
    )
    """,
    """
    CREATE TABLE mids (
        coin TEXT NOT NULL,
        observed_at_ms INTEGER NOT NULL,
        mid TEXT NOT NULL,
        raw_payload TEXT NOT NULL,
        ingested_at_ms INTEGER NOT NULL,
        PRIMARY KEY (coin, observed_at_ms)
    )
    """,
    """
    CREATE TABLE funding (
        wallet_address TEXT NOT NULL,
        coin TEXT NOT NULL,
        event_time_ms INTEGER NOT NULL,
        usdc TEXT NOT NULL,
        funding_rate TEXT NOT NULL,
        signed_size TEXT NOT NULL,
        raw_payload TEXT NOT NULL,
        ingested_at_ms INTEGER NOT NULL,
        PRIMARY KEY (wallet_address, coin, event_time_ms)
    )
    """,
    """
    CREATE TABLE ingest_runs (
        run_id TEXT NOT NULL PRIMARY KEY,
        mode TEXT NOT NULL,
        wallet_address TEXT,
        started_at_ms INTEGER NOT NULL,
        finished_at_ms INTEGER,
        status TEXT NOT NULL,
        records_seen INTEGER NOT NULL DEFAULT 0,
        records_written INTEGER NOT NULL DEFAULT 0,
        error_count INTEGER NOT NULL DEFAULT 0,
        notes TEXT
    )
    """,
)

RUN_STATUS_RUNNING = "running"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"
_RUN_STATUSES = frozenset({RUN_STATUS_RUNNING, RUN_STATUS_COMPLETED, RUN_STATUS_FAILED})


class StorageError(RuntimeError):
    """Raised on schema drift or malformed write input."""


@dataclass(frozen=True, slots=True)
class WriteResult:
    """How many rows were offered versus actually new."""

    seen: int
    written: int

    @property
    def duplicates(self) -> int:
        return self.seen - self.written


def _dump(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str)


def _require_positive_ms(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise StorageError(f"{name} must be a positive millisecond timestamp")
    return value


class LiveDataStore:
    """Owns one SQLite file and all writes into it."""

    def __init__(self, database_path: Path | str, *, create: bool = True) -> None:
        self._path = Path(database_path)
        if str(self._path) != ":memory:":
            if create:
                self._path.parent.mkdir(parents=True, exist_ok=True)
            elif not self._path.exists():
                # Connecting would create an empty file, hiding the real problem.
                raise StorageError(f"database does not exist: {self._path}")
        self._connection = sqlite3.connect(str(self._path))
        try:
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._apply_schema(create=create)
        except Exception:
            # Never leave a handle open on a database we refuse to operate on.
            self._connection.close()
            raise

    def __enter__(self) -> LiveDataStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    # -- schema ---------------------------------------------------------------------

    def _installed_version(self) -> int | None:
        row = self._connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'schema_version'"
        ).fetchone()
        if row is None:
            return None
        version_row = self._connection.execute(
            "SELECT MAX(version) AS version FROM schema_version"
        ).fetchone()
        if version_row is None or version_row["version"] is None:
            raise StorageError("schema_version table exists but records no version")
        return int(version_row["version"])

    def _apply_schema(self, *, create: bool) -> None:
        version = self._installed_version()
        if version == SCHEMA_VERSION:
            return
        if version is None:
            if not create:
                raise StorageError(f"database is not initialized: {self._path}")
            with self._connection:
                for statement in _SCHEMA_STATEMENTS:
                    self._connection.execute(statement)
                self._connection.execute(
                    "INSERT INTO schema_version (version, applied_at_ms) VALUES (?, 0)",
                    (SCHEMA_VERSION,),
                )
            return
        if version > SCHEMA_VERSION:
            raise StorageError(
                f"database schema version {version} is newer than supported {SCHEMA_VERSION}; "
                "refusing to operate on it"
            )
        raise StorageError(
            f"database schema version {version} predates {SCHEMA_VERSION}; "
            "no migration path is defined"
        )

    # -- writes ---------------------------------------------------------------------

    def upsert_wallet(self, address: str, *, observed_at_ms: int, label: str | None = None) -> None:
        _require_positive_ms(observed_at_ms, "observed_at_ms")
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO wallets (address, label, first_seen_at_ms, last_seen_at_ms)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (address) DO UPDATE SET
                    label = COALESCE(excluded.label, wallets.label),
                    last_seen_at_ms = MAX(wallets.last_seen_at_ms, excluded.last_seen_at_ms)
                """,
                (address, label, observed_at_ms, observed_at_ms),
            )

    def write_fills(
        self,
        rows: Sequence[tuple[Fill, Any]],
        *,
        source: str,
        ingested_at_ms: int,
    ) -> WriteResult:
        """Insert fills, ignoring any natural key already present."""
        _require_positive_ms(ingested_at_ms, "ingested_at_ms")
        if not source:
            raise StorageError("source must be a nonempty provenance label")
        written = 0
        with self._connection:
            for fill, raw in rows:
                if not isinstance(fill, Fill):
                    raise StorageError(f"expected Fill, got {type(fill).__name__}")
                cursor = self._connection.execute(
                    """
                    INSERT INTO fills (
                        wallet_address, coin, trade_id, event_time_ms, side, price, size,
                        fee, closed_pnl, start_position, direction, order_id, crossed,
                        tx_hash, fee_token, raw_payload, source, ingested_at_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (wallet_address, coin, trade_id, event_time_ms) DO NOTHING
                    """,
                    (
                        fill.wallet_address,
                        fill.coin,
                        fill.trade_id,
                        fill.event_time_ms,
                        fill.side,
                        str(fill.price),
                        str(fill.size),
                        str(fill.fee),
                        str(fill.closed_pnl),
                        str(fill.start_position),
                        fill.direction,
                        fill.order_id,
                        1 if fill.crossed else 0,
                        fill.tx_hash,
                        fill.fee_token,
                        _dump(raw),
                        source,
                        ingested_at_ms,
                    ),
                )
                written += cursor.rowcount if cursor.rowcount > 0 else 0
        return WriteResult(seen=len(rows), written=written)

    def write_position_snapshot(
        self, state: ClearinghouseState, raw: Any, *, ingested_at_ms: int
    ) -> WriteResult:
        _require_positive_ms(ingested_at_ms, "ingested_at_ms")
        with self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO positions_snapshot (
                    wallet_address, snapshot_time_ms, account_value, total_notional_position,
                    total_margin_used, withdrawable, open_position_count, raw_payload,
                    ingested_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (wallet_address, snapshot_time_ms) DO NOTHING
                """,
                (
                    state.wallet_address,
                    state.snapshot_time_ms,
                    str(state.margin_summary.account_value),
                    str(state.margin_summary.total_notional_position),
                    str(state.margin_summary.total_margin_used),
                    str(state.withdrawable),
                    len(state.positions),
                    _dump(raw),
                    ingested_at_ms,
                ),
            )
        return WriteResult(seen=1, written=max(cursor.rowcount, 0))

    def write_mids(
        self, mids: dict[str, Any], raw: Any, *, observed_at_ms: int, ingested_at_ms: int
    ) -> WriteResult:
        _require_positive_ms(observed_at_ms, "observed_at_ms")
        _require_positive_ms(ingested_at_ms, "ingested_at_ms")
        written = 0
        raw_json = _dump(raw)
        with self._connection:
            for coin, mid in mids.items():
                cursor = self._connection.execute(
                    """
                    INSERT INTO mids (coin, observed_at_ms, mid, raw_payload, ingested_at_ms)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT (coin, observed_at_ms) DO NOTHING
                    """,
                    (coin, observed_at_ms, str(mid), raw_json, ingested_at_ms),
                )
                written += cursor.rowcount if cursor.rowcount > 0 else 0
        return WriteResult(seen=len(mids), written=written)

    def write_funding(
        self, rows: Sequence[tuple[FundingDelta, Any]], *, ingested_at_ms: int
    ) -> WriteResult:
        _require_positive_ms(ingested_at_ms, "ingested_at_ms")
        written = 0
        with self._connection:
            for delta, raw in rows:
                cursor = self._connection.execute(
                    """
                    INSERT INTO funding (
                        wallet_address, coin, event_time_ms, usdc, funding_rate,
                        signed_size, raw_payload, ingested_at_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (wallet_address, coin, event_time_ms) DO NOTHING
                    """,
                    (
                        delta.wallet_address,
                        delta.coin,
                        delta.event_time_ms,
                        str(delta.usdc),
                        str(delta.funding_rate),
                        str(delta.signed_size),
                        _dump(raw),
                        ingested_at_ms,
                    ),
                )
                written += cursor.rowcount if cursor.rowcount > 0 else 0
        return WriteResult(seen=len(rows), written=written)

    # -- run provenance --------------------------------------------------------------

    def start_run(
        self, run_id: str, *, mode: str, started_at_ms: int, wallet_address: str | None = None
    ) -> None:
        _require_positive_ms(started_at_ms, "started_at_ms")
        if not run_id or not mode:
            raise StorageError("run_id and mode must be nonempty")
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO ingest_runs (run_id, mode, wallet_address, started_at_ms, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, mode, wallet_address, started_at_ms, RUN_STATUS_RUNNING),
            )

    def finish_run(
        self,
        run_id: str,
        *,
        finished_at_ms: int,
        status: str,
        records_seen: int,
        records_written: int,
        error_count: int = 0,
        notes: str | None = None,
    ) -> None:
        _require_positive_ms(finished_at_ms, "finished_at_ms")
        if status not in _RUN_STATUSES:
            raise StorageError(f"unknown run status: {status!r}")
        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE ingest_runs SET
                    finished_at_ms = ?, status = ?, records_seen = ?,
                    records_written = ?, error_count = ?, notes = ?
                WHERE run_id = ?
                """,
                (
                    finished_at_ms,
                    status,
                    records_seen,
                    records_written,
                    error_count,
                    notes,
                    run_id,
                ),
            )
        if cursor.rowcount != 1:
            raise StorageError(f"no ingest run to finish: {run_id!r}")

    # -- reads ------------------------------------------------------------------------

    def count(self, table: str) -> int:
        if table not in {"wallets", "fills", "positions_snapshot", "mids", "funding", "ingest_runs"}:
            raise StorageError(f"unknown table: {table!r}")
        row = self._connection.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
        return int(row["n"])

    def latest_fill_time_ms(self, wallet_address: str) -> int | None:
        row = self._connection.execute(
            "SELECT MAX(event_time_ms) AS t FROM fills WHERE wallet_address = ?",
            (wallet_address,),
        ).fetchone()
        return None if row["t"] is None else int(row["t"])

    def recent_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        if limit <= 0:
            raise StorageError("limit must be positive")
        rows: Iterable[sqlite3.Row] = self._connection.execute(
            "SELECT * FROM ingest_runs ORDER BY started_at_ms DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
