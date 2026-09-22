"""Read a rehearsal freeze and say what the T0 discovery is likely to yield.

The plan discovers up to 600 candidates and hard-stops below 200 evaluable
wallets (``L2_ANALYSIS_PLAN.md``, "Hard stop before evaluation"). The only way
to learn before T0 whether the funnel clears that bar is to run it on a sample
and project. This module does the projection from the freeze record the
rehearsal wrote, and nothing else: it reads counts, never fills, prices or a
study database. It is not an evidence file of the study, it decides nothing,
and it never lowers the plan's minimum: a record made with a smaller one is
refused, as :mod:`.l2_arm_inputs` refuses it.

Three readings, each labelled with what it assumes:

* **Exact interval on the evaluable share.** The freeze read ``n``
  characterised candidates and found ``k`` evaluable. The Clopper-Pearson interval is the exact
  binomial interval: its bounds are Beta quantiles, computed here by bisection
  on the regularised incomplete beta function rather than by summing terms, so
  the arithmetic does not depend on the size of the judged set.
* **A fresh discovery at T0.** Under a uniform prior on the share, the number
  evaluable among ``T`` fresh candidates is beta-binomial. The module reports
  its posterior mean, a central interval, the chance of reaching the minimum,
  and the smallest ``T`` reaching that chance at 50, 80 and 90 percent, beside
  the plug-in reading at the observed rate so the prior's share is visible.
* **The rehearsal's own discovered set**, only when the caller states that the
  judged wallets were drawn from it at random (``--sampled-at-random``). Then
  the count evaluable in the whole set is finite-population inference. Without
  that statement the reading is skipped, because the freeze run over every
  wallet with fills judges a set the unjudged wallets are not exchangeable
  with; when the freeze read the whole discovered set, a note says nothing is
  inferred. The same representativeness is what the fresh-discovery reading
  rests on, and the report says so.

Every number is standard-library arithmetic on the printed inputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .cohort_pipeline_freeze import MINIMUM_EVALUABLE as PLAN_MINIMUM_EVALUABLE
from .funnel_arithmetic import (
    DEFAULT_CONFIDENCE,
    ProjectionInputError,
    SEARCH_CAP,
    beta_binomial_pmf,
    betainc,
    binomial_cdf,
    candidates_for_chance,
    central_interval,
    clopper_pearson,
    hypergeometric_posterior,
    tail_at_least,
)

__all__ = [
    "ProjectionInputError", "PLAN_MINIMUM_EVALUABLE", "PLAN_DISCOVERY_TARGET", "DEFAULT_CONFIDENCE",
    "SEARCH_CAP", "CHANCES", "EXCLUSION_STAGES", "CLASSIFIER_STAGES", "betainc", "binomial_cdf",
    "clopper_pearson", "beta_binomial_pmf", "hypergeometric_posterior", "central_interval",
    "tail_at_least", "candidates_for_chance", "funnel_rows", "project", "render", "main", "build_parser",
]

#: The exclusion stages in the order :func:`src.copyability.cohort.select_cohort`
#: applies them: the ledger's certification, the classifier's two verdicts, then
#: the two bounds. ``STAGE_NAMES`` declares the same stages in the record's own
#: order, which is not the order they run in.
EXCLUSION_STAGES: tuple[tuple[str, str], ...] = (
    ("window_unobserved", "ledger cannot certify the characterisation window"),
    ("insufficient_fills", "too few fills in the window"),
    ("probable_market_maker", "classified as a probable market maker"),
    ("rebate_excluded", "rebate dependence at or above the bound"),
    ("scope_excluded", "in-scope share of notional below the bound"),
)
CLASSIFIER_STAGES = ("window_unobserved", "insufficient_fills", "probable_market_maker")
#: ``L2_ANALYSIS_PLAN.md``: "Up to 600 candidates are discovered from the public tape".
PLAN_DISCOVERY_TARGET = 600
CHANCES = (0.5, 0.8, 0.9)


# ---- reading the record ------------------------------------------------------------------


def _count(container: Mapping[str, Any], key: str, what: str, *, default: int | None = None) -> int:
    """One count from a record: an integer, not a float, string or boolean."""
    if key not in container:
        if default is not None:
            return default
        raise ProjectionInputError(f"{what} has no '{key}'; got keys {sorted(container)!r}")
    value = container[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProjectionInputError(
            f"{what}'s '{key}' is {value!r}; a count has to be a whole number, and this projection "
            "does not round one"
        )
    if value < 0:
        raise ProjectionInputError(f"{what}'s '{key}' is {value}; a count cannot be negative")
    return value


def funnel_rows(stage_counts: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """The funnel in selection order, with survivors after each stage, and any inconsistency."""
    discovered = _count(stage_counts, "discovered", "stage_counts")
    rows: list[dict[str, Any]] = []
    remaining = discovered
    for stage, meaning in EXCLUSION_STAGES:
        excluded = _count(stage_counts, stage, "stage_counts", default=0)
        remaining -= excluded
        rows.append({
            "stage": stage,
            "meaning": meaning,
            "excluded": excluded,
            "share_of_discovered": (excluded / discovered) if discovered else 0.0,
            "remaining": remaining,
        })
    if remaining < 0:
        raise ProjectionInputError(
            f"the exclusions add up to more than the {discovered} discovered candidates; "
            "the record's stage_counts cannot be read as a funnel"
        )
    after_classifier = discovered - sum(_count(stage_counts, s, "stage_counts", default=0) for s in CLASSIFIER_STAGES)
    if "prefiltered_directional" in stage_counts:
        directional = _count(stage_counts, "prefiltered_directional", "stage_counts")
        if directional != after_classifier:
            raise ProjectionInputError(
                f"stage_counts do not add up: prefiltered_directional is {directional}, discovered minus "
                f"the classifier exclusions is {after_classifier}; this projection has no hash to check a "
                "record by, so its counts have to agree"
            )
    if "evaluable" in stage_counts:
        evaluable = _count(stage_counts, "evaluable", "stage_counts")
        if evaluable != remaining:
            raise ProjectionInputError(
                f"stage_counts do not add up: evaluable is {evaluable}, the funnel leaves {remaining}"
            )
    return rows, []


def _plan_minimum(freeze: Mapping[str, Any], override: int | None, warnings: list[str],
                  *, allow_underpowered: bool) -> int:
    """The minimum to project against: never below the plan's, as the arm runner reads it."""
    recorded = _count(freeze, "minimum_evaluable", "freeze record", default=PLAN_MINIMUM_EVALUABLE)
    if recorded < PLAN_MINIMUM_EVALUABLE:
        if not allow_underpowered:
            raise ProjectionInputError(
                f"the freeze was made with minimum_evaluable={recorded}, under the plan's "
                f"{PLAN_MINIMUM_EVALUABLE} (pass --allow-underpowered-dry-run for a synthetic dry run)"
            )
        warnings.append(
            f"the record's minimum_evaluable is {recorded}, under the plan's {PLAN_MINIMUM_EVALUABLE}; "
            "projected against the plan's"
        )
    if recorded > PLAN_MINIMUM_EVALUABLE:
        warnings.append(
            f"the record's minimum_evaluable is {recorded}, above the plan's {PLAN_MINIMUM_EVALUABLE}; "
            f"projected against {recorded}"
        )
    minimum = max(recorded, PLAN_MINIMUM_EVALUABLE)
    if override is not None:
        if override < PLAN_MINIMUM_EVALUABLE:
            raise ProjectionInputError(
                f"--minimum {override} is under the plan's {PLAN_MINIMUM_EVALUABLE}; the plan's minimum "
                "is not this projection's to lower"
            )
        if override != minimum:
            warnings.append(f"projected against --minimum {override}, above the plan's {PLAN_MINIMUM_EVALUABLE}")
        minimum = override
    return minimum


