"""Ingest orchestration: REST backfill first, then websocket tailing.

Both paths write through :mod:`.storage`, so a wallet's history converges to
the same rows regardless of how many times a backfill is repeated or how often
the socket reconnects. Every run records its own provenance in ``ingest_runs``.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable

from .config import LiveDataConfig, normalize_wallet_address
from .candles import DEFAULT_MAX_PAGES, CandleFetchMixin
from .hyperliquid_rest import MAX_FILLS_PER_RESPONSE, HyperliquidRestClient
from .hyperliquid_ws import HyperliquidWebSocketClient
from .models import ClearinghouseState, Fill, parse_funding, require_list
from .results import BackfillResult, WalletBackfillResult
from .storage import (
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    LiveDataStore,
)
from .sweep import SweepMixin
from .watch import IngestError, WatchMixin

MILLISECONDS_PER_DAY = 86_400_000

#: The venue returns at most this many rows for one ``userFunding`` call.
MAX_FUNDING_PER_RESPONSE = 500


def _now_ms() -> int:
    return int(time.time() * 1000)


class IngestOrchestrator(WatchMixin, CandleFetchMixin, SweepMixin):
    """Drives REST and websocket ingest for the configured wallets."""

    def __init__(
        self,
        config: LiveDataConfig,
        store: LiveDataStore,
        rest_client: HyperliquidRestClient,
        *,
        ws_client: HyperliquidWebSocketClient | None = None,
        clock_ms: Callable[[], int] = _now_ms,
        run_id_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
    ) -> None:
        config.authorizations.assert_read_only()
        self._config = config
        self._store = store
        self._rest = rest_client
        self._ws = ws_client
        self._clock_ms = clock_ms
        self._run_id_factory = run_id_factory

    @property
    def store(self) -> LiveDataStore:
        return self._store

    @property
    def consumed_weight(self) -> int:
        """Request weight spent so far by this orchestrator's REST client."""
        return self._rest.consumed_weight

    def _requests_coverage(self) -> dict[str, int]:
        """What the run cost against the venue budget, for the run record."""
        return {
            "attempted": self._rest.attempted_requests,
            "retried": self._rest.retried_requests,
            "weight": self._rest.consumed_weight,
        }

    # -- REST backfill ---------------------------------------------------------------

    def _collect_fills(
        self,
        address: str,
        *,
        start_time_ms: int,
        end_time_ms: int | None,
        max_pages: int,
    ) -> tuple[int, int, int, int, bool, int]:
        """Page ``userFillsByTime`` forward.

        Returns ``(pages, seen, written, forced, exhausted, covered_until_ms)``.
        ``exhausted`` is False when the page cap stopped the walk before the
        venue ran out of fills; the window is then only covered up to
        ``covered_until_ms``, and a caller that records it as complete would be
        confusing "the wallet did nothing after that" with "we stopped looking".

        ``covered_until_ms`` is a bound the ledger certifies as fully observed,
        so it is set to the last millisecond actually proven complete, never to
        the last one merely reached:

        * a forced cursor advance knowingly skips fills sharing one timestamp,
          so nothing at or after that millisecond is contiguous and the bound
          stops just before the first one;
        * a walk cut by the page cap ends on a *full* page, so fills sharing
          that page's last timestamp may never have been returned and that
          millisecond is not fully observed either.

        Both bounds can fall before ``start_time_ms``, which means the window
        proves nothing at all; the loader treats that as no observation.
        """
        cursor = start_time_ms
        pages = 0
        seen = 0
        written = 0
        forced = 0
        first_forced_ms: int | None = None
        exhausted = False
        while pages < max_pages:
            payload = self._rest.request(
                "userFillsByTime", user=address, start_time=cursor, end_time=end_time_ms
            )
            rows = require_list(payload, "userFillsByTime")
            pairs = [(Fill.parse(row, address), row) for row in rows]
            result = self._store.write_fills(
                pairs, source="rest:userFillsByTime", ingested_at_ms=self._clock_ms()
            )
            pages += 1
            seen += result.seen
            written += result.written
            if len(rows) < MAX_FILLS_PER_RESPONSE:
                exhausted = True
                break
            # The venue caps a time-ranged response, so resume from the last
            # timestamp. Overlap is intentional: idempotent writes absorb it.
            last_time = max(fill.event_time_ms for fill, _ in pairs)
            next_cursor = last_time
            if next_cursor <= cursor:
                # A full page inside a single millisecond cannot be paged by
                # time. Step past it rather than loop, and record the gap.
                next_cursor = cursor + 1
                forced += 1
                if first_forced_ms is None:
                    first_forced_ms = cursor
            cursor = next_cursor
            if end_time_ms is not None and cursor > end_time_ms:
                exhausted = True
                break
        if first_forced_ms is not None:
            covered_until_ms = first_forced_ms - 1
        elif exhausted:
            covered_until_ms = end_time_ms if end_time_ms is not None else cursor
        else:
            covered_until_ms = cursor - 1
        return pages, seen, written, forced, exhausted, covered_until_ms

    def _collect_funding(
        self, address: str, *, start_time_ms: int | None, max_pages: int = DEFAULT_MAX_PAGES
    ) -> tuple[int, int, bool, int]:
        """Page ``userFunding`` past the venue's response cap.

        Returns ``(seen, written, exhausted, pages)``. The venue answers one
        ``userFunding`` call with at most :data:`MAX_FUNDING_PER_RESPONSE`
        rows, so a full page means the window may hold more than was
        returned: resume from the last event time and ask again, the same
        pattern :meth:`_collect_fills` uses for ``userFillsByTime``.
        ``exhausted`` is False when ``max_pages`` stopped the walk before a
        short page confirmed the window was read completely.
        """
        cursor = start_time_ms
        seen = 0
        written = 0
        exhausted = False
        pages = 0
        while pages < max_pages:
            payload = self._rest.request("userFunding", user=address, start_time=cursor)
            rows = require_list(payload, "userFunding")
            deltas = parse_funding(payload, address)
            pairs = list(zip(deltas, rows, strict=True))
            result = self._store.write_funding(pairs, ingested_at_ms=self._clock_ms())
            pages += 1
            seen += result.seen
            written += result.written
            if len(rows) < MAX_FUNDING_PER_RESPONSE:
                exhausted = True
                break
            # A full page: resume just past the latest event time seen.
            # Rows sharing that millisecond beyond the page cap would be lost;
            # funding settles hourly per coin, so that needs more than a page
            # of coins funded in one instant, more than the venue lists.
            cursor = max(delta.event_time_ms for delta in deltas) + 1
        return seen, written, exhausted, pages

    def backfill_wallet(
        self, wallet: str, days: int, *, max_pages: int = DEFAULT_MAX_PAGES
    ) -> WalletBackfillResult:
        """Backfill everything historical for one wallet, under a single run.

        Fills and funding are collected together rather than behind separate
        flags: both are per-wallet historical REST data, funding is part of net
        expectancy, and a caller asking to backfill a wallet reasonably expects
        its whole economic history. Splitting them is what left ``funding``
        permanently empty.

        A clearinghouse snapshot is taken too. ``clearinghouseState`` has no
        history, so this is the earliest position record that can ever exist
        for the wallet; skipping it would mean a backfilled wallet has fills
        but no position baseline to interpret them against.
        """
        address = normalize_wallet_address(wallet)
        if days <= 0:
            raise IngestError("days must be positive")
        if max_pages <= 0:
            raise IngestError("max_pages must be positive")

        run_id = self._run_id_factory()
        started_at = self._clock_ms()
        window_start = max(0, started_at - days * MILLISECONDS_PER_DAY)
        self._store.start_run(
            run_id, mode="backfill_wallet", started_at_ms=started_at, wallet_address=address
        )
        self._store.upsert_wallet(address, observed_at_ms=started_at)

        coverage: dict[str, Any] = {
            "window": {"start_time_ms": window_start, "end_time_ms": started_at, "days": days},
            "fills": {"attempted": False},
            "funding": {"attempted": False},
            "positions": {"attempted": False},
        }
        result = WalletBackfillResult(run_id=run_id, wallet_address=address)
        try:
            coverage["fills"] = {"attempted": True, "completed": False}
            pages, seen, written, forced, exhausted, covered_until = self._collect_fills(
                address, start_time_ms=window_start, end_time_ms=started_at, max_pages=max_pages
            )
            result.pages, result.fills_seen, result.fills_written = pages, seen, written
            result.forced_cursor_advances = forced
            result.window_exhausted, result.covered_until_ms = exhausted, covered_until
            # Completed means the venue ran out of fills inside the window. A
            # walk stopped by the page cap covers only part of it, and saying
            # otherwise would let a later ledger read the uncovered tail as a
            # period in which the wallet did nothing.
            coverage["fills"] = {
                "attempted": True,
                "completed": exhausted,
                "truncated_at_page_cap": not exhausted,
                "covered_until_ms": covered_until,
                "seen": seen,
                "written": written,
                "pages": pages,
                "forced_cursor_advances": forced,
            }

            coverage["funding"] = {"attempted": True, "completed": False}
            funding_seen, funding_written, funding_exhausted, funding_pages = self._collect_funding(
                address, start_time_ms=window_start, max_pages=max_pages
            )
            result.funding_seen, result.funding_written = funding_seen, funding_written
            result.funding_exhausted = funding_exhausted
            coverage["funding"] = {
                "attempted": True,
                "completed": funding_exhausted,
                "truncated_at_response_cap": not funding_exhausted,
                "seen": funding_seen,
                "written": funding_written,
                "pages": funding_pages,
            }

            coverage["positions"] = {"attempted": True, "completed": False}
            _, snapshot_written = self._write_snapshot(address)
            result.snapshot_taken = True
            coverage["positions"] = {
                "attempted": True,
                "completed": True,
                "snapshots": 1,
                "written": snapshot_written,
            }
        except Exception as exc:
            coverage["requests"] = self._requests_coverage()
            self._store.finish_run(
                run_id,
                finished_at_ms=self._clock_ms(),
                status=RUN_STATUS_FAILED,
                records_seen=result.fills_seen + result.funding_seen,
                records_written=result.fills_written + result.funding_written,
                error_count=1,
                notes=f"{type(exc).__name__}: {exc}",
                coverage=coverage,
            )
            raise

        notes = None if result.forced_cursor_advances == 0 else (
            f"forced cursor advances: {result.forced_cursor_advances}"
        )
        coverage["requests"] = self._requests_coverage()
        self._store.finish_run(
            run_id,
            finished_at_ms=self._clock_ms(),
            status=RUN_STATUS_COMPLETED,
            records_seen=result.fills_seen + result.funding_seen,
            records_written=result.fills_written + result.funding_written,
            notes=notes,
            coverage=coverage,
        )
        return result

    def backfill_wallet_fills(
        self,
        wallet: str,
        *,
        start_time_ms: int,
        end_time_ms: int | None = None,
        max_pages: int = DEFAULT_MAX_PAGES,
    ) -> BackfillResult:
        """Page ``userFillsByTime`` forward until the range is exhausted."""
        address = normalize_wallet_address(wallet)
        if start_time_ms < 0:
            raise IngestError("start_time_ms must be nonnegative")
        if end_time_ms is not None and end_time_ms < start_time_ms:
            raise IngestError("end_time_ms must not precede start_time_ms")
        if max_pages <= 0:
            raise IngestError("max_pages must be positive")

        run_id = self._run_id_factory()
        started_at = self._clock_ms()
        self._store.start_run(
            run_id, mode="backfill_fills", started_at_ms=started_at, wallet_address=address
        )
        self._store.upsert_wallet(address, observed_at_ms=started_at)

        try:
            pages, seen, written, forced, exhausted, covered_until = self._collect_fills(
                address,
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                max_pages=max_pages,
            )
        except Exception as exc:
            self._store.finish_run(
                run_id,
                finished_at_ms=self._clock_ms(),
                status=RUN_STATUS_FAILED,
                records_seen=0,
                records_written=0,
                error_count=1,
                notes=f"{type(exc).__name__}: {exc}",
                coverage={"fills": {"attempted": True, "completed": False}},
            )
            raise

        notes = None if forced == 0 else f"forced cursor advances: {forced}"
        self._store.finish_run(
            run_id,
            finished_at_ms=self._clock_ms(),
            status=RUN_STATUS_COMPLETED,
            records_seen=seen,
            records_written=written,
            notes=notes,
            coverage={
                "fills": {
                    "attempted": True,
                    "completed": exhausted,
                    "truncated_at_page_cap": not exhausted,
                    "covered_until_ms": covered_until,
                    "seen": seen,
                    "written": written,
                    "pages": pages,
                    "forced_cursor_advances": forced,
                },
                "funding": {"attempted": False},
                "positions": {"attempted": False},
                "requests": self._requests_coverage(),
            },
        )
        return BackfillResult(
            run_id=run_id,
            wallet_address=address,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            pages=pages,
            records_seen=seen,
            records_written=written,
            forced_cursor_advances=forced,
            window_exhausted=exhausted,
            covered_until_ms=covered_until,
        )

    def backfill_days(
        self, wallet: str, days: int, *, max_pages: int = DEFAULT_MAX_PAGES
    ) -> BackfillResult:
        """Backfill the trailing ``days`` window for one wallet."""
        if days <= 0:
            raise IngestError("days must be positive")
        now = self._clock_ms()
        return self.backfill_wallet_fills(
            wallet,
            start_time_ms=max(0, now - days * MILLISECONDS_PER_DAY),
            end_time_ms=now,
            max_pages=max_pages,
        )

    def _write_snapshot(self, wallet: str) -> tuple[ClearinghouseState, int]:
        """Fetch and persist one clearinghouse snapshot. Returns (state, rows written).

        Rows written can be zero: snapshots are keyed on the venue's own state
        timestamp, so polling twice without the state advancing is one row, not
        two. Attempts and rows are both reported because they answer different
        questions -- did we look, and did anything change.
        """
        address = normalize_wallet_address(wallet)
        payload = self._rest.request("clearinghouseState", user=address)
        state = ClearinghouseState.parse(payload, address)
        now = self._clock_ms()
        self._store.upsert_wallet(address, observed_at_ms=now)
        written = self._store.write_position_snapshot(state, payload, ingested_at_ms=now).written
        return state, written

    def snapshot_wallet_state(self, wallet: str) -> ClearinghouseState:
        """Persist one clearinghouse snapshot with its raw payload."""
        state, _ = self._write_snapshot(wallet)
        return state

    def backfill_wallet_funding(self, wallet: str, *, start_time_ms: int | None = None) -> int:
        """Persist funding payments for one wallet. Returns rows written."""
        address = normalize_wallet_address(wallet)
        _, written, _, _ = self._collect_funding(address, start_time_ms=start_time_ms)
        return written
