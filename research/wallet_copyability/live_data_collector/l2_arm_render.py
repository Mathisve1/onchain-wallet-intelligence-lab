"""Render an arm's evidence file in the report order the plan fixed.

``L2_ANALYSIS_PLAN.md`` ("Report order for arm A", recorded as binding in
DEC-046) fixes what a completed arm's report says and in which order: the
answer in one sentence; the confidence interval; the survivorship
measurement; n after every filter stage; what broke; only then the tables.
The evidence file is a JSON object sorted alphabetically, which is the right
shape for a machine and the wrong one for that rule, so this module lays the
same values out in the order the owner fixed before any number existed.

It states no figure of its own. Every value is copied from the evidence file
as written, including its rounding; the only arithmetic is counting rows the
report also prints in full, and timestamps stay in the milliseconds the file
uses rather than being converted into something no reader can check against
the JSON.

What it does compute is a check, not a number. The plan's reading and
decision rules are re-applied to the interval the file prints, and a label
that does not follow from those bounds is a refusal rather than a sentence:
this module exists to state a result and must not be the place where a wrong
one is laundered into prose. It refuses on the same principle when the
target is not the plan's, when an arm carries the other arm's verdict, when
the status is one it does not know, and when the disclosures or limitations
the approval requires beside a result are missing.

A report is also the most forwardable thing the study produces, and the
plan's stop rule says no result leaves the repository before both windows
close. Every report says so on its face.

Run from the repository root, after an arm has completed::

    python -m research.wallet_copyability.live_data_collector.l2_arm_render \\
        --evidence EV/L2_ARM_A_001.json --out EV/L2_ARM_A_001_REPORT.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from .l2_arm_statistics import (
    ARM_A_CASE_STUDY_UNDER_MINIMUM,
    ARM_A_INCONCLUSIVE,
    ARM_A_NEGATIVE,
    ARM_A_NOT_MEASURABLE,
    ARM_A_POSITIVE,
    GO_TO_ENTITY_CLUSTER_RESEARCH,
    NO_GO_NO_COPYABLE_ALPHA,
    PRIMARY_LATENCY_MS,
    REPAIR_AND_RERUN,
    TARGET_POINTS_PER_14D,
    decision_for,
    reading_for,
)

EXIT_REFUSED = 2
SCHEMA_VERSION = "1.0"

#: The plan's order. The headings are the report's contract: a reader who
#: knows DEC-046 can check the order without reading the prose.
SECTIONS = (
    "The answer",
    "The confidence interval",
    "Survivorship",
    "n after every filter stage",
    "What broke",
    "Tables",
)

#: Every block the plan or the approval requires beside a result. A file that
#: lacks one is refused, because a report that silently drops the caveats
#: reads as more complete than the run it describes.
REQUIRED_KEYS = (
    "schema_version", "run_id", "arm", "variant", "plan_commit", "cohort_sha256", "t0_ms",
    "evaluation_window", "primary", "survivorship", "counts", "refusals", "scope", "pool",
    "stage_counts", "per_wallet_reason", "assumptions", "secondary", "diagnostics_rollup",
    "price_source", "price_provenance", "price_series_span_by_coin", "reading_rule",
    "sample_limitations_disclosure", "what_broke", "empirical_result_status",
    "copyability_claim_produced",
)
_PRIMARY_KEYS = ("n", "mean", "ci95", "target", "minimum", "case_study", "disclosures", "excluded", "d_by_wallet")

#: Statuses this renderer knows how to state. One it does not know is a
#: refusal: a status added later must not be reported as a result by a
#: renderer that predates it.
STATUS_EARLY_READ = "ARM_A_EARLY_READ_ONLY"
STATUS_DECIDED = "ARM_B_DECIDED"
STATUS_CASE_STUDY = "CASE_STUDY_UNDER_MINIMUM"
STATUS_NOT_MEASURABLE = "NOT_MEASURABLE"
STATUS_DRY_RUN = "DRY_RUN_UNDERPOWERED"
STATUS_BROKE = "BROKE_SEE_WHAT_BROKE"
KNOWN_STATUSES = frozenset({
    STATUS_EARLY_READ, STATUS_DECIDED, STATUS_CASE_STUDY, STATUS_NOT_MEASURABLE, STATUS_DRY_RUN, STATUS_BROKE,
})
#: Statuses whose numbers are not a reading. Their verdict row is withheld.
NO_VERDICT_STATUSES = frozenset({STATUS_BROKE, STATUS_DRY_RUN, STATUS_NOT_MEASURABLE})
ARM_A_LABELS = frozenset({ARM_A_NEGATIVE, ARM_A_POSITIVE, ARM_A_INCONCLUSIVE,
                          ARM_A_NOT_MEASURABLE, ARM_A_CASE_STUDY_UNDER_MINIMUM})
ARM_B_LABELS = frozenset({GO_TO_ENTITY_CLUSTER_RESEARCH, NO_GO_NO_COPYABLE_ALPHA, REPAIR_AND_RERUN})

#: The plan's own words, so a reader who has not read it still knows what was
#: measured and under which rule.
QUESTION = ("Does copying a directional Hyperliquid wallet, at a stated latency and after every follower cost, "
            "earn more than copying a random wallet of similar activity?")
D_DEFINITION = ("Per wallet i, d_i = R_i minus M_i: the follower's net return on the capital the copy actually "
                f"deployed, minus the mean of that same measure over the wallet's matched-random peers, at the "
                f"primary latency of {PRIMARY_LATENCY_MS} ms. The reported statistic is the mean of d_i over the "
                "evaluated set, in points per 14-day equivalent.")
STOP_RULE = ("The plan's stop rule: no result leaves this repository before both windows close and the "
             "disclosures are written. Arm B closes at T0 plus 56 days and is the arm that decides.")
EXPLORATORY = ("EXPLORATORY. The plan excludes subgroup hunting in advance: no latency, coin, wallet class or "
               "time window below can carry a GO, and the plan permits no wallet-level claims. These rows exist "
               "so the primary can be audited, not selected from.")

_ANSWERS = {
    ARM_A_NEGATIVE: "Arm A reads negative: the 95 percent interval for mean d lies entirely below the target "
                    "of {target} points per 14-day equivalent, and arm A decides nothing.",
    ARM_A_POSITIVE: "Arm A reads positive: the 95 percent interval for mean d lies entirely above the target "
                    "of {target} points per 14-day equivalent, which is interesting and not actionable, and "
                    "arm A decides nothing.",
    ARM_A_INCONCLUSIVE: "Arm A is inconclusive: the 95 percent interval for mean d contains the target of "
                        "{target} points per 14-day equivalent, and arm A decides nothing.",
    GO_TO_ENTITY_CLUSTER_RESEARCH: "Arm B decides GO_TO_ENTITY_CLUSTER_RESEARCH: the lower bound of the 95 "
                                   "percent interval for mean d reaches the target of {target} points per "
                                   "14-day equivalent.",
    NO_GO_NO_COPYABLE_ALPHA: "Arm B decides NO_GO_NO_COPYABLE_ALPHA: the upper bound of the 95 percent interval "
                             "for mean d stays below the target of {target} points per 14-day equivalent.",
    REPAIR_AND_RERUN: "Arm B decides REPAIR_AND_RERUN: the 95 percent interval for mean d contains the target "
                      "of {target} points per 14-day equivalent, so the repair is named before any rerun.",
}


class RenderError(ValueError):
    """The file handed in is not a completed arm's evidence, or contradicts itself."""


