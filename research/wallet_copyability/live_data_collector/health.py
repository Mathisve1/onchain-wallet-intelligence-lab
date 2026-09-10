"""Arm B operational-health check: counts and timestamps, never a result.

Phase 8 of ``research/wallet_copyability/live_data/L2_BUILD_PLAN.md``. The
frozen ``L2_ANALYSIS_PLAN.md`` says only "operational health (sweep failures,
coverage gaps, candle gaps, unscorable wallets)" may be inspected during
collection, "by a script that prints counts and no returns." This module is
that script: it prints and returns counts, timestamps and gap sizes only,
against the read-only database, and never touches a price beyond what is
needed to measure a gap between observation timestamps.

It reads no price level, no fill price, no funding rate value and no closed
profit-and-loss column -- only ``event_time_ms``/``observed_at_ms``/
``open_time_ms`` for freshness and gap arithmetic, and counts.

Coverage-gap computation deliberately does not reuse
``src.copyability.loader.load_coverage``: that function merges backfill *and*
watch-session intervals into one ledger per wallet, which would fold a websocket
session's coverage into a number this ticket calls "backfill/sweep coverage
windows." This module therefore does its own parse of the ``coverage`` JSON,
but it applies the same truncation rule the loader does: a backfill window is
trusted only as far as ``coverage["fills"]["covered_until_ms"]``, falling back
to the window end only when ``fills["completed"]`` is set. Trusting
``window["end_time_ms"]`` alone would report a walk stopped at the page cap as
having covered its whole window.

The two modes are stored differently and must be read differently.
``backfill_wallet`` writes one run per wallet and fills in ``wallet_address``.
``sweep`` writes one run for the whole cohort with ``wallet_address`` left
NULL, and records what happened to each wallet in
``coverage["per_wallet"][address]``; a per-wallet ``status`` of ``"ok"`` means
that wallet was swept, anything else is that wallet's failure inside an
otherwise completed run. Filtering sweeps by ``wallet_address`` therefore
matches nothing at all, and reading only the run-level ``status`` hides every
per-wallet failure.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Sequence

from src.live_data.storage import LiveDataStore

from .l2_arm_inputs import BENCHMARK_COIN, MAX_PRICE_AGE_MS
from .l2_arm_report import arm_b_preconditions

#: The venue's 15-minute candle spacing and the arm B mids poll cadence, as
#: milliseconds. A gap wider than this in either series is flagged stale.
FIFTEEN_MINUTE_MS = 900_000

#: Modes that write one run per wallet, with ``wallet_address`` filled in
#: and a ``window``/``fills`` coverage block. ``sweep_wallet`` is the
#: per-wallet row a sweep writes alongside its cohort-level ``sweep`` run.
_WALLET_ADDRESSED_MODES = ("backfill_wallet", "sweep_wallet")
_WALLET_MODE_PLACEHOLDERS = ", ".join("?" * len(_WALLET_ADDRESSED_MODES))

#: ``sweep.py`` marks a wallet it swept without incident with this exact
#: status; any other string in that slot is that wallet's failure.
_SWEEP_OK = "ok"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _max_gap(sorted_times: Sequence[int]) -> int | None:
    """Largest difference between consecutive values, or ``None`` under two."""
    if len(sorted_times) < 2:
        return None
    return max(b - a for a, b in zip(sorted_times, sorted_times[1:]))


def _sweep_runs(store: LiveDataStore) -> list[dict]:
    """Every sweep run with its per-wallet coverage parsed, oldest first.

    Fetched once per report rather than once per wallet: a single sweep run
    carries the whole cohort, so the per-wallet lookup is a dict hit.
    """
    runs: list[dict] = []
    for run in store.connection.execute(
        "SELECT finished_at_ms, status, coverage FROM ingest_runs "
        "WHERE mode = 'sweep' ORDER BY started_at_ms"
    ):
        per_wallet: dict[str, Any] = {}
        if run["coverage"]:
            parsed = json.loads(run["coverage"])
            candidate = parsed.get("per_wallet")
            if isinstance(candidate, dict):
                per_wallet = candidate
        runs.append(
            {
                "finished_at_ms": run["finished_at_ms"],
                "status": run["status"],
                "per_wallet": per_wallet,
            }
        )
    return runs


def _writes_per_wallet_rows(store: LiveDataStore) -> bool:
    """Does this database record each swept wallet as its own run row?

    A sweep can record a wallet twice: once as a ``sweep_wallet`` row naming it
    in ``wallet_address``, and again inside the cohort-level ``sweep`` run's
    ``coverage["per_wallet"]``. Counting both would double every failure. Where
    the per-wallet rows exist they are the record of truth -- they carry their
    own status, timing and coverage -- so the embedded statuses are read only
    when no such rows are written.
    """
    row = store.connection.execute(
        "SELECT 1 FROM ingest_runs WHERE mode = 'sweep_wallet' LIMIT 1"
    ).fetchone()
    return row is not None


def _sweep_entry(run: dict, wallet_address: str) -> dict | None:
    """This wallet's entry in one sweep run, or ``None`` if it has none."""
    entry = run["per_wallet"].get(wallet_address)
    return entry if isinstance(entry, dict) else None


