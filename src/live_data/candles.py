"""Candle collection: one coin's OHLCV series over a bounded window.

Split out of :mod:`.ingest` to keep both modules inside the 500-line cap the
read-only guard enforces. The mixin is composed into
:class:`~.ingest.IngestOrchestrator`, so ``fetch_candles`` is a method on the
orchestrator like every other collection entry point and shares its store,
REST client, clock and run-id factory.

The venue answers ``candleSnapshot`` with at most
:data:`~.hyperliquid_rest.MAX_CANDLES_PER_RESPONSE` candles counted backwards
from ``endTime``, and its history is a rolling retention rather than a
paginated archive (L2 candle probe, 2026-09-04), so the walk here moves
backwards and stops as soon as a page is short.
"""

from __future__ import annotations

from typing import Any, Callable

from .hyperliquid_rest import MAX_CANDLES_PER_RESPONSE, HyperliquidRestClient
from .models import parse_candles, require_list
from .storage import RUN_STATUS_COMPLETED, RUN_STATUS_FAILED, LiveDataStore
from .watch import IngestError

#: A hard stop so a pagination bug cannot turn into an unbounded request loop.
#: Shared with :mod:`.ingest`, which re-exports it for its own paging walks.
DEFAULT_MAX_PAGES = 200


class CandleFetchMixin:
    """``fetch_candles`` for the ingest orchestrator.

    The attributes below are provided by the orchestrator this mixin is
    composed into; they are declared so the module reads on its own and type
    checking does not have to guess at them.
    """

    _rest: HyperliquidRestClient
    _store: LiveDataStore
    _clock_ms: Callable[[], int]
    _run_id_factory: Callable[[], str]
    #: Supplied by the orchestrator: request cost so far, for the run record.
    _requests_coverage: Callable[[], dict[str, int]]


    def _collect_candles(
        self, coin: str, interval: str, *, start_ms: int, end_ms: int, max_pages: int
    ) -> tuple[int, int, int, list[int], bool]:
        """Walk ``candleSnapshot`` backwards from ``end_ms``.

        Returns ``(pages, rows, written, open_times, exhausted)``. The venue
        answers at most :data:`MAX_CANDLES_PER_RESPONSE` candles counting back
        from ``endTime``, so a full page means the window reaches further back
        than the answer does: ask again ending one millisecond before the
        earliest candle returned. ``exhausted`` is False only when the page cap
        stopped a walk that was still returning full pages, which is the one
        case where the window is not covered to ``start_ms``.
        """
        cursor_end = end_ms
        pages = 0
        rows = 0
        written = 0
        open_times: list[int] = []
        exhausted = False
        while pages < max_pages:
            payload = self._rest.request(
                "candleSnapshot",
                coin=coin,
                interval=interval,
                start_time=start_ms,
                end_time=cursor_end,
            )
            raw_rows = require_list(payload, "candleSnapshot")
            candles = parse_candles(payload, coin, interval)
            result = self._store.write_candles(
                list(zip(candles, raw_rows, strict=True)), ingested_at_ms=self._clock_ms()
            )
            pages += 1
            rows += result.seen
            written += result.written
            open_times.extend(candle.open_time_ms for candle in candles)
            if len(candles) < MAX_CANDLES_PER_RESPONSE:
                exhausted = True
                break
            earliest = min(candle.open_time_ms for candle in candles)
            if earliest <= start_ms:
                exhausted = True
                break
            cursor_end = earliest - 1
        return pages, rows, written, open_times, exhausted

    def fetch_candles(
        self,
        coin: str,
        interval: str,
        start_ms: int,
        end_ms: int,
        *,
        max_pages: int = DEFAULT_MAX_PAGES,
    ) -> dict[str, Any]:
        """Fetch one coin's candle series over a window and record the run.

        Returns the ``candles`` coverage block, with the run id added. The
        maximum gap between consecutive open times is part of it because a
        series with a hole is not a price series a study may quote from, and
        the hole is invisible once the rows are in the table.
        """
        if start_ms < 0:
            raise IngestError("start_ms must be nonnegative")
        if end_ms < start_ms:
            raise IngestError("end_ms must not precede start_ms")
        if max_pages <= 0:
            raise IngestError("max_pages must be positive")

        run_id = self._run_id_factory()
        started_at = self._clock_ms()
        self._store.start_run(run_id, mode="fetch_candles", started_at_ms=started_at)
        candles: dict[str, Any] = {"coin": coin, "interval": interval, "pages": 0, "rows": 0}
        try:
            pages, rows, written, open_times, exhausted = self._collect_candles(
                coin, interval, start_ms=start_ms, end_ms=end_ms, max_pages=max_pages
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
                coverage={"candles": candles, "requests": self._requests_coverage()},
            )
            raise

        ordered = sorted(open_times)
        gaps = [b - a for a, b in zip(ordered, ordered[1:])]
        candles = {
            "coin": coin,
            "interval": interval,
            "pages": pages,
            "rows": rows,
            "written": written,
            "first_open_ms": ordered[0] if ordered else None,
            "last_open_ms": ordered[-1] if ordered else None,
            "max_gap_ms": max(gaps) if gaps else 0,
            "exhausted": exhausted,
        }
        self._store.finish_run(
            run_id,
            finished_at_ms=self._clock_ms(),
            status=RUN_STATUS_COMPLETED,
            records_seen=rows,
            records_written=written,
            coverage={"candles": candles, "requests": self._requests_coverage()},
        )
        return {"run_id": run_id, **candles}
