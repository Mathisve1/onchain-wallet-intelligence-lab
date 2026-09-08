"""Argument parsing and orchestrator wiring for the read-only live data pipeline.

This module is deliberately not an executable entry point. It builds no
transports: the concrete network implementations, and the entry point that
supplies them, live in the outer collector layer under ``research/``. Keeping
them there is what lets ``src/`` depend on nothing outside itself.

Importing this module has no side effects: it opens no database, performs no
network call and constructs no client until :func:`main` is invoked.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .config import (
    DEFAULT_SNAPSHOT_INTERVAL_SECONDS,
    LiveDataConfig,
    normalize_coin,
    normalize_wallet_address,
)
from .hyperliquid_rest import CANDLE_INTERVALS, HyperliquidRestClient, Transport
from .hyperliquid_ws import ConnectionFactory, HyperliquidWebSocketClient
from .ingest import IngestOrchestrator
from .storage import LiveDataStore
from .sweep import DEFAULT_SNAPSHOT_TOP

DEFAULT_MAX_WATCH_ITERATIONS = 1000

#: Seconds to wait between coins in a ``candles`` run. The L2 candle probe
#: (2026-09-04) took three HTTP 429s at one request per second with 5000-row
#: responses and none at one request per 2.5 s, so the pace is fixed here
#: rather than left to the operator.
CANDLE_REQUEST_PAUSE_SECONDS = 2.5

MILLISECONDS_PER_DAY = 86_400_000


@dataclass(frozen=True, slots=True)
class Dependencies:
    """Concrete I/O supplied by the caller.

    Commands that only touch the local database need nothing here. Commands
    that reach the venue require the matching dependency and fail with a clear
    message rather than silently constructing a transport of their own.
    """

    transport: Transport | None = None
    connection_factory: ConnectionFactory | None = None


def _wallet(value: str) -> str:
    try:
        return normalize_wallet_address(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _coin(value: str) -> str:
    try:
        return normalize_coin(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _coin_list(value: str) -> tuple[str, ...]:
    coins = tuple(_coin(part) for part in value.split(",") if part.strip())
    if not coins:
        raise argparse.ArgumentTypeError("--coins must name at least one coin")
    return coins


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser. Pure: no I/O, no client construction."""
    parser = argparse.ArgumentParser(
        prog="live_data",
        description="Read-only Hyperliquid observation pipeline. Never places orders.",
    )
    defaults = LiveDataConfig()
    parser.add_argument(
        "--db",
        type=Path,
        default=defaults.database_path,
        help="SQLite database path",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="create the database schema")

    backfill = subparsers.add_parser(
        "backfill", help="backfill a wallet's fills, funding and a position snapshot over REST"
    )
    backfill.add_argument("--wallet", type=_wallet, required=True)
    backfill.add_argument("--days", type=int, required=True, help="trailing window in days")

    watch = subparsers.add_parser("watch", help="tail wallets and coins over the websocket")
    watch.add_argument("--wallets", type=_wallet, nargs="+", default=[])
    watch.add_argument("--coins", type=_coin, nargs="+", default=[])
    watch.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_WATCH_ITERATIONS,
        help="stop after this many websocket frames",
    )
    watch.add_argument(
        "--snapshot-interval",
        type=float,
        default=DEFAULT_SNAPSHOT_INTERVAL_SECONDS,
        help="seconds between clearinghouse position snapshots per tracked wallet",
    )

    candles = subparsers.add_parser(
        "candles", help="fetch OHLCV candles for one or more coins over REST"
    )
    candles.add_argument(
        "--coins", type=_coin_list, required=True, help="comma-separated coin symbols"
    )
    candles.add_argument("--interval", choices=CANDLE_INTERVALS, default="15m")
    candles.add_argument(
        "--days", type=int, default=52, help="trailing window in days, ignored with --start-ms"
    )
    candles.add_argument("--start-ms", type=int, default=None)
    candles.add_argument("--end-ms", type=int, default=None)

    mids = subparsers.add_parser(
        "mids", help="sample allMids once and store the mid for each named coin"
    )
    mids.add_argument(
        "--coins", type=_coin_list, required=True, help="comma-separated coin symbols"
    )

    sweep = subparsers.add_parser(
        "sweep", help="one arm B pass over a frozen cohort: mids, then fills and funding"
    )
    sweep.add_argument(
        "--cohort", type=Path, required=True, help="path to the frozen cohort JSON record"
    )
    sweep.add_argument(
        "--coins",
        type=_coin_list,
        default=None,
        help="comma-separated coins to sample; defaults to the coins the cohort has traded",
    )
    sweep.add_argument(
        "--snapshot-top",
        type=int,
        default=DEFAULT_SNAPSHOT_TOP,
        help="take a position snapshot for this many leading cohort wallets",
    )

    subparsers.add_parser("status", help="report row counts and recent ingest runs")

    wallets = subparsers.add_parser(
        "wallets", help="list wallets discovered on the public tape, most active first"
    )
    wallets.add_argument("--limit", type=int, default=10)
    return parser


