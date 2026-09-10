"""The L2 arm report pieces, shared by both arm runners.

Everything here reads the database or the simulator's outputs and turns them
into the blocks the evidence file carries beside the primary result: the
instrument scope as the freeze measured it, the price series' provenance and
span, the survivorship measures, the diagnostics roll-up and the plain-language
limitations. Nothing here scores, prices or decides.
"""

from __future__ import annotations

import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.copyability.cohort import InstrumentScope
from src.copyability.inputs import MarketData, SourceFill
from src.live_data.storage import LiveDataStore

from .cohort_pipeline_freeze import candle_complete_coins, coin_list_sha256

MILLISECONDS_PER_DAY = 86_400_000
FOUR_PLACES = Decimal("0.0001")
#: The plan's two survivorship measures.
STOPPED_TAIL_DAYS = 7
FADED_TAIL_DAYS = 14
FADED_SHARE = Decimal("0.25")


class ScopeMismatchError(ValueError):
    """The scope rebuilt now is not the scope the freeze measured."""


# -- scope -----------------------------------------------------------------------


def funding_coins_until(store: LiveDataStore, *, until_ms: int) -> frozenset[str]:
    """Coins with a funding row at or before ``until_ms``.

    The freeze read every funding row in the database at the instant it ran,
    which is the same set as "every row at or before T0" as long as the
    freeze preceded the first arm B sweep. Bounding here keeps a later rerun,
    after sweeps have written post-T0 funding, from seeing a different scope.
    """
    rows = store.connection.execute(
        "SELECT DISTINCT coin FROM funding WHERE event_time_ms <= ?", (until_ms,)
    ).fetchall()
    return frozenset(row["coin"] for row in rows)


def build_scope(
    store: LiveDataStore, candles_json: Path, *, excluded: Iterable[str], until_ms: int
) -> tuple[InstrumentScope, dict]:
    """The scope the freeze built, and the lists behind it for the file."""
    payload = json.loads(candles_json.read_text(encoding="utf-8"))
    funding = funding_coins_until(store, until_ms=until_ms)
    complete = candle_complete_coins(payload)
    scope = InstrumentScope(
        funding_coins=funding, candle_complete_coins=complete, excluded_coins=frozenset(excluded)
    )
    lists = {
        "funding_coins": sorted(funding),
        "candle_complete_coins": sorted(complete),
        "excluded": sorted(scope.excluded_coins),
        "deviation_from_plan_wording": (
            "funding scope is every coin with a funding row at or before T0, as the freeze "
            "measured it, not only coins with a rate observed inside the characterisation set"
        ),
    }
    return scope, lists


def check_scope_against_record(lists: Mapping[str, Any], record_scope: Mapping[str, Any]) -> None:
    """Refuse when the rebuilt scope differs in size from what the freeze recorded."""
    for key in ("funding_coins", "candle_complete_coins"):
        recorded = record_scope.get(key)
        if recorded is None:
            continue
        if int(recorded) != len(lists[key]):
            raise ScopeMismatchError(
                f"{key}: the freeze recorded {recorded} coins, this database yields {len(lists[key])}; "
                "the scope is not the one the cohort was frozen under"
            )
        recorded_hash = record_scope.get(f"{key}_sha256")
        if recorded_hash is not None and recorded_hash != coin_list_sha256(lists[key]):
            raise ScopeMismatchError(
                f"{key}: the same number of coins, but not the same coins the freeze recorded; "
                "the scope is not the one the cohort was frozen under"
            )


def split_by_scope(
    fills_by_wallet: Mapping[str, Sequence[SourceFill]], scope: InstrumentScope
) -> tuple[dict[str, list[SourceFill]], dict[str, int]]:
    """In-scope fills per wallet, and how many each wallet lost to scope."""
    kept: dict[str, list[SourceFill]] = {}
    dropped: dict[str, int] = {}
    for wallet, fills in fills_by_wallet.items():
        inside = [f for f in fills if scope.in_scope(f.coin)]
        kept[wallet] = inside
        dropped[wallet] = len(fills) - len(inside)
    return kept, dropped


# -- the ledger ------------------------------------------------------------------------


