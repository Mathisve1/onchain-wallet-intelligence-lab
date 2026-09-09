"""The L2 study statistics, shared by both arm runners.

Pure functions over the simulator's outputs: the primary measure of
``L2_ANALYSIS_PLAN.md`` (mean ``d_i`` at 30 seconds with a two-sided one-sample
t interval at alpha 0.05, in points per 14-day equivalent), the secondary
figures that are reported and do not decide, the four disclosures that travel
with every result, the reading rule the owner fixed before arm A was seen, and
the decision rule that only arm B applies.

"Points per 14-day equivalent" is the linear ``14 / T`` conversion the power
analysis (``L2_POWER_001``) used to build its MDE table, so the target of 0.5
and the ``d_i`` computed here are in the same units.

The Student t quantile is computed from the regularised incomplete beta
function, because this package carries no SciPy and a statistic the study
depends on should not depend on a library that is not pinned.
"""

from __future__ import annotations

import json
import math
import statistics
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

#: ``L2_ANALYSIS_PLAN.md`` "Primary measure": the primary latency and target.
PRIMARY_LATENCY_MS = 30_000
TARGET_POINTS_PER_14D = Decimal("0.5")
POINTS_PER_14D_SCALE = Decimal(100) * Decimal(14)
#: The plan's stop rule: under this many wallets an arm is a case study.
MINIMUM_EVALUATED = 200
FOUR_PLACES = Decimal("0.0001")

ARM_A_NEGATIVE = "ARM_A_NEGATIVE"
ARM_A_POSITIVE = "ARM_A_POSITIVE"
ARM_A_INCONCLUSIVE = "ARM_A_INCONCLUSIVE"
ARM_A_NOT_MEASURABLE = "ARM_A_NOT_MEASURABLE"
ARM_A_CASE_STUDY_UNDER_MINIMUM = "ARM_A_CASE_STUDY_UNDER_MINIMUM"
#: The three outcomes arm B may produce; nothing else is a decision.
GO_TO_ENTITY_CLUSTER_RESEARCH = "GO_TO_ENTITY_CLUSTER_RESEARCH"
NO_GO_NO_COPYABLE_ALPHA = "NO_GO_NO_COPYABLE_ALPHA"
REPAIR_AND_RERUN = "REPAIR_AND_RERUN"


class StatisticsError(ValueError):
    """A statistic asked for outside its domain."""


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Lentz's method)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / (c if abs(c) > tiny else tiny)
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / (c if abs(c) > tiny else tiny)
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta ``I_x(a, b)``."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log(1.0 - x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def student_t_cdf(t: float, df: float) -> float:
    x = df / (df + t * t)
    tail = 0.5 * _betainc(df / 2.0, 0.5, x)
    return 1.0 - tail if t >= 0 else tail


def student_t_quantile(p: float, df: float) -> float:
    """Inverse of the Student t CDF by bisection."""
    if not 0.0 < p < 1.0 or df <= 0:
        raise StatisticsError("t quantile needs 0 < p < 1 and df > 0")
    lo, hi = -1e3, 1e3
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if student_t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def reading_for(lower: float, upper: float) -> str:
    """The arm A reading fixed before it was seen; it decides nothing.

    Applied to the bounds *as written* in the file, so a reader can verify
    the label from the interval they see.
    """
    target = float(TARGET_POINTS_PER_14D)
    if upper < target:
        return ARM_A_NEGATIVE
    if lower > target:
        return ARM_A_POSITIVE
    return ARM_A_INCONCLUSIVE


def decision_for(primary: Mapping[str, Any]) -> str | None:
    """Arm B's decision rule, ``L2_ANALYSIS_PLAN.md`` "B decides, A measures".

    ``GO_TO_ENTITY_CLUSTER_RESEARCH`` when the lower 95 percent bound reaches
    the target, ``NO_GO_NO_COPYABLE_ALPHA`` when the upper bound stays below
    it, ``REPAIR_AND_RERUN`` for anything else that was measured. A case study
    or an unmeasurable primary decides nothing, so ``None``.
    """
    if primary.get("case_study") or primary.get("ci95") is None or primary.get("reading") == ARM_A_NOT_MEASURABLE:
        return None
    lower, upper = primary["ci95"]
    target = float(TARGET_POINTS_PER_14D)
    if lower >= target:
        return GO_TO_ENTITY_CLUSTER_RESEARCH
    if upper < target:
        return NO_GO_NO_COPYABLE_ALPHA
    return REPAIR_AND_RERUN


def points_per_14d(value: Decimal, window_days: Decimal) -> Decimal:
    return value * POINTS_PER_14D_SCALE / window_days


def _outcome_at(study: Any, latency_ms: int) -> Any | None:
    return next((o for o in study.outcomes if o.latency_ms == latency_ms), None)


