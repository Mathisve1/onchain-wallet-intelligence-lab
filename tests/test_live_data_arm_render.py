"""The report renderer: the plan's order, the file's own numbers, nothing else.

``L2_ANALYSIS_PLAN.md`` fixes the order a completed arm is reported in, and
DEC-046 records that order as binding. These tests hold the renderer to it,
and to the harder promise in its docstring: that it copies figures and never
computes one. The evidence used is a real run's, produced by the arm A and
arm B fixtures rather than hand-written, so a change in the runner's output
shape fails here too.
"""

from __future__ import annotations

import hashlib
import json
import re
import unittest

from research.wallet_copyability.live_data_collector import l2_arm_render as render_module
from research.wallet_copyability.live_data_collector.l2_arm_render import (
    SECTIONS,
    RenderError,
    load_evidence,
    render,
)
from tests.test_live_data_arm_a_runner import ArmARunnerStoreTestCase, patched_minimum
from tests.test_live_data_arm_b_runner import ArmBStoreTestCase


def headings(report: str) -> list[str]:
    return [line[3:].strip() for line in report.splitlines() if line.startswith("## ")]


def numbers(text: str) -> set[str]:
    """Every numeric literal in the text, as written."""
    return set(re.findall(r"-?\d+\.\d+|-?\d+", text))


def sentences(text: str) -> int:
    """How many sentences a passage is, ignoring decimal points."""
    return 1 + len(re.findall(r"\.\s+[A-Z(]", text.strip()))