def load_evidence(path: Path) -> dict:
    """The evidence file, refused unless it is one and it is complete."""
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RenderError(f"{path}: cannot be read as JSON: {exc}") from exc
    if not isinstance(evidence, dict):
        raise RenderError(f"{path}: an evidence file is a JSON object")
    if evidence.get("checkpoint"):
        raise RenderError(
            f"{path}: this is a checkpoint written while the arm was still running, not its evidence. "
            "An arm's report is delivered only when the arm is complete."
        )
    missing = [key for key in REQUIRED_KEYS if key not in evidence]
    if missing:
        raise RenderError(f"{path}: not a complete evidence file; it lacks {', '.join(missing)}")
    if evidence["schema_version"] != SCHEMA_VERSION:
        raise RenderError(
            f"{path}: evidence schema {evidence['schema_version']!r}, this report writes {SCHEMA_VERSION!r}; "
            "a file from another schema is refused rather than rendered on guesses"
        )
    for key in ("primary", "survivorship", "counts", "evaluation_window", "scope", "pool"):
        if not isinstance(evidence[key], dict):
            raise RenderError(f"{path}: {key!r} must be an object")
    missing = [key for key in _PRIMARY_KEYS if key not in evidence["primary"]]
    if missing:
        raise RenderError(f"{path}: primary lacks {', '.join(missing)}")
    if evidence["empirical_result_status"] not in KNOWN_STATUSES:
        raise RenderError(
            f"{path}: empirical_result_status {evidence['empirical_result_status']!r} is not one this report "
            f"knows how to state (it knows {', '.join(sorted(KNOWN_STATUSES))})"
        )
    if not evidence["sample_limitations_disclosure"] or not evidence["primary"]["disclosures"]:
        raise RenderError(
            f"{path}: the disclosures and limitations the approval requires beside a result are empty; "
            "a report without them would read as more complete than the run it describes"
        )
    return evidence


