from __future__ import annotations

import copy
import subprocess
import sys
import unittest

from governance import validate_r10d_backward_consistency as validator


class R10DBackwardConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validator.load(validator.REPORT)
        cls.result = validator.load(validator.RESULT)
        cls.diagnostics = validator.load(validator.DIAGNOSTICS)

    def test_retained_evidence_supports_only_classification_c(self) -> None:
        validator.validate_report(self.report, self.result, self.diagnostics)
        classification = self.report["backward_consistency_classification"]
        self.assertEqual(classification["classification"], "C_R10D_UNCERTAIN_UNDER_CANONICAL_IDENTITY")
        self.assertFalse(classification["option_a_exact_reproduction_proven"])
        self.assertFalse(classification["option_b_demonstrable_correction_proven"])
        self.assertTrue(classification["option_c_r10d_uncertain"])

    def test_mutation_claiming_exact_reproduction_fails(self) -> None:
        mutated = copy.deepcopy(self.report)
        mutated["backward_consistency_classification"]["classification"] = "A_R10D_EXACTLY_REPRODUCED"
        mutated["backward_consistency_classification"]["option_a_exact_reproduction_proven"] = True
        mutated["backward_consistency_classification"]["option_c_r10d_uncertain"] = False
        with self.assertRaises(AssertionError):
            validator.validate_report(mutated, self.result, self.diagnostics)

    def test_mutation_promoting_observations_to_canonical_fills_fails(self) -> None:
        mutated = copy.deepcopy(self.report)
        mutated["retained_legacy_wallet_aggregate"]["semantic_status"] = "CANONICAL_UNIQUE_FILL_LEDGER"
        with self.assertRaises(AssertionError):
            validator.validate_report(mutated, self.result, self.diagnostics)

    def test_mutation_removing_coin_from_canonical_identity_fails(self) -> None:
        mutated = copy.deepcopy(self.report)
        mutated["canonical_identity_model_under_review"]["wallet_user_fill_key"].remove("canonical_coin")
        with self.assertRaises(AssertionError):
            validator.validate_report(mutated, self.result, self.diagnostics)

    def test_mutation_reopening_downstream_authority_fails(self) -> None:
        mutated = copy.deepcopy(self.report)
        mutated["execution_and_downstream_boundaries"]["wallet_ranking_authorized"] = True
        with self.assertRaises(AssertionError):
            validator.validate_report(mutated, self.result, self.diagnostics)

    def test_mutation_breaking_fill_conservation_fails(self) -> None:
        mutated_result = copy.deepcopy(self.result)
        mutated_result["per_hour_summaries"][0]["event_pair_count"] += 1
        with self.assertRaises(AssertionError):
            validator.validate_report(self.report, mutated_result, self.diagnostics)

    def test_mutation_claiming_r11a_covers_the_six_r10d_objects_fails(self) -> None:
        mutated = copy.deepcopy(self.report)
        mutated["scientific_consequences"]["r11a_exact_72_object_diagnostic_does_not_include_r10d_six_objects"] = False
        mutated["scientific_consequences"]["next_permitted_empirical_source"] = "R11A"
        with self.assertRaises(AssertionError):
            validator.validate_report(mutated, self.result, self.diagnostics)

    def test_mutation_promoting_source_path_hours_to_event_time_fails(self) -> None:
        mutated = copy.deepcopy(self.report)
        mutated["evidence_matrix"]["source_path_active_hour_counts_equal_event_time_active_hour_counts"] = "PROVEN"
        with self.assertRaises(AssertionError):
            validator.validate_report(mutated, self.result, self.diagnostics)

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, "governance/validate_r10d_backward_consistency.py"],
            cwd=validator.ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10D_BACKWARD_CONSISTENCY_VALID_C_UNCERTAIN_UNDER_CANONICAL_IDENTITY", done.stdout)


if __name__ == "__main__":
    unittest.main()
