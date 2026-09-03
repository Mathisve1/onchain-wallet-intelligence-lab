"""Websocket tailing: the live half of the ingest orchestrator.

Split out of :mod:`.ingest` purely for size. The methods here are mixed into
:class:`~.ingest.IngestOrchestrator` and rely on its store, config, clock,
run-id factory, snapshot writer and request accounting; nothing here is meant
to stand alone.
"""

from __future__ import annotations

from typing import Any, Callable

from .config import normalize_wallet_address
from .hyperliquid_ws import Subscription
from .models import Fill, PayloadError, parse_all_mids, require_list, require_mapping
from .results import WatchResult
from .storage import RUN_STATUS_COMPLETED, RUN_STATUS_FAILED
from .trades import DISCOVERY_LABEL, make_trades_handler


class IngestError(RuntimeError):
    """Raised when an ingest run cannot proceed safely."""


class WatchMixin:
    """Websocket session behaviour; see the module docstring."""


    def build_watch_subscriptions(self) -> tuple[Subscription, ...]:
        """One ``userFills`` stream per tracked wallet, plus ``allMids`` if coins are tracked."""
        subscriptions = [
            Subscription(type="userFills", user=wallet) for wallet in self._config.tracked_wallets
        ]
        if self._config.tracked_coins:
            subscriptions.append(Subscription(type="allMids"))
            # The public tape per coin is what discovers wallets: it is the
            # only read-only stream that names counterparties unprompted.
            subscriptions.extend(
                Subscription(type="trades", coin=coin) for coin in self._config.tracked_coins
            )
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
        # One tape handler shared by every coin subscription: the ``trades``
        # channel routes on the channel alone, so a per-coin handler would see
        # every coin's frames anyway and discovery must count each wallet once.
        trades_handler = self._make_trades_handler(result)
        handlers = {
            "userFills": lambda: self._make_user_fills_handler(result),
            "allMids": lambda: self._make_all_mids_handler(result),
            "trades": lambda: trades_handler,
        }
        for subscription in self.build_watch_subscriptions():
            self._ws.subscribe(subscription, handlers[subscription.type]())

        snapshot_due: dict[str, float] = {}
        coverage: dict[str, Any] = {
            "fills": {"attempted": True, "source": "ws:userFills"},
            "mids": {"attempted": bool(self._config.tracked_coins)},
            "trades": {
                "attempted": bool(self._config.tracked_coins),
                "coins": list(self._config.tracked_coins),
            },
            "positions": {
                "attempted": bool(self._config.tracked_wallets),
                "wallets": len(self._config.tracked_wallets),
                # The exact subscription list: coverage is credited to these
                # and to nothing else, whatever else wrote rows meanwhile.
                "tracked_wallets": list(self._config.tracked_wallets),
                "interval_seconds": self._config.snapshot_interval_seconds,
            },
            "connection": {"reconnects": 0},
        }
        try:
            self._ws.connect()
            # Baseline before any frame arrives: a wallet that trades nothing
            # during the session still needs one position record, otherwise an
            # empty query is indistinguishable from an unobserved wallet.
            self._snapshot_tracked_wallets(result, snapshot_due, force=True)
            result.iterations = self._ws.run(
                max_iterations=max_iterations,
                on_iteration=lambda: self._snapshot_tracked_wallets(result, snapshot_due),
            )
        except Exception as exc:
            coverage["positions"]["snapshots"] = result.snapshots_taken
            coverage["requests"] = self._requests_coverage()
            self._store.finish_run(
                run_id,
                finished_at_ms=self._clock_ms(),
                status=RUN_STATUS_FAILED,
                records_seen=result.fills_seen,
                records_written=result.fills_written,
                error_count=len(result.errors) + 1,
                notes=f"{type(exc).__name__}: {exc}",
                coverage=coverage,
            )
            raise
        finally:
            self._ws.close()

        result.errors.extend(self._ws.handler_errors)
        coverage["fills"]["seen"] = result.fills_seen
        coverage["fills"]["written"] = result.fills_written
        coverage["mids"]["written"] = result.mids_written
        coverage["positions"]["snapshots"] = result.snapshots_taken
        coverage["positions"]["written"] = result.snapshots_written
        coverage["trades"]["seen"] = result.trades_seen
        coverage["trades"]["written"] = result.trades_written
        coverage["trades"]["wallets_discovered"] = result.wallets_discovered
        coverage["connection"]["reconnects"] = self._ws.reconnects
        coverage["requests"] = self._requests_coverage()
        self._store.finish_run(
            run_id,
            finished_at_ms=self._clock_ms(),
            status=RUN_STATUS_COMPLETED,
            records_seen=result.fills_seen + result.trades_seen,
            records_written=result.fills_written + result.trades_written,
            error_count=len(result.errors),
            notes=(
                f"mids written: {result.mids_written}; snapshots: {result.snapshots_taken}; "
                f"trades written: {result.trades_written}; "
                f"wallets discovered: {result.wallets_discovered}; "
                f"reconnects: {self._ws.reconnects}"
            ),
            coverage=coverage,
        )
        return result

    def _make_trades_handler(self, result: WatchResult) -> Callable[[dict[str, Any]], None]:
        def observe(wallet: str) -> None:
            self._store.upsert_wallet(
                wallet, observed_at_ms=self._clock_ms(), label=DISCOVERY_LABEL
            )

        def tally(seen: int, written: int, discovered: int) -> None:
            result.trades_seen += seen
            result.trades_written += written
            result.wallets_discovered += discovered

        return make_trades_handler(
            write_trades=lambda rows: self._store.write_trades(
                rows, ingested_at_ms=self._clock_ms()
            ).written,
            observe_wallet=observe,
            on_trades=tally,
        )

    def _snapshot_tracked_wallets(
        self, result: WatchResult, due: dict[str, float], *, force: bool = False
    ) -> None:
        """Snapshot each tracked wallet whose interval has elapsed.

        Cadence is a baseline on connect plus a fixed interval floor, and
        deliberately not fill-triggered. Position *state* is already
        reconstructible from the fill stream, which carries ``startPosition``,
        ``dir`` and size; what snapshots uniquely provide is account value,
        and equity drifts with mark prices continuously rather than stepping
        with fills. So sampling on a clock is what the data actually needs,
        and a fill trigger would add cost and burstiness for information the
        fills already carry.

        Known limitation: this runs per websocket loop iteration, so it only
        advances while frames arrive. With ``allMids`` subscribed that is
        continuous; a wallets-only session with no activity will not refresh
        past the baseline until a frame arrives. A receive timeout would fix
        it and is deliberately out of scope here.
        """
        now_ms = self._clock_ms()
        for wallet in self._config.tracked_wallets:
            deadline = due.get(wallet)
            if not force and deadline is not None and now_ms < deadline:
                continue
            try:
                _, written = self._write_snapshot(wallet)
                result.snapshots_taken += 1
                result.snapshots_written += written
            except Exception as exc:  # one wallet's failure must not stop the feed
                result.errors.append(f"snapshot {wallet}: {type(exc).__name__}: {exc}")
            due[wallet] = now_ms + self._config.snapshot_interval_seconds * 1000.0

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