def verdict_of(evidence: Mapping[str, Any]) -> str | None:
    """The arm's own verdict, refused when it is not the arm's to carry.

    Arm A reads and decides nothing; arm B decides and carries no reading.
    A file that mixes them is a file this report will not narrate.
    """
    arm, primary = evidence["arm"], evidence["primary"]
    reading, decision = primary.get("reading"), evidence.get("decision")
    if arm == "A":
        if decision is not None:
            raise RenderError(f"an arm A file carries decision {decision!r}; arm A decides nothing")
        if reading is not None and reading not in ARM_A_LABELS:
            raise RenderError(f"arm A carries an unknown reading {reading!r}")
        return reading
    if reading is not None:
        raise RenderError(f"an arm B file carries the arm A reading {reading!r}; arm B's verdict is its decision")
    if decision is not None and decision not in ARM_B_LABELS:
        raise RenderError(f"arm B carries an unknown decision {decision!r}")
    return decision


def check_against_the_rule(evidence: Mapping[str, Any]) -> None:
    """Re-apply the plan's own rule to the interval the file prints.

    ``reading_taken_on: ci95 as written`` is the promise; this is where it is
    kept. No statistic is recomputed: the plan's rule is applied to the two
    bounds the report shows, and a label those bounds do not support is
    refused rather than narrated.
    """
    primary = evidence["primary"]
    if str(primary["target"]) != str(TARGET_POINTS_PER_14D):
        raise RenderError(
            f"the file's target is {primary['target']!r}, the plan's is {TARGET_POINTS_PER_14D}; the plan "
            "excludes any lowering of the target in advance, so this file is refused rather than reported"
        )
    verdict = verdict_of(evidence)
    if verdict is None or primary["ci95"] is None or evidence["what_broke"]:
        return
    if verdict in (ARM_A_CASE_STUDY_UNDER_MINIMUM, ARM_A_NOT_MEASURABLE):
        return
    lower, upper = primary["ci95"]
    expected = decision_for(primary) if evidence["arm"] == "B" else reading_for(lower, upper)
    if expected != verdict:
        raise RenderError(
            f"the file's verdict {verdict!r} is not what the plan's rule gives for the interval it prints "
            f"([{lower}, {upper}] against {TARGET_POINTS_PER_14D}), which is {expected!r}"
        )


