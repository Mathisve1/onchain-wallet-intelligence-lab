#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AMENDMENT = ROOT / "research/archive_inventory/r11a_v2/R11A_CORRECTIVE_PREREGISTRATION_AMENDMENT.json"
ORIGINAL = ROOT / "research/archive_inventory/r11a/R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_PREREGISTRATION.json"
SELECTION = ROOT / "research/archive_inventory/r11/R11_72H_SELECTION.json"
PRIOR_RESULT = ROOT / "research/archive_inventory/r11_evidence/run-31436753081/r11-result.json"
INSTALLED_WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-r11a-v2-identity-boundary-diagnostic.yml"
APPROVAL_ROOT = ROOT / "research/archive_inventory/r11a_v2_approval"
RUNTIME_ROOT = ROOT / "research/archive_inventory/r11a_v2_runtime"
EVIDENCE_ROOT = ROOT / "research/archive_inventory/r11a_v2_evidence"

EXPECTED_TOP_LEVEL = {
    "schema_version",
    "amendment_id",
    "diagnostic_id",
    "status",
    "canonical_parent_commit",
    "original_preregistration_merge_commit",
    "original_inert_implementation_merge_commit",
    "failed_closure_attempt_merge_commit",
    "containment_merge_commit",
    "original_r11_run_id",
    "original_r11_artifact_id",
    "original_r11_artifact_sha256",
    "independent_review_verdict",
    "owner_approval_eligible_now",
    "amendment_scope",
    "reason_for_amendment",
    "scientific_question",
    "exact_input_scope",
    "request_and_resource_envelope",
    "identity_model",
    "duplicate_taxonomy",
    "authoritative_unit_universes",
    "global_schema_census_contract",
    "group_wide_classification_precedence",
    "block_group_precedence",
    "expected_counterparty_pair_predicate",
    "two_pass_and_reducer_architecture",
    "artifact_contract",
    "required_conservation_and_proof_gates",
    "terminal_decision_table",
    "failure_and_runtime_contract",
    "stage_separation",
    "values_required_before_owner_approval",
    "current_runtime_authority",
    "downstream_authorizations",
    "trading_authorizations",
    "network_requests_executed_by_this_amendment",
    "aws_iam_mutations_executed_by_this_amendment",
    "diagnostic_rows_created_by_this_amendment",
    "wallet_feature_rows_created_by_this_amendment",
    "r11_closed",
    "r12_ready",
    "empirical_result",
}