def sweep_closure(store: LiveDataStore, wallets: Sequence[str], *, window_end_ms: int, finished_by_ms: int) -> dict:
    """Has the closing sweep touched every cohort wallet?

    A completed ``sweep_wallet`` row that finished at or after the window end
    (and within the closing grace) says the collection for that wallet ran
    to the end, whatever it found. A wallet without one has not been closed,
    and reading the arm before it is would be the interim look the approval
    forbids.
    """
    rows = store.connection.execute(
        "SELECT wallet_address, MAX(finished_at_ms) AS finished FROM ingest_runs "
        "WHERE mode = 'sweep_wallet' AND status = 'completed' AND finished_at_ms >= ? AND finished_at_ms <= ? "
        "GROUP BY wallet_address",
        (window_end_ms, finished_by_ms),
    ).fetchall()
    finished = {row["wallet_address"]: int(row["finished"]) for row in rows}
    per_wallet = {w: finished.get(w) for w in wallets}
    present = [t for t in per_wallet.values() if t is not None]
    return {
        "rule": "every cohort wallet carries a completed sweep_wallet row that finished at or after the "
                "window end and within the closing grace",
        "closed": all(t is not None for t in per_wallet.values()),
        "wallets_without_closing_sweep": sorted(w for w, t in per_wallet.items() if t is None),
        "earliest_closing_sweep_ms": min(present) if present else None,
        "latest_closing_sweep_ms": max(present) if present else None,
    }


# -- price series ---------------------------------------------------------------------


def series_span(
    market: MarketData, coins: Iterable[str], *, window: tuple[int, int], tolerance_ms: int, end_tolerance_ms: int = 0,
) -> tuple[frozenset[str], dict]:
    """Which coins' price series really span the window, and each series' edges.

    The tolerances are the caller's: the first usable quote must sit less
    than ``tolerance_ms`` after the window start (two candle intervals for
    closes, which is what the freeze's post-check admits on opens; the
    freshness bound for mids) and the last at most ``end_tolerance_ms``
    before the window end (zero for candles fetched after the window closed,
    the freshness bound for mids). A coin whose table cannot price the whole
    window is scored on skipped copies unless it is taken out of scope,
    which is what the caller does with the result.
    """
    start_ms, end_ms = window
    spanning: set[str] = set()
    detail: dict[str, dict] = {}
    for coin in sorted(coins):
        series = market.prices.get(coin)
        first, last = (series.first_time_ms, series.last_time_ms) if series is not None else (None, None)
        rows = len(series) if series is not None else 0
        ok = (first is not None and last is not None
              and first < start_ms + tolerance_ms and last >= end_ms - end_tolerance_ms)
        detail[coin] = {"rows": rows, "first_ms": first, "last_ms": last, "spans_window": ok}
        if ok:
            spanning.add(coin)
    return frozenset(spanning), detail


def candle_provenance(store: LiveDataStore, coins: Iterable[str], *, interval: str) -> dict:
    """When the candles used were fetched, and by which runs."""
    per_coin: dict[str, dict] = {}
    for coin in sorted(coins):
        row = store.connection.execute(
            "SELECT COUNT(*) AS n, MIN(ingested_at_ms) AS first, MAX(ingested_at_ms) AS last "
            "FROM candles WHERE coin = ? AND interval = ?",
            (coin, interval),
        ).fetchone()
        per_coin[coin] = {"rows": int(row["n"]), "first_ingested_at_ms": row["first"], "last_ingested_at_ms": row["last"]}
    runs = _runs(store, "fetch_candles", detail_key="candles", fields=("coin", "interval", "rows", "exhausted"))
    return {"kind": "candles", "interval": interval, "ingested_by_coin": per_coin, "fetch_runs": runs}


def mids_provenance(store: LiveDataStore, coins: Iterable[str], *, window: tuple[int, int], max_age_ms: int) -> dict:
    """How densely each coin's mid was sampled over the window, where the
    series has holes wider than the freshness bound, and by how many polls
    and sweeps."""
    start_ms, end_ms = window
    per_coin: dict[str, dict] = {}
    for coin in sorted(coins):
        times = [int(r["observed_at_ms"]) for r in store.connection.execute(
            "SELECT observed_at_ms FROM mids WHERE coin = ? AND observed_at_ms BETWEEN ? AND ? ORDER BY observed_at_ms",
            (coin, start_ms, end_ms),
        )]
        gaps = [later - earlier for earlier, later in zip(times, times[1:])]
        per_coin[coin] = {
            "rows_in_window": len(times),
            "first_observed_ms": times[0] if times else None, "last_observed_ms": times[-1] if times else None,
            "mean_spacing_ms": None if len(times) < 2 else int((times[-1] - times[0]) / (len(times) - 1)),
            "max_gap_ms": max(gaps) if gaps else None,
            "gaps_over_max_age": sum(1 for gap in gaps if gap > max_age_ms),
        }

    def runs(mode: str) -> dict:
        row = store.connection.execute(
            "SELECT COUNT(*) AS n, MIN(started_at_ms) AS first, MAX(finished_at_ms) AS last "
            "FROM ingest_runs WHERE mode = ? AND status = 'completed'", (mode,)
        ).fetchone()
        return {"completed": int(row["n"]), "first_started_ms": row["first"], "last_finished_ms": row["last"]}

    return {"kind": "mids", "max_age_ms": max_age_ms, "sampled_by_coin": per_coin,
            "polls": runs("mids"), "sweeps": runs("sweep")}


