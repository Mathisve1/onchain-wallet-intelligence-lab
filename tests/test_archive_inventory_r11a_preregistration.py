from __future__ import annotations

import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from governance import validate_r11a_preregistration as validator


class R11APreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prereg = validator.load(validator.PREREG)
        cls.dossier = validator.load(validator.DOSSIER)
        cls.root_cause = validator.load(validator.ROOT_CAUSE)
        cls.selection = validator.load(validator.SELECTION)
        cls.result = validator.load(validator.R11_RESULT)
        cls.consumption = validator.load(validator.R11_CONSUMPTION)

    def validate(self, prereg: dict | None = None, dossier: dict | None = None, root_cause: dict | None = None) -> None:
        validator.validate(
            self.prereg if prereg is None else prereg,
            self.dossier if dossier is None else dossier,
            self.root_cause if root_cause is None else root_cause,
            self.selection,
            self.result,
            self.consumption,
        )

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, "governance/validate_r11a_preregistration.py"],
            cwd=validator.ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R11A_PREREGISTRATION_VALID_NO_EXECUTION", completed.stdout)

    def assert_prereg_rejected(self, mutated: dict) -> None:
        with self.assertRaises(validator.R11APreregistrationError):
            self.validate(prereg=mutated)

    def test_request_and_retry_caps_fail_independently(self) -> None:
        for field, value in (("maximum_get_object_requests", 73), ("maximum_retries_per_request", 1)):
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.prereg)
                mutated["proposed_request_envelope"][field] = value
                self.assert_prereg_rejected(mutated)

    def test_additional_object_or_window_fails(self) -> None:
        mutated = copy.deepcopy(self.prereg)
        mutated["exact_input_scope"]["seventy_third_object_authorized"] = True
        with self.assertRaises(validator.R11APreregistrationError):
            self.validate(prereg=mutated)

    def test_weak_key_promotion_fails(self) -> None:
        mutated = copy.deepcopy(self.prereg)
        mutated["identity_contract"]["protocol_matched_trade_key"] = ["wallet", "tid"]
        with self.assertRaises(validator.R11APreregistrationError):
            self.validate(prereg=mutated)

    def test_tid_coercion_and_coin_rewrite_fail_independently(self) -> None:
        for field in (
            "string_decimal_float_or_boolean_tid_coercion_authorized",
            "coin_rewriting_without_versioned_schema_authorized",
        ):
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.dossier)
                mutated["schema_boundaries"][field] = True
                with self.assertRaises(validator.R11APreregistrationError):
                    self.validate(dossier=mutated)

    def test_blind_dedup_and_repair_authority_fail_independently(self) -> None:
        for field in ("blind_drop_duplicates_authorized", "repair_selected_by_this_dossier"):
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.dossier)
                mutated["decision_boundaries"][field] = True
                with self.assertRaises(validator.R11APreregistrationError):
                    self.validate(dossier=mutated)

    def test_role_mutation_and_runtime_authority_fail_independently(self) -> None:
        mutations = (
            ("iam", lambda value: value["iam_and_session_boundary"].__setitem__("role_or_policy_mutation_authorized", True)),
            ("runtime", lambda value: value["current_runtime_authority"].__setitem__("get_object", True)),
        )
        for label, mutate in mutations:
            with self.subTest(mutation=label):
                mutated = copy.deepcopy(self.prereg)
                mutate(mutated)
                self.assert_prereg_rejected(mutated)

    def test_root_cause_and_r12_overclaims_fail_independently(self) -> None:
        for field in ("root_cause_claim_authorized_now", "r12_ready"):
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.root_cause)
                mutated[field] = True
                with self.assertRaises(validator.R11APreregistrationError):
                    self.validate(root_cause=mutated)

    def test_preregistration_top_level_schema_is_exact(self) -> None:
        mutations = (
            ("extra", lambda value: value.__setitem__("unreviewed_extra", False)),
            ("missing", lambda value: value.pop("study_role")),
        )
        for label, mutate in mutations:
            with self.subTest(mutation=label):
                mutated = copy.deepcopy(self.prereg)
                mutate(mutated)
                self.assert_prereg_rejected(mutated)

    def test_frozen_taxonomy_rejects_alias_missing_extra_and_order_drift(self) -> None:
        mutations = (
            ("legacy_alias", lambda values: values.__setitem__(0, "LEGITIMATE_TID_REUSE")),
            ("missing", lambda values: values.pop()),
            ("extra", lambda values: values.append("UNKNOWN")),
            ("reordered", lambda values: values.reverse()),
        )
        for source in ("preregistration", "dossier"):
            for label, mutate in mutations:
                with self.subTest(source=source, mutation=label):
                    prereg = copy.deepcopy(self.prereg)
                    dossier = copy.deepcopy(self.dossier)
                    target = prereg if source == "preregistration" else dossier
                    mutate(target["duplicate_taxonomy"])
                    with self.assertRaises(validator.R11APreregistrationError):
                        self.validate(prereg=prereg, dossier=dossier)

    def test_required_occurrence_and_global_output_fields_are_exact(self) -> None:
        for field in ("required_occurrence_fields", "required_global_outputs"):
            mutations = (
                ("missing", lambda values: values.pop()),
                ("extra", lambda values: values.append("ambiguous_legacy_field")),
                ("reordered", lambda values: values.reverse()),
                ("wrong_type", lambda values: values.__setitem__(0, False)),
            )
            for label, mutate in mutations:
                with self.subTest(field=field, mutation=label):
                    mutated = copy.deepcopy(self.prereg)
                    mutate(mutated[field])
                    self.assert_prereg_rejected(mutated)

    def test_raw_locator_requires_object_key_sha_record_and_event(self) -> None:
        paths = (
            ("identity", ["identity_contract", "emitted_raw_observation_locator", "exact_fields"]),
            ("occurrence", ["occurrence_record_contract", "raw_observation_locator_exact_fields"]),
        )
        for source, path in paths:
            for component in validator.EXPECTED_RAW_OBSERVATION_LOCATOR["exact_fields"]:
                with self.subTest(source=source, missing=component):
                    mutated = copy.deepcopy(self.prereg)
                    values: object = mutated
                    for key in path:
                        values = values[key]  # type: ignore[index]
                    self.assertIsInstance(values, list)
                    values.remove(component)  # type: ignore[union-attr]
                    self.assert_prereg_rejected(mutated)

    def test_locator_schema_rejects_alias_extra_order_and_key_without_sha(self) -> None:
        mutations = (
            (
                "alias",
                lambda value: value["identity_contract"]["emitted_raw_observation_locator"]["exact_fields"].__setitem__(
                    1, "verified_object_sha256"
                ),
            ),
            (
                "extra",
                lambda value: value["identity_contract"]["emitted_raw_observation_locator"]["exact_fields"].append(
                    "path_hour_utc"
                ),
            ),
            (
                "order",
                lambda value: value["identity_contract"]["emitted_raw_observation_locator"]["exact_fields"].reverse(),
            ),
            (
                "key_without_sha",
                lambda value: value["identity_contract"]["emitted_raw_observation_locator"].__setitem__(
                    "source_object_key_and_verified_compressed_sha256_both_required", False
                ),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(mutation=label):
                mutated = copy.deepcopy(self.prereg)
                mutate(mutated)
                self.assert_prereg_rejected(mutated)

    def test_uint50_contract_is_type_strict_and_exact(self) -> None:
        mutations = (
            ("raw_type", "required_raw_json_type", "NUMBER"),
            ("minimum", "minimum_inclusive", -1),
            ("maximum", "maximum_exclusive", 2**50 + 1),
            ("minimum_bool", "minimum_inclusive", False),
            ("maximum_float", "maximum_exclusive", float(2**50)),
            ("coercion", "string_decimal_float_or_boolean_tid_coercion_authorized", True),
            ("violation_taxon", "schema_violation_taxon", "UNKNOWN"),
        )
        for label, field, value in mutations:
            with self.subTest(mutation=label):
                mutated = copy.deepcopy(self.prereg)
                mutated["identity_contract"]["tid_schema_contract"][field] = value
                self.assert_prereg_rejected(mutated)

    def test_schema_violation_rows_cannot_fabricate_a_valid_tid_or_identity(self) -> None:
        for field in (
            "validated_integer_tid_must_be_null",
            "protocol_trade_identity_must_be_null",
            "wallet_fill_identity_must_be_null",
            "coercion_authorized",
        ):
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.prereg)
                current = mutated["occurrence_record_contract"]["tid_schema_violation_row"][field]
                mutated["occurrence_record_contract"]["tid_schema_violation_row"][field] = not current
                self.assert_prereg_rejected(mutated)

    def test_replay_and_counterparty_classifications_require_proof_joins(self) -> None:
        fields = (
            "exact_user_fill_reobservation_requires_nonnull_exact_block_replay_proof",
            "expected_counterparty_pair_requires_nonnull_counterparty_pair_proof",
        )
        for field in fields:
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.prereg)
                mutated["occurrence_record_contract"][field] = False
                self.assert_prereg_rejected(mutated)

    def test_taxonomy_predicates_and_count_units_are_exact(self) -> None:
        mutations = (
            (
                "payload_only_replay",
                lambda value: value["taxonomy_decision_contract"].__setitem__(
                    "payload_hash_only_replay_classification_authorized", True
                ),
            ),
            (
                "missing_replay_proof",
                lambda value: value["taxonomy_decision_contract"]["exact_user_fill_reobservation_requires"].pop(),
            ),
            (
                "counterparty_pair_weakened",
                lambda value: value["taxonomy_decision_contract"]["expected_counterparty_pair_requires"].pop(),
            ),
            (
                "taxonomy_unit_alias",
                lambda value: value["taxonomy_decision_contract"]["taxonomy_units_by_class"].__setitem__(
                    "EXPECTED_COUNTERPARTY_PAIR", "DUPLICATE_GROUP"
                ),
            ),
            (
                "count_key_missing",
                lambda value: value["global_output_contract"]["taxonomy_count_fields_must_have_exact_zero_filled_keys"].pop(),
            ),
            (
                "cross_layer_sum",
                lambda value: value["global_output_contract"].__setitem__(
                    "cross_layer_taxonomy_counts_must_not_be_summed_as_one_partition", False
                ),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(mutation=label):
                mutated = copy.deepcopy(self.prereg)
                mutate(mutated)
                self.assert_prereg_rejected(mutated)

    def test_block_replay_uses_dossier_invariants_not_raw_record_identity(self) -> None:
        mutations = (
            (
                "raw_record_promoted",
                lambda value: value["diagnostic_passes"][0]["classification_invariants"].append("raw_record_sha256"),
            ),
            (
                "event_fingerprint_removed",
                lambda value: value["diagnostic_passes"][0]["classification_invariants"].remove(
                    "ordered_event_fingerprint"
                ),
            ),
            (
                "raw_record_role_rewritten",
                lambda value: value["taxonomy_decision_contract"].__setitem__(
                    "raw_record_sha256_role_for_block_replay", "PRIMARY_IDENTITY"
                ),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(mutation=label):
                mutated = copy.deepcopy(self.prereg)
                mutate(mutated)
                self.assert_prereg_rejected(mutated)

    def test_canonical_evidence_merge_binding_is_exact_and_non_authorizing(self) -> None:
        mutations = (
            (
                "wrong_sha",
                lambda value: value["canonical_r11_evidence_closure_binding"].__setitem__(
                    "canonical_merge_commit_sha", "0" * 40
                ),
            ),
            (
                "short_sha",
                lambda value: value["canonical_r11_evidence_closure_binding"].__setitem__(
                    "canonical_merge_commit_sha", "f7aa612d"
                ),
            ),
            (
                "binding_incomplete",
                lambda value: value["canonical_r11_evidence_closure_binding"].__setitem__("binding_complete", False),
            ),
            (
                "approval_overclaim",
                lambda value: value["canonical_r11_evidence_closure_binding"].__setitem__(
                    "binding_is_owner_approval", True
                ),
            ),
            ("extra", lambda value: value["canonical_r11_evidence_closure_binding"].__setitem__("extra", False)),
            ("missing", lambda value: value["canonical_r11_evidence_closure_binding"].pop("validator_path")),
        )
        for label, mutate in mutations:
            with self.subTest(mutation=label):
                mutated = copy.deepcopy(self.prereg)
                mutate(mutated)
                self.assert_prereg_rejected(mutated)
        self.assertNotIn("TODO", validator.PREREG.read_text(encoding="utf-8"))

    def test_every_frozen_cap_is_required_with_exact_schema(self) -> None:
        for field in validator.EXPECTED_ENVELOPE:
            with self.subTest(missing=field):
                mutated = copy.deepcopy(self.prereg)
                mutated["proposed_request_envelope"].pop(field)
                self.assert_prereg_rejected(mutated)
        for label, mutate in (
            ("extra", lambda value: value["proposed_request_envelope"].__setitem__("extra_false_cap", False)),
            (
                "bool_for_integer",
                lambda value: value["proposed_request_envelope"].__setitem__("maximum_get_object_requests", True),
            ),
        ):
            with self.subTest(mutation=label):
                mutated = copy.deepcopy(self.prereg)
                mutate(mutated)
                self.assert_prereg_rejected(mutated)

    def test_input_and_future_implementation_bindings_are_exact(self) -> None:
        sections = (
            ("exact_input_scope", validator.EXPECTED_INPUT_SCOPE),
            ("future_implementation_contract_requirements", validator.EXPECTED_FUTURE_IMPLEMENTATION_REQUIREMENTS),
        )
        for section, expected in sections:
            for field in expected:
                with self.subTest(section=section, missing=field):
                    mutated = copy.deepcopy(self.prereg)
                    mutated[section].pop(field)
                    self.assert_prereg_rejected(mutated)
            with self.subTest(section=section, mutation="extra"):
                mutated = copy.deepcopy(self.prereg)
                mutated[section]["unreviewed_extra"] = False
                self.assert_prereg_rejected(mutated)
        for label, mutate in (
            (
                "binding_missing",
                lambda value: value["implementation_values_bound_before_owner_approval"].pop(),
            ),
            (
                "binding_extra",
                lambda value: value["implementation_values_bound_before_owner_approval"].append(
                    "unreviewed_dependency"
                ),
            ),
        ):
            with self.subTest(mutation=label):
                mutated = copy.deepcopy(self.prereg)
                mutate(mutated)
                self.assert_prereg_rejected(mutated)

    def test_every_authority_and_retention_map_is_exact(self) -> None:
        sections = (
            ("current_runtime_authority", validator.EXPECTED_RUNTIME_AUTHORITY),
            ("downstream_authorizations", validator.EXPECTED_DOWNSTREAM_AUTHORIZATIONS),
            ("governance_gates", validator.EXPECTED_GOVERNANCE_GATES),
            ("iam_and_session_boundary", validator.EXPECTED_IAM_BOUNDARY),
            ("retention_and_privacy", validator.EXPECTED_RETENTION),
        )
        for section, expected in sections:
            for field in expected:
                with self.subTest(section=section, missing=field):
                    mutated = copy.deepcopy(self.prereg)
                    mutated[section].pop(field)
                    self.assert_prereg_rejected(mutated)
            with self.subTest(section=section, mutation="extra"):
                mutated = copy.deepcopy(self.prereg)
                mutated[section]["unreviewed_false_key"] = False
                self.assert_prereg_rejected(mutated)

    def test_every_closed_runtime_and_downstream_authority_rejects_true(self) -> None:
        for section, expected in (
            ("current_runtime_authority", validator.EXPECTED_RUNTIME_AUTHORITY),
            ("downstream_authorizations", validator.EXPECTED_DOWNSTREAM_AUTHORIZATIONS),
        ):
            for field, frozen in expected.items():
                self.assertIs(frozen, False)
                with self.subTest(section=section, authority=field):
                    mutated = copy.deepcopy(self.prereg)
                    mutated[section][field] = True
                    self.assert_prereg_rejected(mutated)

    def test_terminal_and_artifact_cap_status_cannot_diverge(self) -> None:
        mutations = (
            (
                "terminal_alias",
                lambda value: value["allowed_terminal_classes"].__setitem__(
                    1, "R11A_DIAGNOSTIC_ARTIFACT_CAP_EXCEEDED_WITH_NO_CAUSE_OR_REPAIR_CONCLUSION"
                ),
            ),
            (
                "cap_behavior_alias",
                lambda value: value["retention_and_privacy"].__setitem__(
                    "artifact_cap_exceeded_behavior",
                    "R11A_DIAGNOSTIC_ARTIFACT_CAP_EXCEEDED_WITH_NO_CAUSE_OR_REPAIR_CONCLUSION",
                ),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(mutation=label):
                mutated = copy.deepcopy(self.prereg)
                mutate(mutated)
                self.assert_prereg_rejected(mutated)

    def test_json_loader_rejects_duplicates_nonfinite_and_nonobject_roots(self) -> None:
        invalid = (
            '{"outer":{"key":1,"key":2}}',
            '{"value":NaN}',
            '{"value":Infinity}',
            '{"value":-Infinity}',
            '{"value":1e9999}',
        )
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(validator.R11APreregistrationError):
                validator.strict_json_loads(text, "synthetic preregistration")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "root.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(validator.R11APreregistrationError):
                validator.load(path)

    def test_validation_stays_active_under_python_optimized_mode(self) -> None:
        code = """
import copy
from governance import validate_r11a_preregistration as v
p = v.load(v.PREREG)
p["duplicate_taxonomy"][0] = "LEGITIMATE_TID_REUSE"
try:
    v.validate(p, v.load(v.DOSSIER), v.load(v.ROOT_CAUSE), v.load(v.SELECTION), v.load(v.R11_RESULT), v.load(v.R11_CONSUMPTION))
except v.R11APreregistrationError:
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

    def test_readme_records_frozen_nonexecuting_status_and_exact_merge(self) -> None:
        readme = (validator.BASE / "r11a/README.md").read_text(encoding="utf-8")
        self.assertIn("PREREGISTERED_NO_EXECUTION", readme)
        self.assertIn("frozen resource ceilings", readme)
        self.assertIn("f7aa612d2a5638cce0fd197f57efea4b787f87f1", readme)
        self.assertIn("Owner approval remains absent", readme)
        self.assertNotIn("draft preregistration skeleton", readme)


if __name__ == "__main__":
    unittest.main()
