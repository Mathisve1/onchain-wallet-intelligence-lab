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
* matched-random peers are drawn from every characterised wallet the ledger
  certifies over the window, not from the cohort alone, and the pool's hash
  is recorded (``l2_arm_report.limitations`` says why);
* the primary measure is ``d_i = R_i - M_i`` at 30 seconds, in points per
  14-day equivalent, with a two-sided one-sample t interval at alpha 0.05;
* **arm A** runs over ``T0-52d`` to ``T0-7d`` on 15-minute candle closes with
  a 15-minute price-age bound, is read by the rule fixed before it was seen,
  and decides nothing: its ``decision`` is always ``null``;
* **arm B** runs over ``T0`` to ``T0+56d`` on the polled mids, refuses to
  compute anything before the ledger certifies that window for the cohort
  (the approval forbids interim result inspection), and applies the decision
  rule: B decides, A measures.

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
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

from src.copyability.classify import ClassifierThresholds
from src.copyability.cohort import cohort_hash
from src.copyability.costs import CostModel, FeeSchedule
from src.copyability.coverage import CoverageLedger
from src.copyability.execution import LATENCY_GRID_MS, FollowerConfig
from src.copyability.inputs import InputError, LiquidityProfile
from src.copyability.loader import build_market, load_coverage, load_fills, load_funding_truncation
from src.copyability.metrics import as_row
from src.copyability.simulate import StudyConfig, run_study
from src.live_data.storage import LiveDataStore, StorageError

from . import l2_arm_report as report
from .cohort_pipeline_freeze import FreezeInputError
from .l2_arm_statistics import (
    ARM_A_NOT_MEASURABLE,
    MINIMUM_EVALUATED,
    PRIMARY_LATENCY_MS,
    decision_for,
    disclosure_rollup,
    primary_statistic,
    secondary_summary,
)

MILLISECONDS_PER_DAY = 86_400_000
#: Both arms: 15-minute freshness, no mixed-resolution series.
MAX_PRICE_AGE_MS = 900_000
CANDLE_INTERVAL = "15m"
CANDLE_INTERVAL_MS = 900_000
#: The characterisation window the freeze used; the record must agree.
CHARACTERISATION_START_DAYS_BEFORE_T0 = 90
CHARACTERISATION_END_DAYS_BEFORE_T0 = 60

#: Study parameters carried over from ``L1_INSTRUMENT_VALIDATION_001`` so the
#: instruments agree on every cost, plus the ones this runner fixes and
#: discloses because neither the plan nor L1 did.
NOMINAL_CAPITAL = Decimal("10000")
SIZE_SCALE = Decimal(1)
FEES = FeeSchedule(taker_bps=Decimal("4.5"), maker_bps=Decimal("1.5"))
IMPACT_BPS_PER_FULL_DEPTH = Decimal("10")
BENCHMARK_COIN = "BTC"
MOMENTUM_LOOKBACK_MS = 3_600_000
MOMENTUM_STEP_MS = 600_000
MATCHED_RANDOM_SAMPLE_SIZE = 20
MATCHED_RANDOM_TOLERANCE = Decimal("0.5")
TIER1_COINS = frozenset({"BTC", "ETH"})
TIER2_COINS = frozenset({
    "AAVE", "ADA", "APT", "ARB", "ATOM", "AVAX", "BNB", "DOGE", "ENA", "HYPE", "LINK",
    "LTC", "NEAR", "PAXG", "SOL", "SUI", "TAO", "TRX", "UNI", "WLD", "XLM", "XRP", "kPEPE",
})
LIQUIDITY_TIERS = {
    "tier1": (Decimal("0.5"), Decimal("2000000")),
    "tier2": (Decimal("1.5"), Decimal("300000")),
    "tier3": (Decimal("5"), Decimal("50000")),
}

