from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
AMENDMENT = BASE / "r11a_v2/R11A_CORRECTIVE_PREREGISTRATION_AMENDMENT.json"
ORIGINAL = BASE / "r11a/R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_PREREGISTRATION.json"
SELECTION = BASE / "r11/R11_72H_SELECTION.json"
PRIOR_RESULT = BASE / "r11_evidence/run-31436753081/r11-result.json"

from governance.validate_r11a_v2_preregistration import (  # noqa: E402
    R11AV2PreregistrationError,
    strict_load,
    validate_document,
)


class R11AV2PreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = strict_load(AMENDMENT)
        cls.original = strict_load(ORIGINAL)
        cls.selection = strict_load(SELECTION)
        cls.prior = strict_load(PRIOR_RESULT)

    def validate(self, document: dict) -> None:
        validate_document(
            document,
            original=self.original,
            selection=self.selection,
            prior_result=self.prior,
        )

    def test_dedicated_validator_passes_normal_and_optimized(self) -> None:
        for args in (
            [sys.executable, "governance/validate_r11a_v2_preregistration.py"],
            [sys.executable, "-O", "governance/validate_r11a_v2_preregistration.py"],
        ):
            completed = subprocess.run(
                args,
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertIn("R11A_V2_PREREGISTRATION_VALID_NO_EXECUTION", completed.stdout)

    def test_amendment_is_explicit_and_does_not_rewrite_original_evidence(self) -> None:
        document = self.document
        self.assertEqual(document["status"], "PREREGISTERED_NO_EXECUTION")
        self.assertEqual(document["independent_review_verdict"], "RED")
        self.assertTrue(document["amendment_scope"]["supersedes_original_runtime_and_retention_design"])
        self.assertTrue(document["amendment_scope"]["preserves_original_scientific_question"])
        self.assertTrue(document["amendment_scope"]["does_not_reinterpret_original_r11_or_r10d_evidence"])
        self.assertFalse(document["owner_approval_eligible_now"])
        self.assertFalse(document["r11_closed"])
        self.assertFalse(document["r12_ready"])

    def test_scope_budget_and_transport_are_unchanged_and_inert(self) -> None:
        scope = self.document["exact_input_scope"]
        envelope = self.document["request_and_resource_envelope"]
        self.assertEqual(scope["selected_object_count"], 72)
        self.assertEqual(scope["complete_utc_day_count"], 3)
        self.assertEqual(scope["selection_sha256"], "7c134f4b62f547904126a5f810c177484dceeffa246d53c5c35944367d563eb2")
        self.assertEqual(envelope["maximum_get_object_requests"], 72)
        self.assertEqual(envelope["maximum_requests_per_object"], 1)
        self.assertEqual(envelope["maximum_retries_per_request"], 0)
        self.assertEqual(envelope["maximum_total_compressed_bytes"], 2107738436)
        self.assertEqual(envelope["maximum_total_decompressed_bytes_across_two_local_passes"], 21079958490)
        self.assertEqual(envelope["maximum_ephemeral_workspace_bytes"], 5368709120)
        self.assertEqual(envelope["maximum_retained_artifact_bytes"], 134217728)
        self.assertEqual(envelope["maximum_one_time_budget_eur_micros"], 500000)
        self.assertTrue(all(value is False for value in self.document["current_runtime_authority"].values()))

    def test_identity_layers_and_taxonomy_remain_exact(self) -> None:
        identity = self.document["identity_model"]
        self.assertEqual(
            identity["protocol_matched_trade_key"],
            ["exact_raw_block_time", "exact_raw_coin_string", "validated_json_integer_tid"],
        )
        self.assertEqual(
            identity["wallet_user_fill_key"],
            [
                "canonical_lowercase_wallet_address",
                "exact_raw_block_time",
                "exact_raw_coin_string",
                "validated_json_integer_tid",
            ],
        )
        self.assertEqual(identity["historical_wallet_plus_typed_tid_key_role"], "DIAGNOSTIC_TRIGGER_ONLY_NOT_CANONICAL_IDENTITY")
        self.assertFalse(identity["deduplication_authorized"])
        self.assertEqual(len(self.document["duplicate_taxonomy"]), 9)
        self.assertIn("UNCLASSIFIABLE", self.document["duplicate_taxonomy"])

    def test_group_wide_predicates_replace_first_current_shortcut(self) -> None:
        predicates = "\n".join(row["predicate"] for row in self.document["group_wide_classification_precedence"])
        self.assertIn("COMPLETE_CANONICAL_WALLET_FILL_GROUP", predicates)
        self.assertIn("COMPLETE_CANONICAL_WALLET_FILL_SUBGROUP", predicates)
        self.assertIn("COMPLETE_LEGACY_WEAK_KEY_GROUP", predicates)
        self.assertNotIn("GROUP_FIRST", predicates)
        self.assertEqual(
            self.document["two_pass_and_reducer_architecture"]["group_processing"],
            "BOUNDED_SPOOL_FILES_WITH_NO_UNBOUNDED_PAYLOAD_LIST",
        )

    def test_global_schema_counts_are_conserved_without_unrelated_row_retention(self) -> None:
        census = self.document["global_schema_census_contract"]
        self.assertTrue(census["all_raw_events_are_counted"])
        self.assertTrue(census["valid_tid_plus_tid_violation_equals_raw_events"])
        self.assertTrue(census["valid_coin_plus_coin_violation_equals_raw_events"])
        self.assertTrue(census["valid_wallet_plus_wallet_violation_equals_raw_events"])
        self.assertTrue(census["first_and_second_pass_counts_and_commitments_must_match"])
        self.assertFalse(census["detailed_rows_for_nonrepeat_singleton_schema_violations_required"])

    def test_failure_artifact_and_terminal_semantics_are_fail_closed(self) -> None:
        artifact = self.document["artifact_contract"]
        failure = self.document["failure_and_runtime_contract"]
        terminals = {row["terminal_class"]: row for row in self.document["terminal_decision_table"]}
        self.assertTrue(artifact["all_scientific_files_are_exact_zero_bytes_on_early_stop_or_cap_fallback"])
        self.assertFalse(artifact["partial_scientific_prefix_authorized"])
        self.assertFalse(artifact["upload_before_local_artifact_validation_authorized"])
        self.assertTrue(failure["every_terminal_path_produces_a_locally_valid_minimal_artifact"])
        self.assertEqual(terminals["R11A_V2_DIAGNOSTIC_INCOMPLETE"]["scientific_output_status"], "COMPLETE")
        self.assertEqual(terminals["R11A_V2_FAIL_CLOSED_EARLY_STOP"]["scientific_output_status"], "EMPTY")

    def test_pricing_snapshot_and_distinct_stage_validators_remain_required(self) -> None:
        self.assertIn(
            "provider_pricing_and_eur_conversion_snapshot_sha256",
            self.document["values_required_before_owner_approval"],
        )
        stages = self.document["stage_separation"]
        validator_paths = [
            value
            for key, value in stages.items()
            if key != "inert_validator_must_not_be_called_by_post_approval_runtime_workflow"
        ]
        self.assertEqual(len(validator_paths), len(set(validator_paths)))
        self.assertTrue(stages["inert_validator_must_not_be_called_by_post_approval_runtime_workflow"])

    def test_authority_scope_and_scientific_mutations_fail_closed(self) -> None:
        mutations: list[tuple[str, callable]] = [
            ("owner approval", lambda d: d.__setitem__("owner_approval_eligible_now", True)),
            ("runtime", lambda d: d["current_runtime_authority"].__setitem__("get_object", True)),
            ("downstream", lambda d: d["downstream_authorizations"].__setitem__("deduplication", True)),
            ("trading", lambda d: d["trading_authorizations"].__setitem__("live", True)),
            ("scope", lambda d: d["exact_input_scope"].__setitem__("selected_object_count", 73)),
            ("retry", lambda d: d["request_and_resource_envelope"].__setitem__("maximum_retries_per_request", 1)),
            ("weak key", lambda d: d["identity_model"].__setitem__("historical_wallet_plus_typed_tid_key_role", "CANONICAL_IDENTITY")),
            ("dedup", lambda d: d["identity_model"].__setitem__("deduplication_authorized", True)),
            ("partial science", lambda d: d["artifact_contract"].__setitem__("partial_scientific_prefix_authorized", True)),
            ("constant proof", lambda d: d["required_conservation_and_proof_gates"].__setitem__("all_proof_references_resolve_must_be_computed_not_constant", False)),
            ("lifecycle", lambda d: d.__setitem__("r12_ready", True)),
        ]
        for label, mutate in mutations:
            with self.subTest(label=label):
                document = copy.deepcopy(self.document)
                mutate(document)
                with self.assertRaises(R11AV2PreregistrationError):
                    self.validate(document)

    def test_extra_missing_and_type_drift_fail_closed(self) -> None:
        extra = copy.deepcopy(self.document)
        extra["unexpected"] = False
        missing = copy.deepcopy(self.document)
        del missing["scientific_question"]
        wrong_type = copy.deepcopy(self.document)
        wrong_type["original_r11_run_id"] = str(wrong_type["original_r11_run_id"])
        for document in (extra, missing, wrong_type):
            with self.assertRaises(R11AV2PreregistrationError):
                self.validate(document)

    def test_strict_loader_rejects_duplicate_keys_and_nonfinite(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            duplicate = root / "duplicate.json"
            duplicate.write_text('{"a":1,"a":2}\n', encoding="utf-8")
            nonfinite = root / "nonfinite.json"
            nonfinite.write_text('{"a":NaN}\n', encoding="utf-8")
            for path in (duplicate, nonfinite):
                with self.assertRaises(R11AV2PreregistrationError):
                    strict_load(path)

    def test_no_v2_runtime_files_exist_during_preregistration(self) -> None:
        self.assertFalse((ROOT / ".github/workflows/hyperliquid-archive-r11a-v2-identity-boundary-diagnostic.yml").exists())
        self.assertFalse((BASE / "r11a_v2_approval").exists())
        self.assertFalse((BASE / "r11a_v2_runtime").exists())
        self.assertFalse((BASE / "r11a_v2_evidence").exists())


if __name__ == "__main__":
    unittest.main()