def _fresh_reading(label: str, target: int, k: int, n: int, minimum: int, confidence: float) -> dict[str, Any]:
    pmf = beta_binomial_pmf(target, k, n)
    lower, upper = central_interval(pmf, confidence)
    return {
        "label": label,
        "candidates": target,
        "posterior_mean_evaluable": target * (k + 1) / (n + 2),
        "plug_in_evaluable": target * k / n,
        "interval": [lower, upper],
        "chance_of_minimum": tail_at_least(pmf, minimum),
    }


def project(
    freeze: Mapping[str, Any],
    *,
    target: int = PLAN_DISCOVERY_TARGET,
    minimum: int | None = None,
    confidence: float = DEFAULT_CONFIDENCE,
    discovery: Mapping[str, Any] | None = None,
    sampled_at_random: bool = False,
    allow_underpowered: bool = False,
    source: str | None = None,
) -> dict[str, Any]:
    """The projection as a JSON-ready dict; every number traceable to the inputs."""
    stage_counts = freeze.get("stage_counts")
    if not isinstance(stage_counts, Mapping):
        raise ProjectionInputError(
            f"freeze record has no 'stage_counts' object; got keys {sorted(freeze)!r}. "
            "Pass the file the freeze wrote."
        )
    if not 0.0 < confidence < 1.0:
        raise ProjectionInputError(f"confidence must be strictly between 0 and 1, got {confidence}")
    if target <= 0:
        raise ProjectionInputError(f"the discovery target must be positive, got {target}")

    n = _count(stage_counts, "discovered", "stage_counts")
    k = _count(freeze, "evaluable_count", "freeze record")
    if n == 0:
        raise ProjectionInputError("the freeze read no candidates; nothing to project from")
    if k > n:
        raise ProjectionInputError(f"evaluable_count {k} is larger than the {n} candidates characterised")

    rows, warnings = funnel_rows(stage_counts)
    if rows and rows[-1]["remaining"] != k:
        raise ProjectionInputError(
            f"the record disagrees with itself: evaluable_count is {k}, the funnel leaves "
            f"{rows[-1]['remaining']}; this projection has no hash to check a record by, so its counts "
            "have to agree"
        )
    recorded_minimum = _count(freeze, "minimum_evaluable", "freeze record", default=PLAN_MINIMUM_EVALUABLE)
    if "hard_stop" in freeze and freeze["hard_stop"] != (k < recorded_minimum):
        raise ProjectionInputError(
            f"the record disagrees with itself: hard_stop is {freeze['hard_stop']!r} with {k} evaluable "
            f"against its own minimum of {recorded_minimum}"
        )
    the_minimum = _plan_minimum(freeze, minimum, warnings, allow_underpowered=allow_underpowered)
    if k >= the_minimum:
        warnings.append(
            f"this record already has {k} evaluable, at or above the {the_minimum} projected against; "
            "there is nothing to project towards"
        )
    if target != PLAN_DISCOVERY_TARGET:
        warnings.append(
            f"projected at --target {target}; the plan discovers up to {PLAN_DISCOVERY_TARGET}, and a larger "
            "discovery is the owner's amendment, not this projection's"
        )
    label = "the plan's target" if target == PLAN_DISCOVERY_TARGET else f"--target {target}"
    readings = [_fresh_reading(label, target, k, n, the_minimum, confidence)]
    population = None
    if discovery is not None:
        population = _count(discovery, "candidate_count", "discovery report")
        if population == 0:
            raise ProjectionInputError("the discovery report found no candidates; nothing to read from")
        if population != target:
            readings.append(
                _fresh_reading("the rehearsal's own yield", population, k, n, the_minimum, confidence)
            )

    own_set: dict[str, Any] | None = None
    if population is not None:
        if population < n:
            warnings.append(
                f"discovery found {population} candidates but the freeze read {n}; the freeze did not "
                "sample that discovery, so the own-set reading is skipped"
            )
        elif population == n:
            own_set = {
                "discovered": population, "sampled": n, "degenerate": True,
                "note": f"the freeze read the whole discovered set; the count is the record's {k}, "
                        "nothing is inferred",
            }
        elif not sampled_at_random:
            warnings.append(
                f"the freeze read {n} of {population} discovered candidates, but nothing in the record "
                "says how those were chosen; the own-set reading needs --sampled-at-random, which asserts "
                "the characterised wallets were drawn from the discovery at random, and the fresh-discovery "
                "reading above rests on that same representativeness, here unstated"
            )
        else:
            posterior = hypergeometric_posterior(n, k, population)
            low, high = central_interval(posterior, confidence)
            own_set = {
                "discovered": population, "sampled": n, "degenerate": False,
                "expected_evaluable": sum(j * p for j, p in enumerate(posterior)),
                "interval": [low, high],
                "chance_of_minimum": tail_at_least(posterior, the_minimum),
                "discovery_target": discovery.get("target") if discovery else None,
            }

    peak = max((r["excluded"] for r in rows), default=0)
    largest = [r["stage"] for r in rows if r["excluded"] == peak] if peak else []
    assumptions = [
        "the T0 tape yields candidates like the rehearsal's tape did; the rehearsal cannot test this",
        "the characterised wallets are representative of what a discovery yields: the rehearsal draws them "
        "at random (repetitie.ps1, seed 7); a freeze run over every wallet with fills is not, and its "
        "projection is biased",
        "the T0 discovery reaches the size each reading names; the plan discovers up to "
        f"{PLAN_DISCOVERY_TARGET}",
        "a uniform prior on the evaluable share, which moves the share by (n - 2k) / (n(n + 2)), at most "
        "1 / (n + 2): at a discovery of T that is at most T / (n + 2) wallets, so it matters for a small "
        "characterised set with few survivors or few drop-outs and fades as n grows. The plug-in reading "
        "beside each posterior mean is the same number without the prior",
        f"the plan's minimum of {PLAN_MINIMUM_EVALUABLE} is not lowered and the freeze is not rerun with "
        "other flags",
    ]
    if own_set is not None and not own_set["degenerate"]:
        assumptions.append(
            "the characterised wallets were drawn from the discovered set at random, as --sampled-at-random states; "
            "the own-set reading is worth nothing otherwise"
        )
    return {
        "kind": "funnel projection from a freeze record; not an evidence file, and it decides nothing",
        "source": {
            "file": source,
            "t0_utc": freeze.get("t0_utc"),
            "plan_commit": freeze.get("plan_commit"),
            "attempted_sha256": freeze.get("attempted_sha256"),
            "hard_stop": freeze.get("hard_stop"),
        },
        "inputs": {"characterised": n, "evaluable": k, "minimum": the_minimum, "confidence": confidence},
        "evaluable_share": {
            "estimate": k / n,
            "interval": list(clopper_pearson(k, n, confidence)),
            "method": "Clopper-Pearson, the exact binomial interval",
        },
        "funnel": rows,
        "largest_losses": largest,
        "fresh_discovery": readings,
        "candidates_needed": {
            f"{int(round(c * 100))}_percent": candidates_for_chance(k, n, the_minimum, c) for c in CHANCES
        },
        "search_cap": SEARCH_CAP,
        "plan": {"minimum": PLAN_MINIMUM_EVALUABLE, "discovery_target": PLAN_DISCOVERY_TARGET},
        "rehearsal_set": own_set,
        "warnings": warnings,
        "assumptions": assumptions,
    }


