"""The funnel projection: exact arithmetic, the plan's minimum, and what it refuses."""

from __future__ import annotations

import inspect
import json
import math
import tempfile
import unittest
from pathlib import Path

from research.wallet_copyability.live_data_collector import funnel_projection as fp
from research.wallet_copyability.live_data_collector.cohort_pipeline_freeze import MINIMUM_EVALUABLE
from src.copyability.cohort import STAGE_NAMES, select_cohort


def record(*, discovered: int = 100, unobserved: int = 0, insufficient: int = 0, makers: int = 0,
           rebate: int = 0, scope: int = 0, minimum: int = MINIMUM_EVALUABLE, **extra) -> dict:
    """A freeze record whose funnel adds up, with the fields the projection reads."""
    directional = discovered - unobserved - insufficient - makers
    evaluable = directional - rebate - scope
    payload = {
        "stage_counts": {
            "discovered": discovered, "window_unobserved": unobserved, "insufficient_fills": insufficient,
            "probable_market_maker": makers, "prefiltered_directional": directional,
            "rebate_excluded": rebate, "scope_excluded": scope, "evaluable": evaluable,
        },
        "evaluable_count": evaluable,
        "minimum_evaluable": minimum,
        "hard_stop": evaluable < minimum,
        "t0_utc": "2026-09-19T12:00:00Z",
        "plan_commit": "1833f34",
        "attempted_sha256": "cd" * 32,
    }
    payload.update(extra)
    return payload


def direct_binomial_cdf(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p ** i * (1.0 - p) ** (n - i) for i in range(k + 1))