def _build_orchestrator(
    config: LiveDataConfig,
    store: LiveDataStore,
    dependencies: Dependencies,
    *,
    with_ws: bool,
) -> IngestOrchestrator:
    if dependencies.transport is None:
        raise ValueError("no HTTP transport was supplied")
    ws_client = None
    if with_ws:
        if dependencies.connection_factory is None:
            raise ValueError("no websocket connection factory was supplied")
        ws_client = HyperliquidWebSocketClient(
            config, connection_factory=dependencies.connection_factory
        )
    return IngestOrchestrator(
        config,
        store,
        HyperliquidRestClient(config, transport=dependencies.transport),
        ws_client=ws_client,
    )


def _cmd_init_db(args: argparse.Namespace, dependencies: Dependencies) -> int:
    with LiveDataStore(args.db) as store:
        print(f"initialized {args.db} ({store.count('ingest_runs')} ingest runs recorded)")
    return 0


def _cmd_backfill(args: argparse.Namespace, dependencies: Dependencies) -> int:
    if args.days <= 0:
        print("days must be positive", file=sys.stderr)
        return 2
    if dependencies.transport is None:
        print("backfill needs an HTTP transport; run the collector entry point", file=sys.stderr)
        return 2
    config = LiveDataConfig(database_path=args.db, tracked_wallets=(args.wallet,))
    with LiveDataStore(args.db) as store:
        orchestrator = _build_orchestrator(config, store, dependencies, with_ws=False)
        result = orchestrator.backfill_wallet(args.wallet, args.days)
    print(
        f"run {result.run_id}: {result.fills_written} new of {result.fills_seen} fills "
        f"over {result.pages} page(s), "
        f"{result.funding_written} new of {result.funding_seen} funding rows, "
        f"{'1' if result.snapshot_taken else '0'} position snapshot, "
        f"{orchestrator.consumed_weight} request weight"
        + (
            ""
            if result.window_exhausted
            else f"; WINDOW TRUNCATED at page cap, covered until {result.covered_until_ms} ms"
        )
    )
    return 0


def _cmd_watch(args: argparse.Namespace, dependencies: Dependencies) -> int:
    if not args.wallets and not args.coins:
        print("watch requires at least one --wallets or --coins value", file=sys.stderr)
        return 2
    if dependencies.transport is None or dependencies.connection_factory is None:
        print("watch needs network transports; run the collector entry point", file=sys.stderr)
        return 2
    config = LiveDataConfig(
        database_path=args.db,
        tracked_wallets=tuple(args.wallets),
        tracked_coins=tuple(args.coins),
        snapshot_interval_seconds=args.snapshot_interval,
    )
    with LiveDataStore(args.db) as store:
        orchestrator = _build_orchestrator(config, store, dependencies, with_ws=True)
        result = orchestrator.watch(max_iterations=args.max_iterations)
    print(
        f"run {result.run_id}: {result.fills_written} new fills, "
        f"{result.mids_written} mids, {result.snapshots_written} new of "
        f"{result.snapshots_taken} position snapshot(s), "
        f"{result.trades_written} new of {result.trades_seen} trades, "
        f"{result.wallets_discovered} wallet(s) discovered, "
        f"{len(result.errors)} handler error(s), "
        f"{orchestrator.consumed_weight} request weight"
    )
    return 0


def _cmd_candles(
    args: argparse.Namespace, dependencies: Dependencies, *, sleeper=time.sleep
) -> int:
    """Fetch each coin's candle series in turn, paced between coins.

    This is a bounded pass over the coins the operator named, not a schedule:
    it ends when the list ends and starts again only when a person runs it.
    """
    if dependencies.transport is None:
        print("candles needs an HTTP transport; run the collector entry point", file=sys.stderr)
        return 2
    now = int(time.time() * 1000)
    end_ms = args.end_ms if args.end_ms is not None else now
    if args.start_ms is not None:
        start_ms = args.start_ms
    else:
        if args.days <= 0:
            print("days must be positive", file=sys.stderr)
            return 2
        start_ms = max(0, end_ms - args.days * MILLISECONDS_PER_DAY)
    if end_ms < start_ms:
        print("end-ms must not precede start-ms", file=sys.stderr)
        return 2

    config = LiveDataConfig(database_path=args.db, tracked_coins=tuple(args.coins))
    reports = []
    with LiveDataStore(args.db) as store:
        orchestrator = _build_orchestrator(config, store, dependencies, with_ws=False)
        for index, coin in enumerate(args.coins):
            if index:
                # A fixed pause between requests, required by the rate-limit
                # evidence behind CANDLE_REQUEST_PAUSE_SECONDS.
                sleeper(CANDLE_REQUEST_PAUSE_SECONDS)
            reports.append(
                orchestrator.fetch_candles(
                    coin, args.interval, start_ms, end_ms
                )
            )
        weight = orchestrator.consumed_weight
    print(json.dumps({"candles": reports, "request_weight": weight}, indent=2, sort_keys=True))
    return 0


