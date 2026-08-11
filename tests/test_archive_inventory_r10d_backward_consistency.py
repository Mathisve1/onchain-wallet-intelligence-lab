from __future__ import annotations

import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from governance import validate_r10d_backward_consistency as validator


class R10DBackwardConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validator.load(validator.REPORT)
        cls.result = validator.load(validator.RESULT)
        cls.diagnostics = validator.load(validator.DIAGNOSTICS)
        cls.dossier = validator.load(validator.R11A_DOSSIER)
        cls.preregistration = validator.load(validator.R11A_PREREGISTRATION)
        cls.human_report = validator.REPORT_MD.read_bytes()

    def validate(
        self,
        report: dict | None = None,
        result: dict | None = None,
        diagnostics: dict | None = None,
        dossier: dict | None = None,
        preregistration: dict | None = None,
        human_report: bytes | None = None,
    ) -> None:
        validator.validate_report(
            self.report if report is None else report,
            self.result if result is None else result,
            self.diagnostics if diagnostics is None else diagnostics,
            self.dossier if dossier is None else dossier,
            self.preregistration if preregistration is None else preregistration,
            self.human_report if human_report is None else human_report,
        )

    def test_retained_evidence_supports_only_classification_c(self) -> None:
        self.validate()
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
            self.validate(report=mutated)

    def test_mutation_promoting_observations_to_canonical_fills_fails(self) -> None:
        mutated = copy.deepcopy(self.report)
        mutated["retained_legacy_wallet_aggregate"]["semantic_status"] = "CANONICAL_UNIQUE_FILL_LEDGER"
        with self.assertRaises(AssertionError):
            self.validate(report=mutated)

    def test_mutation_removing_coin_from_canonical_identity_fails(self) -> None:
        mutated = copy.deepcopy(self.report)
        mutated["canonical_identity_model_under_review"]["wallet_user_fill_key"].remove("exact_raw_coin_string")
        with self.assertRaises(AssertionError):
            self.validate(report=mutated)

    def test_mutation_reopening_downstream_authority_fails(self) -> None:
        mutated = copy.deepcopy(self.report)
        mutated["execution_and_downstream_boundaries"]["wallet_ranking_authorized"] = True
        with self.assertRaises(AssertionError):
            self.validate(report=mutated)

    def test_mutation_breaking_fill_conservation_fails(self) -> None:
        mutated_result = copy.deepcopy(self.result)
        mutated_result["per_hour_summaries"][0]["event_pair_count"] += 1
        with self.assertRaises(AssertionError):
            self.validate(result=mutated_result)

    def test_mutation_claiming_r11a_covers_the_six_r10d_objects_fails(self) -> None:
        mutated = copy.deepcopy(self.report)
        mutated["scientific_consequences"]["r11a_exact_72_object_diagnostic_does_not_include_r10d_six_objects"] = False
        mutated["scientific_consequences"]["next_permitted_empirical_source"] = "R11A"
        with self.assertRaises(AssertionError):
            self.validate(report=mutated)

    def test_mutation_promoting_source_path_hours_to_event_time_fails(self) -> None:
        mutated = copy.deepcopy(self.report)
        mutated["evidence_matrix"]["source_path_active_hour_counts_equal_event_time_active_hour_counts"] = "PROVEN"
        with self.assertRaises(AssertionError):
            self.validate(report=mutated)

    def test_full_mapping_rejects_extra_fields(self) -> None:
        mutated = copy.deepcopy(self.report)
        mutated["execution_authorized_now"] = True
        with self.assertRaises(validator.R10DValidationError):
            self.validate(report=mutated)

    def test_canonical_identity_model_is_exactly_r11a_aligned(self) -> None:
        mutated = copy.deepcopy(self.report)
        mutated["canonical_identity_model_under_review"]["archive_block_equality_invariants"].remove(
            "ordered_event_count"
        )
        with self.assertRaises(validator.R10DValidationError):
            self.validate(report=mutated)

    def test_human_report_is_byte_exact_and_prose_fail_closed(self) -> None:
        self.assertEqual(
            validator.byte_digest(self.human_report),
            self.report["source_basis"]["human_report_sha256"],
        )
        mutations = (
            self.human_report.replace(
                b"C_R10D_UNCERTAIN_UNDER_CANONICAL_IDENTITY",
                b"A_R10D_EXACTLY_REPRODUCED",
                1,
            ),
            self.human_report.replace(b"must not be presented", b"may be presented", 1),
            self.human_report + b"\nExecution is authorized.\n",
        )
        for mutated in mutations:
            with self.subTest(sha256=validator.byte_digest(mutated)):
                with self.assertRaises(validator.R10DValidationError):
                    self.validate(human_report=mutated)

    def test_human_report_binding_mapping_is_exact(self) -> None:
        mutations = (
            lambda value: value["source_basis"].__setitem__("human_report_sha256", "0" * 64),
            lambda value: value["source_basis"].__setitem__("human_report_path", "UNBOUND.md"),
            lambda value: value["canonical_identity_authority_binding"].__setitem__(
                "live_dossier_and_preregistration_identity_models_must_match_report_exactly", False
            ),
        )
        for mutate in mutations:
            mutated = copy.deepcopy(self.report)
            mutate(mutated)
            with self.assertRaises(validator.R10DValidationError):
                self.validate(report=mutated)

    def test_live_r11a_dossier_and_preregistration_identity_are_cross_bound(self) -> None:
        mutated_dossier = copy.deepcopy(self.dossier)
        mutated_dossier["identity_layers"]["archive_block"]["equality_invariants"].remove(
            "ordered_event_count"
        )
        with self.assertRaises(validator.R10DValidationError):
            self.validate(dossier=mutated_dossier)

        mutated_preregistration = copy.deepcopy(self.preregistration)
        mutated_preregistration["identity_contract"]["protocol_matched_trade_key"][1] = "normalized_coin"
        with self.assertRaises(validator.R10DValidationError):
            self.validate(preregistration=mutated_preregistration)

    def test_joint_live_authority_drift_still_fails_against_report(self) -> None:
        mutated_dossier = copy.deepcopy(self.dossier)
        mutated_preregistration = copy.deepcopy(self.preregistration)
        mutated_dossier["identity_layers"]["archive_block"]["equality_invariants"].remove(
            "ordered_event_count"
        )
        mutated_preregistration["identity_contract"]["archive_block_equality_invariants"].remove(
            "ordered_event_count"
        )
        with self.assertRaises(validator.R10DValidationError):
            self.validate(dossier=mutated_dossier, preregistration=mutated_preregistration)

    def test_json_loader_rejects_duplicates_nonfinite_and_nonobject_roots(self) -> None:
        for text in (
            '{"outer":{"key":1,"key":2}}',
            '{"value":NaN}',
            '{"value":Infinity}',
            '{"value":-Infinity}',
            '{"value":1e9999}',
        ):
            with self.subTest(text=text), self.assertRaises(validator.R10DValidationError):
                validator.strict_json_loads(text, "synthetic R10D evidence")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "root.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(validator.R10DValidationError):
                validator.load(path)

    def test_validation_stays_active_under_python_optimized_mode(self) -> None:
        code = """
import copy
from governance import validate_r10d_backward_consistency as v
r = v.load(v.REPORT)
r["backward_consistency_classification"]["classification"] = "A_R10D_EXACTLY_REPRODUCED"
r["execution_and_downstream_boundaries"]["wallet_ranking_authorized"] = True
result = v.load(v.RESULT)
result["per_hour_summaries"][0]["event_pair_count"] += 1
dossier = v.load(v.R11A_DOSSIER)
preregistration = v.load(v.R11A_PREREGISTRATION)
preregistration["identity_contract"]["archive_block_equality_invariants"].remove("ordered_event_count")
try:
    v.validate_report(
        r,
        result,
        v.load(v.DIAGNOSTICS),
        dossier,
        preregistration,
        v.REPORT_MD.read_bytes(),
    )
except v.R10DValidationError:
    raise SystemExit(0)
raise SystemExit(1)
"""
        completed = subprocess.run(
            [sys.executable, "-O", "-c", code],
            cwd=validator.ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

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
