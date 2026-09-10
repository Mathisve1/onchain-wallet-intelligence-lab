"""The freeze half of the cohort pipeline: scope, selection, and the record.

Split out of :mod:`.cohort_pipeline` for size; the two are one command surface.

The freeze is the moment the study stops being able to choose. It reads fills
that are already in the database, builds the instrument scope from what was
actually measured, runs :func:`src.copyability.cohort.select_cohort` and writes
the frozen list with its digest. It counts and hashes; it never scores, prices
or ranks. Below the plan's minimum of 200 evaluable wallets it writes the
counts and refuses with exit code 2, so the owner can see how far short the
pass fell without a cohort list existing to be run against.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from src.copyability.cohort import (
    CohortSelection,
    cohort_hash,
    InstrumentScope,
    freeze_record,
    select_cohort,
)
from src.copyability.loader import coverage_snapshot, load_coverage, load_fills
from src.live_data.config import normalize_coin, normalize_wallet_address
from src.live_data.storage import LiveDataStore

from .l2_arm_inputs import BENCHMARK_COIN, L2_LEDGER_MODES, MAX_PRICE_AGE_MS

MILLISECONDS_PER_DAY = 86_400_000

#: The plan's hard stop: below this many evaluable wallets the study does not
#: proceed to evaluation (``L2_ANALYSIS_PLAN.md``, "Hard stop before evaluation").
MINIMUM_EVALUABLE = 200

DEFAULT_BACKFILL_DAYS = 90
DEFAULT_CHARACTERISATION_DAYS = 30


def characterisation_window(
    t0_ms: int,
    *,
    backfill_days: int = DEFAULT_BACKFILL_DAYS,
    characterisation_days: int = DEFAULT_CHARACTERISATION_DAYS,
) -> tuple[int, int]:
    """The oldest ``characterisation_days`` of the backfill, relative to T0.

    With the plan's defaults that is ``[T0-90d, T0-60d]``. The oldest slice is
    the one that matters: characterising on days that overlap the evaluation
    window would select wallets on the same fills the study then scores.
    """
    start_ms = t0_ms - backfill_days * MILLISECONDS_PER_DAY
    return start_ms, start_ms + characterisation_days * MILLISECONDS_PER_DAY


def funding_coins_in_db(store: LiveDataStore) -> frozenset[str]:
    """Every coin with at least one funding row: the measured funding set."""
    rows = store.connection.execute("SELECT DISTINCT coin FROM funding").fetchall()
    return frozenset(row["coin"] for row in rows)


class FreezeInputError(ValueError):
    """A freeze input file is not the shape this module knows how to read."""


def coin_list_sha256(coins: Iterable[str]) -> str:
    """A digest of a sorted coin list, so a scope can be compared as a set."""
    return hashlib.sha256("\n".join(sorted(set(coins))).encode("utf-8")).hexdigest()


def candle_complete_coins(payload: Mapping[str, Any]) -> frozenset[str]:
    """Coins the phase 6 post-check marked complete.

    Raises :class:`FreezeInputError` when the payload carries no ``per_coin``
    list. Defaulting to an empty set here would hand ``build_scope`` an empty
    candle set, and the freeze would then report ``HARD_STOP: 0 evaluable
    wallets`` -- a sentence that reads as a finding about the cohort when it is
    really a wrong file passed on the command line.
    """
    per_coin = payload.get("per_coin")
    if not isinstance(per_coin, list):
        raise FreezeInputError(
            "candle post-check has no 'per_coin' list; got keys "
            f"{sorted(payload)!r}. Pass the file phase 6 (arm_a_candles) wrote."
        )
    return frozenset(
        entry["coin"]
        for entry in per_coin
        if isinstance(entry, Mapping) and entry.get("complete") and entry.get("coin")
    )


def build_scope(
    *,
    funding: Iterable[str],
    candles: Iterable[str],
    excluded: Iterable[str],
    funding_source: str,
    candle_source: str,
) -> tuple[InstrumentScope, dict]:
    """The scope plus the record of where each of its three sets came from.

    The provenance is part of the evidence, not decoration: a scope built from
    a coin list typed on the command line is a weaker claim than one built
    from the funding rows and the candle post-check, and the record has to say
    which one this freeze used.
    """
    scope = InstrumentScope(
        funding_coins=frozenset(funding),
        candle_complete_coins=frozenset(candles),
        excluded_coins=frozenset(excluded),
    )
    record = {
        "funding_coins": len(scope.funding_coins),
        "candle_complete_coins": len(scope.candle_complete_coins),
        "funding_coins_sha256": coin_list_sha256(scope.funding_coins),
        "candle_complete_coins_sha256": coin_list_sha256(scope.candle_complete_coins),
        "excluded": sorted(scope.excluded_coins),
        "sources": {"funding": funding_source, "candles": candle_source},
    }
    return scope, record


#: The venue's rolling 15-minute candle retention, measured by the phase 6
#: probe (``L2_CANDLE_PROBE_001.json``: ``history_depth_days["15m"] = 52.2``).
#: Arm A's window opens at T0-52d, so the retention is what a day of delay
#: costs: the oldest evaluation day falls off the back as T0 moves forward.
CANDLE_RETENTION_DAYS_15M = 52.2
ARM_A_WINDOW_OPENS_DAYS_BEFORE_T0 = 52


def hard_stop_report(record: Mapping[str, Any], *, minimum: int) -> str:
    """Outcome 1 of the plan's pre-registered reading, as a report.

    ``L2_ANALYSIS_PLAN.md``: "Fewer than 200 evaluable wallets after
    filtering. The run stops before any evaluation and returns to the owner,
    who widens the pool. The report states the clock price of the delay."
    That clock price is the one figure the owner needs to decide how long
    they may take, and nothing else in the repository states it.

    Every count here is the freeze record's own. The clock price is the
    plan's own arithmetic on the probe's measured retention, and it is
    labelled as what it is.
    """
    counts = record.get("stage_counts") or {}
    reasons = record.get("per_wallet_reason") or {}
    evaluable = record.get("evaluable_count", 0)
    lines = [
        "# L2 cohort freeze: HARD STOP",
        "",
        "**No evaluation was run and no cohort was frozen.** The plan's first pre-registered outcome: "
        f"fewer than {minimum} evaluable wallets after filtering, so the study returns to the owner to "
        "widen the pool. No underpowered study is run to have something.",
        "",
        f"Evaluable wallets: {evaluable}, against a minimum of {minimum}.",
        "",
        "## n after every filter stage",
        "",
    ]
    lines += ["| stage | n |", "|---|---|"]
    lines += [f"| {stage} | {n} |" for stage, n in sorted(counts.items())]
    lines += ["", "Why each candidate was excluded:", "", "| reason | n |", "|---|---|"]
    lines += [f"| {reason} | {n} |" for reason, n in sorted(reasons.items())]
    lines += [
        "",
        "## The clock price of the delay",
        "",
        f"Arm A's window opens {ARM_A_WINDOW_OPENS_DAYS_BEFORE_T0} days before T0, and the venue keeps "
        f"{CANDLE_RETENTION_DAYS_15M} days of 15-minute candles on a rolling basis. Every day T0 moves "
        "forward, the oldest evaluation day falls out of retention and cannot be fetched again.",
        "",
        "| days of delay | evaluation days arm A can still cover |",
        "|---|---|",
    ]
    for delay in (0, 1, 7, 14, 30):
        remaining = CANDLE_RETENTION_DAYS_15M - delay
        lines.append(f"| {delay} | {round(remaining, 1)} |")
    lines += [
        "",
        "The figure is the probe's measured retention minus the delay; it is arithmetic on a measured "
        "constant, not an estimate of anything about the wallets.",
        "",
        "## What is not allowed here",
        "",
        "- Rerunning the freeze with different flags until 200 is reached. The plan calls that a result, "
        "not a cohort.",
        "- Lowering the minimum. It is the plan's, and the runner refuses a record that lowers it.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _candidate_fills(
    store: LiveDataStore, candidates: Sequence[str] | None
) -> dict[str, list]:
    """Fills per candidate, with named candidates that have none kept as empty.

    A candidate the backfill never returned a fill for is still a candidate
    that was discovered and did not qualify. Dropping it here would quietly
    shrink ``discovered`` and make the funnel look tighter than it was.
    """
    fills = load_fills(store, candidates)
    if candidates is None:
        return fills
    return {wallet: fills.get(wallet, []) for wallet in candidates}


def freeze(
    store: LiveDataStore,
    *,
    t0_ms: int,
    plan_commit: str,
    scope: InstrumentScope,
    scope_record: Mapping[str, Any],
    window: tuple[int, int],
    candidates: Sequence[str] | None = None,
    minimum: int = MINIMUM_EVALUABLE,
) -> tuple[dict, CohortSelection]:
    """Select, freeze and describe. Pure apart from reading the store."""
    # T0 is the freeze instant, taken after the last backfill: the ledger the
    # freeze reads is the rows that had finished by T0, and the record carries
    # a snapshot of them so arm A can refuse to run on any other ledger. A row
    # that finished after T0 means T0 was typed too early.
    snapshot = coverage_snapshot(store, modes=L2_LEDGER_MODES, finished_by_ms=t0_ms)
    if snapshot["run_ids_sha256"] != coverage_snapshot(store, modes=L2_LEDGER_MODES)["run_ids_sha256"]:
        raise FreezeInputError(
            "collection rows finished after T0; T0 is the freeze instant and must not precede the last backfill"
        )
    # Arm B prices on the polled mids and its window opens at T0, so its first
    # usable quote must sit within the freshness bound of T0. Nothing can
    # supply that afterwards: a mids series that starts late makes the
    # decisive arm unrunnable for the whole 56 days. The only moment this can
    # be caught is here, so the freeze refuses a T0 the poller has not reached.
    row = store.connection.execute(
        "SELECT MIN(observed_at_ms) AS first FROM mids WHERE coin = ?", (BENCHMARK_COIN,)
    ).fetchone()
    first_mid = None if row["first"] is None else int(row["first"])
    if first_mid is None or first_mid > t0_ms:
        raise FreezeInputError(
            f"no {BENCHMARK_COIN} mid at or before T0 ({first_mid} is the first): start the mids poll before "
            f"freezing. Arm B's first quote must sit within {MAX_PRICE_AGE_MS} ms of T0 and cannot be collected "
            "afterwards, so a freeze taken before the poller starts makes the decisive arm unrunnable."
        )
    # The ledger, not an assertion, decides whether a candidate's window was
    # observed in full: a wallet whose backfill stopped inside the window is
    # excluded as WINDOW_UNOBSERVED rather than characterised on a fragment.
    selection = select_cohort(
        _candidate_fills(store, candidates),
        scope=scope,
        characterisation_window=window,
        certify=load_coverage(store, modes=L2_LEDGER_MODES, finished_by_ms=t0_ms).certify,
    )
    record = dict(
        freeze_record(
            t0_ms=t0_ms,
            wallets=selection.evaluable,
            plan_commit=plan_commit,
            stage_counts=selection.stage_counts,
            minimum=minimum,
        )
    )
    start_ms, end_ms = window
    record["characterisation_window"] = {
        "start_ms": start_ms,
        "end_ms": end_ms,
        "days": (end_ms - start_ms) / MILLISECONDS_PER_DAY,
    }
    record["scope"] = dict(scope_record)
    record["per_wallet_reason"] = dict(Counter(selection.per_wallet.values()))
    record["minimum_evaluable"] = minimum
    record["ledger_snapshot"] = snapshot
    # Every candidate this freeze judged, cohort member or not. Recording the
    # set is not the same as deciding that the matched-random peers are drawn
    # from it -- that is the owner's pre-T0 amendment -- but the set has to be
    # named at T0 either way, because only wallets swept over the forward
    # window can be certified over it, and the sweep needs a list.
    pool = sorted(selection.per_wallet)
    record["pool"] = pool
    record["pool_sha256"] = cohort_hash(pool)
    record["pool_definition"] = (
        "every characterised wallet this freeze read, cohort member or not; whether the matched-random peers "
        "are drawn from it is fixed by the plan, not by this record"
    )
    record["benchmark_first_mid_ms"] = first_mid
    return record, selection


def add_freeze_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--t0-ms", type=int, required=True, dest="t0_ms")
    parser.add_argument("--plan-commit", required=True)
    parser.add_argument("--backfill-days", type=int, default=DEFAULT_BACKFILL_DAYS)
    parser.add_argument(
        "--characterisation-days", type=int, default=DEFAULT_CHARACTERISATION_DAYS
    )
    parser.add_argument("--candidates", type=Path, default=None)
    parser.add_argument("--candles-json", type=Path, default=None)
    parser.add_argument("--candle-complete-coins", default=None)
    parser.add_argument("--funding-coins-from-db", action="store_true")
    parser.add_argument("--funding-coins", default=None)
    parser.add_argument("--minimum", type=int, default=MINIMUM_EVALUABLE)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def _coin_set(value: str) -> tuple[str, ...]:
    return tuple(normalize_coin(part.strip()) for part in value.split(",") if part.strip())


def _resolve_funding(args: argparse.Namespace, store: LiveDataStore) -> tuple[frozenset[str], str]:
    if args.funding_coins_from_db:
        return funding_coins_in_db(store), "database:funding rows"
    if args.funding_coins:
        return frozenset(_coin_set(args.funding_coins)), "argument:--funding-coins"
    raise ValueError("pass --funding-coins-from-db or --funding-coins")


def _resolve_candles(args: argparse.Namespace) -> tuple[frozenset[str], str]:
    if args.candles_json is not None and args.candles_json.exists():
        payload = json.loads(args.candles_json.read_text(encoding="utf-8"))
        return candle_complete_coins(payload), f"post_check:{args.candles_json.name}"
    if args.candle_complete_coins:
        source = "argument:--candle-complete-coins"
        if args.candles_json is not None:
            source += f" (post-check file {args.candles_json.name} absent)"
        return frozenset(_coin_set(args.candle_complete_coins)), source
    raise ValueError(
        "pass --candles-json pointing at an existing post-check, or --candle-complete-coins"
    )


def run_freeze(args: argparse.Namespace, *, log: Callable[[str], None] = print) -> int:
    """Run the freeze subcommand.

    Exit 0 on a cohort at or above the minimum, 2 on the hard stop and on any
    input the freeze refuses. The file is written on the hard stop: the counts
    are what the owner needs in order to decide whether to widen the candidate
    pool, and the record's ``cohort`` is empty, so nothing can be run against
    it by accident.

    A refused input is a sentence, not a traceback. This runs once, on the T0
    day, in front of an operator with a clock; the two things it can say are
    what is wrong and what to do about it.
    """
    from .cohort_pipeline import UNMEASURED_COINS, read_candidate_file, write_evidence

    candidates = (
        None if args.candidates is None else [
            normalize_wallet_address(w) for w in read_candidate_file(args.candidates)
        ]
    )
    window = characterisation_window(
        args.t0_ms,
        backfill_days=args.backfill_days,
        characterisation_days=args.characterisation_days,
    )
    with LiveDataStore(args.db, create=False) as store:
        funding, funding_source = _resolve_funding(args, store)
        candles, candle_source = _resolve_candles(args)
        scope, scope_record = build_scope(
            funding=funding,
            candles=candles,
            excluded=UNMEASURED_COINS,
            funding_source=funding_source,
            candle_source=candle_source,
        )
        try:
            record, _ = freeze(
                store,
                t0_ms=args.t0_ms,
                plan_commit=args.plan_commit,
                scope=scope,
                scope_record=scope_record,
                window=window,
                candidates=candidates,
                minimum=args.minimum,
            )
        except FreezeInputError as exc:
            log(f"freeze: refusing to freeze: {exc}")
            return 2
    write_evidence(args.out, record)

    log(json.dumps(record["stage_counts"], sort_keys=True))
    log(f"cohort_sha256: {record['cohort_sha256']}")
    log(f"plan_commit: {record['plan_commit']}")
    if record["hard_stop"]:
        log(
            f"HARD_STOP: {record['evaluable_count']} evaluable wallets, "
            f"minimum {args.minimum}"
        )
        # Outcome 1 of the plan's pre-registered reading has a report, and it
        # states the clock price of the delay the owner is about to take.
        report_path = args.out.with_name(args.out.stem + "_HARD_STOP.md")
        report_path.write_text(
            hard_stop_report(record, minimum=args.minimum), encoding="utf-8", newline="\n"
        )
        log(f"hard-stop report: {report_path}")
        return 2
    return 0
