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
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from src.copyability.cohort import (
    CohortSelection,
    InstrumentScope,
    freeze_record,
    select_cohort,
)
from src.copyability.loader import load_fills
from src.live_data.config import normalize_coin, normalize_wallet_address
from src.live_data.storage import LiveDataStore

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
        "excluded": sorted(scope.excluded_coins),
        "sources": {"funding": funding_source, "candles": candle_source},
    }
    return scope, record


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
    selection = select_cohort(
        _candidate_fills(store, candidates), scope=scope, characterisation_window=window
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

    Exit 0 on a cohort at or above the minimum, 2 on the hard stop. The file is
    written either way: the counts are what the owner needs in order to decide
    whether to widen the candidate pool, and under a hard stop the record's
    ``cohort`` is empty, so nothing can be run against it by accident.
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
    write_evidence(args.out, record)

    log(json.dumps(record["stage_counts"], sort_keys=True))
    log(f"cohort_sha256: {record['cohort_sha256']}")
    log(f"plan_commit: {record['plan_commit']}")
    if record["hard_stop"]:
        log(
            f"HARD_STOP: {record['evaluable_count']} evaluable wallets, "
            f"minimum {args.minimum}"
        )
        return 2
    return 0