def _runs(store: LiveDataStore, mode: str, *, detail_key: str, fields: Sequence[str]) -> list[dict]:
    runs = []
    for run in store.connection.execute(
        "SELECT run_id, started_at_ms, finished_at_ms, status, coverage FROM ingest_runs "
        "WHERE mode = ? ORDER BY started_at_ms", (mode,)
    ):
        coverage = json.loads(run["coverage"]) if run["coverage"] else {}
        detail = coverage.get(detail_key, {})
        runs.append({
            "run_id": run["run_id"], "started_at_ms": run["started_at_ms"], "finished_at_ms": run["finished_at_ms"],
            "status": run["status"], **{f: detail.get(f) for f in fields},
        })
    return runs


# -- survivorship ---------------------------------------------------------------------


def survivorship(
    fills_by_wallet: Mapping[str, Sequence[SourceFill]],
    wallets: Sequence[str],
    *,
    window: tuple[int, int],
    characterisation: tuple[int, int],
) -> dict:
    """The plan's two measures, per wallet and as shares of the frozen cohort.

    Measured on every fill the wallet made, in or out of scope: the question is
    whether the wallet quit, not whether it quit the instruments the study
    can price. ``stopped``: the wallet's last in-window fill lies more than 7
    days before the window's end. ``faded``: its fill count in the last 14
    evaluation days is under a quarter of what its characterisation rate
    predicts for 14 days; a wallet with no characterisation fills has no rate
    and is not judged. A wallet with no fill inside the window at all is the
    most stopped case there is and counts as stopped.

    Shares are reported over the frozen cohort, which is the plan's wording,
    and over the wallets active in the window, which is the narrower reading;
    both denominators are written so neither has to be guessed.
    """
    start_ms, end_ms = window
    c_start, c_end = characterisation
    c_days = Decimal(c_end - c_start) / Decimal(MILLISECONDS_PER_DAY)
    tail_start = end_ms - FADED_TAIL_DAYS * MILLISECONDS_PER_DAY
    per_wallet: dict[str, dict] = {}
    stopped = faded = judged_fade = active = 0
    for wallet in wallets:
        fills = fills_by_wallet.get(wallet, ())
        inside = [f.time_ms for f in fills if start_ms <= f.time_ms <= end_ms]
        c_count = sum(1 for f in fills if c_start <= f.time_ms <= c_end)
        entry: dict[str, Any] = {"fills_in_window": len(inside), "characterisation_fills": c_count}
        if inside:
            active += 1
            last = max(inside)
            entry["last_fill_ms"] = last
            entry["stopped"] = (end_ms - last) > STOPPED_TAIL_DAYS * MILLISECONDS_PER_DAY
        else:
            entry["last_fill_ms"] = None
            entry["stopped"] = True
        stopped += entry["stopped"]
        if c_count == 0:
            entry["faded"] = None
        else:
            expected = (Decimal(c_count) / c_days) * FADED_TAIL_DAYS
            tail = sum(1 for t in inside if t >= tail_start)
            entry["faded"] = Decimal(tail) < FADED_SHARE * expected
            entry["tail_fills"] = tail
            entry["expected_tail_fills"] = str(expected.quantize(FOUR_PLACES))
            judged_fade += 1
            faded += entry["faded"]
        per_wallet[wallet] = entry
    cohort = len(wallets)
    return {
        "definition": {
            "stopped": f"last in-window fill more than {STOPPED_TAIL_DAYS} days before the window end, "
                       "or no in-window fill at all; measured on every fill, in or out of scope",
            "faded": f"fills in the last {FADED_TAIL_DAYS} evaluation days under {FADED_SHARE} of the "
                     "characterisation rate's prediction; wallets without characterisation fills are not judged",
            "denominators": "shares are over the frozen cohort; the active-only shares are given beside them",
        },
        "cohort": cohort,
        "active_in_window": active,
        "stopped": stopped,
        "stopped_share_of_cohort": _share(stopped, cohort),
        "stopped_share_of_active": _share(stopped - (cohort - active), active),
        "faded": faded,
        "faded_judged": judged_fade,
        "faded_share_of_cohort": _share(faded, cohort),
        "faded_share_of_judged": _share(faded, judged_fade),
        "per_wallet": per_wallet,
    }


