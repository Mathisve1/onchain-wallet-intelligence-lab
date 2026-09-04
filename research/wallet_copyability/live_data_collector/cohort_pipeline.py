"""Cohort discovery and characterisation: two bounded operator-started runs.

Phase 5 of ``research/wallet_copyability/live_data/L2_BUILD_PLAN.md``. The
selection logic itself is not here: it lives in :mod:`src.copyability.cohort`
and is deterministic and network-free. What this module adds is the operator
layer around it, in three subcommands:

``discover``
    Run tape sessions over a coin list until enough distinct wallets have been
    named on the public trades channel, then write the candidate list.
``characterise``
    Backfill 90 days of fills and funding for each candidate, one wallet at a
    time with a fixed pause, and write what each backfill actually covered.
``freeze``
    Build the instrument scope, run the selection and write the frozen cohort.
    That one lives in :mod:`.cohort_pipeline_freeze` purely for size.

Every subcommand is one bounded pass that a person starts. Nothing here
schedules, retries beyond what the REST client already does, or loops
unattended, and nothing here scores, prices or ranks a wallet: discovery
counts addresses, characterisation counts rows, and the freeze counts and
hashes. Which of them is worth copying is a question for the study, after T0.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from src.copyability.cohort import BUILDER_PREFIX, SPOT_PREFIX
from src.copyability.loader import load_coverage
from src.live_data.config import LiveDataConfig, normalize_coin, normalize_wallet_address
from src.live_data.hyperliquid_rest import HyperliquidRestClient
from src.live_data.hyperliquid_ws import HyperliquidWebSocketClient
from src.live_data.ingest import IngestOrchestrator
from src.live_data.storage import LiveDataStore

from .cohort_pipeline_freeze import add_freeze_arguments, run_freeze
from .transports import build_default_connection_factory, build_urllib_transport

MILLISECONDS_PER_DAY = 86_400_000

#: The three coins the L2 candle probe could not measure, each stopped by an
#: HTTP 429 rather than by an answer (``evidence/L2_CANDLE_PROBE_001.json``,
#: ``cohort_coverage_15m_last_52d.coins_not_measured_http_429``). Unmeasured is
#: out of scope: the analysis plan admits a coin only on a measurement.
UNMEASURED_COINS: tuple[str, ...] = ("xyz:BRENTOIL", "xyz:CRWV", "xyz:CXMT")

#: Websocket frames per second observed on a three-coin tape in L1-SESSION-001
#: (1000 frames in 254 seconds, ``evidence/L1_SESSION_001.json`` step 1). The
#: watch API bounds a session by frame count, not by time, so a requested
#: session length is converted through this measured rate.
TAPE_FRAMES_PER_SECOND = 1000.0 / 254.0

DEFAULT_TARGET = 600
DEFAULT_MAX_SESSIONS = 4
DEFAULT_SESSION_SECONDS = 300.0
DEFAULT_BACKFILL_DAYS = 90
DEFAULT_PAUSE_SECONDS = 1.0
PROGRESS_EVERY = 25
#: How stale a prior backfill may be and still count as covering the window
#: for ``--resume``. A backfill's coverage ends when it ran, so an exact match
#: against "now" would never resume anything.
DEFAULT_RESUME_GRACE_HOURS = 24.0

#: ``(coins, session_index, max_iterations) -> per-session summary``.
SessionRunner = Callable[[Sequence[str], int, int], Mapping[str, Any]]
#: ``(limit) -> candidate addresses, most active first``.
CandidateReader = Callable[[int], Sequence[str]]

#: The ranking rule the default candidate reader applies, in one sentence.
#: ``LiveDataStore.most_active_wallets`` (``src/live_data/storage.py``) orders
#: its SQL by ``trade_count DESC, address ASC``, so the first ``N`` candidates
#: discovery names are the wallets busiest on the tape, ties broken
#: lexicographically. This constant is the single place that rule is spelled
#: out; the discovery evidence's ``candidate_order`` field is derived from it
#: rather than hand-typed, so the two cannot drift apart.
DEFAULT_CANDIDATE_ORDER = (
    "most_active_wallets: trade_count desc over tape sessions, then lexicographic "
    "address asc (src/live_data/storage.py)"
)

#: What the ``candidate_order`` ranking implies about the candidate set, for
#: readers of the evidence file who did not read the code.
DEFAULT_SELECTION_NOTE = (
    "The candidate set is ranked by tape activity and is therefore biased "
    "toward the most active wallets seen; the cohort's own filters (market "
    "maker exclusion, minimum fills, instrument scope) run after this stage."
)


def _deduplicate_preserve_order(addresses: Iterable[str]) -> list[str]:
    """Distinct addresses, first occurrence kept, in first-seen order.

    ``discover`` cannot assume a :data:`CandidateReader` returns distinct
    addresses, so it deduplicates here rather than trusting the reader; the
    file itself still sorts the final candidate list for the evidence record.
    """
    return list(dict.fromkeys(addresses))


def _now_ms() -> int:
    return int(time.time() * 1000)


def iterations_for_seconds(
    seconds: float, *, frames_per_second: float = TAPE_FRAMES_PER_SECOND
) -> int:
    """Frame budget for a session of roughly ``seconds`` on the tape.

    The websocket session ends on a frame count, so a wall-clock bound can
    only be approximated through an observed rate. The rate is the L1
    measurement, not a guess, and the evidence file records both the requested
    seconds and the frames the session actually ran.
    """
    return max(1, int(seconds * frames_per_second))


def partition_coins(coins: Iterable[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split a coin list into what may be subscribed and what is excluded.

    The analysis plan puts spot indices (``@``-prefixed) and HIP-3 equity
    perpetuals (``xyz:``) out of scope, so subscribing to their tape would
    spend a session discovering wallets the study cannot evaluate. The same
    prefixes are what :func:`src.copyability.cohort.InstrumentScope.in_scope`
    refuses later; applying them at discovery only saves the session.
    """
    kept: list[str] = []
    excluded: list[str] = []
    for coin in coins:
        if coin.startswith(SPOT_PREFIX) or coin.startswith(BUILDER_PREFIX):
            excluded.append(coin)
        else:
            kept.append(coin)
    return tuple(kept), tuple(excluded)


