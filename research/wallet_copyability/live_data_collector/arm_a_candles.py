"""Arm A candle fetch: one bounded pass over the in-scope coins at T0.

Phase 6 of ``research/wallet_copyability/live_data/L2_BUILD_PLAN.md``. For
every coin the cohort trades, this asks ``candles --interval 15m`` (via
:meth:`~src.live_data.ingest.IngestOrchestrator.fetch_candles`, phase 3) over
``[T0-52d, T0]`` and records a post-check: coins whose candle series has a gap
wider than one interval leave scope, and the evidence file records which ones.

This is a bounded pass over the coin list the operator names, not a schedule:
it starts once, walks the list once with a fixed pause between coins, and
ends. Nothing here retries a coin or loops unattended.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from src.live_data.config import LiveDataConfig, normalize_coin
from src.live_data.hyperliquid_rest import CANDLE_INTERVALS, HyperliquidRestClient
from src.live_data.ingest import IngestOrchestrator
from src.live_data.storage import LiveDataStore

from .transports import build_urllib_transport

#: Matches CANDLE_REQUEST_PAUSE_SECONDS in src.live_data.cli: the L2 candle
#: probe (2026-09-04) took 429s at 1 request/second and none at 2.5 s.
DEFAULT_PAUSE_SECONDS = 2.5
DEFAULT_DAYS = 52
DEFAULT_INTERVAL = "15m"
MILLISECONDS_PER_DAY = 86_400_000

#: The venue's 15-minute candle spacing, as milliseconds. A gap wider than
#: this in a coin's series means the price is not available continuously
#: enough for a 15-minute price-age bound, so the coin leaves scope.
FIFTEEN_MINUTE_MS = 900_000

#: Milliseconds per candle interval, for the scope gate. ``--interval``
#: accepts every interval the venue supports, so the gate must measure against
#: the one actually requested rather than assuming 15 minutes.
INTERVAL_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": FIFTEEN_MINUTE_MS,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}

OrchestratorFactory = Callable[[LiveDataConfig, LiveDataStore], Any]


def _interval_ms(interval: str) -> int:
    """Spacing of one ``interval``, in milliseconds."""
    try:
        return INTERVAL_MS[interval]
    except KeyError:  # pragma: no cover - argparse restricts this to CANDLE_INTERVALS
        raise ValueError(f"unknown candle interval {interval!r}") from None


def plan_window(t0_ms: int, days: int = DEFAULT_DAYS) -> tuple[int, int]:
    """Return the ``[T0-days, T0]`` window, in milliseconds, as a pair."""
    return t0_ms - days * MILLISECONDS_PER_DAY, t0_ms


def fetch_all(
    orchestrator: Any,
    coins: Sequence[str],
    *,
    t0_ms: int,
    interval: str = DEFAULT_INTERVAL,
    days: int = DEFAULT_DAYS,
    pause_seconds: float = DEFAULT_PAUSE_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> list[dict]:
    """Fetch each coin's candle series in turn, paced between coins.

    One bounded walk over ``coins``, in order: no retry, no scheduler. A
    failure fetching one coin is caught, logged and recorded as an error entry
    so the remaining coins still get a chance; it never aborts the arm.
    """
    start_ms, end_ms = plan_window(t0_ms, days)
    results: list[dict] = []
    for index, coin in enumerate(coins):
        if index:
            sleep(pause_seconds)
        try:
            coverage = orchestrator.fetch_candles(coin, interval, start_ms, end_ms)
        except Exception as exc:  # noqa: BLE001 - one bad coin must not abort the arm
            message = f"{type(exc).__name__}: {exc}"
            log(f"arm_a_candles: {coin} failed: {message}")
            results.append({"coin": coin, "error": message})
            continue
        results.append(coverage)
    return results


def post_check(
    results: Sequence[dict],
    *,
    interval_ms: int = FIFTEEN_MINUTE_MS,
    expected_rows: int | None = None,
    window: tuple[int, int] | None = None,
) -> dict:
    """Classify each coin's fetch result. Pure: no I/O, no ordering side effects.

    A coin is ``complete`` when it fetched without error, has at least one row,
    its maximum gap between consecutive open times does not exceed
    ``interval_ms``, and -- when ``window`` is given -- its series actually
    spans that window from end to end. Everything else is ``out_of_scope``:
    the cohort file is where that exclusion gets recorded, not this function.

    The window check is not optional in practice and :func:`main` always
    passes it. ``max_gap_ms`` is measured *between returned rows* only, and is
    0 for a single row, so a coin listed five days ago returns a few hundred
    dense candles for a 52-day request and looks flawless by gap alone. Without
    comparing ``first_open_ms``/``last_open_ms`` against the window,
    ``cohort_pipeline_freeze.candle_complete_coins`` would admit it to
    ``InstrumentScope`` as though its whole history were priced.
    """
    per_coin: list[dict] = []
    out_of_scope: list[str] = []
    total_rows = 0
    complete_count = 0

    for result in results:
        coin = result.get("coin")
        error = result.get("error")
        rows = int(result.get("rows", 0) or 0)
        max_gap_ms = result.get("max_gap_ms")
        exhausted = bool(result.get("exhausted", False))
        first_open_ms = result.get("first_open_ms")
        last_open_ms = result.get("last_open_ms")
        complete = error is None and rows > 0 and max_gap_ms is not None and max_gap_ms <= interval_ms
        if expected_rows is not None:
            complete = complete and rows >= expected_rows

        spans_window: bool | None = None
        if window is not None:
            start_ms, end_ms = window
            # Candle opens are interval-aligned, so the first open may sit up
            # to one interval after the requested start and the last up to one
            # interval before the requested end. Anything further is history
            # the venue does not have.
            spans_window = (
                isinstance(first_open_ms, int)
                and isinstance(last_open_ms, int)
                and first_open_ms - start_ms <= interval_ms
                and end_ms - last_open_ms <= interval_ms
            )
            complete = complete and spans_window

        entry: dict = {
            "coin": coin,
            "rows": rows,
            "max_gap_ms": max_gap_ms,
            "first_open_ms": first_open_ms,
            "last_open_ms": last_open_ms,
            "exhausted": exhausted,
            "complete": complete,
        }
        if spans_window is not None:
            entry["spans_window"] = spans_window
        if error is not None:
            entry["error"] = error
        per_coin.append(entry)

        total_rows += rows
        if complete:
            complete_count += 1
        else:
            out_of_scope.append(coin)

    totals = {
        "coins": len(per_coin),
        "complete": complete_count,
        "out_of_scope": len(out_of_scope),
        "rows": total_rows,
    }
    return {"per_coin": per_coin, "out_of_scope": out_of_scope, "totals": totals}


def _default_orchestrator_factory(config: LiveDataConfig, store: LiveDataStore) -> IngestOrchestrator:
    """Build the same orchestrator the ``candles`` CLI command uses."""
    rest = HyperliquidRestClient(config, transport=build_urllib_transport())
    return IngestOrchestrator(config, store, rest, ws_client=None)


def _coin_list(value: str) -> tuple[str, ...]:
    coins = tuple(normalize_coin(part) for part in value.split(",") if part.strip())
    if not coins:
        raise argparse.ArgumentTypeError("--coins must name at least one coin")
    return coins


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arm_a_candles",
        description="Arm A: fetch each in-scope coin's candle series over [T0-days, T0].",
    )
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--coins", type=_coin_list, required=True)
    parser.add_argument("--t0-ms", type=int, required=True, dest="t0_ms")
    parser.add_argument("--interval", choices=CANDLE_INTERVALS, default=DEFAULT_INTERVAL)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--pause", type=float, default=DEFAULT_PAUSE_SECONDS)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    orchestrator_factory: OrchestratorFactory = _default_orchestrator_factory,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> int:
    """Run the arm A candle fetch and write the evidence file.

    Exit code 0 even when some coins land in ``out_of_scope``: that is a
    measurement the cohort file records, not a failure of this run. Only a
    database or transport that cannot be set up returns non-zero.
    """
    args = _build_parser().parse_args(argv)
    if args.days <= 0:
        print("days must be positive", file=sys.stderr)
        return 2

    try:
        config = LiveDataConfig(database_path=args.db, tracked_coins=tuple(args.coins))
        with LiveDataStore(args.db) as store:
            orchestrator = orchestrator_factory(config, store)
            results = fetch_all(
                orchestrator,
                args.coins,
                t0_ms=args.t0_ms,
                interval=args.interval,
                days=args.days,
                pause_seconds=args.pause,
                sleep=sleep,
                log=log,
            )
    except Exception as exc:  # noqa: BLE001 - setup failure is the one non-zero case
        print(f"arm_a_candles: could not set up the database or transport: {exc}", file=sys.stderr)
        return 2

    start_ms, end_ms = plan_window(args.t0_ms, args.days)
    interval_ms = _interval_ms(args.interval)
    checked = post_check(results, interval_ms=interval_ms, window=(start_ms, end_ms))
    report = {
        "t0_ms": args.t0_ms,
        "interval": args.interval,
        "days": args.days,
        "window": {"start_ms": start_ms, "end_ms": end_ms},
        "per_coin": checked["per_coin"],
        "out_of_scope": checked["out_of_scope"],
        "totals": checked["totals"],
    }
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    log(json.dumps(checked["totals"], sort_keys=True))
    log(f"out_of_scope: {checked['out_of_scope']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
