from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PREREG = BASE / "r11a/R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_PREREGISTRATION.json"
DOSSIER = BASE / "r11a/R11A_IDENTITY_DECISION_DOSSIER.json"
ROOT_CAUSE = BASE / "r11a/R11_ROOT_CAUSE_STATUS.json"
SELECTION = BASE / "r11/R11_72H_SELECTION.json"
R11_RESULT = BASE / "r11_evidence/run-31436753081/r11-result.json"
R11_CONSUMPTION = BASE / "r11_runtime/R11_EXECUTION_RELEASE_CONSUMPTION.json"

ID = "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-001"
SELECTION_SHA256 = "57ed7476401ed50ce2008177b2accf58e99de81184661ebc05d74308138f74d6"
RESULT_SHA256 = "9d3266eb53791d83df29b6ec3ae5f33c254b29a8182f2e6be7e3261c02686862"
EXPECTED_STUDY_ROLE = "EXACT_72_OBJECT_IDENTITY_BLOCK_OVERLAP_AND_DUPLICATE_PROVENANCE_DIAGNOSTIC_ONLY"
EXPECTED_RESEARCH_QUESTION = (
    "Across the exact 72 already selected R11 objects, which complete and conserving combination of TID scope "
    "false positives, expected counterparty pairs, exact block replay across objects, exact user-fill reobservation "
    "from proven block replay, conflicts, intra-block repeats, strict TID schema violations or unclassifiable "
    "evidence explains every repeated legacy wallet-plus-TID observation?"
)