def excluded_coins(coins: Iterable[str]) -> tuple[str, ...]:
    """Every coin this discovery run refuses, prefix-excluded and unmeasured."""
    _, prefixed = partition_coins(coins)
    return tuple(sorted(set(prefixed) | set(UNMEASURED_COINS)))


def discover(
    *,
    coins: Sequence[str],
    run_session: SessionRunner,
    read_candidates: CandidateReader,
    target: int = DEFAULT_TARGET,
    max_sessions: int = DEFAULT_MAX_SESSIONS,
    session_seconds: float = DEFAULT_SESSION_SECONDS,
    candidate_order: str = DEFAULT_CANDIDATE_ORDER,
    selection_note: str = DEFAULT_SELECTION_NOTE,
    clock_ms: Callable[[], int] = _now_ms,
    log: Callable[[str], None] = print,
) -> dict:
    """Run tape sessions until the candidate target or the session cap is hit.

    Two bounds, both hard: the run stops the moment ``target`` distinct
    candidates are known, and it never starts more than ``max_sessions``
    sessions. A session that fails is recorded and the walk continues, because
    a dropped websocket is a normal event on a tape and not a reason to lose
    the candidates the earlier sessions already found.

    ``read_candidates`` is not trusted to return distinct addresses, so the
    result is deduplicated (first occurrence kept) before it is counted
    against ``target`` or written to the evidence record. ``candidate_order``
    and ``selection_note`` describe how whatever ``read_candidates`` was
    passed in ranks its candidates; pass a different value than the default
    when the caller supplies a reader other than the default
    ``most_active_wallets``-backed one.
    """
    subscribed, _ = partition_coins(coins)
    started_ms = clock_ms()
    iterations = iterations_for_seconds(session_seconds)
    sessions: list[dict] = []
    candidates: list[str] = _deduplicate_preserve_order(read_candidates(target))

    for index in range(max_sessions):
        if len(candidates) >= target:
            break
        entry: dict = {
            "session": index,
            "coins": list(subscribed),
            "requested_seconds": session_seconds,
            "max_iterations": iterations,
        }
        session_started = clock_ms()
        try:
            summary = run_session(subscribed, index, iterations)
            entry.update(dict(summary))
        except Exception as exc:  # noqa: BLE001 - one lost socket must not lose the run
            entry["error"] = f"{type(exc).__name__}: {exc}"
            log(f"discover: session {index} failed: {entry['error']}")
        entry["elapsed_ms"] = clock_ms() - session_started
        candidates = _deduplicate_preserve_order(read_candidates(target))
        entry["candidates_after"] = len(candidates)
        sessions.append(entry)
        log(f"discover: session {index}: {len(candidates)} of {target} candidates")

    return {
        "started_ms": started_ms,
        "finished_ms": clock_ms(),
        "coins": list(subscribed),
        "excluded_coins": list(excluded_coins(coins)),
        "sessions": sessions,
        "candidates": sorted(candidates),
        "candidate_count": len(candidates),
        "candidate_order": candidate_order,
        "selection_note": selection_note,
        "target": target,
    }


