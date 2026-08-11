from __future__ import annotations

import copy
import hashlib
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

    def validate(
        self,
        *,
        prereg: dict | None = None,
        dossier: dict | None = None,
        root_cause: dict | None = None,
        selection: dict | None = None,
        result: dict | None = None,
        consumption: dict | None = None,
    ) -> None:
        validator.validate(
            self.prereg if prereg is None else prereg,
            self.dossier if dossier is None else dossier,
            self.root_cause if root_cause is None else root_cause,
            self.selection if selection is None else selection,
            self.result if result is None else result,
            self.consumption if consumption is None else consumption,
        )

    def reject_prereg(self, mutate) -> None:
        value = copy.deepcopy(self.prereg)
        mutate(value)
        with self.assertRaises(validator.R11APreregistrationError):
            self.validate(prereg=value)

    def reject_prereg_structurally(self, mutate) -> None:
        value = copy.deepcopy(self.prereg)
        mutate(value)
        original = validator.PREREG_SEMANTIC_SHA256
        validator.PREREG_SEMANTIC_SHA256 = validator.semantic_digest(value)
        try:
            with self.assertRaises(validator.R11APreregistrationError):
                self.validate(prereg=value)
        finally:
            validator.PREREG_SEMANTIC_SHA256 = original

    def reject_dossier(self, mutate) -> None:
        value = copy.deepcopy(self.dossier)
        mutate(value)
        with self.assertRaises(validator.R11APreregistrationError):
            self.validate(dossier=value)

    def reject_root(self, mutate) -> None:
        value = copy.deepcopy(self.root_cause)
        mutate(value)
        with self.assertRaises(validator.R11APreregistrationError):
            self.validate(root_cause=value)

    def test_dedicated_validator_passes_normal_and_optimized(self) -> None:
        for flags in ([], ["-O"]):
            with self.subTest(flags=flags):
                completed = subprocess.run(
                    [sys.executable, *flags, "governance/validate_r11a_preregistration.py"],
                    cwd=validator.ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertIn("R11A_PREREGISTRATION_VALID_NO_EXECUTION", completed.stdout)

    def test_validator_has_no_optimization_sensitive_checks(self) -> None:
        source = Path(validator.__file__).read_text(encoding="utf-8")
        forbidden = "as" + "sert"
        self.assertNotIn(forbidden, source)

    def test_current_full_semantic_bindings_are_exact(self) -> None:
        self.assertEqual(validator.semantic_digest(self.prereg), validator.PREREG_SEMANTIC_SHA256)
        self.assertEqual(validator.semantic_digest(self.dossier), validator.DOSSIER_SEMANTIC_SHA256)
        self.assertEqual(validator.semantic_digest(self.root_cause), validator.ROOT_CAUSE_SEMANTIC_SHA256)
        self.assertEqual(validator.semantic_digest(self.selection), validator.SELECTION_SEMANTIC_SHA256)
        self.assertEqual(validator.semantic_digest(self.result), validator.RESULT_SEMANTIC_SHA256)
        self.assertEqual(validator.semantic_digest(self.consumption), validator.CONSUMPTION_SEMANTIC_SHA256)

    def test_contract_significant_mapping_order_changes_semantic_digest(self) -> None:
        mutated = copy.deepcopy(self.prereg)
        containers = mutated["global_output_contract"]["artifact_layout_contract"]["scientific_output_containers"]
        first = containers.pop("taxonomy_unit_ledger")
        containers["taxonomy_unit_ledger"] = first
        self.assertNotEqual(validator.semantic_digest(mutated), validator.PREREG_SEMANTIC_SHA256)
        with self.assertRaises(validator.R11APreregistrationError):
            self.validate(prereg=mutated)

    def test_exact_decimal_token_alias_changes_semantic_and_byte_digest(self) -> None:
        original = validator.PREREG.read_text(encoding="utf-8")
        needle = '"maximum_one_time_budget_eur": 0.5'
        self.assertEqual(original.count(needle), 1)
        mutated_text = original.replace(needle, '"maximum_one_time_budget_eur": 0.50000000000000001')
        mutated = validator.strict_json_loads(mutated_text, "decimal alias mutation")
        self.assertIsInstance(mutated, dict)
        self.assertNotEqual(validator.semantic_digest(mutated), validator.PREREG_SEMANTIC_SHA256)
        with self.assertRaises(validator.R11APreregistrationError):
            self.validate(prereg=mutated)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mutated-prereg.json"
            path.write_text(mutated_text, encoding="utf-8")
            code = (
                "import sys; from pathlib import Path; "
                "from governance import validate_r11a_preregistration as v; "
                "v.require(v.digest(Path(sys.argv[1])) == v.PREREG_BYTE_SHA256, 'preregistration byte drift')"
            )
            for flags in ([], ["-O"]):
                with self.subTest(flags=flags):
                    completed = subprocess.run(
                        [sys.executable, *flags, "-c", code, str(path)],
                        cwd=validator.ROOT,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn("preregistration byte drift", completed.stderr)

    def test_prereg_top_level_extra_missing_and_type_drift_fail(self) -> None:
        mutations = (
            lambda value: value.__setitem__("unreviewed_extra", False),
            lambda value: value.pop("research_question"),
            lambda value: value.__setitem__("network_requests_executed_by_preregistration", False),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.reject_prereg(mutate)

    def test_execution_owner_and_runtime_authority_fail(self) -> None:
        mutations = (
            lambda value: value.__setitem__("execution_authorized_now", True),
            lambda value: value.__setitem__("owner_approval_status", "APPROVED"),
            lambda value: value["current_runtime_authority"].__setitem__("get_object", True),
            lambda value: value["governance_gates"].__setitem__("r11b_repair_authorized_by_r11a", True),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.reject_prereg(mutate)

    def test_scope_expansion_or_release_reuse_fails(self) -> None:
        mutations = (
            lambda value: value["exact_input_scope"].__setitem__("seventy_third_object_authorized", True),
            lambda value: value["exact_input_scope"].__setitem__("other_historical_window_authorized", True),
            lambda value: value["parent_r11_run"].__setitem__("rerun_authorized", True),
            lambda value: value["exact_input_scope"].__setitem__("canonical_selection_sha256", "0" * 64),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.reject_prereg(mutate)

    def test_identity_coin_tid_and_locator_mutations_fail(self) -> None:
        mutations = (
            lambda value: value["identity_contract"].__setitem__("protocol_matched_trade_key", ["wallet", "tid"]),
            lambda value: value["identity_contract"]["coin_identity_contract"].__setitem__("canonical_identity_value", "NORMALIZED_COIN"),
            lambda value: value["identity_contract"]["tid_schema_contract"].__setitem__("maximum_exclusive", 2**53),
            lambda value: value["proof_and_classification_contract"]["raw_block_locator_contract"]["exact_fields"].append("block_number"),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.reject_prereg(mutate)

    def test_taxonomy_proof_and_wallet_unit_mutations_fail(self) -> None:
        mutations = (
            lambda value: value["duplicate_taxonomy"].__setitem__(0, "LEGITIMATE_TID_REUSE"),
            lambda value: value["proof_and_classification_contract"]["taxonomy_unit_ledger_record_contract"]["taxonomy_unit_type_exact_values"].remove("RAW_WALLET_SCHEMA_VIOLATION_OBSERVATION"),
            lambda value: value["proof_and_classification_contract"]["proof_id_contract"].__setitem__("generated_primary_key_is_excluded_from_its_own_preimage", False),
            lambda value: value["taxonomy_decision_contract"].__setitem__("payload_hash_only_replay_classification_authorized", True),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.reject_prereg(mutate)

    def test_transport_reducer_and_cap_contract_mutations_fail(self) -> None:
        mutations = (
            lambda value: value["proof_and_classification_contract"]["object_transport_and_two_pass_conservation_ledger_record_contract"]["processing_status_exact_values"].remove("BODY_READ_FAILED_AFTER_RESPONSE_METADATA"),
            lambda value: value["proof_and_classification_contract"]["reducer_partition_conservation_ledger_record_contract"].__setitem__("reducer_processing_order", ["HISTORICAL_LEGACY_WEAK_KEY", "BLOCK_NUMBER"]),
            lambda value: value["proposed_request_envelope"].__setitem__("maximum_retained_scientific_output_bytes", 130023424),
            lambda value: value["global_output_contract"]["resource_and_cap_conservation_ledger_contract"].__setitem__("post_measurement_packaging_reservation_milliseconds_exact", 0),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.reject_prereg(mutate)

    def test_repaired_stop_cap_and_empty_output_rules_are_structurally_guarded(self) -> None:
        mutations = (
            lambda value: value["global_output_contract"]["resource_and_cap_conservation_ledger_contract"].__setitem__(
                "metadata_projection_mode_exact_values", ["ONE_FABRICATED_MODE"]
            ),
            lambda value: value["global_output_contract"]["preflight_and_stop_evidence_ledger_contract"].__setitem__(
                "phase_check_order", "WORKSPACE_WITHOUT_RUNTIME_ENDPOINT"
            ),
            lambda value: value["global_output_contract"]["preflight_and_stop_evidence_ledger_contract"][
                "parse_failure_record_ordinal_nullability_by_failure_code"
            ]["record_ordinal_must_be_null"].remove("LZ4_DECOMPRESSION_FAILURE"),
            lambda value: value["global_output_contract"]["block_reducer_aggregate_derivation_contract"].__setitem__(
                "applicability", "ALL_FIELDS_NULL_UNLESS_REDUCER_COMPLETE"
            ),
            lambda value: value["proof_and_classification_contract"][
                "complete_block_overlap_matrix_record_contract"
            ].__setitem__("record_scope", "COMPLETE_ONLY_WITH_NO_EMPTY_STATUS_RULE"),
            lambda value: value["global_output_contract"]["package_boundary_record_contract"].__setitem__(
                "exact_byte_count", 512
            ),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.reject_prereg_structurally(mutate)

    def test_result_self_reference_and_projected_evidence_mutations_fail(self) -> None:
        mutations = (
            lambda value: value["global_output_contract"]["artifact_layout_contract"].__setitem__("result_file_container_reference_shape", "REFERENCES_EVERY_FILE_INCLUDING_ITSELF"),
            lambda value: value["global_output_contract"]["artifact_layout_contract"]["acyclic_sealing_order"].reverse(),
            lambda value: value["global_output_contract"]["resource_and_cap_conservation_ledger_contract"]["exact_fields"].remove("projected_scientific_output_entry_ledger"),
            lambda value: value["global_output_contract"]["incomplete_and_cap_output_applicability_contract"].__setitem__("all_required_global_output_keys_are_present_for_every_terminal_even_when_the_exact_value_is_null_by_this_contract", False),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.reject_prereg(mutate)

    def test_dossier_full_mapping_and_authority_mutations_fail(self) -> None:
        mutations = (
            lambda value: value.__setitem__("execution_authorized_now", True),
            lambda value: value.__setitem__("schema_version", 999),
            lambda value: value["identity_layers"]["protocol_matched_trade"].__setitem__("canonical_key", ["wallet", "tid"]),
            lambda value: value["decision_boundaries"].__setitem__("blind_drop_duplicates_authorized", True),
            lambda value: value["fingerprints"].__setitem__("raw_record_sha256", "NORMALIZED_JSON"),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.reject_dossier(mutate)

    def test_root_cause_full_mapping_and_overclaims_fail(self) -> None:
        mutations = (
            lambda value: value.__setitem__("execution_authorized_now", True),
            lambda value: value.__setitem__("required_empirical_gate", "NONE"),
            lambda value: value.__setitem__("root_cause_claim_authorized_now", True),
            lambda value: value.__setitem__("repair_selection_authorized_now", True),
            lambda value: value.__setitem__("r12_ready", True),
            lambda value: value.__setitem__("invented_repeat_count", 1),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.reject_root(mutate)

    def test_duplicate_root_finding_identifier_fails(self) -> None:
        self.reject_root(
            lambda value: value["finding_register"][1].__setitem__(
                "finding", value["finding_register"][0]["finding"]
            )
        )

    def test_selection_result_and_consumption_mutations_fail(self) -> None:
        mutated_selection = copy.deepcopy(self.selection)
        mutated_selection["exact_targets"].pop()
        with self.assertRaises(validator.R11APreregistrationError):
            self.validate(selection=mutated_selection)

        mutated_result = copy.deepcopy(self.result)
        mutated_result["research_conclusion"] = "R11_CLOSED"
        with self.assertRaises(validator.R11APreregistrationError):
            self.validate(result=mutated_result)

        consumption_mutations = (
            lambda value: value.__setitem__("remaining_get_object_budget_from_consumed_release", 72),
            lambda value: value.__setitem__("duplicate_root_cause_known", True),
            lambda value: value.__setitem__("future_r11_dispatch_authorized", True),
            lambda value: value["trading_authorizations"].__setitem__("live", True),
            lambda value: value.__setitem__("status", "CONSUMED_COMPLETE"),
            lambda value: value.__setitem__("workflow_run_id", 0),
            lambda value: value.__setitem__("artifact_zip_sha256", "0" * 64),
            lambda value: value.__setitem__("new_execution_authorized", True),
        )
        for mutate in consumption_mutations:
            value = copy.deepcopy(self.consumption)
            mutate(value)
            with self.assertRaises(validator.R11APreregistrationError):
                self.validate(consumption=value)

    def test_strict_json_rejects_duplicate_keys_at_any_depth(self) -> None:
        for text in ('{"a":1,"a":1}', '{"a":{"b":1,"b":2}}'):
            with self.subTest(text=text):
                with self.assertRaises(validator.R11APreregistrationError):
                    validator.strict_json_loads(text, "mutation")

    def test_strict_json_rejects_nonfinite_and_overflow(self) -> None:
        for token in ("NaN", "Infinity", "-Infinity", "1e1000000"):
            with self.subTest(token=token):
                with self.assertRaises(validator.R11APreregistrationError):
                    validator.strict_json_loads('{"value":' + token + '}', "mutation")

    def test_strict_load_rejects_invalid_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_bytes(b'{"x":"\xff"}')
            with self.assertRaises(validator.R11APreregistrationError):
                validator.load(path)

    def test_every_prose_artifact_is_byte_bound(self) -> None:
        validator.validate_prose_hashes()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "normative.md"
            original = b"R11 remains unresolved.\n"
            path.write_bytes(original)
            expected = hashlib.sha256(original).hexdigest()
            validator.validate_prose_hashes({path: expected})
            path.write_bytes(b"R11 is closed.\n")
            with self.assertRaises(validator.R11APreregistrationError):
                validator.validate_prose_hashes({path: expected})


if __name__ == "__main__":
    unittest.main()