def _sweep_outcome(run: dict, wallet_address: str) -> str | None:
    """``"ok"``, a failure string, or ``None`` if the run never reached the wallet.

    A run that failed outright died before or during its wallet loop -- a
    failed mids poll aborts the sweep before any wallet is touched -- so a
    wallet with no entry in a failed run went unswept by it. That is a failure
    for the wallet, not merely an absence.
    """
    entry = _sweep_entry(run, wallet_address)
    if entry is not None:
        status = entry.get("status")
        return status if isinstance(status, str) else None
    if run["status"] == "failed":
        return "sweep run failed before this wallet"
    return None


def _coverage_windows(
    store: LiveDataStore,
    wallet_address: str,
    sweep_runs: Sequence[dict],
    *,
    per_wallet_rows: bool = False,
) -> list[tuple[int, int]]:
    """Trusted backfill/sweep coverage windows for one wallet, oldest first.

    A window is admitted only as far as the collector proved it read. For a
    backfill that is ``fills["covered_until_ms"]``, or the window end when
    ``fills["completed"]`` is set -- the same precondition
    ``loader.load_coverage`` applies. For a sweep it is the run's finish time,
    and only when that wallet's fill walk ran to exhaustion: a sweep cut short
    by the page cap records no bound worth trusting, so it contributes no
    window and the gap it left stays visible.
    """
    windows: list[tuple[int, int]] = []
    for run in store.connection.execute(
        "SELECT coverage FROM ingest_runs "
        "WHERE wallet_address = ? AND status = 'completed' "
        f"AND mode IN ({_WALLET_MODE_PLACEHOLDERS})",
        (wallet_address, *_WALLET_ADDRESSED_MODES),
    ):
        if not run["coverage"]:
            continue
        coverage = json.loads(run["coverage"])
        window = coverage.get("window", {})
        fills = coverage.get("fills", {})
        start_ms = window.get("start_time_ms")
        if not isinstance(start_ms, int) or not fills.get("attempted"):
            continue
        end_ms = fills.get("covered_until_ms")
        if not isinstance(end_ms, int):
            end_ms = window.get("end_time_ms") if fills.get("completed") else None
        if isinstance(end_ms, int) and end_ms >= start_ms:
            windows.append((start_ms, end_ms))

    # With per-wallet sweep rows on file the query above already returned each
    # sweep's window in its authoritative form; the digest embedded in the
    # cohort run would only repeat it. Same rule as the failure count.
    for run in () if per_wallet_rows else sweep_runs:
        entry = _sweep_entry(run, wallet_address)
        if entry is None or entry.get("status") != _SWEEP_OK:
            continue
        if not entry.get("fills_exhausted"):
            continue
        start_ms = entry.get("fills_from_ms")
        end_ms = run["finished_at_ms"]
        if isinstance(start_ms, int) and isinstance(end_ms, int) and end_ms >= start_ms:
            windows.append((start_ms, end_ms))

    windows.sort()
    return windows