def answer(evidence: Mapping[str, Any]) -> str:
    """The one sentence the plan puts first, chosen by the file's own labels."""
    status, primary, counts = evidence["empirical_result_status"], evidence["primary"], evidence["counts"]
    if status == STATUS_BROKE or evidence["what_broke"]:
        broke = len(evidence["what_broke"])
        return (f"Arm {evidence['arm']} produced no reading because {broke} thing(s) broke, listed under "
                f"'{SECTIONS[4]}', so nothing in this report decides anything.")
    if status == STATUS_DRY_RUN:
        return (f"This run is stamped {STATUS_DRY_RUN} (the freeze recorded a minimum of "
                f"{evidence.get('record_minimum_evaluable')} against the plan's {primary['minimum']}, and "
                f"{counts['wallets']} wallets were evaluated), so it is not a result.")
    if status == STATUS_NOT_MEASURABLE:
        return (f"Arm {evidence['arm']} is not measurable: the {primary['n']} wallets in the primary carry no "
                "spread for an interval to be built on.")
    if status == STATUS_CASE_STUDY:
        return (f"{primary['n']} wallets entered the primary, under the plan's minimum of {primary['minimum']}, "
                f"so arm {evidence['arm']} is a case study and decides nothing.")
    verdict = verdict_of(evidence)
    sentence = _ANSWERS.get(verdict)
    if sentence is None:
        raise RenderError(f"the file carries no verdict this report knows how to state: {verdict!r}")
    return sentence.format(target=TARGET_POINTS_PER_14D)


def _cell(value: Any) -> str:
    """One table cell: the file's text, kept on one row and inside one column."""
    text = _scalar(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    if not rows:
        return ["_none_", ""]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    lines += ["| " + " | ".join(_cell(cell) for cell in row) + " |" for row in rows]
    return lines + [""]


def _pairs(items: Mapping[str, Any]) -> list[str]:
    return _table(("field", "value"), list(items.items()))


def _scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, sort_keys=True) if value else "none"
    return str(value)


def _answer_section(evidence: Mapping[str, Any]) -> list[str]:
    out = [f"## {SECTIONS[0]}", "", answer(evidence), ""]
    out += [f"No copyability claim is produced (`copyability_claim_produced`: "
            f"{_scalar(evidence['copyability_claim_produced'])}). This report measures d under the stated "
            "assumptions; it recommends nothing, forecasts nothing, and names no wallet as copyable.", ""]
    inflation = evidence.get("survivorship_inflation")
    if isinstance(inflation, dict) and inflation.get("available"):
        out += [f"Measured survivorship inflation: mean d_A {inflation['mean_d_a']} minus mean d_B "
                f"{inflation['mean_d_b']} is {inflation['inflation_points_per_14d']} points per 14-day "
                f"equivalent, against arm A's reading {inflation.get('arm_a_reading')}.", ""]
        if inflation.get("a_negative_b_positive"):
            out += ["**Arm A read negative and arm B decides GO.** The plan names this case explicitly and "
                    "never handles it silently: " + str(inflation.get("note", "")) + " Read the diagnosis "
                    "before this GO is acted on.", ""]
    out += [f"Reading rule: {evidence['reading_rule']}", ""]
    return out


def _interval_section(evidence: Mapping[str, Any]) -> list[str]:
    primary = evidence["primary"]
    withheld = evidence["empirical_result_status"] in NO_VERDICT_STATUSES or bool(evidence["what_broke"])
    out = [f"## {SECTIONS[1]}", ""]
    if withheld:
        out += [f"The figures below are the file's own, and they are not a reading: this run is stamped "
                f"{evidence['empirical_result_status']} and its verdict is withheld.", ""]
    lower, upper = (primary["ci95"] or [None, None])
    fields = {
        "mean d": primary["mean"], "ci95 lower": lower, "ci95 upper": upper, "n": primary["n"],
        "unit": primary.get("unit"), "target": primary["target"], "latency_ms": primary.get("latency_ms"),
        "sd": primary.get("sd"), "standard_error": primary.get("standard_error"),
        "t_statistic": primary.get("t_statistic"), "t_critical": primary.get("t_critical"),
        "measurable": primary.get("measurable"), "case_study": primary["case_study"],
        "minimum": primary["minimum"],
    }
    field = primary.get("verdict_field") or "reading"
    fields[f"{field} (withheld: not a reading)" if withheld else field] = (
        "withheld" if withheld else verdict_of(evidence)
    )
    fields["reading_taken_on"] = primary.get("reading_taken_on")
    return out + _pairs(fields)


