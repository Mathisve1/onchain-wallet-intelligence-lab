"""The report renderer: the plan's order, the file's own numbers, nothing else.

``L2_ANALYSIS_PLAN.md`` fixes the order a completed arm is reported in, and
DEC-046 records that order as binding. These tests hold the renderer to it,
and to the harder promise in its docstring: that it copies figures and never
computes one. The evidence used is a real run's, produced by the arm A and
arm B fixtures rather than hand-written, so a change in the runner's output
shape fails here too.
"""

from __future__ import annotations

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
        # A case study says so and claims no reading, whatever the interval is.
        self.assertIn("is not a result", answer)
        self.assertIn("dry run", answer)

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
        self.assertRegex(logged[0], r"[0-9a-f]{64}")

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
        self.assertIn(str(evidence["survivorship_inflation"]["mean_d_a"]), report)


# Imported late so the module-level fixtures above stay the runners' own.
from src.live_data.storage import LiveDataStore  # noqa: E402
from tests.test_live_data_arm_a_runner import COHORT, DAY, END, POOL_ONLY, _coverage  # noqa: E402

if __name__ == "__main__":
    unittest.main()
