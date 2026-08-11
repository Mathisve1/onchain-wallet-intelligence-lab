from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREREG = BASE / "r11a/R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_PREREGISTRATION.json"
DOSSIER = BASE / "r11a/R11A_IDENTITY_DECISION_DOSSIER.json"
ROOT_CAUSE = BASE / "r11a/R11_ROOT_CAUSE_STATUS.json"
SELECTION = BASE / "r11/R11_72H_SELECTION.json"
R11_RESULT = BASE / "r11_evidence/run-31436753081/r11-result.json"
R11_CONSUMPTION = BASE / "r11_runtime/R11_EXECUTION_RELEASE_CONSUMPTION.json"

ID = "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-001"
SELECTION_SHA256 = "7c134f4b62f547904126a5f810c177484dceeffa246d53c5c35944367d563eb2"
RESULT_SHA256 = "9d3266eb53791d83df29b6ec3ae5f33c254b29a8182f2e6be7e3261c02686862"
CONSUMPTION_SHA256 = "e00ac71726fa6f28efed741ed1d83c4ad323d9cde1aad2d101a50195bd4256d0"
PREREG_BYTE_SHA256 = "5203742b86695d935604c60739dedb95c563df515fca97b5cc56647a5f800b91"
DOSSIER_BYTE_SHA256 = "e994116d5c672369271e2525df83f9c0a3d3c1bddf4ba2f51df6a4f4e39daf31"
ROOT_CAUSE_BYTE_SHA256 = "cb4e77ad3a21d2b6ba7dc6a3d775e16b5607468118ba288be30158c2ccad0935"
PREREG_SEMANTIC_SHA256 = "a2f05d4b0d6dfa4cd9367c23b528cfb81be9c020f6901552ef509164d66bfb6c"
DOSSIER_SEMANTIC_SHA256 = "11e942eb1a0c89e5d12e341a45131f2ab06ff8bf186123a69a40257831209a41"
ROOT_CAUSE_SEMANTIC_SHA256 = "079c581d694e60ee09fce8221d43bc5b9ac7574e7686b23006fba8354deee10f"
SELECTION_SEMANTIC_SHA256 = "3126c0954a52c62001f5df0ed2ba8a014302d23a7bf52e150ffb4067400a2212"
RESULT_SEMANTIC_SHA256 = "c709d8d60dd2b69c9d324bd86ae1072325e5220054d33125c1d0ca31a62fab5b"
CONSUMPTION_SEMANTIC_SHA256 = "82e59bd76c78a6cf05ac78ae761f41362bd7e5b8f80ffc089ef13c2bd91ae6af"

PROSE_SHA256 = {
    BASE / "r11a/R11A_IDENTITY_DECISION_DOSSIER.md": "4debdcfb89107de26e70d0bd048b6be811c48289aa448952b69b3eecc6316ca7",
    BASE / "r11a/R11_ROOT_CAUSE_STATUS.md": "61a66e96d9b0c09bd63b2425afcc1374f6e7c30bdff0aaf69d489a8fee0ecea4",
    BASE / "r11a/R11_REPAIR_ARCHITECTURE.md": "40821219fadaf4a63fd8e67a34a0321f8dab2acd8cfc80755865244477ee0d00",
    BASE / "r11a/R11A_GOVERNANCE_AND_EVIDENCE_CLOSURE_CHECKLIST.md": "35abe126fbaa2c04871933184bb0f6ac5349f9986a75587f8387beffa056ae27",
    BASE / "r11a/README.md": "9331b008d6bd8a3aacb81d88cd9c85be1f2b6c0bde32e6458964ea44964ab2c6",
}

EXPECTED_TOP_LEVEL_KEYS = {
    "allowed_terminal_classes",
    "canonical_r11_evidence_closure_binding",
    "conservation_invariants",
    "current_runtime_authority",
    "diagnostic_id",
    "diagnostic_passes",
    "diagnostic_rows_created_by_preregistration",
    "downstream_authorizations",
    "duplicate_taxonomy",
    "exact_input_scope",
    "execution_authorized_now",
    "future_implementation_contract_requirements",
    "global_output_contract",
    "governance_gates",
    "iam_and_session_boundary",
    "identity_contract",
    "implementation_values_bound_before_owner_approval",
    "network_requests_executed_by_preregistration",
    "object_bytes_read_by_preregistration",
    "occurrence_record_contract",
    "owner_approval_status",
    "parent_r11_run",
    "pilot_id",
    "proof_and_classification_contract",
    "proposed_request_envelope",
    "required_global_outputs",
    "required_occurrence_fields",
    "research_question",
    "retention_and_privacy",
    "schema_version",
    "status",
    "stop_conditions",
    "study_role",
    "taxonomy_decision_contract",
}

