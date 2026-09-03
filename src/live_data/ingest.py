"""Ingest orchestration: REST backfill first, then websocket tailing.

Both paths write through :mod:`.storage`, so a wallet's history converges to
the same rows regardless of how many times a backfill is repeated or how often
the socket reconnects. Every run records its own provenance in ``ingest_runs``.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from .config import LiveDataConfig, normalize_wallet_address
from .hyperliquid_rest import MAX_FILLS_PER_RESPONSE, HyperliquidRestClient
from .hyperliquid_ws import HyperliquidWebSocketClient, Subscription
from .models import (
    ClearinghouseState,
    Fill,
    PayloadError,
    parse_all_mids,
    parse_funding,
    require_list,
    require_mapping,
)
from .storage import (
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    LiveDataStore,
)

MILLISECONDS_PER_DAY = 86_400_000

#: A hard stop so a pagination bug cannot turn into an unbounded request loop.
DEFAULT_MAX_PAGES = 200


class IngestError(RuntimeError):
    """Raised when an ingest run cannot proceed safely."""


@dataclass(frozen=True, slots=True)
class BackfillResult:
    run_id: str
    wallet_address: str
    start_time_ms: int
    end_time_ms: int | None
    pages: int
    records_seen: int
    records_written: int
    forced_cursor_advances: int


@dataclass(slots=True)
class WatchResult:
    run_id: str
    iterations: int
    fills_seen: int = 0
    fills_written: int = 0
    mids_written: int = 0
    errors: list[str] = field(default_factory=list)


def _now_ms() -> int:
    return int(time.time() * 1000)


class IngestOrchestrator:
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

    # -- REST backfill ---------------------------------------------------------------

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

        cursor = start_time_ms
        pages = 0
        seen = 0
        written = 0
        forced = 0
        try:
            while pages < max_pages:
                payload = self._rest.request(
                    "userFillsByTime",
                    user=address,
                    start_time=cursor,
                    end_time=end_time_ms,
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
                cursor = next_cursor
                if end_time_ms is not None and cursor > end_time_ms:
                    break
        except Exception as exc:
            self._store.finish_run(
                run_id,
                finished_at_ms=self._clock_ms(),
                status=RUN_STATUS_FAILED,
                records_seen=seen,
                records_written=written,
                error_count=1,
                notes=f"{type(exc).__name__}: {exc}",
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

    def snapshot_wallet_state(self, wallet: str) -> ClearinghouseState:
        """Persist one clearinghouse snapshot with its raw payload."""
        address = normalize_wallet_address(wallet)
        payload = self._rest.request("clearinghouseState", user=address)
        state = ClearinghouseState.parse(payload, address)
        now = self._clock_ms()
        self._store.upsert_wallet(address, observed_at_ms=now)
        self._store.write_position_snapshot(state, payload, ingested_at_ms=now)
        return state

    def backfill_wallet_funding(self, wallet: str, *, start_time_ms: int | None = None) -> int:
        """Persist funding payments for one wallet. Returns rows written."""
        address = normalize_wallet_address(wallet)
        payload = self._rest.request("userFunding", user=address, start_time=start_time_ms)
        rows = require_list(payload, "userFunding")
        deltas = parse_funding(payload, address)
        pairs = list(zip(deltas, rows, strict=True))
        return self._store.write_funding(pairs, ingested_at_ms=self._clock_ms()).written

    # -- websocket tailing -------------------------------------------------------------

    def build_watch_subscriptions(self) -> tuple[Subscription, ...]:
        """One ``userFills`` stream per tracked wallet, plus ``allMids`` if coins are tracked."""
        subscriptions = [
            Subscription(type="userFills", user=wallet) for wallet in self._config.tracked_wallets
        ]
        if self._config.tracked_coins:
            subscriptions.append(Subscription(type="allMids"))
        if not subscriptions:
            raise IngestError("nothing to watch: configure tracked wallets or coins")
        return tuple(subscriptions)

    def watch(self, *, max_iterations: int) -> WatchResult:
        """Tail the websocket, persisting fills and mids as they arrive."""
        if self._ws is None:
            raise IngestError("watch requires a websocket client")
        run_id = self._run_id_factory()
        started_at = self._clock_ms()
        self._store.start_run(run_id, mode="watch", started_at_ms=started_at)
        result = WatchResult(run_id=run_id, iterations=0)

        for wallet in self._config.tracked_wallets:
            self._store.upsert_wallet(wallet, observed_at_ms=started_at)
        for subscription in self.build_watch_subscriptions():
            handler = (
                self._make_user_fills_handler(result)
                if subscription.type == "userFills"
                else self._make_all_mids_handler(result)
            )
            self._ws.subscribe(subscription, handler)

        try:
            self._ws.connect()
            result.iterations = self._ws.run(max_iterations=max_iterations)
        except Exception as exc:
            self._store.finish_run(
                run_id,
                finished_at_ms=self._clock_ms(),
                status=RUN_STATUS_FAILED,
                records_seen=result.fills_seen,
                records_written=result.fills_written,
                error_count=len(result.errors) + 1,
                notes=f"{type(exc).__name__}: {exc}",
            )
            raise
        finally:
            self._ws.close()

        result.errors.extend(self._ws.handler_errors)
        self._store.finish_run(
            run_id,
            finished_at_ms=self._clock_ms(),
            status=RUN_STATUS_COMPLETED,
            records_seen=result.fills_seen,
            records_written=result.fills_written,
            error_count=len(result.errors),
            notes=f"mids written: {result.mids_written}; reconnects: {self._ws.reconnects}",
        )
        return result

    def _make_user_fills_handler(self, result: WatchResult) -> Callable[[dict[str, Any]], None]:
        def handle(message: dict[str, Any]) -> None:
            data = require_mapping(message.get("data"), "ws.userFills.data")
            user = data.get("user")
            if not isinstance(user, str):
                raise PayloadError("ws.userFills.data.user must be a string")
            address = normalize_wallet_address(user)
            rows = require_list(data.get("fills"), "ws.userFills.data.fills")
            pairs = [(Fill.parse(row, address), row) for row in rows]
            written = self._store.write_fills(
                pairs, source="ws:userFills", ingested_at_ms=self._clock_ms()
            )
            result.fills_seen += written.seen
            result.fills_written += written.written

        return handle

    def _make_all_mids_handler(self, result: WatchResult) -> Callable[[dict[str, Any]], None]:
        def handle(message: dict[str, Any]) -> None:
            data = require_mapping(message.get("data"), "ws.allMids.data")
            mids = parse_all_mids(data)
            tracked = set(self._config.tracked_coins)
            selected = {coin: mid for coin, mid in mids.items() if coin in tracked}
            observed_at = self._clock_ms()
            result.mids_written += self._store.write_mids(
                selected, data, observed_at_ms=observed_at, ingested_at_ms=observed_at
            ).written

        return handle