class ExactArithmeticTests(unittest.TestCase):
    def test_the_beta_identity_reproduces_the_summed_binomial_tail(self) -> None:
        for n, p in ((10, 0.5), (25, 0.3), (40, 0.87), (7, 0.05)):
            for k in range(n):
                with self.subTest(n=n, k=k, p=p):
                    self.assertAlmostEqual(fp.binomial_cdf(k, n, p), direct_binomial_cdf(k, n, p), places=10)

    def test_the_binomial_cdf_edges(self) -> None:
        self.assertAlmostEqual(fp.binomial_cdf(0, 10, 0.5), 0.5 ** 10, places=12)
        self.assertEqual(fp.binomial_cdf(10, 10, 0.3), 1.0)
        self.assertEqual(fp.binomial_cdf(-1, 4, 0.5), 0.0)
        self.assertEqual(fp.binomial_cdf(2, 4, 0.0), 1.0)
        self.assertEqual(fp.binomial_cdf(2, 4, 1.0), 0.0)

    def test_clopper_pearson_reproduces_the_boundary_closed_forms(self) -> None:
        lower, upper = fp.clopper_pearson(0, 10)
        self.assertEqual(lower, 0.0)
        self.assertAlmostEqual(upper, 1.0 - 0.025 ** (1 / 10), places=9)
        lower, upper = fp.clopper_pearson(10, 10)
        self.assertAlmostEqual(lower, 0.025 ** (1 / 10), places=9)
        self.assertEqual(upper, 1.0)

    def test_clopper_pearson_bounds_carry_the_exact_tail_mass(self) -> None:
        for k, n in ((33, 100), (1, 100), (99, 100), (7, 12), (0, 1), (1, 1)):
            with self.subTest(k=k, n=n):
                lower, upper = fp.clopper_pearson(k, n)
                if 0 < k < n:
                    self.assertLess(lower, k / n)
                    self.assertGreater(upper, k / n)
                if k > 0:
                    self.assertAlmostEqual(1.0 - fp.binomial_cdf(k - 1, n, lower), 0.025, places=8)
                if k < n:
                    self.assertAlmostEqual(fp.binomial_cdf(k, n, upper), 0.025, places=8)

    def test_clopper_pearson_is_monotone_in_the_count(self) -> None:
        previous = fp.clopper_pearson(0, 50)
        for k in range(1, 51):
            current = fp.clopper_pearson(k, 50)
            self.assertGreaterEqual(current[0], previous[0])
            self.assertGreaterEqual(current[1], previous[1])
            previous = current

    def test_a_judged_set_far_beyond_the_plans_scale_does_not_overflow(self) -> None:
        lower, upper = fp.clopper_pearson(2000, 5000)
        self.assertLess(lower, 0.4)
        self.assertGreater(upper, 0.4)
        self.assertAlmostEqual(fp.binomial_cdf(2000, 5000, upper), 0.025, places=6)
        # a million candidates at the continued fraction's switch point still converges under the raised
        # cap: at p = 1/2 the two halves of the distribution are exact mirror images
        n = 1_000_000
        self.assertAlmostEqual(fp.binomial_cdf(n // 2, n, 0.5) + fp.binomial_cdf(n // 2 - 1, n, 0.5), 1.0, places=9)

    def test_the_continued_fraction_says_so_when_it_does_not_converge(self) -> None:
        from unittest import mock
        from research.wallet_copyability.live_data_collector import funnel_arithmetic as fa
        with mock.patch.object(fa, "BETACF_ITERATIONS", 5), self.assertRaises(ArithmeticError) as caught:
            fa.binomial_cdf(500_000, 1_000_000, 0.5)
        self.assertIn("did not converge", str(caught.exception))

    def test_clopper_pearson_refuses_impossible_counts_and_confidence(self) -> None:
        for args in ((5, 4), (0, 0), (-1, 4)):
            with self.subTest(args=args), self.assertRaises(fp.ProjectionInputError):
                fp.clopper_pearson(*args)
        with self.assertRaises(fp.ProjectionInputError):
            fp.clopper_pearson(1, 4, 1.0)

    def test_the_beta_binomial_with_no_data_is_uniform(self) -> None:
        pmf = fp.beta_binomial_pmf(9, 0, 0)
        self.assertEqual(len(pmf), 10)
        for p in pmf:
            self.assertAlmostEqual(p, 0.1, places=12)

    def test_the_beta_binomial_sums_to_one_and_has_the_textbook_mean(self) -> None:
        for t, k, n in ((600, 33, 100), (600, 0, 100), (600, 100, 100), (25, 3, 7), (20000, 30, 100)):
            with self.subTest(t=t, k=k, n=n):
                pmf = fp.beta_binomial_pmf(t, k, n)
                self.assertAlmostEqual(sum(pmf), 1.0, places=9)
                mean = sum(y * p for y, p in enumerate(pmf))
                self.assertAlmostEqual(mean, t * (k + 1) / (n + 2), places=5)

    def test_the_hypergeometric_posterior_is_a_point_mass_when_the_sample_is_the_population(self) -> None:
        posterior = fp.hypergeometric_posterior(40, 13, 40)
        self.assertAlmostEqual(posterior[13], 1.0, places=12)
        self.assertAlmostEqual(sum(posterior), 1.0, places=12)

    def test_the_hypergeometric_posterior_never_puts_mass_where_the_sample_forbids_it(self) -> None:
        posterior = fp.hypergeometric_posterior(100, 30, 600)
        self.assertEqual(sum(posterior[:30]), 0.0)
        self.assertEqual(sum(posterior[600 - 70 + 1:]), 0.0)
        self.assertAlmostEqual(sum(posterior), 1.0, places=9)
        mean = sum(j * p for j, p in enumerate(posterior))
        self.assertGreater(mean, 170)
        self.assertLess(mean, 190)

    def test_a_population_far_beyond_the_plans_scale_does_not_overflow(self) -> None:
        posterior = fp.hypergeometric_posterior(600, 200, 5000)
        self.assertAlmostEqual(sum(posterior), 1.0, places=9)
        mean = sum(j * p for j, p in enumerate(posterior))
        self.assertAlmostEqual(mean / 5000, 200 / 600, delta=0.02)

    def test_the_hypergeometric_posterior_refuses_impossible_counts(self) -> None:
        with self.assertRaises(fp.ProjectionInputError):
            fp.hypergeometric_posterior(100, 30, 50)

    def test_central_interval_is_equal_tailed_and_the_tail_sums(self) -> None:
        pmf = [0.01, 0.02, 0.07, 0.4, 0.4, 0.07, 0.02, 0.01]
        self.assertEqual(fp.central_interval(pmf, 0.95), (1, 6))
        self.assertEqual(fp.central_interval(pmf, 0.90), (2, 5))
        self.assertAlmostEqual(fp.tail_at_least(pmf, 4), 0.5, places=12)
        self.assertEqual(fp.tail_at_least(pmf, 8), 0.0)

    def test_candidates_needed_is_the_smallest_size_that_reaches_the_chance(self) -> None:
        k, n, minimum = 30, 100, 200
        for chance in fp.CHANCES:
            with self.subTest(chance=chance):
                needed = fp.candidates_for_chance(k, n, minimum, chance)
                self.assertIsNotNone(needed)
                assert needed is not None
                self.assertGreaterEqual(needed, minimum)
                self.assertLessEqual(needed, fp.SEARCH_CAP)
                self.assertGreaterEqual(fp.tail_at_least(fp.beta_binomial_pmf(needed, k, n), minimum), chance)
                self.assertLess(fp.tail_at_least(fp.beta_binomial_pmf(needed - 1, k, n), minimum), chance)
        needs = [fp.candidates_for_chance(k, n, minimum, c) for c in fp.CHANCES]
        self.assertEqual(needs, sorted(needs))

    def test_candidates_needed_is_none_beyond_the_cap(self) -> None:
        self.assertIsNone(fp.candidates_for_chance(0, 100_000, 200, 0.9))
        self.assertIsNone(fp.candidates_for_chance(30, 100, fp.SEARCH_CAP + 1, 0.5))


class CountReadingTests(unittest.TestCase):
    def test_a_count_that_is_not_a_whole_number_is_refused_by_name(self) -> None:
        for value in ("thirty", None, 30.9, True, [30], {"n": 30}):
            with self.subTest(value=value), self.assertRaises(fp.ProjectionInputError) as caught:
                fp.project(record(evaluable_count=value))
            self.assertIn("evaluable_count", str(caught.exception))

    def test_a_negative_count_is_refused(self) -> None:
        with self.assertRaises(fp.ProjectionInputError) as caught:
            fp.funnel_rows({"discovered": 100, "window_unobserved": -5})
        self.assertIn("cannot be negative", str(caught.exception))

    def test_exclusions_larger_than_the_discovered_set_are_refused(self) -> None:
        with self.assertRaises(fp.ProjectionInputError) as caught:
            fp.funnel_rows({"discovered": 10, "insufficient_fills": 8, "scope_excluded": 5})
        self.assertIn("more than the 10 discovered", str(caught.exception))

    def test_a_record_without_the_counts_is_refused_with_a_sentence(self) -> None:
        for payload in ({"evaluable_count": 1}, {"stage_counts": [], "evaluable_count": 1},
                        {"stage_counts": {"evaluable": 1}, "evaluable_count": 1}):
            with self.subTest(payload=payload), self.assertRaises(fp.ProjectionInputError):
                fp.project(payload)

    def test_more_evaluable_than_judged_is_refused(self) -> None:
        payload = record(discovered=10)
        payload["evaluable_count"] = 11
        with self.assertRaises(fp.ProjectionInputError):
            fp.project(payload)

    def test_a_freeze_that_judged_nothing_is_refused(self) -> None:
        with self.assertRaises(fp.ProjectionInputError):
            fp.project({"stage_counts": {"discovered": 0}, "evaluable_count": 0})


class FunnelTests(unittest.TestCase):
    def test_the_funnel_names_every_stage_the_cohort_module_counts(self) -> None:
        # STAGE_NAMES is the record's declaration order; the funnel is select_cohort's application
        # order (window, classifier, rebate, scope), which this module states itself.
        stages = [stage for stage, _ in fp.EXCLUSION_STAGES]
        self.assertEqual(set(stages) | {"discovered", "prefiltered_directional", "evaluable"}, set(STAGE_NAMES))
        self.assertEqual(stages[:3], list(fp.CLASSIFIER_STAGES))

    def test_the_funnel_order_is_the_order_select_cohort_increments_its_counts(self) -> None:
        # The application order is read off select_cohort's own source: the position at which each
        # stage's counter is incremented. A reordering of the filters would move those lines.
        source = inspect.getsource(select_cohort)
        positions = [source.index(f'counts["{stage}"] += 1') for stage, _ in fp.EXCLUSION_STAGES]
        self.assertEqual(positions, sorted(positions), [stage for stage, _ in fp.EXCLUSION_STAGES])

    def test_survivors_chain_through_every_stage(self) -> None:
        rows, warnings = fp.funnel_rows(record(discovered=100, unobserved=5, insufficient=20, makers=15,
                                               rebate=10, scope=20)["stage_counts"])
        self.assertEqual(warnings, [])
        self.assertEqual([r["remaining"] for r in rows], [95, 75, 60, 50, 30])
        self.assertEqual(rows[1]["share_of_discovered"], 0.2)

    def test_counts_that_do_not_add_up_are_refused(self) -> None:
        counts = record(discovered=100, insufficient=20)["stage_counts"]
        counts["prefiltered_directional"] = 79
        with self.assertRaises(fp.ProjectionInputError) as caught:
            fp.funnel_rows(counts)
        self.assertIn("prefiltered_directional is 79", str(caught.exception))
        counts = record(discovered=100, insufficient=20)["stage_counts"]
        counts["evaluable"] = 70
        with self.assertRaises(fp.ProjectionInputError):
            fp.funnel_rows(counts)

    def test_an_evaluable_count_that_contradicts_the_funnel_is_refused_even_without_the_key(self) -> None:
        payload = record(discovered=100, insufficient=20)
        payload["evaluable_count"] = 12
        del payload["stage_counts"]["evaluable"]
        payload["hard_stop"] = True
        with self.assertRaises(fp.ProjectionInputError) as caught:
            fp.project(payload)
        self.assertIn("the funnel leaves 80", str(caught.exception))

    def test_a_hard_stop_flag_that_contradicts_the_counts_is_refused(self) -> None:
        payload = record(discovered=100)  # 100 evaluable under a minimum of 200: hard_stop must be True
        payload["hard_stop"] = False
        with self.assertRaises(fp.ProjectionInputError) as caught:
            fp.project(payload)
        self.assertIn("hard_stop is False", str(caught.exception))


class PlanMinimumTests(unittest.TestCase):
    def test_the_plan_minimum_is_the_freeze_modules_own_constant(self) -> None:
        self.assertEqual(fp.PLAN_MINIMUM_EVALUABLE, MINIMUM_EVALUABLE)
        self.assertEqual(fp.PLAN_MINIMUM_EVALUABLE, 200)

    def test_a_record_made_under_the_plans_minimum_is_refused(self) -> None:
        with self.assertRaises(fp.ProjectionInputError) as caught:
            fp.project(record(discovered=50, minimum=120))
        self.assertIn("under the plan's 200", str(caught.exception))

    def test_such_a_record_is_projected_against_the_plans_minimum_with_the_flag(self) -> None:
        projection = fp.project(record(discovered=50, minimum=120), allow_underpowered=True)
        self.assertEqual(projection["inputs"]["minimum"], 200)
        self.assertTrue(any("under the plan's 200" in w for w in projection["warnings"]))

    def test_a_minimum_below_the_plans_is_refused_and_one_above_is_warned_about(self) -> None:
        with self.assertRaises(fp.ProjectionInputError) as caught:
            fp.project(record(discovered=100), minimum=100)
        self.assertIn("not this projection's to lower", str(caught.exception))
        projection = fp.project(record(discovered=100), minimum=250)
        self.assertEqual(projection["inputs"]["minimum"], 250)
        self.assertTrue(any("above the plan's" in w for w in projection["warnings"]))
        self.assertIn("Projected against a minimum of 250 (the plan's is 200)", fp.render(projection))

    def test_a_record_made_with_a_minimum_above_the_plans_is_named_not_adopted_silently(self) -> None:
        projection = fp.project(record(discovered=100, minimum=300))
        self.assertEqual(projection["inputs"]["minimum"], 300)
        self.assertTrue(any("above the plan's 200; projected against 300" in w for w in projection["warnings"]))

    def test_a_record_at_or_above_the_projected_minimum_says_there_is_nothing_to_project_towards(self) -> None:
        reached = record(discovered=250)  # 250 evaluable, hard_stop False by the helper
        self.assertTrue(any("nothing to project towards" in w for w in fp.project(reached)["warnings"]))
        # the flag alone is not enough: an underpowered record that passed its own bar is still under the plan's
        under = record(discovered=200, insufficient=50, minimum=120)  # 150 evaluable, hard_stop False
        projection = fp.project(under, allow_underpowered=True)
        self.assertFalse(any("nothing to project towards" in w for w in projection["warnings"]))
        self.assertIsNotNone(projection["candidates_needed"]["50_percent"])

    def test_a_target_other_than_the_plans_is_labelled_and_warned_about(self) -> None:
        projection = fp.project(record(discovered=100, insufficient=60), target=1000)
        self.assertEqual(projection["fresh_discovery"][0]["label"], "--target 1000")
        self.assertTrue(any("projected at --target 1000" in w for w in projection["warnings"]))
        self.assertEqual(fp.project(record(discovered=100, insufficient=60))["fresh_discovery"][0]["label"],
                         "the plan's target")


class ProjectionTests(unittest.TestCase):
    def test_the_projection_carries_every_reading_with_traceable_inputs(self) -> None:
        payload = record(discovered=100, unobserved=5, insufficient=20, makers=15, rebate=10, scope=20)
        projection = fp.project(payload, discovery={"candidate_count": 600, "target": 600}, source="REP_FREEZE.json")
        self.assertEqual(projection["inputs"],
                         {"characterised": 100, "evaluable": 30, "minimum": 200, "confidence": 0.95})
        self.assertAlmostEqual(projection["evaluable_share"]["estimate"], 0.3)
        self.assertEqual(projection["source"]["plan_commit"], "1833f34")
        self.assertEqual(projection["source"]["file"], "REP_FREEZE.json")
        self.assertTrue(projection["source"]["hard_stop"])
        self.assertIn("decides nothing", projection["kind"])
        reading = projection["fresh_discovery"][0]
        self.assertEqual(reading["candidates"], 600)
        self.assertAlmostEqual(reading["posterior_mean_evaluable"], 600 * 31 / 102)
        self.assertAlmostEqual(reading["plug_in_evaluable"], 180.0)
        self.assertLess(reading["interval"][0], 180)
        self.assertGreater(reading["interval"][1], 180)
        self.assertGreater(reading["chance_of_minimum"], 0.0)
        self.assertLess(reading["chance_of_minimum"], 0.5)
        self.assertEqual(set(projection["candidates_needed"]), {"50_percent", "80_percent", "90_percent"})
        self.assertEqual(projection["largest_losses"], ["insufficient_fills", "scope_excluded"])  # 20 each
        self.assertEqual(projection["plan"], {"minimum": 200, "discovery_target": 600})
        self.assertEqual(projection["search_cap"], fp.SEARCH_CAP)

    def test_a_discovery_short_of_the_target_is_read_as_a_second_reading(self) -> None:
        projection = fp.project(record(discovered=100, insufficient=60),
                                discovery={"candidate_count": 480, "target": 600})
        labels = [r["label"] for r in projection["fresh_discovery"]]
        self.assertEqual(labels, ["the plan's target", "the rehearsal's own yield"])
        first, second = projection["fresh_discovery"]
        self.assertEqual((first["candidates"], second["candidates"]), (600, 480))
        self.assertLess(second["chance_of_minimum"], first["chance_of_minimum"])

    def test_all_evaluable_projects_above_the_minimum(self) -> None:
        projection = fp.project(record(discovered=100))
        self.assertGreater(projection["fresh_discovery"][0]["chance_of_minimum"], 0.99)
        self.assertIsNone(projection["rehearsal_set"])
        self.assertEqual(projection["largest_losses"], [])

    def test_tied_largest_losses_are_all_named(self) -> None:
        projection = fp.project(record(discovered=100, rebate=20, scope=20))
        self.assertEqual(projection["largest_losses"], ["rebate_excluded", "scope_excluded"])
        self.assertIn("The largest losses are `rebate_excluded` and `scope_excluded`, tied.", fp.render(projection))

    def test_the_fresh_reading_states_the_representativeness_it_rests_on(self) -> None:
        projection = fp.project(record(discovered=100, insufficient=70), discovery={"candidate_count": 600})
        self.assertTrue(any("representative of what a discovery yields" in a for a in projection["assumptions"]))
        self.assertTrue(any("here unstated" in w for w in projection["warnings"]))

    def test_the_own_set_reading_needs_the_callers_word_that_the_sample_was_random(self) -> None:
        payload = record(discovered=100, insufficient=70)
        projection = fp.project(payload, discovery={"candidate_count": 600})
        self.assertIsNone(projection["rehearsal_set"])
        self.assertTrue(any("--sampled-at-random" in w for w in projection["warnings"]))
        projection = fp.project(payload, discovery={"candidate_count": 600}, sampled_at_random=True)
        own = projection["rehearsal_set"]
        self.assertFalse(own["degenerate"])
        self.assertEqual((own["discovered"], own["sampled"]), (600, 100))
        self.assertTrue(any("drawn from the discovered set at random" in a for a in projection["assumptions"]))

    def test_a_freeze_over_the_whole_discovered_set_infers_nothing(self) -> None:
        projection = fp.project(record(discovered=100, insufficient=70), discovery={"candidate_count": 100})
        own = projection["rehearsal_set"]
        self.assertTrue(own["degenerate"])
        self.assertIn("nothing is inferred", own["note"])
        self.assertNotIn("chance_of_minimum", own)

    def test_a_discovery_smaller_than_the_judged_set_skips_the_own_set_reading(self) -> None:
        projection = fp.project(record(discovered=100, insufficient=50), discovery={"candidate_count": 40})
        self.assertIsNone(projection["rehearsal_set"])
        self.assertTrue(any("did not sample that discovery" in w for w in projection["warnings"]))

    def test_an_empty_or_malformed_discovery_is_refused(self) -> None:
        for discovery in ({"candidate_count": 0}, {"candidate_count": "600"}, {"target": 600}):
            with self.subTest(discovery=discovery), self.assertRaises(fp.ProjectionInputError):
                fp.project(record(discovered=100), discovery=discovery)

    def test_bad_confidence_or_target_is_refused(self) -> None:
        for kwargs in ({"confidence": 1.0}, {"confidence": 0.0}, {"target": 0}, {"target": -5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(fp.ProjectionInputError):
                fp.project(record(discovered=10), **kwargs)


class RenderingTests(unittest.TestCase):
    def text(self, **kwargs) -> str:
        payload = kwargs.pop("payload", record(discovered=100, insufficient=40, scope=30))
        return fp.render(fp.project(payload, **kwargs))

    def test_a_needed_count_past_the_cap_prints_the_cap(self) -> None:
        projection = fp.project(record(discovered=100, insufficient=100))  # nothing evaluable
        self.assertIn("more than 100000 (the search cap)", fp.render(projection))

    def test_the_rendering_names_the_readings_and_the_source(self) -> None:
        text = self.text(discovery={"candidate_count": 600}, sampled_at_random=True, source="REP_FREEZE.json")
        for phrase in ("# Funnel projection from a freeze record", "not an evidence file", "decides nothing",
                       "freeze REP_FREEZE.json", "plan commit `1833f34`", "## The funnel, in selection order",
                       "## What a fresh discovery at T0 gives", "| the plan's target | 600 |",
                       "## The rehearsal's own discovered set", "## What this assumes",
                       "| insufficient_fills | 40 |", "chance of 200"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_the_plans_discovery_target_is_stated_beside_the_needed_candidates(self) -> None:
        self.assertIn("The plan discovers up to 600 candidates.", self.text())
        self.assertIn("not a number this projection authorises", self.text())

    def test_the_confidence_level_is_printed_as_given(self) -> None:
        self.assertIn("exact 99.9 % interval", self.text(confidence=0.999))
        self.assertIn("exact 95 % interval", self.text())

    def test_warnings_are_rendered_where_the_owner_will_see_them(self) -> None:
        self.assertIn("## Warnings", fp.render(fp.project(record(discovered=250))))


class CommandLineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def write(self, name: str, payload) -> Path:
        path = self.root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_the_command_writes_json_and_markdown(self) -> None:
        freeze = self.write("REP_FREEZE.json", record(discovered=100, insufficient=40, scope=25))
        discovery = self.write("REP_DISCOVERY.json", {"candidate_count": 580, "target": 600})
        out, md = self.root / "projection.json", self.root / "projection.md"
        logged: list[str] = []
        code = fp.main(["--freeze", str(freeze), "--discovery", str(discovery), "--sampled-at-random",
                        "--out", str(out), "--markdown", str(md)], log=logged.append)
        self.assertEqual(code, 0, logged)
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(payload["inputs"]["characterised"], 100)
        self.assertEqual(payload["source"]["file"], "REP_FREEZE.json")
        self.assertEqual(payload["rehearsal_set"]["discovered"], 580)
        self.assertIn("# Funnel projection", md.read_text(encoding="utf-8"))
        self.assertNotIn(b"\r", md.read_bytes())
        self.assertNotIn(b"\r", out.read_bytes())
        self.assertIn("# Funnel projection", logged[0])
        self.assertEqual(len(logged), 1)

    def test_a_missing_or_wrong_file_is_refused_with_exit_2(self) -> None:
        logged: list[str] = []
        self.assertEqual(fp.main(["--freeze", str(self.root / "absent.json")], log=logged.append), 2)
        self.assertIn("refusing", logged[0])
        wrong = self.write("wrong.json", {"candidates": []})
        self.assertEqual(fp.main(["--freeze", str(wrong)], log=logged.append), 2)
        self.assertIn("stage_counts", logged[-1])
        not_json = self.root / "broken.json"
        not_json.write_text("{oops", encoding="utf-8")
        self.assertEqual(fp.main(["--freeze", str(not_json)], log=logged.append), 2)
        self.assertIn("not readable JSON", logged[-1])
        a_list = self.write("list.json", [1, 2])
        self.assertEqual(fp.main(["--freeze", str(a_list)], log=logged.append), 2)

    def test_a_malformed_count_is_a_sentence_not_a_traceback(self) -> None:
        for value in ("thirty", None, 30.5, True):
            with self.subTest(value=value):
                freeze = self.write("f.json", record(discovered=100, evaluable_count=value))
                logged: list[str] = []
                self.assertEqual(fp.main(["--freeze", str(freeze)], log=logged.append), 2)
                self.assertIn("refusing", logged[0])
                self.assertIn("evaluable_count", logged[0])

    def test_an_unwritable_output_path_is_refused_with_exit_2(self) -> None:
        freeze = self.write("REP_FREEZE.json", record(discovered=100, insufficient=40))
        logged: list[str] = []
        code = fp.main(["--freeze", str(freeze), "--markdown", str(self.root / "nope" / "p.md")], log=logged.append)
        self.assertEqual(code, 2)
        self.assertIn("cannot write", logged[0])

    def test_a_record_under_the_plans_minimum_needs_the_flag_at_the_command_line(self) -> None:
        freeze = self.write("REP_FREEZE.json", record(discovered=100, insufficient=40, minimum=120))
        logged: list[str] = []
        self.assertEqual(fp.main(["--freeze", str(freeze)], log=logged.append), 2)
        self.assertIn("--allow-underpowered-dry-run", logged[0])
        self.assertEqual(fp.main(["--freeze", str(freeze), "--allow-underpowered-dry-run"], log=logged.append), 0)
        self.assertIn("Projected against a minimum of 200.", logged[-1])

    def test_a_file_with_a_byte_order_mark_is_read(self) -> None:
        freeze = self.write("REP_FREEZE.json", record(discovered=100, insufficient=40))
        freeze.write_bytes(b"\xef\xbb\xbf" + freeze.read_bytes())
        logged: list[str] = []
        self.assertEqual(fp.main(["--freeze", str(freeze)], log=logged.append), 0, logged)


if __name__ == "__main__":
    unittest.main()
