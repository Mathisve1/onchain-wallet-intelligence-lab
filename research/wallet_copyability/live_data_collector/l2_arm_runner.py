"""The L2 arm runner: one core, two arms, under the frozen ``L2_ANALYSIS_PLAN.md``.

Phase 7 of ``research/wallet_copyability/live_data/L2_BUILD_PLAN.md`` for arm A
(variant A-45, DEC-044/DEC-046) and its forward counterpart for arm B. The two
arms differ in their window, their price series, and in what they may
conclude; everything else - the freeze record's checks, the scope, the peer
pool, the primary measure, the disclosures - is one code path, so the two
numbers the plan compares are computed the same way. The rules it applies:

* a freeze record is trusted only after its cohort list hashes to the
  recorded digest, and a cohort under the plan's minimum is not evaluated
  unless the caller says in so many words that this is an underpowered dry
  run;
* the instrument scope is the one the freeze measured, bounded to T0, and a
  coin whose price table does not span the window leaves scope, counted;
* matched-random peers are drawn from every wallet the coverage ledger
  certifies over the window, cohort member or not, and the pool's hash and
  composition are recorded (``l2_arm_report.limitations`` says why);
* the primary measure is ``d_i = R_i - M_i`` at 30 seconds, in points per
  14-day equivalent, with a two-sided one-sample t interval at alpha 0.05;
* **arm A** runs over ``T0-52d`` to ``T0-7d`` on 15-minute candle closes with
  a 15-minute price-age bound, is read by the rule fixed before it was seen,
  and decides nothing: its ``decision`` is always ``null``;
* **arm B** runs over ``T0`` to ``T0+56d`` on the polled mids, refuses to
  compute anything until every cohort wallet carries a closing sweep row and
  the ledger certifies that window for at least one of them (the approval
  forbids interim result inspection), and applies the decision rule: B
  decides, A measures.

Each runner reads the database and the freeze record and issues no request.
It writes the evidence file and prints counts only: never a return, never a
mean. While it runs it writes a checkpoint beside the evidence file after
every wallet, so an interruption after hour N leaves something to report from.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

from src.copyability.cohort import cohort_hash
from src.copyability.loader import build_market, coverage_snapshot, load_coverage, load_fills, load_funding_truncation
from src.copyability.metrics import as_row
from src.copyability.simulate import run_study
from src.live_data.storage import LiveDataStore

from . import l2_arm_report as report
from .l2_arm_inputs import (  # noqa: F401 - the arm modules and the tests reach these through this namespace
    DEFAULT_CLOSING_GRACE_DAYS,
    BENCHMARK_COIN,
    CANDLE_INTERVAL,
    CANDLE_INTERVAL_MS,
    CHARACTERISATION_END_DAYS_BEFORE_T0,
    CHARACTERISATION_START_DAYS_BEFORE_T0,
    EXIT_BROKE,
    EXIT_REFUSED,
    FEES,
    IMPACT_BPS_PER_FULL_DEPTH,
    L2_LEDGER_MODES,
    LIQUIDITY_TIERS,
    MATCHED_RANDOM_SAMPLE_SIZE,
    MATCHED_RANDOM_TOLERANCE,
    MAX_PRICE_AGE_MS,
    MILLISECONDS_PER_DAY,
    MOMENTUM_LOOKBACK_MS,
    MOMENTUM_STEP_MS,
    NOMINAL_CAPITAL,
    SIZE_SCALE,
    STATUS_BROKE,
    STATUS_CASE_STUDY,
    STATUS_DECIDED,
    STATUS_DRY_RUN,
    STATUS_EARLY_READ,
    STATUS_NOT_MEASURABLE,
    TIER1_COINS,
    TIER2_COINS,
    ArmRunnerError,
    ArmSpec,
    assumptions,
    characterisation_window,
    liquidity_for,
    load_cohort,
    pool_wallets,
    seed_from,
    study_config,
)
from .l2_arm_statistics import (
    MINIMUM_EVALUATED,
    PRIMARY_LATENCY_MS,
    decision_for,
    disclosure_rollup,
    inflation_block,
    primary_statistic,
    read_arm_a,
    secondary_summary,
)


# -- the run -----------------------------------------------------------------------------


def run(
    store: LiveDataStore, cohort: dict, spec: ArmSpec, *, candles_json: Path, plan_commit: str,
    dry_run: bool = False, checkpoint: Path | None = None, arm_a_json: Path | None = None,
    closing_grace_days: int = DEFAULT_CLOSING_GRACE_DAYS, log=print,
) -> tuple[dict, int]:
    t0_ms = int(cohort["t0_ms"])
    wallets = list(cohort["cohort"])
    window = spec.window(t0_ms)
    window_days = Decimal(window[1] - window[0]) / Decimal(MILLISECONDS_PER_DAY)
    what_broke: list[str] = []
    recorded_minimum = int(cohort.get("minimum_evaluable", MINIMUM_EVALUATED))

    # Arm A's file must not move whenever it is rerun: its ledger is the rows
    # that had finished by T0, and it must be the ledger the freeze recorded.
    # Arm B's is the REST-swept rows finishing within the closing grace.
    modes = L2_LEDGER_MODES
    grace_ms = closing_grace_days * MILLISECONDS_PER_DAY
    finished_by = t0_ms if spec.arm == "A" else window[1] + grace_ms
    ledger = load_coverage(store, modes=modes, finished_by_ms=finished_by)
    snapshot = coverage_snapshot(store, modes=modes, finished_by_ms=finished_by)
    closure: dict | None = None
    if spec.arm == "A":
        frozen = cohort["ledger_snapshot"].get("run_ids_sha256")
        if frozen != snapshot["run_ids_sha256"]:
            raise ArmRunnerError(
                "the ledger in this database (rows finished at or before T0) is not the ledger the freeze "
                f"recorded: {snapshot['run_ids_sha256'][:12]} here, {str(frozen)[:12]} in the record"
            )
    else:
        # The approval forbids interim result inspection: nothing is computed
        # until every cohort wallet carries a closing sweep row (collection is
        # complete, whatever it found) and at least one is certified over the
        # window. A wallet with a closing row but uncertifiable coverage is
        # refused and counted, as the plan says; a wallet without one means
        # the closing sweep has not finished.
        closure = report.sweep_closure(store, wallets, window_end_ms=window[1], finished_by_ms=finished_by)
        closure["closing_grace_days"] = closing_grace_days
        if not closure["closed"]:
            missing = closure["wallets_without_closing_sweep"]
            raise ArmRunnerError(
                f"arm B's window is not closed in this database: {len(missing)} of {len(wallets)} cohort wallets "
                f"were not reached by a sweep between the window end {window[1]} and {finished_by}, the end of the "
                f"{closing_grace_days}-day closing grace. Run the closing sweep for them, or widen the grace with "
                "--closing-grace-days if it has already run and finished later than that."
            )
        if not any(ledger.is_fully_known(w, *window) for w in wallets):
            raise ArmRunnerError("arm B's window is not closed in this database: no cohort wallet is certified over it")
    # Arm A's file is read and judged before the hours of scoring, so a wrong
    # file refuses in seconds; the number itself is computed at the end.
    arm_a, arm_a_reason = (read_arm_a(arm_a_json, cohort_sha256=cohort["cohort_sha256"], plan_commit=plan_commit)
                           if spec.decides else (None, None))

    scope, scope_lists = report.build_scope(
        store, candles_json, excluded=cohort.get("scope", {}).get("excluded", ()), until_ms=t0_ms
    )
    report.check_scope_against_record(scope_lists, cohort.get("scope", {}))

    pool = pool_wallets(ledger, window)
    pool_cohort = len(set(wallets) & set(pool))
    if pool and len(pool) == pool_cohort:
        # Peers drawn from the cohort alone subtract the cohort's own mean
        # return from itself: whatever the cohort earns in common cancels, and
        # the primary measure is blind to exactly the part that would be
        # copyable. That is not a result to be labelled; it is a broken input.
        what_broke.append(
            f"the peer pool is the cohort itself ({pool_cohort} wallets): mean d cancels any return the "
            "cohort earns in common. Collect the non-cohort characterised wallets over this window."
        )
    bound_ms = t0_ms if spec.arm == "A" else window[1]
    raw_pool_fills = {
        w: [f for f in fills if f.time_ms <= bound_ms]
        for w, fills in load_fills(store, sorted(set(pool) | set(wallets))).items()
    }
    pool_fills, _ = report.split_by_scope(raw_pool_fills, scope)
    # Counted per wallet over the evaluation window only: the fills before it
    # are read for opening positions and characterisation, not evaluated.
    in_window = {w: [f for f in fills if window[0] <= f.time_ms <= window[1]] for w, fills in raw_pool_fills.items()}
    _, out_of_scope = report.split_by_scope(in_window, scope)

    # Every coin any pool wallet traded in scope, not the cohort's alone: a
    # peer whose coin the market cannot price drops out of M_i, and a pool
    # priced only on the cohort's coins would drop exactly the broad-book
    # peers the cohort does not resemble.
    coins = sorted({f.coin for fills in pool_fills.values() for f in fills} | {BENCHMARK_COIN})
    liquidity = {coin: liquidity_for(coin) for coin in coins}
    market = build_market(store, coins, liquidity, price_source=spec.price_source, candle_interval=CANDLE_INTERVAL)
    spanning, span_detail = report.series_span(
        market, coins, window=window, tolerance_ms=spec.span_tolerance_ms, end_tolerance_ms=spec.end_tolerance_ms
    )
    unspanned = sorted(set(coins) - spanning)
    if unspanned:
        for w, fills in pool_fills.items():
            pool_fills[w] = [f for f in fills if f.coin in spanning]
            dropped_in_window = sum(1 for f in in_window.get(w, ()) if f.coin in unspanned)
            out_of_scope[w] = out_of_scope.get(w, 0) + dropped_in_window
    if BENCHMARK_COIN not in spanning:
        # Buy-and-hold and momentum apply no age bound at their exit mark, so
        # an unspanned benchmark would be scored on a stale price and the
        # figures would sit in every row. That is missing data, not a result.
        raise ArmRunnerError(
            f"benchmark coin {BENCHMARK_COIN} has no price series spanning the window "
            f"({span_detail.get(BENCHMARK_COIN)}); the series cannot be collected after the fact"
        )

    seed = seed_from(cohort["cohort_sha256"])
    config = study_config(seed)
    truncated = load_funding_truncation(store, modes=modes, finished_by_ms=finished_by)
    studies: list[Any] = []
    runtime: dict[str, float] = {}
    for index, wallet in enumerate(wallets, start=1):
        started = time.perf_counter()
        (study,) = run_study(
            fills_by_wallet=pool_fills, market=market, ledger=ledger, config=config,
            funding_truncated=truncated, wallets=[wallet], window=window,
        )
        runtime[wallet] = round(time.perf_counter() - started, 1)
        studies.append(study)
        # Checkpoint first, then say so: a stop between the two can leave a
        # checkpoint the log understates, never a log the checkpoint belies.
        if checkpoint is not None:
            _write_checkpoint(checkpoint, spec, studies, runtime, total=len(wallets))
        refused = sum(1 for s in studies if s.refusal is not None)
        log(f"{spec.run_id}: {index}/{len(wallets)} {'refused' if study.refusal else 'scored'} "
            f"refused_so_far={refused} elapsed_s={runtime[wallet]}")

    primary = primary_statistic(studies, window_days=window_days, minimum=MINIMUM_EVALUATED, arm=spec.arm)
    disclosures = disclosure_rollup(studies, wallets=list(primary["d_by_wallet"]))
    surviv = report.survivorship(raw_pool_fills, wallets, window=window, characterisation=characterisation_window(t0_ms))
    refusals = {s.wallet: s.refusal for s in studies if s.refusal is not None}
    scored = len(studies) - len(refusals)
    if scored == 0:
        what_broke.append("no cohort wallet could be scored; see refusals")
    elif primary["n"] == 0:
        what_broke.append("no scored wallet entered the primary; see primary.excluded and the scope counts")

    decision = decision_for(primary) if spec.decides and not what_broke else None
    dry_run_needed = len(wallets) < MINIMUM_EVALUATED or recorded_minimum < MINIMUM_EVALUATED
    if what_broke:
        status = STATUS_BROKE
    elif dry_run and dry_run_needed:
        status = STATUS_DRY_RUN
    elif not primary["measurable"]:
        status = STATUS_NOT_MEASURABLE
    elif primary["case_study"]:
        status = STATUS_CASE_STUDY
    else:
        status = STATUS_DECIDED if spec.decides else STATUS_EARLY_READ
    provenance = (report.candle_provenance(store, coins, interval=CANDLE_INTERVAL) if spec.price_source == "candles"
                  else report.mids_provenance(store, coins, window=window, max_age_ms=MAX_PRICE_AGE_MS))
    # The peers behind the primary's M_i: the sample at the primary latency,
    # not at whichever latency happened to be simulated last.
    cohort_set = set(wallets)
    peers_by_wallet: dict[str, dict] = {}
    shares: list[float] = []
    for s in studies:
        matched = s.matched_by_latency.get(PRIMARY_LATENCY_MS)
        if matched is None or not matched.chosen:
            continue
        count = len(matched.contributed)
        share = round(sum(1 for p in matched.contributed if p in cohort_set) / count, 4) if count else None
        if share is not None:
            shares.append(share)
        peers_by_wallet[s.wallet] = {
            "latency_ms": PRIMARY_LATENCY_MS, "contributed": list(matched.contributed), "count": count,
            "dropped": dict(sorted(matched.dropped.items())), "cohort_share": share,
        }
    evidence = {
        "schema_version": "1.0",
        "run_id": spec.run_id, "arm": spec.arm, "variant": spec.variant, "approvals": list(spec.approvals),
        "plan_commit": plan_commit,
        "cohort_sha256": cohort["cohort_sha256"], "cohort_size": len(wallets),
        "stage_counts": cohort.get("stage_counts"), "per_wallet_reason": cohort.get("per_wallet_reason"),
        "characterisation_window": cohort.get("characterisation_window"),
        "t0_ms": t0_ms,
        "window_closed_before_run": True if closure is None else bool(closure["closed"]),
        "closure": closure,
        "evaluation_window": {"start_ms": window[0], "end_ms": window[1], "days": str(window_days)},
        "price_source": spec.price_kind,
        "price_provenance": provenance,
        "price_series_span_by_coin": span_detail,
        "price_series_span_rule": {
            "tolerance_ms": spec.span_tolerance_ms, "end_tolerance_ms": spec.end_tolerance_ms,
            "rule": "first quote less than tolerance_ms after the window start, "
                    "last quote at most end_tolerance_ms before the window end",
        },
        "ledger_snapshot": snapshot,
        "pool_record": {"sha256": cohort.get("pool_sha256"), "size": len(cohort.get("pool", []) or [])},
        "dry_run_flag_passed": bool(dry_run),
        "record_minimum_evaluable": recorded_minimum,
        "assumptions": assumptions(seed),
        "pool": {"definition": "every wallet the coverage ledger certifies over the evaluation window",
                 "ledger_modes": list(modes) if modes is not None else "all",
                 "ledger_finished_by_ms": finished_by,
                 "size": len(pool), "sha256": cohort_hash(pool),
                 "cohort_wallets_in_pool": pool_cohort, "non_cohort_wallets_in_pool": len(pool) - pool_cohort,
                 "mean_cohort_share_of_peers": round(sum(shares) / len(shares), 4) if shares else None,
                 "cohort_wallets_not_in_pool": sorted(set(wallets) - set(pool))},
        "scope": {**scope_lists, "record": cohort.get("scope"), "coins_evaluated": sorted(spanning & set(coins)),
                  "out_of_scope_fills_by_wallet": {w: n for w, n in sorted(out_of_scope.items()) if w in wallets and n},
                  "out_of_scope_definition": "cohort fills inside the evaluation window whose coin is out of scope "
                                             "or has no price series spanning the window"},
        "counts": {"wallets": len(wallets), "scored": scored, "refused": len(refusals), "in_primary": primary["n"]},
        "refusals": refusals,
        "primary": {**primary, "disclosures": disclosures},
        "secondary": secondary_summary(studies, window_days=window_days),
        "survivorship": surviv,
        "survivorship_inflation": (
            inflation_block(arm_a, arm_a_reason, primary, decision,
                            file_name=arm_a_json.name if arm_a_json is not None else None)
            if spec.decides else None
        ),
        "matched_peers_by_wallet": peers_by_wallet,
        "diagnostics_rollup": report.diagnostics_rollup(studies, latency_ms=PRIMARY_LATENCY_MS, coins_without_span=unspanned),
        "rows": [as_row(o) for s in studies for o in s.outcomes],
        "_runtime_seconds_by_wallet": runtime,
        "sample_limitations_disclosure": report.limitations(
            arm=spec.arm, survivorship_block=surviv, disclosures=disclosures, pool_size=len(pool),
            pool_cohort=pool_cohort, cohort_size=len(wallets),
        ),
        "what_broke": what_broke,
        "reading_rule": (
            "L2_ANALYSIS_PLAN.md, 'How arm A is read, fixed before it is seen'" if spec.arm == "A" else
            "L2_ANALYSIS_PLAN.md, 'Decision rule: B decides, A measures': GO when the written lower bound reaches "
            "0.5 (inclusive), NO_GO when the written upper bound is below it, REPAIR_AND_RERUN otherwise; arm A's "
            "positive reading is strict, so one interval can read inconclusive for A and GO for B"
        ),
        "decisive_arm": "B",
        "decision": decision,
        "empirical_result_status": status,
        "copyability_claim_produced": False,
    }
    # Rule 5 of the reading: something broke, stop and report. The file is
    # still written so the report has something to say.
    return evidence, (EXIT_BROKE if what_broke else 0)


def _write_checkpoint(path: Path, spec: ArmSpec, studies: Sequence[Any], runtime: dict[str, float], *, total: int) -> None:
    # Stamped like the evidence file so a partial can never be read as one.
    partial = {
        "run_id": spec.run_id, "arm": spec.arm, "checkpoint": True, "completed": len(studies), "of": total,
        "decision": None, "empirical_result_status": "PARTIAL_CHECKPOINT", "copyability_claim_produced": False,
        "refusals": {s.wallet: s.refusal for s in studies if s.refusal is not None},
        "runtime_seconds_by_wallet": runtime,
        "rows": [as_row(o) for s in studies for o in s.outcomes],
    }
    path.write_text(json.dumps(partial, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def build_parser(spec: ArmSpec) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"arm_{spec.arm.lower()}_runner",
        description=f"Arm {spec.arm}: score the frozen cohort over its window. No request, no return printed.",
    )
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, required=True, help="the freeze record")
    parser.add_argument("--candles-json", type=Path, required=True, help="the arm A candle post-check the freeze used")
    parser.add_argument("--plan-commit", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true", help="replace an existing evidence file under --out")
    if spec.decides:
        parser.add_argument(
            "--closing-grace-days", type=int, default=DEFAULT_CLOSING_GRACE_DAYS, dest="closing_grace_days",
            help="how long after the window end the closing sweep may still have finished (default 3 days); "
                 "the value is written into the evidence file",
        )
    parser.add_argument("--allow-underpowered-dry-run", action="store_true", dest="dry_run",
                        help="evaluate a cohort under the plan's minimum; the file is stamped DRY_RUN_UNDERPOWERED")
    if spec.decides:
        parser.add_argument("--arm-a-json", type=Path, default=None,
                            help="arm A's evidence file, for the survivorship inflation mean d_A - mean d_B")
    return parser


def _keep_aborted(checkpoint: Path, out: Path) -> None:
    """Whatever was scored before a stop is kept under a name no later run
    treats as its checkpoint, and never as evidence."""
    if not checkpoint.exists():
        return
    try:
        completed = int(json.loads(checkpoint.read_text(encoding="utf-8")).get("completed", 0))
    except (OSError, ValueError):
        completed = 0
    aborted = out.with_name(f"{out.name}.aborted-{completed}.json")
    aborted.unlink(missing_ok=True)
    checkpoint.rename(aborted)


def main(spec: ArmSpec, argv: Sequence[str] | None = None, *, log=print) -> int:
    """Write the evidence file; print counts only. Exit 2 when refusing, 3 when something broke."""
    args = build_parser(spec).parse_args(argv)
    if args.out.exists() and not args.overwrite:
        log(f"{spec.run_id}: refusing to run: {args.out} exists; pass --overwrite to replace it")
        return EXIT_REFUSED
    try:
        cohort = load_cohort(args.cohort, plan_commit=args.plan_commit, allow_underpowered=args.dry_run)
    except (ArmRunnerError, OSError, ValueError) as exc:
        log(f"{spec.run_id}: refusing to run: {exc}")
        return EXIT_REFUSED
    if cohort["hard_stop"]:
        log(f"{spec.run_id}: the freeze recorded a hard stop; no evaluation")
        return EXIT_REFUSED
    checkpoint = args.out.with_name(args.out.name + ".partial.json")
    try:
        with LiveDataStore(args.db, create=False) as store:
            evidence, code = run(
                store, cohort, spec, candles_json=args.candles_json, plan_commit=args.plan_commit,
                dry_run=args.dry_run, checkpoint=checkpoint, arm_a_json=getattr(args, "arm_a_json", None),
                closing_grace_days=getattr(args, "closing_grace_days", DEFAULT_CLOSING_GRACE_DAYS), log=log,
            )
    except BaseException as exc:  # rule 5: stop and report; nothing, Ctrl-C included, escapes without the line
        log(f"{spec.run_id}: stopped: {type(exc).__name__}: {exc}")
        _keep_aborted(checkpoint, args.out)
        if not isinstance(exc, Exception):
            raise
        return EXIT_REFUSED
    runtime = evidence.pop("_runtime_seconds_by_wallet")
    text = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    args.out.write_text(text, encoding="utf-8", newline="\n")
    args.out.with_name(args.out.name + ".runtime.json").write_text(
        json.dumps({"run_id": spec.run_id, "runtime_seconds_by_wallet": runtime}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    if checkpoint.exists():
        checkpoint.unlink()
    counts = evidence["counts"]
    log(
        f"{spec.run_id}: wallets={counts['wallets']} scored={counts['scored']} refused={counts['refused']} "
        f"in_primary={counts['in_primary']} status={evidence['empirical_result_status']} "
        f"file_sha256={hashlib.sha256(text.encode('utf-8')).hexdigest()}"
        + (f" broke={len(evidence['what_broke'])}" if evidence["what_broke"] else "")
    )
    return code