TAXA = [
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


class R11AV2PreregistrationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise R11AV2PreregistrationError(message)


def strict_load(path: Path) -> dict[str, Any]:
    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise R11AV2PreregistrationError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    def reject_constant(token: str) -> Any:
        raise R11AV2PreregistrationError(f"non-finite JSON constant in {path}: {token}")

    try:
        value = json.loads(
            path.read_text(encoding="utf-8", errors="strict"),
            object_pairs_hook=pairs_hook,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise R11AV2PreregistrationError(f"strict JSON read failed for {path}: {exc}") from exc
    require(isinstance(value, dict), f"JSON root must be object: {path}")
    return value


def validate_document(
    document: dict[str, Any],
    *,
    original: dict[str, Any],
    selection: dict[str, Any],
    prior_result: dict[str, Any],
) -> None:
    require(set(document) == EXPECTED_TOP_LEVEL, "amendment top-level schema drift")
    require(document["schema_version"] == "1.0", "schema version drift")
    require(document["amendment_id"] == "R11A-CORRECTIVE-PREREGISTRATION-AMENDMENT-002", "amendment id drift")
    require(document["diagnostic_id"] == "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-002", "diagnostic id drift")
    require(document["status"] == "PREREGISTERED_NO_EXECUTION", "amendment is not inert")
    require(document["canonical_parent_commit"] == "57566456624eb758049aa7687bdb7b8a2844c91d", "canonical parent drift")
    require(document["original_preregistration_merge_commit"] == "5103c846be8a53732d8559a281ac8b57ce4d7aac", "original preregistration lineage drift")
    require(document["original_inert_implementation_merge_commit"] == "8e778fdf6e7b5ef5475791bd4292b2d04055afcd", "PR141 lineage drift")
    require(document["failed_closure_attempt_merge_commit"] == "4bb3eaf4cbcfea7771261ade73d618912496585a", "failed closure lineage drift")
    require(document["containment_merge_commit"] == "57566456624eb758049aa7687bdb7b8a2844c91d", "containment lineage drift")
    require(document["original_r11_run_id"] == 31436753081, "R11 run binding drift")
    require(document["original_r11_artifact_id"] == 9082810554, "R11 artifact binding drift")
    require(document["original_r11_artifact_sha256"] == "45ee57df7a63561bef1772d8612d5fe32b06b9c407d9c1464ce0a02b65a15cc5", "R11 artifact digest drift")
    require(document["independent_review_verdict"] == "RED", "independent review verdict drift")
    require(document["owner_approval_eligible_now"] is False, "owner approval opened")

    scope = document["amendment_scope"]
    require(isinstance(scope, dict), "amendment scope absent")
    require(all(value is True for value in scope.values()), "amendment scope contains an unacknowledged false boundary")
    reason = document["reason_for_amendment"]
    require(isinstance(reason, dict), "amendment rationale absent")
    require(all(value is True for value in reason.values()), "amendment rationale drift")

    inputs = document["exact_input_scope"]
    require(inputs["selection_sha256"] == "7c134f4b62f547904126a5f810c177484dceeffa246d53c5c35944367d563eb2", "selection digest drift")
    require(inputs["prior_result_sha256"] == "9d3266eb53791d83df29b6ec3ae5f33c254b29a8182f2e6be7e3261c02686862", "prior result digest drift")
    require(inputs["selected_object_count"] == inputs["selected_hour_count"] == 72, "72-object/hour scope drift")
    require(inputs["complete_utc_day_count"] == 3, "three-day scope drift")
    require(inputs["window_start_utc"] == "2025-07-28T00:00:00Z", "window start drift")
    require(inputs["window_end_exclusive_utc"] == "2025-07-31T00:00:00Z", "window end drift")
    require(inputs["target_bucket"] == "hl-mainnet-node-data", "target bucket drift")
    require(inputs["signing_region"] == "ap-northeast-1", "signing region drift")
    require(inputs["seventy_third_object_authorized"] is False, "73rd object opened")
    require(inputs["other_historical_window_authorized"] is False, "historical expansion opened")

    exact_targets = selection.get("exact_targets")
    require(isinstance(exact_targets, list) and len(exact_targets) == 72, "canonical selection is not exact 72")
    require(len({row["key"] for row in exact_targets if isinstance(row, dict) and "key" in row}) == 72, "selection object keys are not unique")
    require(selection.get("selected_hour_count") == 72, "selection hour count drift")
    require(selection.get("complete_utc_day_count") == 3, "selection day count drift")
    require(selection.get("aggregate_expected_compressed_bytes") == 2107738436, "selection compressed bytes drift")
    require(prior_result.get("completed_hour_count") == 72, "prior result did not complete 72 hours")
    require(prior_result.get("completed_day_count") == 3, "prior result did not complete three days")
    require(prior_result.get("total_compressed_bytes") == 2107738436, "prior compressed bytes drift")
    require(prior_result.get("total_decompressed_bytes") == 10539979245, "prior decompressed bytes drift")

    envelope = document["request_and_resource_envelope"]
    expected_envelope = {
        "maximum_one_time_budget_eur_micros": 500000,
        "maximum_monthly_budget_eur_micros": 0,
        "maximum_get_object_requests": 72,
        "maximum_requests_per_object": 1,
        "maximum_retries_per_request": 0,
        "maximum_total_compressed_bytes": 2107738436,
        "maximum_individual_compressed_bytes": 76616104,
        "maximum_total_decompressed_bytes_across_two_local_passes": 21079958490,
        "maximum_individual_decompressed_bytes_per_pass": 536870912,
        "maximum_ephemeral_workspace_bytes": 5368709120,
        "minimum_free_workspace_bytes_before_oidc": 6442450944,
        "maximum_retained_artifact_bytes": 134217728,
        "reserved_non_scientific_package_metadata_bytes": 4194304,
        "maximum_retained_scientific_output_bytes": 130023424,
        "maximum_runtime_seconds": 21600,
        "post_measurement_packaging_reservation_seconds": 300,
        "minimum_upload_window_seconds": 60,
        "partition_count": 256,
        "external_sort_memory_bytes": 67108864,
        "maximum_retained_repeated_legacy_groups": 100000,
        "maximum_retained_repeated_legacy_observations": 250000,
        "maximum_retained_repeated_block_groups": 100000,
        "maximum_single_group_spool_bytes": 67108864,
        "request_order": "PATH_HOUR_ASCENDING",
        "stop_after_first_transport_integrity_or_parse_failure": True,
        "requester_pays_required": True,
        "if_match_etag_required": True,
        "exact_response_etag_required": True,
        "exact_content_length_required": True,
        "preknown_compressed_sha256_required": True,
        "http_redirect_following_authorized": False,
        "head_object_authorized": False,
        "range_get_authorized": False,
        "list_objects_v2_authorized": False,
        "list_object_versions_authorized": False,
        "list_all_my_buckets_authorized": False,
        "get_object_attributes_authorized": False,
        "get_object_version_authorized": False,
    }
    require(envelope == expected_envelope, "request/resource envelope drift")
    require(envelope["maximum_retained_scientific_output_bytes"] + envelope["reserved_non_scientific_package_metadata_bytes"] == envelope["maximum_retained_artifact_bytes"], "artifact subcaps do not sum exactly")
    require(envelope["minimum_free_workspace_bytes_before_oidc"] >= envelope["maximum_ephemeral_workspace_bytes"], "free-space threshold below workspace cap")
    require(envelope["post_measurement_packaging_reservation_seconds"] + envelope["minimum_upload_window_seconds"] < envelope["maximum_runtime_seconds"], "runtime leaves no packaging/upload reserve")

    identity = document["identity_model"]
    require(identity["protocol_matched_trade_key"] == ["exact_raw_block_time", "exact_raw_coin_string", "validated_json_integer_tid"], "protocol identity drift")
    require(identity["wallet_user_fill_key"] == ["canonical_lowercase_wallet_address", "exact_raw_block_time", "exact_raw_coin_string", "validated_json_integer_tid"], "wallet-fill identity drift")
    require(identity["historical_wallet_plus_typed_tid_key_role"] == "DIAGNOSTIC_TRIGGER_ONLY_NOT_CANONICAL_IDENTITY", "legacy weak key became canonical")
    for key in ("payload_hash_only_identity_authorized", "deduplication_authorized", "first_seen_wins_authorized", "last_seen_wins_authorized"):
        require(identity[key] is False, f"forbidden identity behavior opened: {key}")
    require(document["duplicate_taxonomy"] == TAXA, "nine-taxon vocabulary drift")

    units = document["authoritative_unit_universes"]
    require(set(units) == {
        "LEGACY_REPEAT_OCCURRENCE",
        "ARCHIVE_BLOCK_NUMBER_GROUP",
        "PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE",
        "REPEAT_INTERSECTING_TID_SCHEMA_VIOLATION",
        "REPEAT_INTERSECTING_COIN_SCHEMA_VIOLATION",
        "REPEAT_INTERSECTING_WALLET_SCHEMA_VIOLATION",
    }, "authoritative unit universes drift")
    census = document["global_schema_census_contract"]
    require(census["all_raw_events_are_counted"] is True, "global event census disabled")
    require(census["first_and_second_pass_counts_and_commitments_must_match"] is True, "two-pass schema commitment equality disabled")
    require(census["detailed_rows_for_nonrepeat_singleton_schema_violations_required"] is False, "amendment did not narrow singleton schema rows")

    precedence = document["group_wide_classification_precedence"]
    require([row["priority"] for row in precedence] == list(range(1, 8)), "group-wide precedence priorities drift")
    require([row["taxon"] for row in precedence] == [
        "TID_SCHEMA_VIOLATION",
        "UNCLASSIFIABLE",
        "CONFLICTING_USER_FILL",
        "INTRA_BLOCK_REPEAT",
        "EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY",
        "TID_SCOPE_FALSE_POSITIVE",
        "UNCLASSIFIABLE",
    ], "group-wide precedence taxa drift")
    require(all("COMPLETE" in row["predicate"] or row["taxon"] in {"TID_SCHEMA_VIOLATION", "UNCLASSIFIABLE"} for row in precedence), "group-wide predicates regressed to pairwise shortcuts")

    architecture = document["two_pass_and_reducer_architecture"]
    require(architecture["single_network_download_per_object"] is True, "second network download opened")
    require(architecture["external_sort_multiset_verification"] == "EXACT_SQLITE_BLOB_MULTIPLICITY_LEDGER_PER_PARTITION_THEN_DELETE", "exact multiset verifier drift")
    require(architecture["group_processing"] == "BOUNDED_SPOOL_FILES_WITH_NO_UNBOUNDED_PAYLOAD_LIST", "unbounded group materialization reopened")
    require(architecture["all_workspace_files_live_under_one_metered_root"] is True, "artifact/workspace split reopened")

    artifacts = document["artifact_contract"]
    require(len(artifacts["scientific_containers"]) == 7, "scientific container count drift")
    require(len(set(artifacts["scientific_containers"])) == 7, "duplicate scientific path")
    require(len(set(artifacts["metadata_containers"])) == len(artifacts["metadata_containers"]), "duplicate metadata path")
    for key in (
        "wallet_feature_file_must_be_exact_zero_bytes",
        "scientific_output_is_streamed_to_staging_files",
        "all_scientific_files_are_exact_zero_bytes_on_early_stop_or_cap_fallback",
        "partial_scientific_prefix_authorized",
        "upload_before_local_artifact_validation_authorized",
        "atomic_commit_occurs_only_after_all_local_validations_pass",
        "post_commit_failure_must_remove_final_directory_or_fail_the_job_before_upload",
    ):
        expected = False if key in {"partial_scientific_prefix_authorized", "upload_before_local_artifact_validation_authorized"} else True
        require(artifacts[key] is expected, f"artifact boundary drift: {key}")

    gates = document["required_conservation_and_proof_gates"]
    require(all(value is True for value in gates.values()), "a required conservation/proof gate was disabled")
    terminals = document["terminal_decision_table"]
    require([row["priority"] for row in terminals] == [1, 2, 3, 4], "terminal precedence drift")
    require([row["terminal_class"] for row in terminals] == [
        "R11A_V2_ARTIFACT_CAP_EXCEEDED",
        "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE",
        "R11A_V2_DIAGNOSTIC_INCOMPLETE",
        "R11A_V2_FAIL_CLOSED_EARLY_STOP",
    ], "terminal classes drift")
    require(terminals[0]["scientific_output_status"] == "EMPTY", "cap terminal retains science")
    require(terminals[2]["scientific_output_status"] == "COMPLETE", "fully processed incomplete taxonomy mislabeled empty")
    require(terminals[3]["scientific_output_status"] == "EMPTY", "early stop retains science")

    failure = document["failure_and_runtime_contract"]
    require(all(value is True for value in failure.values()), "failure/runtime fail-closed contract weakened")
    stages = document["stage_separation"]
    require(stages["inert_validator_must_not_be_called_by_post_approval_runtime_workflow"] is True, "stage validator contradiction reopened")
    require(len(set(value for key, value in stages.items() if key != "inert_validator_must_not_be_called_by_post_approval_runtime_workflow")) == 9, "stage validators are not distinct")

    required_values = document["values_required_before_owner_approval"]
    require(len(required_values) == len(set(required_values)) == 11, "pre-approval hash binding list drift")
    require("provider_pricing_and_eur_conversion_snapshot_sha256" in required_values, "pricing/EUR snapshot no longer required")

    require(all(value is False for value in document["current_runtime_authority"].values()), "runtime authority opened")
    require(all(value is False for value in document["downstream_authorizations"].values()), "downstream authority opened")
    require(all(value is False for value in document["trading_authorizations"].values()), "trading authority opened")
    for key in (
        "network_requests_executed_by_this_amendment",
        "aws_iam_mutations_executed_by_this_amendment",
        "diagnostic_rows_created_by_this_amendment",
        "wallet_feature_rows_created_by_this_amendment",
    ):
        require(document[key] == 0, f"amendment activity overclaim: {key}")
    require(document["r11_closed"] is False and document["r12_ready"] is False, "lifecycle overclaim")
    require(document["empirical_result"] is None, "amendment contains empirical result")

    require(original.get("diagnostic_id") == "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-001", "original preregistration id drift")
    require(original.get("status") == "PREREGISTERED_NO_EXECUTION", "original preregistration snapshot mutated")
    require(original.get("owner_approval_status") == "NOT_PRESENT", "original preregistration approval drift")
    require(original.get("execution_authorized_now") is False, "original preregistration execution opened")


def validate_repository_state() -> None:
    document = strict_load(AMENDMENT)
    original = strict_load(ORIGINAL)
    selection = strict_load(SELECTION)
    prior = strict_load(PRIOR_RESULT)
    validate_document(document, original=original, selection=selection, prior_result=prior)
    require(not INSTALLED_WORKFLOW.exists(), "R11A V2 workflow installed during preregistration")
    require(not APPROVAL_ROOT.exists(), "R11A V2 approval exists during preregistration")
    require(not RUNTIME_ROOT.exists(), "R11A V2 runtime release exists during preregistration")
    require(not EVIDENCE_ROOT.exists(), "R11A V2 evidence exists before execution")


def main() -> int:
    validate_repository_state()
    print("R11A_V2_PREREGISTRATION_VALID_NO_EXECUTION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