# ---- rendering ----------------------------------------------------------------------------


def _pct(x: float) -> str:
    return f"{100.0 * x:.1f} %"


def _level(confidence: float) -> str:
    return f"{100.0 * confidence:g} %"


def render(projection: Mapping[str, Any]) -> str:
    """The projection as short Markdown for the owner."""
    inputs, rate, source = projection["inputs"], projection["evaluable_share"], projection["source"]
    n, k, minimum = inputs["characterised"], inputs["evaluable"], inputs["minimum"]
    level = _level(inputs["confidence"])
    provenance = ", ".join(
        part for part in (
            f"freeze {source['file']}" if source.get("file") else None,
            f"T0 {source['t0_utc']}" if source.get("t0_utc") else None,
            f"plan commit `{source['plan_commit']}`" if source.get("plan_commit") else None,
            "hard stop" if source.get("hard_stop") else None,
        ) if part
    )
    lines = [
        "# Funnel projection from a freeze record",
        "",
        f"*{projection['kind']}.*" + (f" Read from: {provenance}." if provenance else ""),
        "",
        f"The freeze read {n} characterised candidates and found {k} evaluable: an evaluable share of "
        f"{_pct(rate['estimate'])}, exact {level} interval {_pct(rate['interval'][0])} to "
        f"{_pct(rate['interval'][1])}. Projected against a minimum of {minimum}"
        + ("." if minimum == PLAN_MINIMUM_EVALUABLE else f" (the plan's is {PLAN_MINIMUM_EVALUABLE})."),
        "",
        "## The funnel, in selection order",
        "",
        "| stage | excluded | share of discovered | remaining |",
        "|---|---|---|---|",
    ]
    for row in projection["funnel"]:
        lines.append(
            f"| {row['stage']} | {row['excluded']} | {_pct(row['share_of_discovered'])} | {row['remaining']} |"
        )
    if projection["largest_losses"]:
        named = " and ".join(f"`{s}`" for s in projection["largest_losses"])
        lines += ["", f"The largest loss is {named}." if len(projection["largest_losses"]) == 1
                  else f"The largest losses are {named}, tied."]
    lines += ["", "## What a fresh discovery at T0 gives", "",
              f"| discovery | candidates | posterior mean | plug-in at {_pct(rate['estimate'])} | "
              f"{level} interval | chance of {minimum} |", "|---|---|---|---|---|---|"]
    for reading in projection["fresh_discovery"]:
        lines.append(
            f"| {reading['label']} | {reading['candidates']} | {reading['posterior_mean_evaluable']:.1f} | "
            f"{reading['plug_in_evaluable']:.1f} | {reading['interval'][0]} to {reading['interval'][1]} | "
            f"{_pct(reading['chance_of_minimum'])} |"
        )
    lines += ["", "| chance of reaching the minimum | candidates to discover |", "|---|---|"]
    for label, needed in projection["candidates_needed"].items():
        shown = f"more than {projection['search_cap']} (the search cap)" if needed is None else str(needed)
        lines.append(f"| {label.replace('_percent', ' %')} | {shown} |")
    lines += [
        "",
        f"The plan discovers up to {PLAN_DISCOVERY_TARGET} candidates. A larger discovery is a change to "
        "the plan the owner records before T0, not a number this projection authorises.",
    ]
    own = projection["rehearsal_set"]
    if own is not None:
        lines += ["", f"## The rehearsal's own discovered set ({own['discovered']} candidates, "
                      f"{own['sampled']} characterised)", ""]
        if own["degenerate"]:
            lines.append(own["note"].capitalize() + ".")
        else:
            lines.append(
                f"Had the full set been frozen: expected evaluable {own['expected_evaluable']:.1f}, "
                f"{level} interval {own['interval'][0]} to {own['interval'][1]}, chance of reaching "
                f"{minimum}: {_pct(own['chance_of_minimum'])}. This is about the rehearsal's set, not T0's."
            )
    lines += ["", "## What this assumes", ""] + [f"- {a}" for a in projection["assumptions"]]
    if projection["warnings"]:
        lines += ["", "## Warnings", ""] + [f"- {w}" for w in projection["warnings"]]
    return "\n".join(lines).rstrip() + "\n"