EXPECTED_TAXONOMY = [
    "TID_SCOPE_FALSE_POSITIVE",
    "EXPECTED_COUNTERPARTY_PAIR",
    "EXACT_BLOCK_REPLAY_ACROSS_OBJECTS",
    "EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY",
    "CONFLICTING_BLOCK_REPLAY",
    "CONFLICTING_USER_FILL",
    "INTRA_BLOCK_REPEAT",
    "TID_SCHEMA_VIOLATION",
    "UNCLASSIFIABLE",
]

EXPECTED_UNIT_TYPES = [
    "LEGACY_REPEAT_OCCURRENCE",
    "ARCHIVE_BLOCK_NUMBER_GROUP",
    "PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE",
    "RAW_TID_SCHEMA_VIOLATION_OBSERVATION",
    "RAW_COIN_SCHEMA_VIOLATION_OBSERVATION",
    "RAW_WALLET_SCHEMA_VIOLATION_OBSERVATION",
]


class R11APreregistrationError(ValueError):
    pass


@dataclass(frozen=True)
class ExactJSONFloat:
    token: str


def require(condition: bool, message: str) -> None:
    if not condition:
        raise R11APreregistrationError(message)


def exact_json_equal(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(  # type: ignore[arg-type]
            exact_json_equal(actual[key], value)  # type: ignore[index]
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(  # type: ignore[arg-type]
            exact_json_equal(left, right)
            for left, right in zip(actual, expected, strict=True)  # type: ignore[arg-type]
        )
    return actual == expected


def check_exact(actual: object, expected: object, label: str) -> None:
    require(exact_json_equal(actual, expected), f"{label} exact schema, type or value drift")


def strict_json_loads(text: str, label: str) -> object:
    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise R11APreregistrationError(f"{label} contains duplicate key {key}")
            value[key] = item
        return value

    def reject_constant(token: str) -> object:
        raise R11APreregistrationError(f"{label} contains non-finite constant {token}")

    def finite_float(token: str) -> ExactJSONFloat:
        if not math.isfinite(float(token)):
            raise R11APreregistrationError(f"{label} contains non-finite number {token}")
        Decimal(token)
        return ExactJSONFloat(token)

    try:
        return json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_constant,
            parse_float=finite_float,
        )
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise R11APreregistrationError(f"{label} is not strict JSON: {exc}") from exc


def load(path: Path) -> dict[str, Any]:
    try:
        text = path.read_bytes().decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise R11APreregistrationError(f"{path} is not strict UTF-8") from exc
    value = strict_json_loads(text, str(path))
    require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_form(value: object) -> object:
    if value is None:
        return ["null"]
    if type(value) is bool:
        return ["bool", value]
    if type(value) is int:
        return ["int", str(value)]
    if isinstance(value, ExactJSONFloat):
        return ["float-token", value.token]
    if type(value) is str:
        return ["string", value]
    if isinstance(value, list):
        return ["array", [semantic_form(item) for item in value]]
    if isinstance(value, dict):
        return ["object", [[key, semantic_form(item)] for key, item in value.items()]]
    raise R11APreregistrationError(f"unsupported exact JSON value type: {type(value).__name__}")


def semantic_digest(value: object) -> str:
    canonical = json.dumps(
        semantic_form(value),
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_prose_hashes(expected_hashes: dict[Path, str] | None = None) -> None:
    for path, expected in (PROSE_SHA256 if expected_hashes is None else expected_hashes).items():
        require(path.is_file(), f"required D0 prose missing: {path}")
        label = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        require(digest(path) == expected, f"D0 prose byte drift: {label}")


def require_all_false(value: object, label: str) -> None:
    require(isinstance(value, dict) and value, f"{label} must be a nonempty mapping")
    require(all(item is False for item in value.values()), f"{label} contains authority")


def validate(
    prereg: dict[str, Any],
    dossier: dict[str, Any],
    root_cause: dict[str, Any],
    selection: dict[str, Any],
    result: dict[str, Any],
    consumption: dict[str, Any],
) -> None:
    require(semantic_digest(prereg) == PREREG_SEMANTIC_SHA256, "preregistration full mapping drift")
    require(semantic_digest(dossier) == DOSSIER_SEMANTIC_SHA256, "identity dossier full mapping drift")
    require(semantic_digest(root_cause) == ROOT_CAUSE_SEMANTIC_SHA256, "root-cause register full mapping drift")
    require(semantic_digest(selection) == SELECTION_SEMANTIC_SHA256, "selection full mapping drift")
    require(semantic_digest(result) == RESULT_SEMANTIC_SHA256, "R11 result full mapping drift")
    require(semantic_digest(consumption) == CONSUMPTION_SEMANTIC_SHA256, "R11 consumption full mapping drift")
    require(set(prereg) == EXPECTED_TOP_LEVEL_KEYS, "preregistration top-level schema drift")

    require(prereg["schema_version"] == "1.0", "preregistration schema version drift")
    require(prereg["diagnostic_id"] == prereg["pilot_id"] == ID, "diagnostic identity drift")
    require(prereg["status"] == "PREREGISTERED_NO_EXECUTION", "preregistration status drift")
    require(prereg["owner_approval_status"] == "NOT_PRESENT", "owner approval overclaim")
    require(prereg["execution_authorized_now"] is False, "execution authority overclaim")
    require(prereg["network_requests_executed_by_preregistration"] == 0, "network execution overclaim")
    require(prereg["object_bytes_read_by_preregistration"] == 0, "object-read overclaim")
    require(prereg["diagnostic_rows_created_by_preregistration"] == 0, "diagnostic execution overclaim")
    require_all_false(prereg["current_runtime_authority"], "current runtime authority")
    require_all_false(prereg["downstream_authorizations"], "downstream authority")
    require(prereg["governance_gates"]["execution_authorized_by_this_preregistration"] is False, "gate execution authority")
    require(prereg["governance_gates"]["r11b_repair_authorized_by_r11a"] is False, "repair authority")

    closure = prereg["canonical_r11_evidence_closure_binding"]
    require(closure["pull_request_number"] == 139, "R11 closure PR drift")
    require(closure["canonical_merge_commit_sha"] == "f7aa612d2a5638cce0fd197f57efea4b787f87f1", "R11 closure merge drift")
    require(closure["binding_complete"] is True and closure["binding_is_owner_approval"] is False, "closure authority drift")

    scope = prereg["exact_input_scope"]
    require(scope["canonical_selection_sha256"] == SELECTION_SHA256, "selection binding drift")
    require(scope["selection_file_sha256"] == SELECTION_SHA256, "selection byte binding drift")
    require(scope["prior_result_sha256"] == RESULT_SHA256, "R11 result binding drift")
    require(scope["selected_object_count"] == scope["selected_hour_count"] == 72, "72-object scope drift")
    require(scope["complete_utc_day_count"] == 3, "three-day scope drift")
    require(scope["seventy_third_object_authorized"] is False, "73rd object authority")
    require(scope["other_historical_window_authorized"] is False, "historical expansion authority")
    require(selection["selection_id"] == scope["selection_id"], "selection identity mismatch")
    require(len(selection["exact_targets"]) == 72, "canonical target count drift")
    require(selection["selected_hour_count"] == 72 and selection["complete_utc_day_count"] == 3, "canonical selection scope drift")

    identity = prereg["identity_contract"]
    layers = dossier["identity_layers"]
    require(dossier["decision_id"] == identity["decision_id"], "identity decision binding drift")
    check_exact(layers["raw_observation"]["canonical_key"], identity["raw_observation_key"], "raw identity layer")
    require(layers["archive_block"]["locator"] == identity["archive_block_locator"], "block locator drift")
    check_exact(layers["archive_block"]["equality_invariants"], identity["archive_block_equality_invariants"], "block invariants")
    check_exact(layers["protocol_matched_trade"]["canonical_key"], identity["protocol_matched_trade_key"], "protocol identity")
    check_exact(layers["wallet_user_fill"]["canonical_key"], identity["wallet_user_fill_key"], "wallet-fill identity")
    require(identity["tid_schema_contract"]["maximum_exclusive"] == 2**50, "uint50 bound drift")
    require(identity["coin_identity_contract"]["canonical_identity_value"] == "EXACT_RAW_COIN_STRING", "raw coin identity drift")
    require(identity["canonical_serialization_contract"]["implementation_must_match_ALL_FROZEN_GOLDEN_VECTORS_AND_EXACT_SCHEMA_HASH_BEFORE_OWNER_APPROVAL"] is True, "serialization freeze missing")
    require(len(identity["canonical_serialization_contract"]["frozen_golden_vectors"]) == 7, "golden vector set drift")

    require(prereg["duplicate_taxonomy"] == EXPECTED_TAXONOMY, "taxonomy vocabulary drift")
    require(dossier["duplicate_taxonomy"] == EXPECTED_TAXONOMY, "dossier taxonomy drift")
    unit_contract = prereg["proof_and_classification_contract"]["taxonomy_unit_ledger_record_contract"]
    require(unit_contract["taxonomy_unit_type_exact_values"] == EXPECTED_UNIT_TYPES, "taxonomy unit vocabulary drift")
    raw_locator = prereg["proof_and_classification_contract"]["raw_block_locator_contract"]
    require(raw_locator["exact_fields"] == ["source_object_key", "compressed_object_sha256", "record_ordinal_zero_based"], "raw block locator drift")
    require("block_number" not in raw_locator["exact_fields"], "semantic block number leaked into raw locator")

    object_contract = prereg["proof_and_classification_contract"]["object_transport_and_two_pass_conservation_ledger_record_contract"]
    require("BODY_READ_FAILED_AFTER_RESPONSE_METADATA" in object_contract["processing_status_exact_values"], "partial body state missing")
    reducer = prereg["proof_and_classification_contract"]["reducer_partition_conservation_ledger_record_contract"]
    require(reducer["reducer_processing_order"] == ["BLOCK_NUMBER", "HISTORICAL_LEGACY_WEAK_KEY"], "reducer order drift")
    require(reducer["sorted_stream_must_be_an_EXACT_BYTE_FOR_BYTE_MULTISET_PERMUTATION_OF_THE_UNSORTED_ENCODED_RECORDS_WITH_IDENTICAL_MULTIPLICITIES_AND_NO_ADDITION_LOSS_OR_MUTATION"] is True, "reducer multiset conservation missing")

    global_contract = prereg["global_output_contract"]
    layout = global_contract["artifact_layout_contract"]
    reference_shape = layout["result_file_container_reference_shape"]
    require("NEVER_REFERENCES_ITS_OWN_BYTES_OR_HASH" in reference_shape, "result self-reference not forbidden")
    require("hash_manifest" in reference_shape and "package_boundary" in reference_shape, "late package exclusions missing")
    require(layout["acyclic_sealing_order"][-2:] == ["hash_manifest", "package_boundary_record"], "package sealing order drift")
    resource = global_contract["resource_and_cap_conservation_ledger_contract"]
    require("scientific_output_logical_status" in resource["exact_fields"], "scientific status field missing")
    require("projected_scientific_output_entry_ledger" in resource["exact_fields"], "projected science ledger missing")
    check_exact(
        resource["metadata_projection_mode_exact_values"],
        [
            "NONRETENTION_EARLY_ONLY_CONTEXT",
            "COMPLETE_WITH_REACHABLE_CAP_SUCCESSOR_CONTEXT",
            "CAP_ONLY_CONTEXT",
        ],
        "metadata projection contexts",
    )
    require(
        "EVERY_OTHER_NONAPPLICABLE_VALUE_IS_EXACT_JSON_NULL" in resource["metadata_variant_byte_count_rules"],
        "nonapplicable metadata variants are not null",
    )
    require(
        set(resource["predecision_template_contract"])
        == {
            "template_is_counterfactual_and_never_uploaded_or_claimed_as_observed_evidence",
            "NONRETENTION_EARLY_STOP_EMPTY_template",
            "RETENTION_COUNT_OR_GROUP_CAP_EMPTY_template",
            "STREAMING_ARTIFACT_CAP_PREFIX_template",
            "COMPLETE_template",
            "artifact_cap_row_inside_each_template",
            "all_other_fields",
            "decision_rule",
            "cap_variant_must_never_reenter_or_reverse_this_predecision",
        },
        "predecision template schema drift",
    )
    require(
        "NO_NONRETENTION_STOP_BEFORE_THE_ATOMIC_COMPLETE_SCIENCE_COMMIT" in resource["metadata_projection_mode_derivation"]
        and "POST_COMMIT_FINAL_TAXONOMY_OR_CONSERVATION_TRIGGER_IS_ALLOWED" in resource["metadata_projection_mode_derivation"],
        "complete metadata context stop boundary drift",
    )
    require(
        "NO_NONRETENTION_STOP_BEFORE_THE_ATOMIC_COMPLETE_SCIENCE_COMMIT" in resource["final_staging_projection_kind_derivation"]
        and "POST_COMMIT_FINAL_TAXONOMY_OR_CONSERVATION_TRIGGER_IS_EXPLICITLY_ALLOWED" in resource["final_staging_projection_kind_derivation"],
        "full projection stop boundary drift",
    )
    require(resource["post_measurement_packaging_reservation_milliseconds_exact"] == 300000, "runtime packaging reserve drift")
    require("BUDGET_CAP_EXCEEDED" in prereg["stop_conditions"], "cost stop route missing")
    require(resource["cap_comparator_by_key"].find("runtime_milliseconds_IS_exceeded_IFF_observed_GREATER_THAN_OR_EQUAL") >= 0, "runtime comparator drift")
    require(global_contract["incomplete_and_cap_output_applicability_contract"]["all_required_global_output_keys_are_present_for_every_terminal_even_when_the_exact_value_is_null_by_this_contract"] is True, "incomplete output schema missing")
    preflight = global_contract["preflight_and_stop_evidence_ledger_contract"]
    require(
        preflight["phase_check_order"].startswith("INITIAL_RUNTIME_PASS_THEN_ONE_BOOTSTRAP_WORKSPACE_CHECK"),
        "bootstrap runtime/workspace order drift",
    )
    require(
        "INTEGER_0_FOR_THE_INITIAL_RUNTIME_PASS" in preflight["global_evaluation_step_ordinal_rule"]
        and "INTEGER_1_FOR_THE_POST_PLACEHOLDER_BOOTSTRAP_WORKSPACE_CHECK" in preflight["global_evaluation_step_ordinal_rule"],
        "bootstrap evaluation ordinal drift",
    )
    failure_nullability = preflight["parse_failure_record_ordinal_nullability_by_failure_code"]
    check_exact(
        failure_nullability["record_ordinal_must_be_null"],
        [
            "LZ4_DECOMPRESSION_FAILURE",
            "DECOMPRESSED_UTF8_FAILURE",
            "BLANK_OR_WHITESPACE_ONLY_NDJSON_RECORD",
        ],
        "stream-level parse failure locator nullability",
    )
    require(
        set(failure_nullability["record_ordinal_must_be_null"])
        .isdisjoint(failure_nullability["record_ordinal_must_be_nonnegative_json_integer"]),
        "parse failure locator classes overlap",
    )
    require(
        set(failure_nullability["record_ordinal_must_be_null"])
        | set(failure_nullability["record_ordinal_must_be_nonnegative_json_integer"])
        == set(preflight["parse_failure_code_exact_values"]),
        "parse failure locator classes do not cover the exact failure vocabulary",
    )
    block_aggregate = global_contract["block_reducer_aggregate_derivation_contract"]
    require(
        "raw_block_observation_count_IS_ALWAYS_THE_NONNULL_SOURCE_LEDGER_PREFIX_SUM" in block_aggregate["applicability"],
        "raw block source-prefix applicability drift",
    )
    require(
        "IFF_ALL_256_BLOCK_NUMBER_PARTITIONS_ARE_COMPLETE" in block_aggregate["raw_block_observation_count"],
        "raw block reducer equality gate missing",
    )
    matrix_scope = prereg["proof_and_classification_contract"]["complete_block_overlap_matrix_record_contract"]["record_scope"]
    require(
        "RETENTION_CAP_FALLBACK_EMPTY_OR_EARLY_STOP_EMPTY" in matrix_scope,
        "empty-science block matrix scope drift",
    )
    duplicate_contract = prereg["proof_and_classification_contract"]["duplicate_observation_output_record_contract"]
    require(
        any("RETENTION_CAP_FALLBACK_EMPTY_OR_EARLY_STOP_EMPTY" in key for key in duplicate_contract),
        "empty-science duplicate scope drift",
    )
    materialization = prereg["proof_and_classification_contract"]["taxonomy_unit_universe_materialization_contract"]
    require(
        "scientific_output_logical_status_RETENTION_CAP_FALLBACK_EMPTY_OR_EARLY_STOP_EMPTY" in materialization,
        "empty-science taxonomy scope drift",
    )
    boundary = global_contract["package_boundary_record_contract"]
    require(boundary["exact_byte_count"] == 1024, "package boundary byte count drift")
    boundary_literal_bytes = len("|".join(boundary["exact_line_fields_in_order"]).encode("ascii")) + 1
    require(boundary_literal_bytes <= boundary["exact_byte_count"], "package boundary fields exceed fixed record")
    require(
        "INITIAL_RUNTIME_PASS_AT_GLOBAL_STEP_0" in boundary["boundary_placeholder_allocation_contract"]
        and "WORKSPACE_CAP_CHECK_AT_GLOBAL_STEP_1" in boundary["boundary_placeholder_allocation_contract"],
        "package bootstrap evidence order drift",
    )
    require(prereg["proposed_request_envelope"]["maximum_retained_artifact_bytes"] == 134217728, "artifact cap drift")
    require(prereg["proposed_request_envelope"]["maximum_retained_scientific_output_bytes"] == 134217728, "stricter science cap introduced")

    parent = prereg["parent_r11_run"]
    require(parent["run_id"] == 31436753081 and parent["artifact_id"] == 9082810554, "parent R11 identity drift")
    require(parent["release_consumed"] is True and parent["rerun_authorized"] is False, "parent release reopened")
    require(result["research_conclusion"] == "R11_72H_PERSISTENCE_PIPELINE_UNRESOLVED", "parent result closure overclaim")
    require(result["aggregate_wallet_feature_summary"] is None, "parent aggregate evidence drift")
    require(consumption["release_consumed"] is True, "parent release consumption drift")
    require(consumption["remaining_get_object_budget_from_consumed_release"] == 0, "parent request budget reopened")
    require(consumption["future_r11_dispatch_authorized"] is False and consumption["rerun_authorized"] is False, "parent execution reopened")
    require(consumption["duplicate_root_cause_known"] is False, "parent root-cause overclaim")
    require(consumption["new_network_request_requires_new_preregistration_owner_approval_and_release"] is True, "new gate removed")
    require_all_false(consumption["downstream_authorizations"], "parent downstream authority")
    require_all_false(consumption["trading_authorizations"], "parent trading authority")

    require(root_cause["required_empirical_gate"] == ID, "root-cause gate drift")
    require(root_cause["root_cause_claim_authorized_now"] is False, "root-cause overclaim")
    require(root_cause["repair_selection_authorized_now"] is False, "repair overclaim")
    require(root_cause["r11_closed"] is False and root_cause["r12_ready"] is False, "lifecycle overclaim")
    findings = root_cause["finding_register"]
    finding_ids = [row["finding"] for row in findings]
    require(len(finding_ids) == len(set(finding_ids)), "duplicate root-cause finding identifier")


def main() -> int:
    require(digest(PREREG) == PREREG_BYTE_SHA256, "preregistration byte drift")
    require(digest(DOSSIER) == DOSSIER_BYTE_SHA256, "identity dossier byte drift")
    require(digest(ROOT_CAUSE) == ROOT_CAUSE_BYTE_SHA256, "root-cause register byte drift")
    require(digest(SELECTION) == SELECTION_SHA256, "canonical selection byte drift")
    require(digest(R11_RESULT) == RESULT_SHA256, "canonical R11 result byte drift")
    require(digest(R11_CONSUMPTION) == CONSUMPTION_SHA256, "canonical R11 consumption byte drift")
    validate_prose_hashes()
    validate(load(PREREG), load(DOSSIER), load(ROOT_CAUSE), load(SELECTION), load(R11_RESULT), load(R11_CONSUMPTION))
    print("R11A_PREREGISTRATION_VALID_NO_EXECUTION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