STATUS_EARLY_READ = "ARM_A_EARLY_READ_ONLY"
STATUS_DECIDED = "ARM_B_DECIDED"
STATUS_CASE_STUDY = "CASE_STUDY_UNDER_MINIMUM"
STATUS_NOT_MEASURABLE = "NOT_MEASURABLE"
STATUS_DRY_RUN = "DRY_RUN_UNDERPOWERED"
EXIT_REFUSED = 2
EXIT_BROKE = 3


class ArmRunnerError(ValueError):
    """An input the runner refuses to evaluate on."""


@dataclass(frozen=True, slots=True)
class ArmSpec:
    """What distinguishes one arm from the other; everything else is shared."""

    arm: str
    run_id: str
    variant: str
    approvals: tuple[str, ...]
    #: Window edges in days relative to T0: arm A is (-52, -7), arm B (0, +56).
    window_start_days: int
    window_end_days: int
    price_source: str
    #: How far after the window start the first usable quote may sit.
    span_tolerance_ms: int
    decides: bool

    def window(self, t0_ms: int) -> tuple[int, int]:
        return (t0_ms + self.window_start_days * MILLISECONDS_PER_DAY,
                t0_ms + self.window_end_days * MILLISECONDS_PER_DAY)

    @property
    def price_kind(self) -> dict:
        return {"kind": self.price_source, "interval": CANDLE_INTERVAL if self.price_source == "candles" else None,
                "max_age_ms": MAX_PRICE_AGE_MS}


# -- inputs ------------------------------------------------------------------------


def characterisation_window(t0_ms: int) -> tuple[int, int]:
    return (t0_ms - CHARACTERISATION_START_DAYS_BEFORE_T0 * MILLISECONDS_PER_DAY,
            t0_ms - CHARACTERISATION_END_DAYS_BEFORE_T0 * MILLISECONDS_PER_DAY)


def load_cohort(path: Path, *, plan_commit: str, allow_underpowered: bool = False) -> dict:
    """The freeze record, trusted only after every check a reader would make."""
    record = json.loads(path.read_text(encoding="utf-8"))
    for key in ("t0_ms", "cohort", "cohort_sha256", "plan_commit", "hard_stop"):
        if key not in record:
            raise ArmRunnerError(f"freeze record lacks {key!r}: {path}")
    if record["plan_commit"] != plan_commit:
        raise ArmRunnerError(
            f"freeze record was made under plan commit {record['plan_commit']!r}, this run names {plan_commit!r}"
        )
    if cohort_hash(record["cohort"]) != record["cohort_sha256"]:
        raise ArmRunnerError("the cohort list does not hash to the recorded cohort_sha256; the record was altered")
    minimum = int(record.get("minimum_evaluable", MINIMUM_EVALUATED))
    if not record["hard_stop"] and len(record["cohort"]) < minimum and not allow_underpowered:
        raise ArmRunnerError(
            f"{len(record['cohort'])} wallets is under the minimum of {minimum}; an underpowered study "
            "is not run to have something (pass --allow-underpowered-dry-run for a synthetic dry run)"
        )
    recorded = record.get("characterisation_window")
    if recorded is not None:
        if (int(recorded["start_ms"]), int(recorded["end_ms"])) != characterisation_window(int(record["t0_ms"])):
            raise ArmRunnerError("the freeze's characterisation window is not [T0-90d, T0-60d]")
    return record


def liquidity_for(coin: str) -> LiquidityProfile:
    """The L1 tiered assumption, labelled ASSUMED: no order book is read."""
    tier = "tier1" if coin in TIER1_COINS else "tier2" if coin in TIER2_COINS else "tier3"
    half_spread_bps, depth = LIQUIDITY_TIERS[tier]
    return LiquidityProfile(coin, half_spread_bps, depth, IMPACT_BPS_PER_FULL_DEPTH)