def _coverage_gap_ms(windows: Sequence[tuple[int, int]]) -> int:
    """Largest interval between the end of one coverage window and the next start.

    Overlapping or touching windows contribute a zero-width gap. Fewer than two
    windows means there is nothing to measure a gap between, so this returns 0
    rather than a sentinel: "no gap observed" is the honest reading when there
    is at most one coverage window on file.
    """
    if len(windows) < 2:
        return 0
    gap = 0
    _, previous_end = windows[0]
    for start_ms, end_ms in windows[1:]:
        if start_ms > previous_end:
            gap = max(gap, start_ms - previous_end)
        previous_end = max(previous_end, end_ms)
    return gap


def wallet_health(store: LiveDataStore, wallets: Sequence[str], *, t0_ms: int) -> list[dict]:
    """Per-wallet operational counts and timestamps. No price, no P&L."""
    rows: list[dict] = []
    sweep_runs = _sweep_runs(store)
    per_wallet_rows = _writes_per_wallet_rows(store)
    for wallet in wallets:
        last_fill = store.connection.execute(
            "SELECT MAX(event_time_ms) AS t FROM fills WHERE wallet_address = ?", (wallet,)
        ).fetchone()
        fills_since_t0 = store.connection.execute(
            "SELECT COUNT(*) AS n FROM fills WHERE wallet_address = ? AND event_time_ms > ?",
            (wallet, t0_ms),
        ).fetchone()
        last_funding = store.connection.execute(
            "SELECT MAX(event_time_ms) AS t FROM funding WHERE wallet_address = ?", (wallet,)
        ).fetchone()
        funding_since_t0 = store.connection.execute(
            "SELECT COUNT(*) AS n FROM funding WHERE wallet_address = ? AND event_time_ms > ?",
            (wallet, t0_ms),
        ).fetchone()
        # Two sources, because the modes record a wallet differently: a
        # backfill (and a per-wallet sweep row) names it in the column, while a
        # cohort-level sweep run names it only inside its coverage.
        last_wallet_run = store.connection.execute(
            "SELECT MAX(finished_at_ms) AS t FROM ingest_runs "
            "WHERE wallet_address = ? AND status = 'completed' "
            f"AND mode IN ({_WALLET_MODE_PLACEHOLDERS})",
            (wallet, *_WALLET_ADDRESSED_MODES),
        ).fetchone()
        wallet_run_failures = store.connection.execute(
            "SELECT COUNT(*) AS n FROM ingest_runs WHERE wallet_address = ? AND status = 'failed'",
            (wallet,),
        ).fetchone()

        outcomes = [_sweep_outcome(run, wallet) for run in sweep_runs]
        swept_ms = [
            int(run["finished_at_ms"])
            for run, outcome in zip(sweep_runs, outcomes)
            if outcome == _SWEEP_OK and run["finished_at_ms"] is not None
        ]
        candidates = [
            t for t in (last_wallet_run["t"], max(swept_ms, default=None)) if t is not None
        ]
        last_sweep_ms = max(int(t) for t in candidates) if candidates else None
        sweep_failures = int(wallet_run_failures["n"])
        if not per_wallet_rows:
            sweep_failures += sum(
                1 for outcome in outcomes if outcome is not None and outcome != _SWEEP_OK
            )

        rows.append(
            {
                "wallet_address": wallet,
                "last_fill_ms": None if last_fill["t"] is None else int(last_fill["t"]),
                "fills_since_t0": int(fills_since_t0["n"]),
                "last_funding_ms": None if last_funding["t"] is None else int(last_funding["t"]),
                "funding_rows_since_t0": int(funding_since_t0["n"]),
                "last_sweep_ms": last_sweep_ms,
                "sweep_failures": sweep_failures,
                "coverage_gap_ms": _coverage_gap_ms(
                    _coverage_windows(
                        store, wallet, sweep_runs, per_wallet_rows=per_wallet_rows
                    )
                ),
            }
        )
    return rows