EXPECTED_PREREGISTRATION_KEYS = {
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
EXPECTED_INPUT_SCOPE = {
    "selection_id": "HL-ARCHIVE-R11-72H-MODERN-PERSISTENCE-SELECTION-001",
    "canonical_selection_sha256": "7c134f4b62f547904126a5f810c177484dceeffa246d53c5c35944367d563eb2",
    "selection_path": "research/archive_inventory/r11/R11_72H_SELECTION.json",
    "selection_file_sha256": SELECTION_SHA256,
    "prior_result_path": "research/archive_inventory/r11_evidence/run-31436753081/r11-result.json",
    "prior_result_sha256": RESULT_SHA256,
    "selected_object_count": 72,
    "selected_hour_count": 72,
    "complete_utc_day_count": 3,
    "window_start_utc": "2025-07-28T00:00:00Z",
    "window_end_exclusive_utc": "2025-07-31T00:00:00Z",
    "target_bucket": "hl-mainnet-node-data",
    "signing_region": "ap-northeast-1",
    "exact_keys_etags_lengths_inherited_without_change": True,
    "all_72_prior_compressed_sha256_values_required_as_post_download_integrity_anchors": True,
    "seventy_third_object_authorized": False,
    "other_historical_window_authorized": False,
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
EXPECTED_RAW_OBSERVATION_LOCATOR = {
    "container_field": "raw_observation_locator",
    "exact_fields": [
        "source_object_key",
        "compressed_object_sha256",
        "record_ordinal_zero_based",
        "event_ordinal_zero_based",
    ],
    "source_object_key_and_verified_compressed_sha256_both_required": True,
}
EXPECTED_TID_SCHEMA = {
    "required_raw_json_type": "INTEGER",
    "minimum_inclusive": 0,
    "maximum_exclusive": 2**50,
    "string_decimal_float_or_boolean_tid_coercion_authorized": False,
    "schema_violation_taxon": "TID_SCHEMA_VIOLATION",
}
EXPECTED_DOSSIER_SCHEMA_BOUNDARIES = {
    "tid_required_raw_json_type": "INTEGER",
    "tid_minimum_inclusive": 0,
    "tid_maximum_exclusive": 2**50,
    "string_decimal_float_or_boolean_tid_coercion_authorized": False,
    "block_time_tolerance_authorized": False,
    "metadata_timezone_inference_authorized": False,
    "coin_rewriting_without_versioned_schema_authorized": False,
    "wallet_address_canonicalization": "EXACT_0X40HEX_LOWERCASE_AFTER_STRICT_VALIDATION",
}
EXPECTED_DOSSIER_DECISION_BOUNDARIES = {
    "blind_drop_duplicates_authorized": False,
    "first_seen_or_last_seen_wins_authorized": False,
    "payload_hash_only_deduplication_authorized": False,
    "time_or_numeric_tolerance_authorized": False,
    "repair_selected_by_this_dossier": False,
    "r11b_authorized_by_this_dossier": False,
    "wallet_aggregation_may_start_before_identity_resolution": False,
    "unknown_conflict_or_incomplete_group_is_fail_closed": True,
}
EXPECTED_IDENTITY_CONTRACT = {
    "decision_id": "R11A-CANONICAL-IDENTITY-MODEL-001",
    "decision_path": "research/archive_inventory/r11a/R11A_IDENTITY_DECISION_DOSSIER.json",
    "raw_observation_key": [
        "object_key",
        "verified_compressed_sha256",
        "decompressed_record_ordinal",
        "event_ordinal",
    ],
    "emitted_raw_observation_locator": EXPECTED_RAW_OBSERVATION_LOCATOR,
    "archive_block_locator": "block_number",
    "archive_block_equality_invariants": [
        "exact_raw_block_time",
        "ordered_event_count",
        "ordered_event_fingerprint",
    ],
    "protocol_matched_trade_key": [
        "exact_raw_block_time",
        "canonical_schema_validated_coin",
        "validated_json_integer_tid",
    ],
    "wallet_user_fill_key": [
        "canonical_lowercase_wallet_address",
        "exact_raw_block_time",
        "canonical_schema_validated_coin",
        "validated_json_integer_tid",
    ],
    "legacy_weak_key_retained_for_diagnosis_only": [
        "canonical_lowercase_wallet_address",
        "normalized_typed_tid",
    ],
    "tid_schema_contract": EXPECTED_TID_SCHEMA,
    "canonical_serialization_version": "R11A_CANONICAL_JSON_TYPED_FIELDS_V1",
}
EXPECTED_OCCURRENCE_FIELDS = [
    "record_type",
    "primary_taxon",
    "supporting_taxa",
    "taxonomy_unit",
    "taxonomy_unit_id",
    "weak_key_group_id",
    "block_replay_group_id",
    "protocol_trade_group_id",
    "wallet_fill_group_id",
    "legacy_weak_key",
    "raw_wallet_address",
    "raw_tid_json_type",
    "raw_tid_token",
    "tid_validation_status",
    "tid_schema_violation_reason",
    "validated_integer_tid",
    "weak_key_group_multiplicity",
    "block_replay_group_multiplicity",
    "protocol_trade_group_multiplicity",
    "wallet_fill_group_multiplicity",
    "protocol_trade_identity",
    "wallet_fill_identity",
    "raw_observation_locator",
    "source",
    "block_number",
    "block_time_exact",
    "local_time_exact",
    "side_exact",
    "fill_time_exact",
    "selected_fill_sha256",
    "full_fill_sha256",
    "full_event_sha256",
    "block_fingerprints",
    "full_lossless_validated_fill_payload",
    "first_versus_occurrence_field_diffmask",
    "boundary_relationship_to_group_first",
    "exact_block_replay_proof",
    "expected_counterparty_pair_proof",
    "deduplication_authorized",
]
EXPECTED_GLOBAL_OUTPUTS = [
    "raw_event_observation_count",
    "repeat_occurrence_count_sum_n_minus_one",
    "affected_weak_key_group_count",
    "affected_wallet_count",
    "affected_tid_count",
    "affected_canonical_key_count",
    "affected_block_count",
    "affected_object_count",
    "affected_path_hour_count",
    "affected_utc_day_count",
    "repeat_relationship_counts",
    "taxonomy_group_counts_by_class",
    "taxonomy_occurrence_counts_by_class",
    "complete_block_overlap_matrix",
    "taxonomy_conservation_ledger",
    "block_reducer_sorted_output_sha256",
    "fill_reducer_sorted_output_sha256",
    "taxonomy_conservation_passed",
    "unclassifiable_group_count",
    "duplicate_observation_output_sha256",
    "duplicate_observation_output_bytes",
    "block_replay_output_sha256",
    "block_replay_output_bytes",
    "retention_caps_exceeded",
    "fill_time_versus_block_time_evidence_status",
    "terminal_class",
    "root_cause_claim_status",
]
EXPECTED_TAXONOMY_UNITS = {
    "TID_SCOPE_FALSE_POSITIVE": "LEGACY_WALLET_PLUS_TYPED_TID_GROUP",
    "EXPECTED_COUNTERPARTY_PAIR": "PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE",
    "EXACT_BLOCK_REPLAY_ACROSS_OBJECTS": "ARCHIVE_BLOCK_NUMBER_GROUP",
    "EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY": "CANONICAL_WALLET_USER_FILL_GROUP",
    "CONFLICTING_BLOCK_REPLAY": "ARCHIVE_BLOCK_NUMBER_GROUP",
    "CONFLICTING_USER_FILL": "CANONICAL_WALLET_USER_FILL_GROUP",
    "INTRA_BLOCK_REPEAT": "CANONICAL_WALLET_USER_FILL_GROUP_PER_RAW_BLOCK_OCCURRENCE",
    "TID_SCHEMA_VIOLATION": "RAW_TID_OBSERVATION",
    "UNCLASSIFIABLE": "ANY_REQUIRED_TAXONOMY_UNIT",
}
EXPECTED_TAXONOMY_DECISION_CONTRACT = {
    "exactly_one_primary_taxon_per_taxonomy_unit": True,
    "supporting_taxa_do_not_count_as_additional_primary_classifications": True,
    "payload_hash_only_replay_classification_authorized": False,
    "taxonomy_units_by_class": EXPECTED_TAXONOMY_UNITS,
    "exact_block_replay_across_objects_requires": [
        "same_block_number",
        "distinct_raw_block_locators",
        "distinct_source_object_keys",
        "same_exact_raw_block_time",
        "same_ordered_event_count",
        "same_ordered_event_fingerprint",
    ],
    "raw_record_sha256_role_for_block_replay": "SUPPLEMENTAL_EXACT_BYTE_EVIDENCE_NOT_A_REQUIRED_ARCHIVE_BLOCK_EQUALITY_INVARIANT",
    "exact_user_fill_reobservation_requires": [
        "same_canonical_wallet_user_fill_key",
        "same_full_fill_sha256",
        "same_full_event_sha256",
        "distinct_raw_observation_locators",
        "every_reobservation_resolves_to_one_proven_exact_block_replay_group",
        "no_two_reobservations_share_one_raw_block_locator",
    ],
    "expected_counterparty_pair_requires": [
        "same_protocol_matched_trade_key",
        "same_raw_block_locator",
        "exactly_two_distinct_validated_wallets",
        "exact_side_set_A_and_B",
        "each_wallet_fill_occurs_once_in_that_raw_block",
    ],
    "tid_scope_false_positive_requires": [
        "same_legacy_wallet_plus_typed_tid_key",
        "at_least_two_distinct_protocol_matched_trade_keys",
        "no_conflicting_user_fill",
        "no_unresolved_or_missing_proof",
    ],
    "conflicting_block_replay_requires_any_difference_in": [
        "exact_raw_block_time",
        "ordered_event_count",
        "ordered_event_fingerprint",
    ],
    "conflicting_user_fill_requires_same_canonical_key_and_any_payload_difference": True,
    "intra_block_repeat_requires_same_wallet_fill_key_and_distinct_event_ordinals_in_one_raw_block_locator": True,
    "tid_schema_violation_requires_validated_integer_tid_null": True,
    "unclassifiable_required_for_missing_conflicting_or_multiple_non_supporting_proofs": True,
}
EXPECTED_OCCURRENCE_RECORD_CONTRACT = {
    "all_required_occurrence_fields_present_on_every_row_with_explicit_null_when_inapplicable": True,
    "raw_observation_locator_exact_fields": EXPECTED_RAW_OBSERVATION_LOCATOR["exact_fields"],
    "source_exact_fields": [
        "object_key",
        "compressed_sha256",
        "path_hour_utc",
        "object_ordinal_zero_based",
        "record_ordinal_zero_based",
    ],
    "boundary_relationship_exact_fields": [
        "same_object",
        "same_block_number",
        "same_raw_block_locator",
        "same_path_hour",
        "same_utc_day",
        "path_hour_distance",
        "adjacent_hour_boundary",
    ],
    "valid_tid_row": {
        "tid_validation_status": "VALID_UINT50",
        "validated_integer_tid_required": True,
        "protocol_trade_identity_required": True,
        "wallet_fill_identity_required": True,
    },
    "tid_schema_violation_row": {
        "tid_validation_status": "TID_SCHEMA_VIOLATION",
        "raw_tid_json_type_and_token_required": True,
        "validated_integer_tid_must_be_null": True,
        "protocol_trade_identity_must_be_null": True,
        "wallet_fill_identity_must_be_null": True,
        "coercion_authorized": False,
    },
    "exact_user_fill_reobservation_requires_nonnull_exact_block_replay_proof": True,
    "expected_counterparty_pair_requires_nonnull_counterparty_pair_proof": True,
    "deduplication_authorized_must_be_false": True,
}
EXPECTED_GLOBAL_OUTPUT_CONTRACT = {
    "taxonomy_count_fields_must_have_exact_zero_filled_keys": EXPECTED_TAXONOMY,
    "taxonomy_counts_are_nonnegative_json_integers": True,
    "taxonomy_counts_conserve_separately_by_declared_taxonomy_unit": True,
    "cross_layer_taxonomy_counts_must_not_be_summed_as_one_partition": True,
    "repeat_relationship_count_exact_fields": [
        "intra_object",
        "inter_object",
        "intra_block",
        "inter_block",
        "same_path_hour",
        "cross_path_hour",
        "same_utc_day",
        "cross_utc_day",
        "adjacent_hour_boundary",
        "non_adjacent_hour_boundary",
        "exact_identical_payload",
        "conflicting_payload",
    ],
    "taxonomy_conservation_ledger_exact_fields": [
        "raw_event_observation_count",
        "valid_tid_observation_count",
        "tid_schema_violation_observation_count",
        "legacy_repeat_group_count",
        "legacy_repeat_observation_count",
        "repeat_occurrence_count_sum_n_minus_one",
        "protocol_trade_group_count_in_retained_evidence",
        "wallet_fill_group_count_in_retained_evidence",
        "repeated_block_group_count",
        "repeated_block_observation_count",
        "unclassifiable_unit_count",
        "all_required_units_classified",
        "all_occurrences_have_one_unique_raw_locator",
        "all_proof_references_resolve",
        "counts_conserve",
    ],
    "complete_terminal_class_requires_all_72_hours_3_days_caps_and_conservation": True,
    "root_cause_proven_requires_zero_unclassifiable_units_and_no_cap_overflow": True,
}
EXPECTED_DIAGNOSTIC_PASSES = [
    {
        "pass_id": "BLOCK_OVERLAP_PASS",
        "method": "256_FIXED_WIDTH_BLOCK_NUMBER_PARTITIONS_THEN_DETERMINISTIC_SORT_AND_SECOND_LOCAL_PARSE",
        "sort_key": ["block_number", "object_key", "decompressed_record_ordinal"],
        "classification_invariants": [
            "exact_raw_block_time",
            "ordered_event_count",
            "ordered_event_fingerprint",
        ],
        "supplemental_exact_byte_and_writer_metadata_evidence": ["raw_record_sha256", "local_time"],
        "required_output": "COMPLETE_ADJACENT_AND_NON_ADJACENT_BLOCK_OVERLAP_LEDGER",
    },
    {
        "pass_id": "FILL_IDENTITY_PASS",
        "method": "256_FIXED_WIDTH_VALID_WALLET_UINT50_TID_PARTITIONS_PLUS_LOSSLESS_INVALID_TID_LEDGER_THEN_DETERMINISTIC_SORT_AND_SECOND_LOCAL_PARSE",
        "sort_keys": [
            "legacy_weak_key",
            "protocol_matched_trade_key",
            "canonical_wallet_user_fill_key",
            "raw_observation_locator",
        ],
        "required_outputs": [
            "ALL_COMPLETE_REPEAT_GROUPS_WITH_RAW_BLOCK_AND_EVENT_PROVENANCE",
            "ALL_EXPECTED_COUNTERPARTY_PAIR_PROOFS_IN_RETAINED_TRADE_GROUPS",
            "ALL_TID_SCHEMA_VIOLATIONS_WITHOUT_COERCION",
        ],
    },
]
EXPECTED_STOP_CONDITIONS = [
    "NONCANONICAL_MAIN_OR_NONFIRST_ATTEMPT",
    "RELEASE_NOT_EXACT_SINGLE_USE_OR_ALREADY_CONSUMED",
    "INSUFFICIENT_EPHEMERAL_DISK_BEFORE_OIDC",
    "AWS_IDENTITY_MISMATCH",
    "REQUEST_CAP_REACHED",
    "HTTP_OR_REQUESTER_PAYS_FAILURE",
    "ETAG_CONTENT_LENGTH_OR_COMPRESSED_SHA256_MISMATCH",
    "DECOMPRESSION_OR_NON_TID_STRUCTURAL_SCHEMA_FAILURE",
    "FIXED_INDEX_OR_ARTIFACT_CAP_EXCEEDED",
    "TAXONOMY_OR_CONSERVATION_INCOMPLETE",
    "RUNTIME_CAP_REACHED",
]
EXPECTED_IMPLEMENTATION_VALUES_BOUND_BEFORE_APPROVAL = [
    "collector_sha256",
    "schema_sha256",
    "validator_sha256",
    "workflow_git_blob_sha",
    "stdlib_dependency_declaration",
    "dedicated_role_reuse_or_successor_decision",
]
EXPECTED_FUTURE_IMPLEMENTATION_REQUIREMENTS = {
    "implementation_contract_path": "research/archive_inventory/r11a_implementation/R11A_IMPLEMENTATION_CONTRACT.json",
    "collector_path": "research/archive_inventory/r11a_implementation/collector.py",
    "identity_path": "research/archive_inventory/r11a_implementation/identity.py",
    "diagnostic_classifier_path": "research/archive_inventory/r11a_implementation/diagnostic.py",
    "activity_tracker_path": "research/archive_inventory/r11a_implementation/activity.py",
    "immutable_limits_path": "research/archive_inventory/r11a_implementation/limits.py",
    "workflow_candidate_path": (
        "research/archive_inventory/r11a_implementation/workflows/"
        "hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
    ),
    "exact_collector_schema_validator_and_workflow_hashes_required_before_owner_approval": True,
    "stdlib_only_or_exact_dependency_lock_required": True,
    "workflow_candidate_must_remain_outside_dot_github_until_separate_post_approval_installation": True,
    "implementation_merge_is_not_execution_release": True,
}
EXPECTED_ENVELOPE = {
    "maximum_one_time_budget_eur": 0.5,
    "maximum_monthly_budget_eur": 0,
    "maximum_get_object_requests": 72,
    "maximum_requests_per_object": 1,
    "maximum_retries_per_request": 0,
    "maximum_total_compressed_bytes": 2107738436,
    "maximum_individual_compressed_bytes": 76616104,
    "maximum_total_decompressed_bytes_processed_across_two_local_passes": 21079958490,
    "maximum_individual_decompressed_bytes_per_pass": 536870912,
    "maximum_ephemeral_workspace_bytes": 5368709120,
    "minimum_free_workspace_bytes_before_oidc": 6442450944,
    "maximum_retained_artifact_bytes": 134217728,
    "maximum_runtime_seconds": 21600,
    "request_order": "PATH_HOUR_ASCENDING",
    "requester_pays_required": True,
    "if_match_etag_required": True,
    "exact_content_length_required": True,
    "exact_response_etag_required": True,
    "preknown_compressed_sha256_required_for_every_object": True,
    "stop_after_first_transport_or_identity_mismatch": True,
    "head_object_authorized": False,
    "range_get_authorized": False,
    "list_objects_v2_authorized": False,
    "list_object_versions_authorized": False,
    "list_all_my_buckets_authorized": False,
    "get_object_attributes_authorized": False,
    "get_object_version_authorized": False,
    "http_redirect_following_authorized": False,
}
EXPECTED_CONSERVATION_INVARIANTS = {
    "raw_observations_equal_singletons_plus_all_occurrences_in_emitted_repeat_groups": True,
    "each_weak_group_observations_equal_one_plus_repeat_occurrences": True,
    "each_replayed_block_is_exactly_equal_or_conflict": True,
    "every_future_reduction_candidate_has_all_raw_provenance": True,
    "fixed_width_indices_second_parse_and_emitted_taxonomy_must_conserve_counts": True,
    "all_72_hours_and_3_days_must_complete_before_any_complete_terminal_class": True,
    "sampling_authorized": False,
    "partial_cause_claim_authorized": False,
}
EXPECTED_ALLOWED_TERMINALS = [
    "R11A_ROOT_CAUSE_TAXONOMY_COMPLETE",
    "R11A_DIAGNOSTIC_ARTIFACT_CAP_EXCEEDED",
    "R11A_DIAGNOSTIC_INCOMPLETE",
]
EXPECTED_RETENTION = {
    "retain_all_complete_repeat_groups": True,
    "retain_all_occurrences_and_provenance_for_each_repeat_group": True,
    "retain_complete_repeated_block_number_overlap_ledger": True,
    "retain_singleton_raw_fill_payloads": False,
    "retain_singleton_aggregate_counts_and_deterministic_hashes": True,
    "lossy_or_sampled_repeat_group_representation_authorized": False,
    "wallet_feature_output_required_empty": True,
    "ranking_or_economic_output_fields_authorized": False,
    "maximum_repeated_legacy_key_groups_retained": 100000,
    "maximum_repeated_observations_retained": 250000,
    "maximum_repeated_block_groups_retained": 100000,
    "artifact_cap_exceeded_behavior": "R11A_DIAGNOSTIC_ARTIFACT_CAP_EXCEEDED",
}
EXPECTED_IAM_BOUNDARY = {
    "dedicated_r11_role_name": "onchain-wallet-intelligence-hl-archive-scaling-r11",
    "dedicated_r11_role_arn": "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-scaling-r11",
    "role_reuse_requires_new_exact_owner_approval": True,
    "proposed_role_decision": "REUSE_EXISTING_DEDICATED_R11_ROLE_WITHOUT_ANY_POLICY_OR_TRUST_MUTATION_ONLY_IF_NEW_OWNER_APPROVAL_EXPLICITLY_AUTHORIZES_REUSE",
    "role_or_policy_mutation_authorized": False,
    "persistent_allowlist_must_remain_exact_same_72_objects": True,
    "session_policy_allowed_action_only": ["s3:GetObject"],
    "session_policy_date_prefix_intersection": [
        "arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250728/*",
        "arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250729/*",
        "arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250730/*",
    ],
    "role_session_duration_seconds": 7200,
    "fresh_sts_preflight_required": False,
    "existing_role_attestation_and_successful_r11_assumption_must_be_revalidated_offline": True,
}
EXPECTED_RUNTIME_AUTHORITY = {
    "workflow_dispatch": False,
    "aws_iam_mutation": False,
    "aws_oidc": False,
    "requester_pays": False,
    "get_object": False,
    "object_body_download": False,
    "decompression": False,
    "diagnostic_processing": False,
    "diagnostic_artifact_retention": False,
}
EXPECTED_DOWNSTREAM_AUTHORIZATIONS = {
    "blind_deduplication": False,
    "historical_expansion": False,
    "wallet_feature_publication": False,
    "wallet_ranking": False,
    "candidate_shortlisting": False,
    "pnl_or_alpha_analysis": False,
    "copyability_analysis": False,
    "entity_clustering": False,
    "strategy_inference": False,
    "paper_trading": False,
    "live_trading": False,
    "leverage": False,
    "capital_allocation": False,
}
EXPECTED_GOVERNANCE_GATES = {
    "canonical_r11_evidence_closure_required": True,
    "clean_context_identity_review_required": True,
    "explicit_owner_approval_required": True,
    "separate_inert_implementation_review_required": True,
    "separate_execution_release_candidate_required": True,
    "separate_single_use_activation_required": True,
    "separate_execution_evidence_pr_required": True,
    "execution_authorized_by_this_preregistration": False,
    "r11b_repair_authorized_by_r11a": False,
}
EXPECTED_CLOSURE_BINDING = {
    "pull_request_number": 139,
    "canonical_merge_commit_sha": "f7aa612d2a5638cce0fd197f57efea4b787f87f1",
    "attestation_path": "research/archive_inventory/r11_evidence/HL-ARCHIVE-R11-72H-PERSISTENCE-SCALING-001-ATTESTATION.json",
    "release_consumption_path": "research/archive_inventory/r11_runtime/R11_EXECUTION_RELEASE_CONSUMPTION.json",
    "validator_path": "governance/validate_r11_execution_evidence.py",
    "required_validator_terminal_status": "R11_EXECUTION_EVIDENCE_VALID_UNRESOLVED",
    "binding_complete": True,
    "binding_is_owner_approval": False,
}


class R11APreregistrationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise R11APreregistrationError(message)


def exact_json_equal(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return set(actual) == set(expected) and all(
            exact_json_equal(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        return len(actual) == len(expected) and all(
            exact_json_equal(left, right)
            for left, right in zip(actual, expected, strict=True)
        )
    return actual == expected


def assert_exact(actual: object, expected: object, label: str) -> None:
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

    def finite_float(token: str) -> float:
        value = float(token)
        if not math.isfinite(value):
            raise R11APreregistrationError(f"{label} contains non-finite number {token}")
        return value

    return json.loads(
        text,
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=reject_constant,
        parse_float=finite_float,
    )


def load(path: Path) -> dict:
    value = strict_json_loads(path.read_text(encoding="utf-8"), str(path))
    require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value  # type: ignore[return-value]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(prereg: dict, dossier: dict, root_cause: dict, selection: dict, result: dict, consumption: dict) -> None:
    require(set(prereg) == EXPECTED_PREREGISTRATION_KEYS, "preregistration top-level schema drift")
    require(prereg["schema_version"] == "1.0", "preregistration schema version drift")
    require(prereg["diagnostic_id"] == prereg["pilot_id"] == ID, "diagnostic identity drift")
    require(prereg["status"] == "PREREGISTERED_NO_EXECUTION", "preregistration status drift")
    require(prereg["study_role"] == EXPECTED_STUDY_ROLE, "study role drift")
    require(prereg["research_question"] == EXPECTED_RESEARCH_QUESTION, "research question drift")
    require(prereg["owner_approval_status"] == "NOT_PRESENT", "owner approval overclaim")
    require(prereg["execution_authorized_now"] is False, "execution authority overclaim")

    parent = prereg["parent_r11_run"]
    assert_exact(parent, {
        "run_id": 31436753081,
        "job_id": 93612467250,
        "artifact_id": 9082810554,
        "dispatch_sha": "baca1925c23ef6b0136aa3d96d6d479ac7717bdf",
        "artifact_zip_sha256": "45ee57df7a63561bef1772d8612d5fe32b06b9c407d9c1464ce0a02b65a15cc5",
        "research_conclusion": "R11_72H_PERSISTENCE_PIPELINE_UNRESOLVED",
        "release_consumed": True,
        "rerun_authorized": False,
    }, "parent R11 run")
    assert_exact(
        prereg["canonical_r11_evidence_closure_binding"],
        EXPECTED_CLOSURE_BINDING,
        "canonical R11 evidence closure binding",
    )
    require(consumption["release_consumed"] is True, "parent release consumption drift")
    require(
        consumption["remaining_get_object_budget_from_consumed_release"] == 0,
        "parent request budget reopened",
    )
    require(consumption["future_r11_dispatch_authorized"] is False, "future R11 dispatch reopened")
    require(consumption["rerun_authorized"] is False, "R11 rerun reopened")
    require(consumption["duplicate_root_cause_known"] is False, "parent root-cause overclaim")

    scope = prereg["exact_input_scope"]
    assert_exact(scope, EXPECTED_INPUT_SCOPE, "exact input scope")
    require(digest(SELECTION) == scope["selection_file_sha256"] == SELECTION_SHA256, "selection SHA drift")
    require(digest(R11_RESULT) == scope["prior_result_sha256"] == RESULT_SHA256, "parent result SHA drift")
    require(scope["selected_object_count"] == scope["selected_hour_count"] == 72, "72-object scope drift")
    require(scope["complete_utc_day_count"] == 3, "three-day scope drift")
    require(scope["window_start_utc"] == "2025-07-28T00:00:00Z", "window start drift")
    require(scope["window_end_exclusive_utc"] == "2025-07-31T00:00:00Z", "window end drift")
    require(scope["target_bucket"] == "hl-mainnet-node-data", "bucket drift")
    require(scope["signing_region"] == "ap-northeast-1", "signing-region drift")
    require(
        scope["all_72_prior_compressed_sha256_values_required_as_post_download_integrity_anchors"] is True,
        "preknown compressed SHA requirement removed",
    )
    require(scope["seventy_third_object_authorized"] is False, "additional object authority opened")
    require(scope["other_historical_window_authorized"] is False, "historical expansion authority opened")
    require(
        len(selection["exact_targets"]) == len(result["per_hour_summaries"]) == 72,
        "selection/result cardinality drift",
    )
    require(
        sum(row["expected_size_bytes"] for row in selection["exact_targets"]) == 2107738436,
        "compressed-byte scope drift",
    )
    require(
        sum(row["decompressed_byte_count"] for row in result["per_hour_summaries"]) == 10539979245,
        "decompressed-byte scope drift",
    )
    for selected, observed in zip(selection["exact_targets"], result["per_hour_summaries"], strict=True):
        require(selected["path_hour_utc"] == observed["path_hour_utc"], "target path-hour drift")
        require(selected["key"] == observed["object_key"], "target object-key drift")
        require(selected["expected_etag"] == observed["expected_etag"], "target ETag drift")
        require(
            selected["expected_size_bytes"]
            == observed["expected_content_length"]
            == observed["observed_content_length"],
            "target content-length drift",
        )
        require(
            isinstance(observed["compressed_sha256"], str)
            and len(observed["compressed_sha256"]) == 64,
            "target compressed SHA drift",
        )

    identity = prereg["identity_contract"]
    assert_exact(identity, EXPECTED_IDENTITY_CONTRACT, "identity contract")
    require(
        identity["raw_observation_key"]
        == ["object_key", "verified_compressed_sha256", "decompressed_record_ordinal", "event_ordinal"],
        "raw observation identity drift",
    )
    assert_exact(
        identity["emitted_raw_observation_locator"],
        EXPECTED_RAW_OBSERVATION_LOCATOR,
        "emitted raw observation locator",
    )
    require(identity["archive_block_locator"] == "block_number", "archive block locator drift")
    require(
        identity["protocol_matched_trade_key"]
        == ["exact_raw_block_time", "canonical_schema_validated_coin", "validated_json_integer_tid"],
        "protocol matched-trade identity drift",
    )
    require(
        identity["wallet_user_fill_key"]
        == [
            "canonical_lowercase_wallet_address",
            "exact_raw_block_time",
            "canonical_schema_validated_coin",
            "validated_json_integer_tid",
        ],
        "wallet user-fill identity drift",
    )
    assert_exact(identity["tid_schema_contract"], EXPECTED_TID_SCHEMA, "TID schema contract")
    require(type(identity["tid_schema_contract"]["minimum_inclusive"]) is int, "TID minimum type drift")
    require(type(identity["tid_schema_contract"]["maximum_exclusive"]) is int, "TID maximum type drift")
    require(dossier["decision_id"] == identity["decision_id"], "identity dossier binding drift")
    require(
        dossier["status"] == "FROZEN_FOR_DIAGNOSTIC_DESIGN_NO_REPAIR_DECISION",
        "identity dossier status drift",
    )
    require(dossier["authoritative_semantics"]["tid_definition"]["status"] == "PROVEN", "TID evidence drift")
    require(
        dossier["authoritative_semantics"]["globally_unique_matched_trade_key"]["fields"]
        == ["block_time", "coin", "tid"],
        "matched-trade semantics drift",
    )
    require(
        dossier["authoritative_semantics"]["two_wallet_fill_representation"]["status"]
        == "LIKELY_STRONGLY_CORROBORATED_NOT_NORMATIVE",
        "counterparty-pair evidence status drift",
    )
    assert_exact(
        dossier["schema_boundaries"],
        EXPECTED_DOSSIER_SCHEMA_BOUNDARIES,
        "dossier schema boundaries",
    )
    assert_exact(
        dossier["decision_boundaries"],
        EXPECTED_DOSSIER_DECISION_BOUNDARIES,
        "dossier decision boundaries",
    )
    require(type(dossier["schema_boundaries"]["tid_minimum_inclusive"]) is int, "dossier TID minimum type drift")
    require(type(dossier["schema_boundaries"]["tid_maximum_exclusive"]) is int, "dossier TID maximum type drift")
    require(dossier["schema_boundaries"]["tid_required_raw_json_type"] == "INTEGER", "dossier TID raw type drift")
    require(dossier["schema_boundaries"]["tid_minimum_inclusive"] == 0, "dossier TID minimum drift")
    require(dossier["schema_boundaries"]["tid_maximum_exclusive"] == 2**50, "dossier TID maximum drift")
    require(
        dossier["schema_boundaries"]["string_decimal_float_or_boolean_tid_coercion_authorized"] is False,
        "TID coercion opened",
    )
    require(dossier["decision_boundaries"]["blind_drop_duplicates_authorized"] is False, "blind deduplication opened")
    require(dossier["decision_boundaries"]["repair_selected_by_this_dossier"] is False, "repair-selection overclaim")
    require(
        dossier["boundary_evidence_status"]["exact_cross_object_block_replay_exists_in_r11"]
        == "UNKNOWN_PENDING_R11A",
        "empirical replay overclaim",
    )
    dossier_layers = dossier["identity_layers"]
    require(
        dossier_layers["raw_observation"]["canonical_key"] == identity["raw_observation_key"],
        "dossier/prereg raw observation identity split",
    )
    require(
        dossier_layers["archive_block"]["locator"] == identity["archive_block_locator"]
        and dossier_layers["archive_block"]["equality_invariants"]
        == identity["archive_block_equality_invariants"],
        "dossier/prereg archive block identity split",
    )
    require(
        dossier_layers["protocol_matched_trade"]["canonical_key"] == identity["protocol_matched_trade_key"],
        "dossier/prereg matched-trade identity split",
    )
    require(
        dossier_layers["wallet_user_fill"]["canonical_key"] == identity["wallet_user_fill_key"],
        "dossier/prereg wallet-fill identity split",
    )

    assert_exact(dossier["duplicate_taxonomy"], EXPECTED_TAXONOMY, "dossier taxonomy")
    assert_exact(prereg["duplicate_taxonomy"], EXPECTED_TAXONOMY, "preregistration taxonomy")
    assert_exact(prereg["required_occurrence_fields"], EXPECTED_OCCURRENCE_FIELDS, "required occurrence fields")
    assert_exact(prereg["required_global_outputs"], EXPECTED_GLOBAL_OUTPUTS, "required global outputs")
    assert_exact(
        prereg["taxonomy_decision_contract"],
        EXPECTED_TAXONOMY_DECISION_CONTRACT,
        "taxonomy decision contract",
    )
    assert_exact(
        prereg["occurrence_record_contract"],
        EXPECTED_OCCURRENCE_RECORD_CONTRACT,
        "occurrence record contract",
    )
    assert_exact(
        prereg["global_output_contract"],
        EXPECTED_GLOBAL_OUTPUT_CONTRACT,
        "global output contract",
    )
    assert_exact(prereg["diagnostic_passes"], EXPECTED_DIAGNOSTIC_PASSES, "diagnostic passes")
    assert_exact(prereg["stop_conditions"], EXPECTED_STOP_CONDITIONS, "stop conditions")
    assert_exact(
        prereg["implementation_values_bound_before_owner_approval"],
        EXPECTED_IMPLEMENTATION_VALUES_BOUND_BEFORE_APPROVAL,
        "implementation approval bindings",
    )
    assert_exact(
        prereg["future_implementation_contract_requirements"],
        EXPECTED_FUTURE_IMPLEMENTATION_REQUIREMENTS,
        "future implementation requirements",
    )
    assert_exact(
        prereg["conservation_invariants"],
        EXPECTED_CONSERVATION_INVARIANTS,
        "conservation invariants",
    )
    assert_exact(prereg["allowed_terminal_classes"], EXPECTED_ALLOWED_TERMINALS, "allowed terminals")
    assert_exact(prereg["retention_and_privacy"], EXPECTED_RETENTION, "retention and privacy")

    assert_exact(prereg["proposed_request_envelope"], EXPECTED_ENVELOPE, "frozen request envelope")
    assert_exact(prereg["iam_and_session_boundary"], EXPECTED_IAM_BOUNDARY, "IAM and session boundary")
    assert_exact(prereg["current_runtime_authority"], EXPECTED_RUNTIME_AUTHORITY, "current runtime authority")
    assert_exact(
        prereg["downstream_authorizations"],
        EXPECTED_DOWNSTREAM_AUTHORIZATIONS,
        "downstream authorizations",
    )
    assert_exact(prereg["governance_gates"], EXPECTED_GOVERNANCE_GATES, "governance gates")
    for field in (
        "network_requests_executed_by_preregistration",
        "object_bytes_read_by_preregistration",
        "diagnostic_rows_created_by_preregistration",
    ):
        require(type(prereg[field]) is int and prereg[field] == 0, f"{field} must remain exact integer zero")

    require(
        root_cause["status"] == "OFFLINE_AUDIT_COMPLETE_EMPIRICAL_ROOT_CAUSE_PENDING_R11A",
        "root-cause status overclaim",
    )
    statuses = {row["finding"]: row["status"] for row in root_cause["finding_register"]}
    require(
        statuses["AT_LEAST_ONE_REPEATED_LEGACY_WALLET_PLUS_TID_PROJECTION_OCCURRED"] == "PROVEN",
        "retained legacy-repeat finding drift",
    )
    require(
        statuses["WALLET_PLUS_TID_IS_A_SEMANTIC_CANONICAL_EVENT_IDENTITY"] == "DISPROVEN",
        "legacy-key semantic finding drift",
    )
    require(
        statuses["R11_REPEAT_COUNT_LOCATIONS_AND_AFFECTED_CARDINALITIES"] == "UNKNOWN",
        "repeat-cardinality overclaim",
    )
    require(
        statuses["EXACT_CROSS_OBJECT_BLOCK_REPLAY_EXPLAINS_ANY_OR_ALL_R11_REPEATS"] == "UNKNOWN",
        "block-replay root-cause overclaim",
    )
    require(
        statuses["DAYTRACKINGSTATES_GETITEM_MUTATES_STATE_ON_READ"] == "PROVEN",
        "day-tracking mutation finding drift",
    )
    require(
        statuses["DAYTRACKING_READ_MUTATION_CORRUPTED_RETAINED_CANONICAL_R11_WALLET_ROWS"] == "DISPROVEN",
        "day-tracking retained-output finding drift",
    )
    require(root_cause["root_cause_claim_authorized_now"] is False, "root-cause authority opened")
    require(root_cause["repair_selection_authorized_now"] is False, "repair-selection authority opened")
    require(root_cause["r11_closed"] is False and root_cause["r12_ready"] is False, "R11/R12 closure overclaim")

    require(
        not (ROOT / ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml").exists(),
        "R11A workflow is installed before approval",
    )
    require(
        not (BASE / "r11a_runtime/R11A_EXECUTION_RELEASE.json").exists(),
        "R11A execution release exists before approval",
    )


def main() -> int:
    validate(load(PREREG), load(DOSSIER), load(ROOT_CAUSE), load(SELECTION), load(R11_RESULT), load(R11_CONSUMPTION))
    print("R11A_PREREGISTRATION_VALID_NO_EXECUTION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
