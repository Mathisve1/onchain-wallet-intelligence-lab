from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Mapping, Sequence

from . import schema, storage
from .limits import DEFAULT_LIMITS, R11ALimits
from .runtime import ExecutionEvidenceState


class R11AFailureArtifactError(ValueError):
    """Raised when even the minimal truthful evidence package cannot be sealed."""


TAXA = (
    "TID_SCOPE_FALSE_POSITIVE",
    "EXPECTED_COUNTERPARTY_PAIR",
    "EXACT_BLOCK_REPLAY_ACROSS_OBJECTS",
    "EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY",
    "CONFLICTING_BLOCK_REPLAY",
    "CONFLICTING_USER_FILL",
    "INTRA_BLOCK_REPEAT",
    "TID_SCHEMA_VIOLATION",
    "UNCLASSIFIABLE",
)

UNIT_TYPES = (
    "LEGACY_REPEAT_OCCURRENCE",
    "ARCHIVE_BLOCK_NUMBER_GROUP",
    "PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE",
    "RAW_COIN_SCHEMA_VIOLATION_OBSERVATION",
    "RAW_WALLET_SCHEMA_VIOLATION_OBSERVATION",
)

RELATIONSHIPS = (
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
)


def empty_reducer_rows() -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for reducer_id in ("BLOCK_NUMBER", "HISTORICAL_LEGACY_WEAK_KEY"):
        for partition in range(256):
            rows.append(
                {
                    "record_type": "REDUCER_PARTITION_CONSERVATION",
                    "reducer_id": reducer_id,
                    "partition_ordinal_zero_based": partition,
                    "processing_status": "NOT_STARTED_OR_ABORTED_BEFORE_PARTITION_COMPLETE",
                    "partition_function": None,
                    "record_encoding": None,
                    "record_count": None,
                    "logical_input_bytes": None,
                    "unsorted_record_stream_sha256": None,
                    "sorted_record_stream_sha256": None,
                    "singleton_block_observation_count": None,
                    "singleton_block_detail_commitment_sha256": None,
                    "discovered_repeat_group_count": None,
                    "discovered_repeat_observation_count": None,
                    "retained_repeat_group_count": None,
                    "retained_repeat_observation_count": None,
                    "omitted_due_to_cap_group_count": None,
                    "omitted_due_to_cap_observation_count": None,
                    "omitted_group_commitment_sha256": None,
                    "not_retained_due_to_incomplete_group_count": None,
                    "not_retained_due_to_incomplete_observation_count": None,
                    "incomplete_stop_group_commitment_sha256": None,
                }
            )
    return tuple(rows)


def source_prefix_counts(rows: Sequence[Mapping[str, object]]) -> dict[str, int]:
    keys = (
        "raw_record_count",
        "raw_event_observation_count",
        "valid_tid_observation_count",
        "tid_schema_violation_observation_count",
        "valid_coin_observation_count",
        "coin_schema_violation_observation_count",
        "valid_wallet_observation_count",
        "wallet_schema_violation_observation_count",
    )
    totals = {key: 0 for key in keys}
    for row in rows:
        summary = row.get("first_local_parse")
        if not isinstance(summary, Mapping):
            continue
        for key in keys:
            value = summary.get(key, 0)
            if type(value) is not int or value < 0:
                raise R11AFailureArtifactError(f"invalid source-prefix count: {key}")
            totals[key] += value
    return {
        "raw_block_observation_count": totals["raw_record_count"],
        "raw_event_observation_count": totals["raw_event_observation_count"],
        "valid_tid_observation_count": totals["valid_tid_observation_count"],
        "tid_schema_violation_observation_count": totals["tid_schema_violation_observation_count"],
        "valid_coin_observation_count": totals["valid_coin_observation_count"],
        "coin_schema_violation_observation_count": totals["coin_schema_violation_observation_count"],
        "valid_wallet_observation_count": totals["valid_wallet_observation_count"],
        "wallet_schema_violation_observation_count": totals["wallet_schema_violation_observation_count"],
    }