def _survivorship_section(evidence: Mapping[str, Any]) -> list[str]:
    surv = evidence["survivorship"]
    out = [f"## {SECTIONS[2]}", "", "Both measures the plan declares, each with the denominator it is "
           "measured against, in the file's own definitions:", ""]
    definition = surv.get("definition") or {}
    out += [f"- **{key}**: {value}" for key, value in sorted(definition.items())] + [""]
    out += _pairs({
        "cohort": surv["cohort"], "active_in_window": surv["active_in_window"],
        "stopped": surv["stopped"], "stopped_share_of_cohort": surv["stopped_share_of_cohort"],
        "stopped_share_of_active": surv["stopped_share_of_active"],
        "faded": surv["faded"], "faded_judged": surv["faded_judged"],
        "faded_share_of_cohort": surv["faded_share_of_cohort"],
        "faded_share_of_judged": surv["faded_share_of_judged"],
    })
    inflation = evidence.get("survivorship_inflation")
    if isinstance(inflation, dict):
        out += ["Arm B only: the measured inflation against arm A, a number and never a gate.", ""]
        out += _pairs({key: inflation[key] for key in sorted(inflation)})
    return out


def _stages_section(evidence: Mapping[str, Any]) -> list[str]:
    primary, counts, scope = evidence["primary"], evidence["counts"], evidence["scope"]
    out = [f"## {SECTIONS[3]}", "", "From the tape to the primary, every stage that removed something.", ""]
    out += ["Discovery and the freeze:", ""]
    out += _table(("stage", "n"), sorted((evidence["stage_counts"] or {}).items()))
    out += ["Why the freeze excluded a candidate:", ""]
    out += _table(("reason", "n"), sorted((evidence["per_wallet_reason"] or {}).items()))
    out += ["Instrument scope, and the fills it removed inside the window:", ""]
    out += _pairs({
        "funding_coins": scope.get("funding_coins"), "candle_complete_coins": scope.get("candle_complete_coins"),
        "excluded": scope.get("excluded"), "coins_evaluated": scope.get("coins_evaluated"),
        "out_of_scope_definition": scope.get("out_of_scope_definition"),
        "deviation_from_plan_wording": scope.get("deviation_from_plan_wording"),
    })
    out += _table(("wallet", "fills dropped as out of scope"),
                  sorted((scope.get("out_of_scope_fills_by_wallet") or {}).items()))
    out += ["From the frozen cohort to the primary:", ""]
    out += _table(("stage", "n"), [(key, counts[key]) for key in ("wallets", "scored", "refused", "in_primary")])
    out += ["Why a scored wallet did not enter the primary:", ""]
    out += _table(("wallet", "reason"), sorted((primary["excluded"] or {}).items()))
    out += ["The peer pool the primary contrasted against:", ""]
    out += _pairs({key: value for key, value in sorted((evidence["pool"] or {}).items())})
    return out


def _broke_section(evidence: Mapping[str, Any]) -> list[str]:
    out = [f"## {SECTIONS[4]}", ""]
    broke = evidence["what_broke"]
    out += ([f"- {item}" for item in broke] if broke else ["Nothing broke."]) + [""]
    out += ["Wallets the run refused, and why:", ""]
    out += _table(("wallet", "refusal"), sorted((evidence["refusals"] or {}).items()))
    closure = evidence.get("closure")
    if isinstance(closure, dict):
        out += ["Arm B only: on what basis the window was declared closed.", ""]
        out += _pairs({key: closure[key] for key in sorted(closure)})
        out += [f"window_closed_before_run: {_scalar(evidence.get('window_closed_before_run'))}", ""]
    out += ["Diagnostics at the primary latency:", ""]
    out += _pairs({key: value for key, value in sorted((evidence["diagnostics_rollup"] or {}).items())})
    return out


