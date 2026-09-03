"""Outcome records for ingest runs.

Separated from the orchestrator so that ``ingest.py`` is about behaviour and
these are about what a run produced. They are also what the caller reports and
what the ``ingest_runs`` coverage record is built from, so they are part of the
provenance surface rather than incidental bookkeeping.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class BackfillResult:
    """Outcome of a fills-only backfill over an explicit time window."""

    run_id: str
    wallet_address: str
    start_time_ms: int
    end_time_ms: int | None
    pages: int
    records_seen: int
    records_written: int
    forced_cursor_advances: int


@dataclass(slots=True)
class WalletBackfillResult:
    """Outcome of one composite wallet backfill: fills, funding and a snapshot."""

    run_id: str
    wallet_address: str
    pages: int = 0
    fills_seen: int = 0
    fills_written: int = 0
    funding_seen: int = 0
    funding_written: int = 0
    snapshot_taken: bool = False
    forced_cursor_advances: int = 0


@dataclass(slots=True)
class WatchResult:
    """Outcome of one websocket watch session."""

    run_id: str
    iterations: int
    fills_seen: int = 0
    fills_written: int = 0
    mids_written: int = 0
    #: Snapshots requested from the venue.
    snapshots_taken: int = 0
    #: Snapshot rows actually stored. Lower than ``snapshots_taken`` when the
    #: venue state did not advance between polls, which is deduplication
    #: working rather than a failure.
    snapshots_written: int = 0
    errors: list[str] = field(default_factory=list)
