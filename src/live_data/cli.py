"""Command line entry point for the read-only live data pipeline.

Run as ``python -m live_data.cli`` with ``src`` on ``PYTHONPATH``, or as
``python -m src.live_data.cli`` from the project root.

Importing this module has no side effects: it opens no database, performs no
network call and constructs no client until :func:`main` is invoked.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .config import LiveDataConfig, normalize_coin, normalize_wallet_address
from .hyperliquid_rest import HyperliquidRestClient
from .hyperliquid_ws import HyperliquidWebSocketClient
from .ingest import IngestOrchestrator
from .storage import LiveDataStore

DEFAULT_MAX_WATCH_ITERATIONS = 1000


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
    config: LiveDataConfig, store: LiveDataStore, *, with_ws: bool
) -> IngestOrchestrator:
    return IngestOrchestrator(
        config,
        store,
        HyperliquidRestClient(config),
        ws_client=HyperliquidWebSocketClient(config) if with_ws else None,
    )


def _cmd_init_db(args: argparse.Namespace) -> int:
    with LiveDataStore(args.db) as store:
        print(f"initialized {args.db} ({store.count('ingest_runs')} ingest runs recorded)")
    return 0


def _cmd_backfill(args: argparse.Namespace) -> int:
    if args.days <= 0:
        print("days must be positive", file=sys.stderr)
        return 2
    config = LiveDataConfig(database_path=args.db, tracked_wallets=(args.wallet,))
    with LiveDataStore(args.db) as store:
        orchestrator = _build_orchestrator(config, store, with_ws=False)
        result = orchestrator.backfill_days(args.wallet, args.days)
    print(
        f"run {result.run_id}: {result.records_written} new of {result.records_seen} fills "
        f"over {result.pages} page(s)"
    )
    return 0


def _cmd_watch(args: argparse.Namespace) -> int:
    if not args.wallets and not args.coins:
        print("watch requires at least one --wallets or --coins value", file=sys.stderr)
        return 2
    config = LiveDataConfig(
        database_path=args.db,
        tracked_wallets=tuple(args.wallets),
        tracked_coins=tuple(args.coins),
    )
    with LiveDataStore(args.db) as store:
        orchestrator = _build_orchestrator(config, store, with_ws=True)
        result = orchestrator.watch(max_iterations=args.max_iterations)
    print(
        f"run {result.run_id}: {result.fills_written} new fills, "
        f"{result.mids_written} mids, {len(result.errors)} handler error(s)"
    )
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
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


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return _COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