def _cmd_mids(args: argparse.Namespace, dependencies: Dependencies) -> int:
    """Sample the mid price once for the named coins.

    One request of weight 2. The five-minute cadence arm B wants is the
    operator's own loop around this command; there is no scheduler here.
    """
    if dependencies.transport is None:
        print("mids needs an HTTP transport; run the collector entry point", file=sys.stderr)
        return 2
    config = LiveDataConfig(database_path=args.db, tracked_coins=tuple(args.coins))
    with LiveDataStore(args.db) as store:
        orchestrator = _build_orchestrator(config, store, dependencies, with_ws=False)
        report = orchestrator.poll_mids(args.coins)
        weight = orchestrator.consumed_weight
    print(json.dumps({"mids": report, "request_weight": weight}, indent=2, sort_keys=True))
    return 0


def _load_cohort(path: Path) -> tuple[int, tuple[str, ...]]:
    """Read a frozen cohort record. Raises ``ValueError`` on anything malformed.

    The order in the file is the order the sweep uses, so the leading wallets
    are the ones that get a position snapshot. Sorting here would silently
    change which wallets those are.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: cohort record must be a JSON object")
    t0_ms = payload.get("t0_ms")
    if not isinstance(t0_ms, int) or isinstance(t0_ms, bool) or t0_ms <= 0:
        raise ValueError(f"{path}: t0_ms must be a positive millisecond timestamp")
    cohort = payload.get("cohort")
    if not isinstance(cohort, list) or not cohort:
        raise ValueError(f"{path}: cohort must be a nonempty list of addresses")
    addresses = tuple(normalize_wallet_address(address) for address in cohort)
    if len(set(addresses)) != len(addresses):
        raise ValueError(f"{path}: cohort lists the same wallet twice")
    return t0_ms, addresses


def _cmd_sweep(args: argparse.Namespace, dependencies: Dependencies) -> int:
    """Run one bounded sweep over the frozen cohort.

    This walks the cohort once and returns. Repeating it is the operator's
    decision, made by running the command again.
    """
    if dependencies.transport is None:
        print("sweep needs an HTTP transport; run the collector entry point", file=sys.stderr)
        return 2
    if args.snapshot_top < 0:
        print("snapshot-top must not be negative", file=sys.stderr)
        return 2
    try:
        t0_ms, cohort = _load_cohort(args.cohort)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"cannot read cohort: {exc}", file=sys.stderr)
        return 2

    with LiveDataStore(args.db) as store:
        coins = tuple(args.coins) if args.coins else tuple(store.distinct_fill_coins(cohort))
        if not coins:
            print(
                "no coins to sample: pass --coins, the cohort has no stored fills",
                file=sys.stderr,
            )
            return 2
        # The cohort is not put in ``tracked_wallets``: that field is the
        # websocket subscription list, capped at the venue's ten distinct
        # users, and a sweep is REST-only over hundreds of addresses.
        config = LiveDataConfig(database_path=args.db, tracked_coins=coins)
        orchestrator = _build_orchestrator(config, store, dependencies, with_ws=False)
        report = orchestrator.sweep(
            cohort, coins, t0_ms=t0_ms, snapshot_top=args.snapshot_top
        )
        weight = orchestrator.consumed_weight
    failed = sorted(
        address
        for address, entry in report["per_wallet"].items()
        if entry.get("status") != "ok"
    )
    print(
        json.dumps(
            {
                "run_id": report["run_id"],
                "mids": report["mids"],
                "sweep": report["sweep"],
                "failed_wallets": failed,
                "request_weight": weight,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _cmd_status(args: argparse.Namespace, dependencies: Dependencies) -> int:
    with LiveDataStore(args.db, create=False) as store:
        report = {
            "database": str(args.db),
            "counts": {
                table: store.count(table)
                for table in (
                    "wallets", "fills", "positions_snapshot", "mids", "funding", "trades",
                    "candles",
                )
            },
            "recent_runs": store.recent_runs(5),
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _cmd_wallets(args: argparse.Namespace, dependencies: Dependencies) -> int:
    if args.limit <= 0:
        print("limit must be positive", file=sys.stderr)
        return 2
    with LiveDataStore(args.db, create=False) as store:
        rows = store.most_active_wallets(args.limit)
    print(json.dumps(rows, indent=2, sort_keys=True))
    return 0


_COMMANDS = {
    "init-db": _cmd_init_db,
    "backfill": _cmd_backfill,
    "watch": _cmd_watch,
    "candles": _cmd_candles,
    "mids": _cmd_mids,
    "sweep": _cmd_sweep,
    "status": _cmd_status,
    "wallets": _cmd_wallets,
}


def main(argv: Sequence[str] | None = None, *, dependencies: Dependencies | None = None) -> int:
    """Parse ``argv`` and run the selected command against injected dependencies.

    There is no ``__main__`` guard here on purpose. Running this module
    directly would need it to build its own transports, which is exactly the
    dependency this package refuses to take.
    """
    args = build_parser().parse_args(argv)
    return _COMMANDS[args.command](args, dependencies or Dependencies())