def _share(count: int, total: int) -> str | None:
    return None if total <= 0 else str((Decimal(count) / Decimal(total)).quantize(FOUR_PLACES))


# -- diagnostics and limitations --------------------------------------------------------


def diagnostics_rollup(studies: Sequence[Any], *, latency_ms: int, coins_without_span: Iterable[str]) -> dict:
    """Counts a reader needs to weigh the result: what was skipped, stale, caught up, refused."""
    totals = Counter()
    refusal_reasons: Counter = Counter()
    for study in studies:
        if study.refusal is not None:
            refusal_reasons[study.refusal.split(":", 1)[0]] += 1
            continue
        outcome = next((o for o in study.outcomes if o.latency_ms == latency_ms), None)
        if outcome is None:
            continue
        totals["skipped_fills"] += outcome.skipped_fills
        totals["stale_price_skips"] += outcome.stale_price_skips
        totals["catch_up_fills"] += outcome.catch_up_fills
        totals["fills_after_cutoff"] += outcome.fills_after_cutoff
        totals["trades"] += outcome.trade_count
    return {
        "at_latency_ms": latency_ms,
        **{k: int(v) for k, v in sorted(totals.items())},
        "refusal_reasons": dict(sorted(refusal_reasons.items())),
        "coins_without_a_spanning_price_series": sorted(coins_without_span),
    }


def limitations(
    *, arm: str, survivorship_block: Mapping[str, Any], disclosures: Mapping[str, Any],
    pool_size: int, pool_cohort: int, cohort_size: int,
) -> list[str]:
    """The plain-language caveats the approval requires beside the result."""
    notes = []
    if arm == "A":
        notes.append(
            "Survivorship: the cohort was discovered at T0 from wallets active then, so wallets that "
            "stopped trading during the historical window could not be discovered and are absent by "
            "construction. Arm A's estimate is inflated by an unknown amount; this arm cannot see wallets "
            f"that quit. Measured here: {survivorship_block['stopped']} of {survivorship_block['cohort']} "
            f"cohort wallets stopped inside the window and {survivorship_block['faded']} of "
            f"{survivorship_block['faded_judged']} judged wallets faded."
        )
        notes.append("Arm A is the early read. It decides nothing; arm B, read after day 56, decides.")
    else:
        notes.append(
            "Arm B is forward and out of sample: the cohort was frozen before any of its fills existed, so "
            "wallets that stopped or faded during the window are inside the estimate, not missing from it. "
            f"Measured: {survivorship_block['stopped']} of {survivorship_block['cohort']} cohort wallets "
            f"stopped inside the window and {survivorship_block['faded']} of {survivorship_block['faded_judged']} "
            "judged wallets faded; a wallet that quit is scored on what it did before it quit."
        )
        notes.append("Arm B decides by the rule fixed before T0; arm A cannot overrule it in either direction.")
    notes += [
        f"Liquidity is assumed, not measured, for every coin ({disclosures['liquidity_assumed']} of "
        f"{disclosures['of_n']} wallets in the primary): no order book is read on this surface.",
        f"Funding hours the rate schedule could not price were charged as zero, in either direction, for "
        f"{disclosures['funding_incomplete']} of {disclosures['of_n']} wallets in the primary; the net is "
        "uncertain, not bounded, by that much.",
        f"Matched-random peers are drawn from the {pool_size} wallets the coverage ledger certifies over the "
        f"window ({pool_cohort} of them cohort wallets, {pool_size - pool_cohort} not), not from the frozen "
        f"cohort of {cohort_size} alone: a d_i measured against peers drawn from the cohort alone would cancel "
        "any return the cohort earns in common. Wallets the selection kept out of the cohort (market makers, "
        "rebate-dependent and under-characterised wallets among them) are in the pool; the pool's hash, each "
        "wallet's contributing peers and the cohort share of those peers are recorded.",
    ]
    return notes