def coin_health(store: LiveDataStore, coins: Sequence[str], *, since_ms: int) -> list[dict]:
    """Per-coin observation counts and gap sizes. No price level is read."""
    rows: list[dict] = []
    for coin in coins:
        mids_rows = store.connection.execute(
            "SELECT COUNT(*) AS n FROM mids WHERE coin = ?", (coin,)
        ).fetchone()
        mids_last = store.connection.execute(
            "SELECT MAX(observed_at_ms) AS t FROM mids WHERE coin = ?", (coin,)
        ).fetchone()
        mids_recent = [
            int(r["observed_at_ms"])
            for r in store.connection.execute(
                "SELECT observed_at_ms FROM mids WHERE coin = ? AND observed_at_ms > ? "
                "ORDER BY observed_at_ms",
                (coin, since_ms),
            )
        ]
        candle_rows = store.connection.execute(
            "SELECT COUNT(*) AS n FROM candles WHERE coin = ? AND interval = '15m'", (coin,)
        ).fetchone()
        candle_last = store.connection.execute(
            "SELECT MAX(open_time_ms) AS t FROM candles WHERE coin = ? AND interval = '15m'",
            (coin,),
        ).fetchone()
        candles_recent = [
            int(r["open_time_ms"])
            for r in store.connection.execute(
                "SELECT open_time_ms FROM candles WHERE coin = ? AND interval = '15m' "
                "AND open_time_ms > ? ORDER BY open_time_ms",
                (coin, since_ms),
            )
        ]

        rows.append(
            {
                "coin": coin,
                "mids_rows": int(mids_rows["n"]),
                "mids_max_gap_ms": _max_gap(mids_recent),
                "mids_last_ms": None if mids_last["t"] is None else int(mids_last["t"]),
                "candle_rows": int(candle_rows["n"]),
                "candle_max_gap_ms": _max_gap(candles_recent),
                "candle_last_open_ms": None if candle_last["t"] is None else int(candle_last["t"]),
            }
        )
    return rows


def summary(
    wallet_rows: Sequence[dict],
    coin_rows: Sequence[dict],
    *,
    stale_after_ms: int,
    now_ms: int | None = None,
) -> dict:
    """Roll-up counts only: how many wallets or coins need attention, never why.

    ``now_ms`` defaults to wall-clock time and exists only so a test can pin
    it; every caller through :func:`main` gets the real clock.
    """
    now_ms = _now_ms() if now_ms is None else now_ms
    wallets_no_fill_since_t0 = sum(1 for row in wallet_rows if row["fills_since_t0"] == 0)
    wallets_stale_sweep = sum(
        1
        for row in wallet_rows
        if row["last_sweep_ms"] is None or now_ms - row["last_sweep_ms"] > stale_after_ms
    )
    wallets_with_failure = sum(1 for row in wallet_rows if row["sweep_failures"] > 0)
    coins_mids_gap = sum(
        1
        for row in coin_rows
        if row["mids_max_gap_ms"] is not None and row["mids_max_gap_ms"] > FIFTEEN_MINUTE_MS
    )
    coins_candle_gap = sum(
        1
        for row in coin_rows
        if row["candle_max_gap_ms"] is not None and row["candle_max_gap_ms"] > FIFTEEN_MINUTE_MS
    )
    coins_no_mids = sum(1 for row in coin_rows if row["mids_rows"] == 0)
    # A gap measured between samples cannot see a feed that simply stopped:
    # one sample, or a thousand samples that all predate the outage, yield no
    # gap at all. Freshness against the clock is what catches a dead feed.
    coins_stale_mids = sum(
        1
        for row in coin_rows
        if row["mids_last_ms"] is None or now_ms - row["mids_last_ms"] > stale_after_ms
    )
    coins_stale_candles = sum(
        1
        for row in coin_rows
        if row["candle_last_open_ms"] is None
        or now_ms - row["candle_last_open_ms"] > stale_after_ms
    )
    return {
        "wallets_total": len(wallet_rows),
        "wallets_no_fill_since_t0": wallets_no_fill_since_t0,
        "wallets_stale_sweep": wallets_stale_sweep,
        "wallets_with_failure": wallets_with_failure,
        "coins_mids_gap_over_15m": coins_mids_gap,
        "coins_candle_gap_over_15m": coins_candle_gap,
        "coins_no_mids": coins_no_mids,
        "coins_stale_mids": coins_stale_mids,
        "coins_stale_candles": coins_stale_candles,
    }


