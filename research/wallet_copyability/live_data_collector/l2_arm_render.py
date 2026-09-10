"""Render an arm's evidence file in the report order the plan fixed.

``L2_ANALYSIS_PLAN.md`` ("Report order for arm A", recorded as a binding
decision in DEC-046) fixes what a completed arm's report says and in which
order: the answer in one sentence; the confidence interval; the survivorship
measurement; n after every filter stage; what broke; only then the tables.
The evidence file is a JSON object sorted alphabetically, which is the right
shape for a machine and the wrong one for that rule, so this module lays the
same values out in the order the owner fixed before any number existed.

It computes nothing. Every figure here is copied from the evidence file as
written, including its rounding, so a reader can find each one in the JSON.
The answer sentence is chosen by the file's own ``empirical_result_status``,
``primary.reading`` and ``decision`` fields; this module has no opinion about
what the numbers mean and cannot upgrade a case study into a reading.

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
    ARM_A_INCONCLUSIVE,
    ARM_A_NEGATIVE,
    ARM_A_POSITIVE,
    GO_TO_ENTITY_CLUSTER_RESEARCH,
    NO_GO_NO_COPYABLE_ALPHA,
    REPAIR_AND_RERUN,
)

EXIT_REFUSED = 2

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

REQUIRED_KEYS = (
    "run_id", "arm", "variant", "plan_commit", "cohort_sha256", "t0_ms",
    "evaluation_window", "primary", "survivorship", "counts", "what_broke",
    "empirical_result_status", "copyability_claim_produced",
)

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
    """The file handed in is not a completed arm's evidence."""


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
    return evidence


def answer(evidence: Mapping[str, Any]) -> str:
    """The one sentence the plan puts first, chosen by the file's own labels."""
    status = evidence["empirical_result_status"]
    primary = evidence["primary"]
    target = primary.get("target", "0.5")
    if evidence["what_broke"]:
        return (f"Arm {evidence['arm']} produced no reading because something broke "
                f"({evidence['what_broke'][0]}), so nothing in this report decides anything.")
    if status == "DRY_RUN_UNDERPOWERED":
        return (f"This is a synthetic dry run on {evidence['counts']['wallets']} wallets, under the plan's "
                f"minimum of {primary['minimum']}, and it is not a result.")
    if status == "NOT_MEASURABLE":
        return (f"Arm {evidence['arm']} is not measurable: the {primary['n']} wallets in the primary carry no "
                "spread for an interval to be built on.")
    if status == "CASE_STUDY_UNDER_MINIMUM":
        return (f"{primary['n']} wallets entered the primary, under the plan's minimum of {primary['minimum']}, "
                f"so arm {evidence['arm']} is a case study and decides nothing.")
    verdict = evidence.get("decision") or primary.get("reading")
    sentence = _ANSWERS.get(verdict)
    if sentence is None:
        raise RenderError(f"the file carries no verdict this report knows how to state: {verdict!r}")
    return sentence.format(target=target)


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    if not rows:
        return ["_none_", ""]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    lines += ["| " + " | ".join("" if cell is None else str(cell) for cell in row) + " |" for row in rows]
    return lines + [""]


def _pairs(items: Mapping[str, Any]) -> list[str]:
    return _table(("field", "value"), [(key, _scalar(value)) for key, value in items.items()])


def _scalar(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value) if value else "none"
    if isinstance(value, dict):
        return ", ".join(f"{k}: {v}" for k, v in sorted(value.items())) if value else "none"
    return "null" if value is None else str(value)