# ---- command line -------------------------------------------------------------------------


def _read_json(path: Path, what: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise ProjectionInputError(f"{what} not found at {path}") from None
    except (OSError, ValueError) as exc:
        raise ProjectionInputError(f"{what} at {path} is not readable JSON: {exc}") from None
    if not isinstance(payload, Mapping):
        raise ProjectionInputError(f"{what} at {path} is not a JSON object")
    return payload


def _write(path: Path, text: str, what: str) -> None:
    try:
        path.write_text(text, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise ProjectionInputError(f"cannot write the {what} to {path}: {exc}") from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="funnel_projection",
        description="Project the T0 funnel from a rehearsal freeze record. Reads counts only.",
    )
    parser.add_argument("--freeze", type=Path, required=True,
                        help="the freeze record the rehearsal's freeze wrote (repetitie.ps1 names it REP_FREEZE.json)")
    parser.add_argument("--discovery", type=Path, default=None, help="the discovery report the rehearsal wrote")
    parser.add_argument("--target", type=int, default=PLAN_DISCOVERY_TARGET,
                        help=f"candidates the T0 discovery aims for (default {PLAN_DISCOVERY_TARGET}, the plan's)")
    parser.add_argument("--minimum", type=int, default=None,
                        help=f"project against a minimum above the plan's {PLAN_MINIMUM_EVALUABLE}")
    parser.add_argument("--confidence", type=float, default=DEFAULT_CONFIDENCE,
                        help=f"level of the intervals (default {DEFAULT_CONFIDENCE})")
    parser.add_argument("--sampled-at-random", action="store_true", dest="sampled_at_random",
                        help="the judged wallets were drawn from the discovery at random; needed for the own-set reading")
    parser.add_argument("--allow-underpowered-dry-run", action="store_true", dest="allow_underpowered",
                        help="accept a freeze made under the plan's minimum, and project against the plan's anyway")
    parser.add_argument("--out", type=Path, default=None, help="write the projection as JSON")
    parser.add_argument("--markdown", type=Path, default=None, help="write the projection as Markdown")
    return parser


def main(argv: Sequence[str] | None = None, *, log: Callable[[str], None] = print) -> int:
    args = build_parser().parse_args(argv)
    try:
        freeze = _read_json(args.freeze, "freeze record")
        discovery = None if args.discovery is None else _read_json(args.discovery, "discovery report")
        projection = project(
            freeze, target=args.target, minimum=args.minimum, confidence=args.confidence,
            discovery=discovery, sampled_at_random=args.sampled_at_random,
            allow_underpowered=args.allow_underpowered, source=args.freeze.name,
        )
        text = render(projection)
        if args.out is not None:
            _write(args.out, json.dumps(projection, indent=2, sort_keys=True) + "\n", "projection")
        if args.markdown is not None:
            _write(args.markdown, text, "report")
    except ProjectionInputError as exc:
        log(f"funnel_projection: refusing: {exc}")
        return 2
    except (ArithmeticError, ValueError) as exc:  # arithmetic the inputs drove out of range
        log(f"funnel_projection: refusing: the arithmetic did not hold for these inputs: {exc}")
        return 2
    log(text.rstrip("\n"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