def primary_statistic(
    studies: Sequence[Any],
    *,
    window_days: Decimal,
    latency_ms: int = PRIMARY_LATENCY_MS,
    minimum: int = MINIMUM_EVALUATED,
) -> dict:
    """Mean ``d_i`` at the primary latency with its 95 percent t interval.

    ``d_i`` is the follower's return on deployed capital minus its matched-
    random peers' mean, scaled to points per 14-day equivalent. A wallet with
    no matched-random figure (no eligible peer, or nothing deployed) has no
    ``d_i`` and is counted as excluded, never as zero.

    Under ``minimum`` wallets the arm is a case study: the numbers are still
    written, the reading is ``ARM_A_CASE_STUDY_UNDER_MINIMUM`` and cannot be
    negative, positive or inconclusive. A zero-variance sample cannot support
    a t interval and is not measurable either.
    """
    values: dict[str, Decimal] = {}
    excluded: dict[str, str] = {}
    for study in studies:
        if study.refusal is not None:
            excluded[study.wallet] = f"refused: {study.refusal}"
            continue
        outcome = _outcome_at(study, latency_ms)
        if outcome is None or outcome.return_on_deployed is None:
            excluded[study.wallet] = "nothing deployed at the primary latency"
            continue
        peer_mean = outcome.baseline_returns.get("matched_random")
        if peer_mean is None:
            excluded[study.wallet] = "no matched-random peer"
            continue
        values[study.wallet] = points_per_14d(outcome.return_on_deployed - peer_mean, window_days)
    n = len(values)
    result: dict[str, Any] = {
        "latency_ms": latency_ms,
        "unit": "points per 14-day equivalent",
        "target": str(TARGET_POINTS_PER_14D),
        "n": n,
        "minimum": minimum,
        "case_study": n < minimum,
        "excluded": excluded,
        "d_by_wallet": {w: str(v.quantize(FOUR_PLACES)) for w, v in sorted(values.items())},
        "mean": None, "sd": None, "standard_error": None, "ci95": None,
        "t_critical": None, "t_statistic": None,
        "reading": ARM_A_NOT_MEASURABLE,
        "reading_taken_on": "ci95 as written, four decimals",
    }
    if n < 2:
        return result
    floats = [float(v) for v in values.values()]
    mean = statistics.fmean(floats)
    sd = statistics.stdev(floats)
    se = sd / math.sqrt(n)
    t_crit = student_t_quantile(0.975, n - 1)
    lower, upper = round(mean - t_crit * se, 4), round(mean + t_crit * se, 4)
    result.update(
        mean=round(mean, 4), sd=round(sd, 4), standard_error=round(se, 4),
        ci95=[lower, upper], t_critical=round(t_crit, 4),
        t_statistic=None if se == 0 else round(mean / se, 4),
    )
    if se == 0:
        result["reading"] = ARM_A_NOT_MEASURABLE
    elif n < minimum:
        result["reading"] = ARM_A_CASE_STUDY_UNDER_MINIMUM
    else:
        result["reading"] = reading_for(lower, upper)
    return result


def disclosure_rollup(studies: Sequence[Any], *, wallets: Sequence[str], latency_ms: int = PRIMARY_LATENCY_MS) -> dict:
    """The four never-drop disclosures, counted over the wallets in the primary.

    Every outcome row carries them; this says, at the level of the reported
    mean, how many of the ``n`` wallets entering it had unpriced funding
    hours, a truncated source funding history, assumed liquidity, or a copy
    or end-of-window mark that rested on a stale quote.
    """
    wanted = set(wallets)
    counts = {"funding_incomplete": 0, "source_funding_truncated": 0, "liquidity_assumed": 0,
              "stale_price_skips_present": 0, "catch_up_fills_present": 0}
    for study in studies:
        if study.wallet not in wanted or study.refusal is not None:
            continue
        outcome = _outcome_at(study, latency_ms)
        if outcome is None:
            continue
        counts["funding_incomplete"] += bool(outcome.funding_incomplete)
        counts["source_funding_truncated"] += bool(outcome.source_funding_truncated)
        counts["liquidity_assumed"] += bool(outcome.liquidity_assumed)
        counts["stale_price_skips_present"] += outcome.stale_price_skips > 0
        counts["catch_up_fills_present"] += outcome.catch_up_fills > 0
    return {"of_n": len(wanted), **counts}


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

def secondary_summary(studies: Sequence[Any], *, window_days: Decimal) -> dict:
    """Mean ``d`` per latency and mean return versus each baseline: reported, not deciding."""
    by_latency: dict[int, list[Decimal]] = {}
    versus: dict[str, list[Decimal]] = {}
    for study in studies:
        for outcome in study.outcomes:
            if outcome.return_on_deployed is None:
                continue
            peer = outcome.baseline_returns.get("matched_random")
            if peer is not None:
                by_latency.setdefault(outcome.latency_ms, []).append(
                    points_per_14d(outcome.return_on_deployed - peer, window_days)
                )
            for name, value in outcome.versus.items():
                versus.setdefault(f"{name}@{outcome.latency_ms}", []).append(points_per_14d(value, window_days))

    def summary(values: dict) -> dict:
        return {
            str(key): {"n": len(v), "mean": str((sum(v, Decimal(0)) / len(v)).quantize(FOUR_PLACES))}
            for key, v in sorted(values.items())
        }

    return {
        "unit": "points per 14-day equivalent",
        "mean_d_by_latency": summary(by_latency),
        "mean_versus_baseline": summary(versus),
    }