def render(evidence: Mapping[str, Any], *, evidence_sha256: str) -> str:
    """The report, in the plan's order. Every figure is the file's own."""
    primary, counts = evidence["primary"], evidence["counts"]
    window, surv = evidence["evaluation_window"], evidence["survivorship"]
    out: list[str] = [
        f"# {evidence['run_id']} — arm {evidence['arm']} ({evidence['variant']})",
        "",
        "Rendered from the evidence file in the report order fixed by `L2_ANALYSIS_PLAN.md` before any "
        "number existed (DEC-046). Every figure below is copied from that file as written; this report "
        "computes nothing and interprets nothing.",
        "",
    ]
    out += _pairs({
        "evidence_sha256": evidence_sha256,
        "plan_commit": evidence["plan_commit"],
        "approvals": evidence.get("approvals", []),
        "cohort_sha256": evidence["cohort_sha256"],
        "t0_ms": evidence["t0_ms"],
        "evaluation_window": f"{window['start_ms']} to {window['end_ms']} ({window['days']} days)",
        "price_source": _scalar(evidence.get("price_source", {})),
        "empirical_result_status": evidence["empirical_result_status"],
        "decisive_arm": evidence.get("decisive_arm"),
        "copyability_claim_produced": evidence["copyability_claim_produced"],
    })

    out += [f"## {SECTIONS[0]}", "", answer(evidence), "", f"Reading rule: {evidence.get('reading_rule')}", ""]

    out += [f"## {SECTIONS[1]}", ""]
    out += _pairs({
        "mean d": primary["mean"], "ci95": primary["ci95"], "n": primary["n"],
        "unit": primary.get("unit"), "target": primary.get("target"),
        "latency_ms": primary.get("latency_ms"), "sd": primary.get("sd"),
        "standard_error": primary.get("standard_error"), "t_statistic": primary.get("t_statistic"),
        "t_critical": primary.get("t_critical"), "measurable": primary.get("measurable"),
        "case_study": primary.get("case_study"), "minimum": primary.get("minimum"),
        primary.get("verdict_field", "reading"): evidence.get("decision") or primary.get("reading"),
        "reading_taken_on": primary.get("reading_taken_on"),
    })

    out += [f"## {SECTIONS[2]}", "", "Both measures the plan declares, over the frozen cohort and over the "
            "wallets active in the window:", ""]
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
        out += ["Measured inflation against arm A, a number and never a gate:", ""]
        out += _pairs({key: inflation[key] for key in sorted(inflation)})

    out += [f"## {SECTIONS[3]}", ""]
    out += _table(("stage", "n"), sorted((evidence.get("stage_counts") or {}).items()))
    out += ["Why the freeze excluded a candidate:", ""]
    out += _table(("reason", "n"), sorted((evidence.get("per_wallet_reason") or {}).items()))
    out += ["From the frozen cohort to the primary:", ""]
    out += _table(("stage", "n"), [(key, counts[key]) for key in ("wallets", "scored", "refused", "in_primary")])
    out += ["Why a scored wallet did not enter the primary:", ""]
    out += _table(("wallet", "reason"), sorted((primary.get("excluded") or {}).items()))
    out += ["The peer pool the primary contrasted against:", ""]
    out += _pairs({key: value for key, value in sorted((evidence.get("pool") or {}).items())})

    out += [f"## {SECTIONS[4]}", ""]
    broke = evidence["what_broke"]
    out += ([f"- {item}" for item in broke] if broke else ["Nothing broke."]) + [""]
    out += ["Wallets the run refused, and why:", ""]
    out += _table(("wallet", "refusal"), sorted((evidence.get("refusals") or {}).items()))
    out += ["Diagnostics at the primary latency:", ""]
    out += _pairs({key: value for key, value in sorted((evidence.get("diagnostics_rollup") or {}).items())})

    out += [f"## {SECTIONS[5]}", "", "Mean d by latency (reported, does not decide):", ""]
    secondary = evidence.get("secondary") or {}
    out += _table(("latency_ms", "n", "mean"),
                  [(k, v["n"], v["mean"]) for k, v in sorted((secondary.get("mean_d_by_latency") or {}).items())])
    out += ["Mean return versus each baseline:", ""]
    out += _table(("baseline@latency_ms", "n", "mean"),
                  [(k, v["n"], v["mean"]) for k, v in sorted((secondary.get("mean_versus_baseline") or {}).items())])
    out += ["d by wallet:", ""]
    out += _table(("wallet", "d"), sorted((primary.get("d_by_wallet") or {}).items()))
    out += ["Price series against the window:", ""]
    out += _table(("coin", "rows", "first_ms", "last_ms", "spans_window"),
                  [(coin, d["rows"], d["first_ms"], d["last_ms"], d["spans_window"])
                   for coin, d in sorted((evidence.get("price_series_span_by_coin") or {}).items())])
    out += ["The four disclosures that travel with every result:", ""]
    out += _pairs({key: value for key, value in sorted((primary.get("disclosures") or {}).items())})
    out += ["Assumptions, as recorded:", ""]
    out += _pairs({key: _scalar(value) for key, value in sorted((evidence.get("assumptions") or {}).items())})
    out += ["Limitations, in the words the file carries:", ""]
    out += [f"- {note}" for note in evidence.get("sample_limitations_disclosure", [])] + [""]
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
    except RenderError as exc:
        log(f"l2_arm_render: refusing to render: {exc}")
        return EXIT_REFUSED
    if args.out is None:
        log(text)
    else:
        args.out.write_text(text, encoding="utf-8", newline="\n")
        log(f"l2_arm_render: wrote {args.out} from {args.evidence.name} ({digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