def read_candidate_file(path: Path) -> list[str]:
    """The candidate addresses from a discovery evidence file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [normalize_wallet_address(w) for w in payload["candidates"]]


def covered_wallets(
    store: LiveDataStore,
    wallets: Sequence[str],
    *,
    now_ms: int,
    days: int,
    grace_ms: int,
) -> set[str]:
    """Wallets a completed backfill already covers over the trailing window.

    Coverage comes from the ``ingest_runs`` records through the same ledger the
    simulator certifies from, so a run truncated at the page cap contributes
    only the prefix it really read and does not let a wallet be skipped on a
    window nobody observed.
    """
    ledger = load_coverage(store)
    start_ms = max(0, now_ms - days * MILLISECONDS_PER_DAY)
    end_ms = max(start_ms, now_ms - grace_ms)
    return {w for w in wallets if ledger.is_fully_known(w, start_ms, end_ms)}


def characterise(
    orchestrator: Any,
    wallets: Sequence[str],
    *,
    days: int = DEFAULT_BACKFILL_DAYS,
    pause_seconds: float = DEFAULT_PAUSE_SECONDS,
    skip: Iterable[str] = (),
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
    clock_ms: Callable[[], int] = _now_ms,
) -> dict:
    """Backfill every candidate in turn, paced, recording what each run covered.

    One wallet at a time with a fixed pause between the wallets that actually
    make requests, and no retry loop of our own: the REST client already
    retries the statuses it is allowed to. A wallet whose backfill raises is
    recorded as failed with its error and the walk continues, because losing
    the remaining candidates to one bad address would cost a whole pass over
    the venue's rate budget.
    """
    skipped = set(skip)
    started_ms = clock_ms()
    rows: list[dict] = []
    attempted = 0
    failed = 0

    for index, wallet in enumerate(wallets, 1):
        if wallet in skipped:
            rows.append({"wallet": wallet, "status": "skipped", "reason": "already_covered"})
            continue
        if attempted:
            sleep(pause_seconds)
        attempted += 1
        try:
            result = orchestrator.backfill_wallet(wallet, days)
        except Exception as exc:  # noqa: BLE001 - one wallet must not end the pass
            failed += 1
            message = f"{type(exc).__name__}: {exc}"
            log(f"characterise: {wallet} failed: {message}")
            rows.append({"wallet": wallet, "status": "failed", "error": message})
        else:
            rows.append(
                {
                    "wallet": wallet,
                    "status": "completed",
                    "run_id": result.run_id,
                    "fills_seen": result.fills_seen,
                    "fills_written": result.fills_written,
                    "funding_seen": result.funding_seen,
                    "funding_written": result.funding_written,
                    "pages": result.pages,
                    "fills_truncated_at_page_cap": not result.window_exhausted,
                    "funding_truncated_at_response_cap": not result.funding_exhausted,
                    "covered_until_ms": result.covered_until_ms,
                    "snapshot_taken": result.snapshot_taken,
                }
            )
        if index % PROGRESS_EVERY == 0:
            log(f"characterise: {index} of {len(wallets)} wallets, {failed} failed")

    completed = [row for row in rows if row["status"] == "completed"]
    return {
        "started_ms": started_ms,
        "finished_ms": clock_ms(),
        "days": days,
        "pause_seconds": pause_seconds,
        "wallets": rows,
        "totals": {
            "candidates": len(wallets),
            "attempted": attempted,
            "completed": len(completed),
            "failed": failed,
            "skipped": len(rows) - attempted,
            "fills_seen": sum(row["fills_seen"] for row in completed),
            "fills_written": sum(row["fills_written"] for row in completed),
            "funding_seen": sum(row["funding_seen"] for row in completed),
            "funding_written": sum(row["funding_written"] for row in completed),
            "fills_truncated": sum(
                1 for row in completed if row["fills_truncated_at_page_cap"]
            ),
            "funding_truncated": sum(
                1 for row in completed if row["funding_truncated_at_response_cap"]
            ),
            "consumed_weight": orchestrator.consumed_weight,
        },
    }


def write_evidence(path: Path, payload: Mapping[str, Any]) -> None:
    """Write one evidence file, byte-stable for the same inputs."""
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _default_session_runner(db: Path, snapshot_interval: float) -> SessionRunner:
    """A tape session through the same orchestrator the ``watch`` CLI uses."""

    def run(coins: Sequence[str], index: int, max_iterations: int) -> Mapping[str, Any]:
        config = LiveDataConfig(database_path=db, tracked_coins=tuple(coins),
                                snapshot_interval_seconds=snapshot_interval)
        with LiveDataStore(db) as store:
            rest = HyperliquidRestClient(config, transport=build_urllib_transport())
            ws = HyperliquidWebSocketClient(
                config, connection_factory=build_default_connection_factory()
            )
            orchestrator = IngestOrchestrator(config, store, rest, ws_client=ws)
            result = orchestrator.watch(max_iterations=max_iterations)
        return {
            "run_id": result.run_id,
            "iterations": result.iterations,
            "trades_seen": result.trades_seen,
            "trades_written": result.trades_written,
            "wallets_discovered": result.wallets_discovered,
            "errors": len(result.errors),
        }

    return run


def _default_candidate_reader(db: Path) -> CandidateReader:
    def read(limit: int) -> list[str]:
        with LiveDataStore(db, create=False) as store:
            return [row["address"] for row in store.most_active_wallets(limit)]

    return read


def _default_orchestrator(db: Path, store: LiveDataStore, wallet: str | None = None) -> IngestOrchestrator:
    config = LiveDataConfig(
        database_path=db, tracked_wallets=() if wallet is None else (wallet,)
    )
    rest = HyperliquidRestClient(config, transport=build_urllib_transport())
    return IngestOrchestrator(config, store, rest, ws_client=None)


def _coin_list(value: str) -> tuple[str, ...]:
    coins = tuple(normalize_coin(part) for part in value.split(",") if part.strip())
    if not coins:
        raise argparse.ArgumentTypeError("--coins must name at least one coin")
    return coins


def build_parser() -> argparse.ArgumentParser:
    """Pure: builds no store, no transport and no orchestrator."""
    parser = argparse.ArgumentParser(
        prog="cohort_pipeline",
        description="L2 cohort discovery, characterisation and freeze. Read-only.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    found = subparsers.add_parser("discover", help="collect candidate wallets from the tape")
    found.add_argument("--db", type=Path, required=True)
    found.add_argument("--coins", type=_coin_list, required=True)
    found.add_argument("--target", type=int, default=DEFAULT_TARGET)
    found.add_argument("--max-sessions", type=int, default=DEFAULT_MAX_SESSIONS)
    found.add_argument("--session-seconds", type=float, default=DEFAULT_SESSION_SECONDS)
    found.add_argument("--snapshot-interval", type=float, default=60.0)
    found.add_argument("--out", type=Path, required=True)

    marked = subparsers.add_parser("characterise", help="backfill every candidate wallet")
    marked.add_argument("--db", type=Path, required=True)
    marked.add_argument("--candidates", type=Path, required=True)
    marked.add_argument("--days", type=int, default=DEFAULT_BACKFILL_DAYS)
    marked.add_argument("--pause", type=float, default=DEFAULT_PAUSE_SECONDS)
    marked.add_argument("--resume", action="store_true")
    marked.add_argument("--resume-grace-hours", type=float, default=DEFAULT_RESUME_GRACE_HOURS)
    marked.add_argument("--out", type=Path, required=True)

    add_freeze_arguments(subparsers.add_parser("freeze", help="freeze the cohort at T0"))
    return parser


def _cmd_discover(args: argparse.Namespace, *, log: Callable[[str], None]) -> int:
    report = discover(
        coins=args.coins,
        run_session=_default_session_runner(args.db, args.snapshot_interval),
        read_candidates=_default_candidate_reader(args.db),
        target=args.target,
        max_sessions=args.max_sessions,
        session_seconds=args.session_seconds,
        log=log,
    )
    write_evidence(args.out, report)
    log(f"discover: {report['candidate_count']} candidates of {report['target']}")
    return 0


def _cmd_characterise(args: argparse.Namespace, *, log: Callable[[str], None]) -> int:
    wallets = read_candidate_file(args.candidates)
    grace_ms = int(args.resume_grace_hours * 3_600_000)
    with LiveDataStore(args.db) as store:
        skip = (
            covered_wallets(store, wallets, now_ms=_now_ms(), days=args.days, grace_ms=grace_ms)
            if args.resume
            else set()
        )
        orchestrator = _default_orchestrator(args.db, store)
        report = characterise(
            orchestrator, wallets, days=args.days, pause_seconds=args.pause, skip=skip, log=log
        )
    write_evidence(args.out, report)
    log(json.dumps(report["totals"], sort_keys=True))
    return 0


def main(argv: Sequence[str] | None = None, *, log: Callable[[str], None] = print) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "discover":
        return _cmd_discover(args, log=log)
    if args.command == "characterise":
        return _cmd_characterise(args, log=log)
    return run_freeze(args, log=log)


if __name__ == "__main__":
    raise SystemExit(main())