def study_config(seed: int) -> StudyConfig:
    return StudyConfig(
        follower=FollowerConfig(capital=NOMINAL_CAPITAL, size_scale=SIZE_SCALE),
        cost_model=CostModel(FEES), benchmark_coin=BENCHMARK_COIN,
        momentum_lookback_ms=MOMENTUM_LOOKBACK_MS, momentum_step_ms=MOMENTUM_STEP_MS,
        random_seed=seed, random_sample_size=MATCHED_RANDOM_SAMPLE_SIZE, latencies_ms=LATENCY_GRID_MS,
        thresholds=ClassifierThresholds(), max_price_age_ms=MAX_PRICE_AGE_MS,
    )


def seed_from(cohort_sha256: str) -> int:
    """A seed the cohort itself fixes, so a rerun on the same freeze repeats."""
    return int(cohort_sha256[:8], 16)


def pool_wallets(ledger: CoverageLedger, window: tuple[int, int]) -> list[str]:
    """Every wallet the ledger certifies over the whole window: the peer pool."""
    start_ms, end_ms = window
    return sorted(w for w in ledger.wallets() if ledger.is_fully_known(w, start_ms, end_ms))


def assumptions(seed: int) -> dict:
    return {
        "fees_bps": {"taker": str(FEES.taker_bps), "maker": str(FEES.maker_bps)},
        "liquidity_tiers": {k: {"half_spread_bps": str(v[0]), "depth_notional_usd": str(v[1])} for k, v in LIQUIDITY_TIERS.items()},
        "impact_bps_per_full_depth": str(IMPACT_BPS_PER_FULL_DEPTH),
        "liquidity_source": "ASSUMED",
        "benchmark_coin": BENCHMARK_COIN,
        "momentum": {"lookback_ms": MOMENTUM_LOOKBACK_MS, "step_ms": MOMENTUM_STEP_MS},
        "size_scale": str(SIZE_SCALE),
        "nominal_capital": str(NOMINAL_CAPITAL),
        "matched_random_sample_size": MATCHED_RANDOM_SAMPLE_SIZE,
        "matched_random_peer_tolerance": str(MATCHED_RANDOM_TOLERANCE),
        "matched_random_eligibility": "another pool wallet whose in-window fill count is within the tolerance "
                                      "of the target's and whose coverage certifies the same window",
        "seed": seed,
        "seed_derivation": "int(cohort_sha256[:8], 16)",
        "latencies_ms": list(LATENCY_GRID_MS),
        "max_price_age_ms": MAX_PRICE_AGE_MS,
    }


def survivorship_inflation(arm_a_path: Path | None, primary_b: dict) -> dict | None:
    """``mean d_A - mean d_B``: a number in arm B's report, never a gate."""
    if arm_a_path is None:
        return None
    arm_a = json.loads(arm_a_path.read_text(encoding="utf-8"))
    if arm_a.get("arm") != "A" or arm_a.get("primary", {}).get("mean") is None or primary_b.get("mean") is None:
        return {"available": False, "arm_a_file": arm_a_path.name}
    mean_a, mean_b = float(arm_a["primary"]["mean"]), float(primary_b["mean"])
    reading_a = arm_a["primary"].get("reading")
    return {
        "available": True, "arm_a_file": arm_a_path.name, "arm_a_cohort_sha256": arm_a.get("cohort_sha256"),
        "mean_d_a": mean_a, "mean_d_b": mean_b, "inflation_points_per_14d": round(mean_a - mean_b, 4),
        "arm_a_reading": reading_a,
        "a_negative_b_positive": reading_a == "ARM_A_NEGATIVE" and decision_for(primary_b) == "GO_TO_ENTITY_CLUSTER_RESEARCH",
        "note": "a large gap in either direction obliges a written diagnosis before any GO is acted on",
    }


# -- the run -----------------------------------------------------------------------------