def _tables_section(evidence: Mapping[str, Any]) -> list[str]:
    primary, secondary = evidence["primary"], evidence["secondary"] or {}
    out = [f"## {SECTIONS[5]}", "", EXPLORATORY, "", "Mean d by latency:", ""]
    out += _table(("latency_ms", "n", "mean"),
                  [(k, v["n"], v["mean"]) for k, v in sorted((secondary.get("mean_d_by_latency") or {}).items())])
    out += ["Mean return versus each baseline:", ""]
    out += _table(("baseline@latency_ms", "n", "mean"),
                  [(k, v["n"], v["mean"]) for k, v in sorted((secondary.get("mean_versus_baseline") or {}).items())])
    out += ["d by wallet:", ""]
    out += _table(("wallet", "d"), sorted((primary["d_by_wallet"] or {}).items()))
    out += ["Price series against the window:", ""]
    out += _table(("coin", "rows", "first_ms", "last_ms", "spans_window"),
                  [(coin, d["rows"], d["first_ms"], d["last_ms"], d["spans_window"])
                   for coin, d in sorted((evidence["price_series_span_by_coin"] or {}).items())])
    out += ["Where the prices came from:", ""]
    out += _pairs({key: value for key, value in sorted((evidence["price_provenance"] or {}).items())})
    out += ["The four disclosures that travel with every result:", ""]
    out += _pairs({key: value for key, value in sorted((primary["disclosures"] or {}).items())})
    out += ["Assumptions, as recorded:", ""]
    out += _pairs({key: value for key, value in sorted((evidence["assumptions"] or {}).items())})
    out += ["Limitations, in the words the file carries:", ""]
    out += [f"- {note}" for note in evidence["sample_limitations_disclosure"]] + [""]
    return out


def render(evidence: Mapping[str, Any], *, evidence_sha256: str) -> str:
    """The report, in the plan's order. Every figure is the file's own."""
    check_against_the_rule(evidence)
    window = evidence["evaluation_window"]
    out: list[str] = [
        f"# {evidence['run_id']}: arm {evidence['arm']} ({evidence['variant']})",
        "",
        f"**{STOP_RULE}**",
        "",
        f"The question, from the plan: {QUESTION}",
        "",
        D_DEFINITION,
        "",
        "Rendered from the evidence file in the report order fixed by `L2_ANALYSIS_PLAN.md` before any number "
        "existed (DEC-046). Every figure below is copied from that file as written, and instants are the "
        "Unix-epoch milliseconds the file uses.",
        "",
    ]
    out += _pairs({
        "evidence_sha256": evidence_sha256,
        "schema_version": evidence["schema_version"],
        "plan_commit": evidence["plan_commit"],
        "approvals": evidence.get("approvals", []),
        "cohort_sha256": evidence["cohort_sha256"],
        "t0_ms": evidence["t0_ms"],
        "evaluation_window": f"{window['start_ms']} to {window['end_ms']} ({window['days']} days)",
        "price_source": evidence["price_source"],
        "empirical_result_status": evidence["empirical_result_status"],
        "decisive_arm": evidence.get("decisive_arm"),
        "dry_run_flag_passed": evidence.get("dry_run_flag_passed"),
        "record_minimum_evaluable": evidence.get("record_minimum_evaluable"),
        "copyability_claim_produced": evidence["copyability_claim_produced"],
    })
    out += _answer_section(evidence)
    out += _interval_section(evidence)
    out += _survivorship_section(evidence)
    out += _stages_section(evidence)
    out += _broke_section(evidence)
    out += _tables_section(evidence)
    return "\n".join(out).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="l2_arm_render",
        description="Render a completed arm's evidence file in the report order the plan fixed.",
    )
    parser.add_argument("--evidence", type=Path, required=True, help="the arm's evidence file")
    parser.add_argument("--out", type=Path, default=None, help="write here instead of standard output")
    return parser


def main(argv: Sequence[str] | None = None, *, log=print) -> int:
    args = build_parser().parse_args(argv)
    try:
        evidence = load_evidence(args.evidence)
        digest = hashlib.sha256(args.evidence.read_bytes()).hexdigest()
        text = render(evidence, evidence_sha256=digest)
    except (RenderError, KeyError, TypeError, AttributeError, IndexError) as exc:
        log(f"l2_arm_render: refusing to render: {type(exc).__name__}: {exc}")
        return EXIT_REFUSED
    if args.out is None:
        log(text)
    else:
        args.out.write_text(text, encoding="utf-8", newline="\n")
        log(f"l2_arm_render: wrote {args.out} from {args.evidence.name} ({digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