class ArmAReportTests(ArmARunnerStoreTestCase):
    def report_for(self, evidence: dict) -> str:
        return render(evidence, evidence_sha256="0" * 64)

    def test_the_sections_are_the_plans_order(self) -> None:
        report = self.report_for(self.run_ok())
        self.assertEqual(headings(report), list(SECTIONS))
        # The order is the point: the answer cannot follow the tables.
        self.assertLess(report.index("## The answer"), report.index("## The confidence interval"))
        self.assertLess(report.index("## Survivorship"), report.index("## n after every filter stage"))
        self.assertLess(report.index("## What broke"), report.index("## Tables"))

    def test_it_states_no_number_the_evidence_does_not_carry(self) -> None:
        evidence = self.run_ok()
        report = self.report_for(evidence)
        in_file = numbers(json.dumps(evidence)) | numbers(str(evidence))
        # 95 is the interval's confidence level and 14 the unit's own name;
        # 046 is the decision that fixed this report order. Those three are
        # the plan's. The digest is this test's own input. Every other number
        # in the report must come from the evidence file.
        allowed = in_file | numbers("DEC-046 95 percent 14-day") | numbers("0" * 64)
        self.assertEqual(numbers(report) - allowed, set())

    def test_the_answer_is_one_sentence_and_follows_the_files_own_labels(self) -> None:
        evidence = self.run_ok()
        answer = render_module.answer(evidence)
        self.assertEqual(sentences(answer), 1, answer)
        # A dry run says so and claims no reading, whatever the interval is.
        self.assertIn("is not a result", answer)
        self.assertIn("DRY_RUN_UNDERPOWERED", answer)

    def test_over_the_minimum_the_answer_is_the_reading_the_file_carries(self) -> None:
        with patched_minimum(3):
            evidence = self.run_ok()
        answer = render_module.answer(evidence)
        self.assertIn(evidence["primary"]["reading"].split("_")[-1].lower(), answer.lower())
        self.assertIn("arm A decides nothing", answer)
        self.assertEqual(sentences(answer), 1, answer)

    def test_the_report_carries_every_figure_the_plan_names(self) -> None:
        evidence = self.run_ok()
        report = self.report_for(evidence)
        surv = evidence["survivorship"]
        for value in (str(evidence["primary"]["n"]), surv["stopped_share_of_cohort"],
                      surv["faded_share_of_cohort"], str(evidence["counts"]["refused"]),
                      str(evidence["stage_counts"]["discovered"]), evidence["cohort_sha256"]):
            with self.subTest(value=value):
                self.assertIn(value, report)
        for note in evidence["sample_limitations_disclosure"]:
            self.assertIn(note, report)

    def case_study(self) -> dict:
        """A real case study: enough wallets to run, too few in the primary."""
        with LiveDataStore(self.db) as store:
            store.connection.execute(
                "DELETE FROM fills WHERE wallet_address = ? AND event_time_ms >= ?", (COHORT[2], START)
            )
            store.connection.commit()
        with patched_minimum(3):
            # The freeze's own minimum has to match, or the run refuses before
            # it starts: the record's minimum is not the runner's to lower.
            record = self.write_record({**self.record(COHORT), "minimum_evaluable": 3})
            code, logged = self.run_main(self.argv(cohort=record, dry_run=False))
            self.assertEqual(code, 0, logged)
            return json.loads(self.out.read_text(encoding="utf-8"))

    def test_a_case_study_is_never_rendered_as_a_reading(self) -> None:
        evidence = self.case_study()
        self.assertEqual(evidence["empirical_result_status"], "CASE_STUDY_UNDER_MINIMUM")
        answer = render_module.answer(evidence)
        self.assertIn("is a case study and decides nothing", answer)
        for label in ("ARM_A_NEGATIVE", "ARM_A_POSITIVE", "ARM_A_INCONCLUSIVE"):
            self.assertNotIn(label, answer)
        self.assertEqual(sentences(answer), 1, answer)

    def test_a_broken_run_withholds_its_verdict_row(self) -> None:
        evidence = self.run_ok()
        evidence["what_broke"] = ["the benchmark went missing"]
        evidence["empirical_result_status"] = "BROKE_SEE_WHAT_BROKE"
        evidence["primary"]["reading"] = "ARM_A_NEGATIVE"
        report = self.report_for(evidence)
        # The answer says no reading was produced; the interval table must not
        # then print one two lines below it.
        self.assertNotIn("ARM_A_NEGATIVE", report)
        self.assertIn("withheld", report)

    def test_the_filter_stages_are_rendered_row_by_row(self) -> None:
        evidence = self.run_ok()
        report = self.report_for(evidence)
        for stage, n in evidence["stage_counts"].items():
            with self.subTest(stage=stage):
                self.assertIn(f"| {stage} | {n} |", report)
        for reason, n in evidence["per_wallet_reason"].items():
            with self.subTest(reason=reason):
                self.assertIn(f"| {reason} | {n} |", report)
        for stage in ("wallets", "scored", "refused", "in_primary"):
            self.assertIn(f"| {stage} | {evidence['counts'][stage]} |", report)

    def test_the_scope_stage_is_reported_because_it_removes_fills(self) -> None:
        # A coin out of scope takes the wallet's fills with it, and the plan
        # requires those counted per wallet.
        with LiveDataStore(self.db) as store:
            store.write_fills([_fill(COHORT[0], 9_931, START + 4 * DAY, coin="LINK"),
                               _fill(COHORT[0], 9_932, START + 5 * DAY, coin="LINK")],
                              source="test", ingested_at_ms=T0)
        evidence = self.run_ok()
        report = self.report_for(evidence)
        self.assertEqual(evidence["scope"]["out_of_scope_fills_by_wallet"], {COHORT[0]: 2})
        self.assertIn(f"| {COHORT[0]} | 2 |", report)
        self.assertIn(evidence["scope"]["out_of_scope_definition"], report)
        self.assertIn(evidence["scope"]["deviation_from_plan_wording"], report)
        self.assertIn("coins_evaluated", report)

    def test_the_interval_is_rendered_low_bound_first_and_labelled(self) -> None:
        evidence = self.run_ok()
        report = self.report_for(evidence)
        lower, upper = evidence["primary"]["ci95"]
        self.assertLess(lower, upper)
        self.assertIn(f"| ci95 lower | {lower} |", report)
        self.assertIn(f"| ci95 upper | {upper} |", report)

    def test_the_report_carries_every_disclosure_and_the_reading_rule(self) -> None:
        evidence = self.run_ok()
        report = self.report_for(evidence)
        for key, value in evidence["primary"]["disclosures"].items():
            with self.subTest(key=key):
                self.assertIn(f"| {key} | {value} |", report)
        self.assertIn(f"Reading rule: {evidence['reading_rule']}", report)
        self.assertIn("EXPLORATORY", report)  # the label the plan fixes for every non-primary cut
        self.assertIn("no result leaves this repository before both windows close", report)
        self.assertIn("No copyability claim is produced", report)

    def test_the_survivorship_denominators_are_labelled_by_what_they_count(self) -> None:
        evidence = self.case_study()  # one wallet idle, so the denominators differ
        surv = evidence["survivorship"]
        self.assertNotEqual(surv["stopped_share_of_cohort"], surv["stopped_share_of_active"])
        report = self.report_for(evidence)
        for key in ("cohort", "active_in_window", "stopped", "stopped_share_of_cohort",
                    "stopped_share_of_active", "faded", "faded_judged", "faded_share_of_cohort",
                    "faded_share_of_judged"):
            with self.subTest(key=key):
                self.assertIn(f"| {key} | {surv[key]} |", report)
        for definition in surv["definition"].values():
            self.assertIn(definition, report)

    def test_the_price_provenance_is_in_the_report(self) -> None:
        evidence = self.run_ok()
        report = self.report_for(evidence)
        self.assertIn("Where the prices came from", report)
        self.assertIn("ingested_by_coin", report)

    def test_a_verdict_the_printed_interval_does_not_support_is_refused(self) -> None:
        evidence = self.run_ok()
        with patched_minimum(3):
            evidence = self.run_ok()
        self.assertEqual(evidence["primary"]["reading"], "ARM_A_NEGATIVE")
        evidence["primary"]["reading"] = "ARM_A_POSITIVE"
        with self.assertRaises(RenderError) as caught:
            self.report_for(evidence)
        self.assertIn("is not what the plan's rule gives", str(caught.exception))

    def test_a_lowered_target_is_refused_rather_than_reported(self) -> None:
        evidence = self.run_ok()
        evidence["primary"]["target"] = "0.35"
        with self.assertRaises(RenderError) as caught:
            self.report_for(evidence)
        self.assertIn("excludes any lowering of the target", str(caught.exception))

    def test_an_arm_carrying_the_other_arms_verdict_is_refused(self) -> None:
        evidence = self.run_ok()
        evidence["decision"] = "GO_TO_ENTITY_CLUSTER_RESEARCH"
        with self.assertRaises(RenderError) as caught:
            self.report_for(evidence)
        self.assertIn("arm A decides nothing", str(caught.exception))

    def test_a_status_this_report_does_not_know_is_refused(self) -> None:
        evidence = self.run_ok()
        evidence["empirical_result_status"] = "ARM_A_DEFINITELY_TRADEABLE"
        path = self.root / "future.json"
        path.write_text(json.dumps(evidence), encoding="utf-8")
        with self.assertRaises(RenderError) as caught:
            load_evidence(path)
        self.assertIn("not one this report knows how to state", str(caught.exception))

    def test_a_file_without_its_disclosures_is_refused(self) -> None:
        evidence = self.run_ok()
        evidence["sample_limitations_disclosure"] = []
        path = self.root / "bare.json"
        path.write_text(json.dumps(evidence), encoding="utf-8")
        with self.assertRaises(RenderError) as caught:
            load_evidence(path)
        self.assertIn("would read as more complete than the run", str(caught.exception))

    def test_every_required_key_is_actually_required(self) -> None:
        evidence = self.run_ok()
        path = self.root / "trimmed.json"
        for key in render_module.REQUIRED_KEYS:
            with self.subTest(key=key):
                path.write_text(json.dumps({k: v for k, v in evidence.items() if k != key}), encoding="utf-8")
                with self.assertRaises(RenderError):
                    load_evidence(path)

    def test_a_pipe_or_a_newline_in_a_reason_cannot_hide_it(self) -> None:
        evidence = self.run_ok()
        evidence["refusals"] = {COHORT[0]: "UnknownIntervalError: a | b\nand the rest"}
        report = self.report_for(evidence)
        row = next(line for line in report.splitlines() if COHORT[0] in line and "UnknownInterval" in line)
        self.assertIn("a \\| b and the rest", row)
        self.assertEqual(report.count("and the rest"), 1)

    def test_two_renders_of_one_file_are_identical(self) -> None:
        evidence = self.run_ok()
        self.assertEqual(self.report_for(evidence), self.report_for(evidence))

    def test_a_checkpoint_is_refused_because_the_arm_is_not_complete(self) -> None:
        self.run_ok()
        partial = self.root / "partial.json"
        partial.write_text(json.dumps({"checkpoint": True, "run_id": "L2-ARM-A-001", "completed": 2}),
                           encoding="utf-8")
        with self.assertRaises(RenderError) as caught:
            load_evidence(partial)
        self.assertIn("only when the arm is complete", str(caught.exception))

    def test_an_incomplete_file_names_what_it_lacks(self) -> None:
        evidence = self.run_ok()
        del evidence["survivorship"]
        path = self.root / "trimmed.json"
        path.write_text(json.dumps(evidence), encoding="utf-8")
        with self.assertRaises(RenderError) as caught:
            load_evidence(path)
        self.assertIn("survivorship", str(caught.exception))

    def test_the_cli_writes_the_report_and_names_the_file_it_read(self) -> None:
        self.run_ok()
        out = self.root / "report.md"
        logged: list[str] = []
        self.assertEqual(render_module.main(["--evidence", str(self.out), "--out", str(out)], log=logged.append), 0)
        self.assertEqual(headings(out.read_text(encoding="utf-8")), list(SECTIONS))
        self.assertIn(self.out.name, logged[0])
        digest = hashlib.sha256(self.out.read_bytes()).hexdigest()
        self.assertIn(digest, logged[0])
        # The digest binds the report to the file it was rendered from.
        self.assertIn(f"| evidence_sha256 | {digest} |", out.read_text(encoding="utf-8"))

    def test_the_cli_refuses_a_file_that_is_not_evidence(self) -> None:
        junk = self.root / "junk.json"
        junk.write_text("[1, 2, 3]", encoding="utf-8")
        logged: list[str] = []
        self.assertEqual(render_module.main(["--evidence", str(junk)], log=logged.append), 2)
        self.assertIn("refusing to render", logged[0])

    def test_a_broken_run_reports_that_it_decided_nothing(self) -> None:
        with LiveDataStore(self.db) as store:
            store.connection.execute("DELETE FROM ingest_runs WHERE mode = 'backfill_wallet'")
            store.connection.commit()
            for index, wallet in enumerate(COHORT + POOL_ONLY):
                _coverage(store, f"short-{index}", wallet, covered_until_ms=END - DAY)
        self.refreeze()
        self.run_main()
        evidence = json.loads(self.out.read_text(encoding="utf-8"))
        answer = render_module.answer(evidence)
        self.assertIn("produced no reading", answer)
        self.assertIn("nothing in this report decides anything", answer)
        self.assertEqual(sentences(answer), 1, answer)