def _fills_coins(store: LiveDataStore, wallets: Sequence[str]) -> list[str]:
    """Distinct coins traded by the cohort, used when ``--coins`` is omitted."""
    if not wallets:
        return []
    placeholders = ",".join("?" * len(wallets))
    rows = store.connection.execute(
        f"SELECT DISTINCT coin FROM fills WHERE wallet_address IN ({placeholders}) ORDER BY coin",
        tuple(wallets),
    )
    return [r["coin"] for r in rows]


def _short(address: str) -> str:
    return address[:10]


def _print_report(
    wallet_rows: Sequence[dict], coin_rows: Sequence[dict], totals: dict, *, log
) -> None:
    log(
        f"{'wallet':<10} {'last_fill_ms':>14} {'fills_t0':>9} {'last_funding_ms':>16} "
        f"{'funding_t0':>11} {'last_sweep_ms':>14} {'failures':>9} {'gap_ms':>10}"
    )
    for row in wallet_rows:
        log(
            f"{_short(row['wallet_address']):<10} {str(row['last_fill_ms']):>14} "
            f"{row['fills_since_t0']:>9} {str(row['last_funding_ms']):>16} "
            f"{row['funding_rows_since_t0']:>11} {str(row['last_sweep_ms']):>14} "
            f"{row['sweep_failures']:>9} {row['coverage_gap_ms']:>10}"
        )
    log("")
    log(
        f"{'coin':<8} {'mids_rows':>10} {'mids_gap_ms':>13} {'mids_last_ms':>14} "
        f"{'candle_rows':>12} {'candle_gap_ms':>14} {'candle_last_open_ms':>20}"
    )
    for row in coin_rows:
        log(
            f"{row['coin']:<8} {row['mids_rows']:>10} {str(row['mids_max_gap_ms']):>13} "
            f"{str(row['mids_last_ms']):>14} {row['candle_rows']:>12} "
            f"{str(row['candle_max_gap_ms']):>14} {str(row['candle_last_open_ms']):>20}"
        )
    log("")
    log(json.dumps(totals, sort_keys=True))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="health",
        description=(
            "Arm B operational health: counts and timestamps only, never a return or a P&L."
        ),
    )
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--coins", type=str, default=None)
    parser.add_argument("--stale-hours", type=float, default=6.0, dest="stale_hours")
    parser.add_argument("--json", type=Path, default=None, dest="json_out")
    return parser


def main(argv: Sequence[str] | None = None, *, log=print) -> int:
    """Print the health report. Exits 0 whenever the database opens.

    Health is information, not a gate: the plan's stop rule allows only
    operational inspection during collection, so a bad reading here must never
    change the study's flow by way of this script's exit code.
    """
    args = _build_parser().parse_args(argv)

    cohort_payload: dict[str, Any] = json.loads(args.cohort.read_text(encoding="utf-8"))
    wallets: list[str] = list(cohort_payload["cohort"])
    t0_ms = int(cohort_payload["t0_ms"])
    stale_after_ms = int(args.stale_hours * 3_600_000)

    with LiveDataStore(args.db, create=False) as store:
        if args.coins:
            coins = [part.strip() for part in args.coins.split(",") if part.strip()]
        else:
            coins = _fills_coins(store, wallets)

        wallet_rows = wallet_health(store, wallets, t0_ms=t0_ms)
        coin_rows = coin_health(store, coins, since_ms=t0_ms)
        # What the day-56 read needs and no later step can repair.
        preconditions = arm_b_preconditions(
            store, t0_ms=t0_ms, benchmark_coin=BENCHMARK_COIN, max_age_ms=MAX_PRICE_AGE_MS,
            pool=list(cohort_payload.get("pool") or cohort_payload["cohort"]))

    totals = {**summary(wallet_rows, coin_rows, stale_after_ms=stale_after_ms),
              "arm_b_preconditions": preconditions}
    _print_report(wallet_rows, coin_rows, totals, log=log)

    if args.json_out is not None:
        args.json_out.write_text(
            json.dumps(
                {"wallets": wallet_rows, "coins": coin_rows, "summary": totals},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