def run(
    store: LiveDataStore, cohort: dict, spec: ArmSpec, *, candles_json: Path, plan_commit: str,
    dry_run: bool = False, checkpoint: Path | None = None, arm_a_json: Path | None = None, log=print,
) -> tuple[dict, int]:
    t0_ms = int(cohort["t0_ms"])
    wallets = list(cohort["cohort"])
    window = spec.window(t0_ms)
    window_days = Decimal(window[1] - window[0]) / Decimal(MILLISECONDS_PER_DAY)
    what_broke: list[str] = []

    ledger = load_coverage(store)
    if spec.arm == "B" and not any(ledger.is_fully_known(w, *window) for w in wallets):
        # The approval forbids interim result inspection: nothing is computed
        # until the sweeps have certified the whole forward window.
        raise ArmRunnerError("arm B's window is not closed in this database: no cohort wallet is certified over it")

    scope, scope_lists = report.build_scope(
        store, candles_json, excluded=cohort.get("scope", {}).get("excluded", ()), until_ms=t0_ms
    )
    report.check_scope_against_record(scope_lists, cohort.get("scope", {}))

    pool = pool_wallets(ledger, window)
    bound_ms = t0_ms if spec.arm == "A" else window[1]
    raw_pool_fills = {
        w: [f for f in fills if f.time_ms <= bound_ms]
        for w, fills in load_fills(store, sorted(set(pool) | set(wallets))).items()
    }
    pool_fills, out_of_scope = report.split_by_scope(raw_pool_fills, scope)

    coins = sorted({f.coin for w in wallets for f in pool_fills.get(w, ())} | {BENCHMARK_COIN})
    liquidity = {coin: liquidity_for(coin) for coin in coins}
    market = build_market(store, coins, liquidity, price_source=spec.price_source, candle_interval=CANDLE_INTERVAL)
    spanning, span_detail = report.series_span(market, coins, window=window, tolerance_ms=spec.span_tolerance_ms)
    unspanned = sorted(set(coins) - spanning)
    if unspanned:
        for w, fills in pool_fills.items():
            kept = [f for f in fills if f.coin in spanning]
            out_of_scope[w] = out_of_scope.get(w, 0) + (len(fills) - len(kept))
            pool_fills[w] = kept
    if BENCHMARK_COIN not in spanning:
        what_broke.append(f"benchmark coin {BENCHMARK_COIN} has no price series spanning the window")

    seed = seed_from(cohort["cohort_sha256"])
    config = study_config(seed)
    truncated = load_funding_truncation(store)
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
        refused = sum(1 for s in studies if s.refusal is not None)
        log(f"{spec.run_id}: {index}/{len(wallets)} {'refused' if study.refusal else 'scored'} "
            f"refused_so_far={refused} elapsed_s={runtime[wallet]}")
        if checkpoint is not None:
            _write_checkpoint(checkpoint, spec, studies, runtime, total=len(wallets))

    primary = primary_statistic(studies, window_days=window_days)
    disclosures = disclosure_rollup(studies, wallets=list(primary["d_by_wallet"]))
    surviv = report.survivorship(raw_pool_fills, wallets, window=window, characterisation=characterisation_window(t0_ms))
    refusals = {s.wallet: s.refusal for s in studies if s.refusal is not None}
    scored = len(studies) - len(refusals)
    if scored == 0:
        what_broke.append("no cohort wallet could be scored; see refusals")
    elif primary["n"] == 0:
        what_broke.append("no scored wallet entered the primary; see primary.excluded and the scope counts")

    decision = decision_for(primary) if spec.decides else None
    if dry_run:
        status = STATUS_DRY_RUN
    elif primary["reading"] == ARM_A_NOT_MEASURABLE:
        status = STATUS_NOT_MEASURABLE
    elif primary["case_study"]:
        status = STATUS_CASE_STUDY
    else:
        status = STATUS_DECIDED if spec.decides else STATUS_EARLY_READ
    provenance = (report.candle_provenance(store, coins, interval=CANDLE_INTERVAL) if spec.price_source == "candles"
                  else report.mids_provenance(store, coins, window=window))
    evidence = {
        "schema_version": "1.0",
        "run_id": spec.run_id, "arm": spec.arm, "variant": spec.variant, "approvals": list(spec.approvals),
        "plan_commit": plan_commit,
        "cohort_sha256": cohort["cohort_sha256"], "cohort_size": len(wallets),
        "stage_counts": cohort.get("stage_counts"), "per_wallet_reason": cohort.get("per_wallet_reason"),
        "characterisation_window": cohort.get("characterisation_window"),
        "t0_ms": t0_ms,
        "window_closed_before_run": True,
        "evaluation_window": {"start_ms": window[0], "end_ms": window[1], "days": str(window_days)},
        "price_source": spec.price_kind,
        "price_provenance": provenance,
        "price_series_span_by_coin": span_detail,
        "assumptions": assumptions(seed),
        "pool": {"definition": "every wallet the coverage ledger certifies over the evaluation window",
                 "size": len(pool), "sha256": cohort_hash(pool),
                 "cohort_wallets_not_in_pool": sorted(set(wallets) - set(pool))},
        "scope": {**scope_lists, "record": cohort.get("scope"), "coins_evaluated": sorted(spanning & set(coins)),
                  "out_of_scope_fills_by_wallet": {w: n for w, n in sorted(out_of_scope.items()) if w in wallets and n}},
        "counts": {"wallets": len(wallets), "scored": scored, "refused": len(refusals), "in_primary": primary["n"]},
        "refusals": refusals,
        "primary": {**primary, "disclosures": disclosures},
        "secondary": secondary_summary(studies, window_days=window_days),
        "survivorship": surviv,
        "survivorship_inflation": survivorship_inflation(arm_a_json, primary) if spec.decides else None,
        "matched_peers_by_wallet": {s.wallet: list(s.matched_peers) for s in studies if s.matched_peers},
        "diagnostics_rollup": report.diagnostics_rollup(studies, latency_ms=PRIMARY_LATENCY_MS, coins_without_span=unspanned),
        "rows": [as_row(o) for s in studies for o in s.outcomes],
        "_runtime_seconds_by_wallet": runtime,
        "sample_limitations_disclosure": report.limitations(
            arm=spec.arm, survivorship_block=surviv, disclosures=disclosures, pool_size=len(pool), cohort_size=len(wallets)
        ),
        "what_broke": what_broke,
        "reading_rule": "L2_ANALYSIS_PLAN.md, 'How arm A is read, fixed before it is seen'" if spec.arm == "A"
                        else "L2_ANALYSIS_PLAN.md, 'Decision rule: B decides, A measures'",
        "decisive_arm": "B",
        "decision": decision,
        "empirical_result_status": status,
        "copyability_claim_produced": False,
    }
    # Rule 5 of the reading: something broke, stop and report. The file is
    # still written so the report has something to say.
    return evidence, (EXIT_BROKE if what_broke else 0)


def _write_checkpoint(path: Path, spec: ArmSpec, studies: Sequence[Any], runtime: dict[str, float], *, total: int) -> None:
    partial = {
        "run_id": spec.run_id, "checkpoint": True, "completed": len(studies), "of": total,
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
    parser.add_argument("--allow-underpowered-dry-run", action="store_true", dest="dry_run",
                        help="evaluate a cohort under the plan's minimum; the file is stamped DRY_RUN_UNDERPOWERED")
    if spec.decides:
        parser.add_argument("--arm-a-json", type=Path, default=None,
                            help="arm A's evidence file, for the survivorship inflation mean d_A - mean d_B")
    return parser


def main(spec: ArmSpec, argv: Sequence[str] | None = None, *, log=print) -> int:
    """Write the evidence file; print counts only. Exit 2 when refusing, 3 when something broke."""
    args = build_parser(spec).parse_args(argv)
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
                dry_run=args.dry_run, checkpoint=checkpoint, arm_a_json=getattr(args, "arm_a_json", None), log=log,
            )
    except (ArmRunnerError, report.ScopeMismatchError, FreezeInputError, StorageError, InputError, OSError) as exc:
        log(f"{spec.run_id}: stopped: {type(exc).__name__}: {exc}")
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
    )
    return code