class ArmBReportTests(ArmBStoreTestCase):
    def test_arm_bs_answer_is_its_decision_never_an_arm_a_label(self) -> None:
        from src.copyability.cohort import cohort_hash
        from tests.test_live_data_arm_b_runner import COHORT, PLAN
        from tests.test_live_data_arm_b_runner import patched_minimum as patched_b

        arm_a = self.root / "L2_ARM_A_001.json"
        arm_a.write_text(json.dumps({
            "arm": "A", "cohort_sha256": cohort_hash(sorted(w.lower() for w in COHORT)), "plan_commit": PLAN,
            "empirical_result_status": "ARM_A_EARLY_READ_ONLY",
            "primary": {"mean": 0.9, "reading": "ARM_A_NEGATIVE"},
        }), encoding="utf-8")
        with patched_b(3):
            code, logged = self.run_main(self.argv(arm_a=arm_a))
        self.assertEqual(code, 0, logged)
        evidence = json.loads(self.out.read_text(encoding="utf-8"))
        answer = render_module.answer(evidence)
        self.assertIn(evidence["decision"], answer)
        self.assertNotIn("ARM_A_", answer)
        report = render(evidence, evidence_sha256="0" * 64)
        self.assertEqual(headings(report), list(SECTIONS))
        # The survivorship section carries the inflation, as a number.
        self.assertIn("inflation_points_per_14d", report)
        inflation = evidence["survivorship_inflation"]
        self.assertIn(str(inflation["mean_d_a"]), report)
        # The plan names the A-negative/B-GO case explicitly, never silently.
        self.assertIn(f"| a_negative_b_positive | {str(inflation['a_negative_b_positive']).lower()} |", report)
        self.assertIn(inflation["note"], report)
        self.assertIn("Measured survivorship inflation", report)
        # Arm B says on what basis its window was declared closed.
        self.assertIn("on what basis the window was declared closed", report)
        self.assertIn("closing_grace_days", report)


# Imported late so the module-level fixtures above stay the runners' own.
from src.live_data.storage import LiveDataStore  # noqa: E402
from tests.test_live_data_arm_a_runner import (  # noqa: E402
    COHORT,
    DAY,
    END,
    POOL_ONLY,
    START,
    T0,
    _coverage,
    _fill,
)

if __name__ == "__main__":
    unittest.main()