def exact_scope(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    completed = [row for row in rows if row.get("processing_status") == "COMPLETE_TWO_LOCAL_PASSES"]
    hours = {str(row["path_hour_utc"]) for row in completed}
    day_hours: dict[str, set[str]] = {}
    for hour in hours:
        day_hours.setdefault(hour[:10], set()).add(hour)
    return {
        "selected_object_count_processed": len(completed),
        "selected_hour_count_processed": len(hours),
        "complete_utc_day_count_processed": sum(len(value) == 24 for value in day_hours.values()),
        "all_target_object_keys_etags_lengths_and_compressed_sha256_verified": len(completed) == len(rows),
        "all_records_parsed_twice_locally": len(completed) == len(rows),
        "scope_complete": len(completed) == len(rows),
    }


def _seal_files(
    *,
    artifact_directory: Path,
    meter: storage.WorkspaceMeter,
    files: dict[str, bytes],
    elapsed_runtime_milliseconds: int,
    limits: R11ALimits,
) -> None:
    manifest = schema.render_hash_manifest(files)
    schema.verify_hash_manifest(manifest, files)
    files["R11A_FILES.sha256"] = manifest
    scientific_paths = {path for _, path in schema.SCIENTIFIC_CONTAINERS}
    metadata_bytes = sum(len(data) for path, data in files.items() if path not in scientific_paths)
    artifact_directory.parent.mkdir(parents=True, exist_ok=True)
    stat = os.statvfs(artifact_directory.parent)
    unit = stat.f_frsize
    overwrite_reservation = 2 * ((limits.package_boundary_bytes + unit - 1) // unit) * unit
    boundary = schema.render_package_boundary(
        scientific_output_bytes=0,
        other_metadata_bytes_excluding_this_record=metadata_bytes,
        reserved_metadata_limit_bytes=limits.reserved_non_scientific_package_metadata_bytes,
        artifact_limit_bytes=limits.maximum_retained_artifact_bytes,
        preupload_elapsed_runtime_milliseconds=elapsed_runtime_milliseconds,
        hard_runtime_limit_milliseconds=limits.maximum_runtime_seconds * 1000,
        minimum_upload_window_milliseconds=limits.minimum_upload_window_seconds * 1000,
        preupload_peak_workspace_bytes=meter.peak_allocated_bytes,
        filesystem_allocation_unit_bytes=unit,
        boundary_overwrite_allocation_reservation_bytes=overwrite_reservation,
        workspace_limit_bytes=limits.maximum_ephemeral_workspace_bytes,
    )
    schema.verify_package_boundary(boundary)
    files["r11a-package-boundary.txt"] = boundary
    if sum(len(data) for data in files.values()) > limits.maximum_retained_artifact_bytes:
        raise R11AFailureArtifactError("minimal artifact exceeds frozen artifact cap")
    atomic = storage.AtomicOutputDirectory(artifact_directory, meter=meter)
    with atomic as staging:
        for path in sorted(files):
            schema.write_bytes_atomic(staging / path, files[path])
        meter.checkpoint("seal minimal R11A artifact")
        atomic.commit()


def seal_minimal_failure_artifact(
    *,
    artifact_directory: Path,
    meter: storage.WorkspaceMeter,
    state: ExecutionEvidenceState,
    context: Mapping[str, object],
    failure_class: str,
    failure_message: str,
    elapsed_runtime_milliseconds: int,
    limits: R11ALimits = DEFAULT_LIMITS,
) -> Mapping[str, object]:
    limits.validate()
    rows = state.object_rows()
    scope = exact_scope(rows)
    counts = source_prefix_counts(rows)
    zero_taxa = {name: 0 for name in TAXA}
    zero_units = {name: 0 for name in UNIT_TYPES}
    zero_relationships = {name: 0 for name in RELATIONSHIPS}
    files = {path: b"" for _, path in schema.SCIENTIFIC_CONTAINERS}
    files["r11a-object-two-pass-conservation.ndjson"] = schema.deterministic_ndjson(rows)
    files["r11a-reducer-partition-conservation.ndjson"] = schema.deterministic_ndjson(empty_reducer_rows())
    files["r11a-preflight-stop-evidence.json"] = schema.deterministic_json_document(list(state.stop_rows()))
    taxonomy = {
        "schema_version": "R11A_TAXONOMY_CONSERVATION_V1",
        "exact_scope_completion": scope,
        **counts,
        "repeat_occurrence_count_sum_n_minus_one": 0,
        "valid_tid_repeat_occurrence_count_sum_n_minus_one": 0,
        "invalid_tid_repeat_occurrence_count": 0,
        "repeat_relationship_counts": zero_relationships,
        "taxonomy_group_counts_by_class": zero_taxa,
        "taxonomy_occurrence_counts_by_class": dict(zero_taxa),
        "unclassifiable_group_counts_by_taxonomy_unit": zero_units,
        "unclassifiable_occurrence_counts_by_taxonomy_unit": dict(zero_units),
        "all_required_units_classified": False,
        "all_proof_references_resolve": False,
        "counts_conserve": False,
        "retention_caps_exceeded": False,
        "taxonomy_conservation_passed": False,
    }
    files["r11a-taxonomy-conservation.json"] = schema.deterministic_json_document(taxonomy)
    resources = {
        "schema_version": "R11A_RESOURCE_CAP_V1",
        "resource_measurement_completion_status": "PREFLIGHT_OR_SOURCE_INCOMPLETE",
        "scientific_output_logical_status": "EARLY_STOP_EMPTY",
        "peak_ephemeral_workspace_bytes": meter.peak_allocated_bytes,
        "elapsed_runtime_milliseconds": elapsed_runtime_milliseconds,
        "get_object_request_count": sum(int(row["get_object_request_count"]) for row in rows),
        "retry_count": 0,
        "total_compressed_bytes_received": sum(int(row["compressed_response_body_bytes_received"]) for row in rows),
        "total_decompressed_bytes_processed_across_local_parses": sum(
            int(row["first_local_parse_decompressed_bytes_consumed"])
            + int(row["second_local_parse_decompressed_bytes_consumed"])
            for row in rows
        ),
        "retained_scientific_output_entry_ledger": [
            schema.file_reference(path, b"", logical_status="EARLY_STOP_EMPTY")
            for _, path in schema.SCIENTIFIC_CONTAINERS
        ],
        "total_retained_scientific_output_bytes": 0,
        "reserved_non_scientific_package_metadata_bytes": limits.reserved_non_scientific_package_metadata_bytes,
        "retention_caps_exceeded": False,
        "triggered_stop_conditions": [state.stop_condition] if state.stop_condition else [],
    }
    files["r11a-resource-cap-conservation.json"] = schema.deterministic_json_document(resources)
    context_row = {
        **dict(context),
        "terminal_failure_class": failure_class,
        "terminal_failure_message_sha256": hashlib.sha256(
            failure_message.encode("utf-8", errors="strict")
        ).hexdigest(),
    }
    files["r11a-context.json"] = schema.deterministic_json_document(context_row)
    files["r11a-wallet-features.ndjson"] = b""
    files["r11a.rc"] = b"21\n"
    references: dict[str, object] = {}
    for name, path in schema.SCIENTIFIC_CONTAINERS:
        references[name] = schema.file_reference(path, b"", logical_status="EARLY_STOP_EMPTY")
    for name, path in schema.METADATA_CONTAINERS:
        if path == "r11a-result.json":
            continue
        references[name] = schema.file_reference(path, files[path])
    result = {
        "schema_version": "R11A_RESULT_V1",
        "diagnostic_id": "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-001",
        "container_references": references,
        "exact_scope_completion": scope,
        **counts,
        "repeat_occurrence_count_sum_n_minus_one": 0,
        "valid_tid_repeat_occurrence_count_sum_n_minus_one": 0,
        "invalid_tid_repeat_occurrence_count": 0,
        "affected_weak_key_group_count": 0,
        "affected_wallet_count": 0,
        "affected_tid_count": 0,
        "affected_canonical_key_count": 0,
        "affected_block_count": 0,
        "affected_object_count": 0,
        "affected_path_hour_count": 0,
        "affected_utc_day_count": 0,
        "repeat_relationship_counts": zero_relationships,
        "taxonomy_group_counts_by_class": zero_taxa,
        "taxonomy_occurrence_counts_by_class": dict(zero_taxa),
        "unclassifiable_group_count": 0,
        "unclassifiable_group_counts_by_taxonomy_unit": zero_units,
        "unclassifiable_occurrence_counts_by_taxonomy_unit": dict(zero_units),
        "unique_block_number_count": None,
        "singleton_block_number_count": None,
        "singleton_block_observation_count": None,
        "singleton_all_block_aggregate_sha256": None,
        "duplicate_observation_output_sha256": hashlib.sha256(b"").hexdigest(),
        "duplicate_observation_output_bytes": 0,
        "block_replay_output_sha256": hashlib.sha256(b"").hexdigest(),
        "block_replay_output_bytes": 0,
        "retention_caps_exceeded": False,
        "fill_time_versus_block_time_evidence_status": "UNKNOWN_NONCOMPARABLE_OR_INCOMPLETE",
        "taxonomy_conservation_passed": False,
        "terminal_class": "R11A_DIAGNOSTIC_INCOMPLETE",
        "root_cause_claim_status": "NOT_PROVEN",
    }
    files["r11a-result.json"] = schema.deterministic_json_document(result)
    _seal_files(
        artifact_directory=artifact_directory,
        meter=meter,
        files=files,
        elapsed_runtime_milliseconds=elapsed_runtime_milliseconds,
        limits=limits,
    )
    return result
