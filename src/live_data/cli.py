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
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .config import LiveDataConfig, normalize_coin, normalize_wallet_address
from .hyperliquid_rest import HyperliquidRestClient, Transport
from .hyperliquid_ws import ConnectionFactory, HyperliquidWebSocketClient
from .ingest import IngestOrchestrator
from .storage import LiveDataStore

DEFAULT_MAX_WATCH_ITERATIONS = 1000


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

    backfill = subparsers.add_parser("backfill", help="backfill a wallet's fills over REST")
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

    subparsers.add_parser("status", help="report row counts and recent ingest runs")
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
        result = orchestrator.backfill_days(args.wallet, args.days)
    print(
        f"run {result.run_id}: {result.records_written} new of {result.records_seen} fills "
        f"over {result.pages} page(s)"
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
    )
    with LiveDataStore(args.db) as store:
        orchestrator = _build_orchestrator(config, store, dependencies, with_ws=True)
        result = orchestrator.watch(max_iterations=args.max_iterations)
    print(
        f"run {result.run_id}: {result.fills_written} new fills, "
        f"{result.mids_written} mids, {len(result.errors)} handler error(s)"
    )
    return 0


def _cmd_status(args: argparse.Namespace, dependencies: Dependencies) -> int:
    with LiveDataStore(args.db, create=False) as store:
        report = {
            "database": str(args.db),
            "counts": {
                table: store.count(table)
                for table in ("wallets", "fills", "positions_snapshot", "mids", "funding")
            },
            "recent_runs": store.recent_runs(5),
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


_COMMANDS = {
    "init-db": _cmd_init_db,
    "backfill": _cmd_backfill,
    "watch": _cmd_watch,
    "status": _cmd_status,
}


def main(argv: Sequence[str] | None = None, *, dependencies: Dependencies | None = None) -> int:
    """Parse ``argv`` and run the selected command against injected dependencies.

    There is no ``__main__`` guard here on purpose. Running this module
    directly would need it to build its own transports, which is exactly the
    dependency this package refuses to take.
    """
    args = build_parser().parse_args(argv)
    return _COMMANDS[args.command](args, dependencies or Dependencies())
