from __future__ import annotations

import dataclasses
import hashlib
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from . import _artifact_core_r7 as _core
from .artifact_schema import (
    AUTHORITATIVE_UNIT_UNIVERSES,
    BOUNDARY_FILE,
    CONSERVATION_FILE,
    CONTEXT_FILE,
    DIAGNOSTIC_ID,
    EXPECTED_ARTIFACT_FILES,
    HASH_MANIFEST_FILE,
    IMPLEMENTATION_ID,
    OBJECT_LEDGER_FILE,
    PARSE_CONSERVATION_FIELDS,
    PHASES,
    REDUCER_LEDGER_FILE,
    RESOURCE_LEDGER_FILE,
    RESULT_FILE,
    RETURN_CODE_FILE,
    SCIENCE_CONTAINERS,
    STOP_LEDGER_FILE,
    TAXA,
    TERMINAL_GATE_NAMES,
    WALLET_FEATURE_FILE,
    exact_return_code,
    exact_root_cause_status,
    exact_scientific_status,
    validate_object_row_shape,
    validate_sha256,
    validate_terminal_gates,
    validate_research_conclusion,
    validate_terminal_tuple,
    validate_universe_rows,
    zero_taxon_counts,
)
from .canonical import FrozenObject, NumberToken, canonical_json_bytes, strict_json_loads
from .limits import R11ALimits
from .runtime import ExecutionEvidenceState, RuntimeGuard
from .selection import DEFAULT_SELECTION
from .storage_r7 import (
    WorkspaceMeter,
    cleanup_checked_read_bytes,
    cleanup_checked_read_text,
    directory_size,
)
from .taxonomy import TaxonomyResult

ArtifactBoundaryError = _core.ArtifactBoundaryError
ScientificCapExceeded = _core.ScientificCapExceeded
FileEvidence = _core.FileEvidence
ArtifactOutcome = _core.ArtifactOutcome
StreamingScientificEmitter = _core.StreamingScientificEmitter
SharedMetadataWriter = _core.SharedMetadataWriter
complete_reducer_rows = _core.complete_reducer_rows

_JOIN_FIELDS = (
    "unit_count",
    "proof_count",
    "proof_reference_count",
    "retained_row_reference_count",
    "all_unit_ids_unique",
    "all_proof_ids_unique",
    "all_nonnull_proof_references_resolve_exactly_once",
    "all_retained_rows_reference_exactly_one_unit",
    "all_referenced_projections_are_byte_equal",
    "all_retained_row_counts_match_unit_occurrence_counts",
)

_BOUNDARY_FIELDS = {
    "schema_version",
    "record_type",
    "diagnostic_id",
    "implementation_id",
    "preboundary_file_count",
    "preboundary_bytes",
    "metadata_bytes",
    "boundary_elapsed_seconds_floor",
    "maximum_runtime_seconds",
    "minimum_upload_window_seconds",
    "maximum_retained_artifact_bytes",
    "maximum_ephemeral_workspace_bytes",
    "reserved_non_scientific_package_metadata_bytes",
    "workspace_tracked_bytes_before_boundary",
    "workspace_reserved_bytes_before_boundary",
    "metadata_within_reservation",
    "final_staging_within_artifact_limit",
    "preupload_runtime_within_hard_limit_after_upload_window",
    "boundary_write_within_workspace_limit",
}

_RESULT_FIELDS = {
    "schema_version",
    "diagnostic_id",
    "implementation_id",
    "terminal_class",
    "research_conclusion",
    "scientific_output_status",
    "root_cause_claim_status",
    "return_code",
    "scientific_files",
    "wallet_feature_rows",
    "rerun_authorized",
    "R11_CLOSED",
    "R12_READY",
}

_CONTEXT_COMMON_FIELDS = {
    "schema_version",
    "diagnostic_id",
    "implementation_id",
    "execution_phase",
    "event_name",
    "dispatch_ref",
    "dispatch_sha",
    "checked_out_commit",
    "workflow_run_id",
    "workflow_run_attempt",
    "workflow_start_epoch_ns",
    "repository",
    "workflow_name",
    "principal_observed",
    "s3_requests_executed",
    "object_bytes_downloaded",
    "rerun_authorized",
}

_CONTEXT_BOUND_FIELDS = {
    "approval_id",
    "approval_text_sha256",
    "execution_release_id",
    "execution_release_blob_sha256",
    "activation_id",
    "implementation_contract_sha256",
    "workflow_sha256",
    "collector_sha256",
    "validator_sha256",
    "selection_sha256",
    "pricing_snapshot_sha256",
    "single_use_window_start_utc",
    "observed_account_id",
    "observed_assumed_role_session_arn",
    "observed_session_name",
    "expected_role_arn",
    "pricing_projection_eur_micros",
    "raw_aws_credentials_retained",
    "raw_oidc_token_retained",
    "raw_sts_response_retained",
}


def _validate_context_shape(context: Mapping[str, object]) -> None:
    optional_minimal = {"failure_exception_type_sha256"}
    observed = set(context)
    if observed == _CONTEXT_COMMON_FIELDS | _CONTEXT_BOUND_FIELDS:
        if context["principal_observed"] is not True:
            raise ArtifactBoundaryError("bound context lacks observed principal")
        if (
            context["observed_account_id"] != "630956766927"
            or context["observed_session_name"]
            != "HLArchiveR11AIdentityBoundary"
            or context["expected_role_arn"]
            != (
                "arn:aws:iam::630956766927:role/"
                "onchain-wallet-intelligence-hl-archive-identity-r11a"
            )
            or re.fullmatch(
                r"arn:aws:sts::630956766927:assumed-role/"
                r"onchain-wallet-intelligence-hl-archive-identity-r11a/"
                r"HLArchiveR11AIdentityBoundary",
                str(context["observed_assumed_role_session_arn"]),
            )
            is None
            or context["raw_aws_credentials_retained"] is not False
            or context["raw_oidc_token_retained"] is not False
            or context["raw_sts_response_retained"] is not False
            or _integer(
                context["pricing_projection_eur_micros"],
                "pricing projection",
            )
            < 0
        ):
            raise ArtifactBoundaryError("bound context principal or retention drift")
        for name in (
            "approval_text_sha256",
            "execution_release_blob_sha256",
            "implementation_contract_sha256",
            "workflow_sha256",
            "collector_sha256",
            "validator_sha256",
            "selection_sha256",
            "pricing_snapshot_sha256",
        ):
            validate_sha256(context[name], f"context {name}")
    elif observed not in {
        frozenset(_CONTEXT_COMMON_FIELDS),
        frozenset(_CONTEXT_COMMON_FIELDS | optional_minimal),
    }:
        raise ArtifactBoundaryError("artifact context schema drift")
    elif type(context["principal_observed"]) is not bool:
        raise ArtifactBoundaryError("minimal context principal flag drift")
    if "failure_exception_type_sha256" in context:
        validate_sha256(
            context["failure_exception_type_sha256"],
            "failure exception type SHA",
        )
    if (
        context["schema_version"] != "2.0"
        or context["diagnostic_id"] != DIAGNOSTIC_ID
        or context["implementation_id"] != IMPLEMENTATION_ID
        or context["event_name"] != "workflow_dispatch"
        or context["dispatch_ref"] != "refs/heads/main"
        or context["dispatch_sha"] != context["checked_out_commit"]
        or re.fullmatch(r"[0-9a-f]{40}", str(context["dispatch_sha"])) is None
        or _integer(context["workflow_run_id"], "workflow run ID") <= 0
        or _integer(context["workflow_run_attempt"], "workflow run attempt") != 1
        or _integer(context["workflow_start_epoch_ns"], "workflow start epoch") <= 0
        or context["repository"] != "Mathisve1/onchain-wallet-intelligence-lab"
        or context["workflow_name"]
        != "Hyperliquid Archive R11A Identity Boundary Diagnostic"
        or context["rerun_authorized"] is not False
    ):
        raise ArtifactBoundaryError("artifact context identity or authority drift")


def _hash(path: Path) -> str:
    return _core._hash(path)


def _object(value: object, label: str) -> FrozenObject:
    return _core._object(value, label)


def _integer(value: object, label: str) -> int:
    return _core._integer(value, label)


def _parse_ndjson(path: Path) -> tuple[FrozenObject, ...]:
    return _core._parse_ndjson(path)


def _zero_universe_rows() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "unit_universe": universe,
            "group_count": 0,
            "occurrence_count": 0,
            "primary_taxon_group_counts": zero_taxon_counts(),
            "primary_taxon_occurrence_counts": zero_taxon_counts(),
            "unclassifiable_group_count": 0,
            "unclassifiable_occurrence_count": 0,
        }
        for universe in AUTHORITATIVE_UNIT_UNIVERSES
    )


def _zero_join_mapping() -> dict[str, object]:
    return {
        "unit_count": 0,
        "proof_count": 0,
        "proof_reference_count": 0,
        "retained_row_reference_count": 0,
        "all_unit_ids_unique": True,
        "all_proof_ids_unique": True,
        "all_nonnull_proof_references_resolve_exactly_once": True,
        "all_retained_rows_reference_exactly_one_unit": True,
        "all_referenced_projections_are_byte_equal": True,
        "all_retained_row_counts_match_unit_occurrence_counts": True,
    }


def _validate_join_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != set(_JOIN_FIELDS):
        raise ArtifactBoundaryError("join validation schema drift")
    for field in _JOIN_FIELDS[:4]:
        if _integer(value[field], field) < 0:
            raise ArtifactBoundaryError("negative join validation count")
    for field in _JOIN_FIELDS[4:]:
        if type(value[field]) is not bool:
            raise ArtifactBoundaryError("join validation flag is not boolean")
    return value


def _exact_multiplicity_matches(
    value: object,
    *,
    source_count: int,
    destination_count: int,
) -> bool:
    if not isinstance(value, Mapping) or set(value) != {
        "source_record_count",
        "destination_record_count",
        "source_distinct_blob_count",
        "destination_distinct_blob_count",
        "exact_sqlite_blob_multiplicity_verified",
    }:
        return False
    return bool(
        value["exact_sqlite_blob_multiplicity_verified"] is True
        and _integer(value["source_record_count"], "multiplicity source count")
        == source_count
        and _integer(
            value["destination_record_count"],
            "multiplicity destination count",
        )
        == destination_count
        and _integer(
            value["source_distinct_blob_count"],
            "multiplicity source distinct count",
        )
        == _integer(
            value["destination_distinct_blob_count"],
            "multiplicity destination distinct count",
        )
    )


def _reducer_summary(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if len(rows) != 512:
        raise ArtifactBoundaryError("primary reducer row count drift")
    totals: dict[str, dict[str, int]] = {
        "BLOCK_NUMBER": {
            "source_record_count": 0,
            "repeat_group_count": 0,
            "repeat_observation_count": 0,
        },
        "LEGACY_WEAK_KEY_HASH": {
            "source_record_count": 0,
            "repeat_group_count": 0,
            "repeat_observation_count": 0,
        },
    }
    all_exact = True
    expected_fields = {
        "record_type",
        "reducer_id",
        "partition_ordinal_zero_based",
        "processing_status",
        "partition_function",
        "source_record_count",
        "source_logical_bytes",
        "destination_record_count",
        "destination_logical_bytes",
        "exact_multiplicity",
        "sorted_stream_sha256",
        "discovered_repeat_group_count",
        "discovered_repeat_observation_count",
    }
    for position, row in enumerate(rows):
        if set(row) != expected_fields:
            raise ArtifactBoundaryError("primary reducer row schema drift")
        if row["record_type"] != "R11A_V2_REDUCER_PARTITION_CONSERVATION":
            raise ArtifactBoundaryError("primary reducer record type drift")
        if row["partition_function"] != (
            "FIRST_BYTE_OF_SHA256_OF_COMPLETE_EQUALITY_KEY_BYTES"
        ):
            raise ArtifactBoundaryError("primary reducer partition function drift")
        expected_reducer = "BLOCK_NUMBER" if position < 256 else "LEGACY_WEAK_KEY_HASH"
        expected_partition = position if position < 256 else position - 256
        if row["reducer_id"] != expected_reducer:
            raise ArtifactBoundaryError("primary reducer ordering drift")
        if _integer(row["partition_ordinal_zero_based"], "partition ordinal") != expected_partition:
            raise ArtifactBoundaryError("primary reducer partition ordering drift")
        source = row["source_record_count"]
        destination = row["destination_record_count"]
        source_bytes = row["source_logical_bytes"]
        destination_bytes = row["destination_logical_bytes"]
        repeat_groups = row["discovered_repeat_group_count"]
        repeat_observations = row["discovered_repeat_observation_count"]
        exact = row["exact_multiplicity"]
        if source is None:
            if any(
                value is not None
                for value in (
                    destination,
                    source_bytes,
                    destination_bytes,
                    repeat_groups,
                    repeat_observations,
                    exact,
                    row["sorted_stream_sha256"],
                )
            ):
                raise ArtifactBoundaryError("unprocessed reducer row contains partial evidence")
            all_exact = False
            continue
        observed_source = _integer(source, "reducer source count")
        observed_destination = _integer(destination, "reducer destination count")
        observed_source_bytes = _integer(source_bytes, "reducer source bytes")
        observed_destination_bytes = _integer(
            destination_bytes, "reducer destination bytes"
        )
        observed_groups = _integer(repeat_groups, "repeat group count")
        observed_observations = _integer(
            repeat_observations, "repeat observation count"
        )
        if (
            not _exact_multiplicity_matches(
                exact,
                source_count=observed_source,
                destination_count=observed_destination,
            )
            or observed_source != observed_destination
            or observed_source_bytes != observed_destination_bytes
            or observed_observations > observed_source
            or observed_groups > observed_observations
        ):
            raise ArtifactBoundaryError(
                "processed reducer partition lacks exact multiset conservation"
            )
        validate_sha256(row["sorted_stream_sha256"], "sorted reducer stream SHA")
        totals[expected_reducer]["source_record_count"] += observed_source
        totals[expected_reducer]["repeat_group_count"] += observed_groups
        totals[expected_reducer]["repeat_observation_count"] += (
            observed_observations
        )
    block = totals["BLOCK_NUMBER"]
    weak = totals["LEGACY_WEAK_KEY_HASH"]
    return {
        "all_partitions_complete_and_exact": all_exact,
        "block_source_record_count": block["source_record_count"],
        "block_repeat_group_count": block["repeat_group_count"],
        "block_repeat_observation_count": block["repeat_observation_count"],
        "block_singleton_observation_count": (
            block["source_record_count"] - block["repeat_observation_count"]
        ),
        "legacy_source_record_count": weak["source_record_count"],
        "legacy_repeat_group_count": weak["repeat_group_count"],
        "legacy_repeat_observation_count": weak["repeat_observation_count"],
        "legacy_repeat_occurrence_count": (
            weak["repeat_observation_count"] - weak["repeat_group_count"]
        ),
    }


def _validate_secondary_reducers(value: object) -> dict[str, int] | None:
    if not isinstance(value, (tuple, list)):
        raise ArtifactBoundaryError("secondary reducer rows must be an array")
    rows = tuple(value)
    reducer_ids = (
        "MATERIALIZED_BLOCK_NUMBER",
        "PROTOCOL_MATCHED_TRADE_PER_RAW_BLOCK",
        "EXACT_LEGACY_WEAK_KEY",
    )
    if len(rows) != 256 * len(reducer_ids):
        return None
    source_totals = {reducer_id: 0 for reducer_id in reducer_ids}
    expected_fields = {
        "record_type",
        "reducer_id",
        "partition_ordinal_zero_based",
        "source_record_count",
        "source_logical_bytes",
        "destination_record_count",
        "destination_logical_bytes",
        "exact_multiplicity",
        "sorted_stream_sha256",
    }
    for position, raw in enumerate(rows):
        if not isinstance(raw, Mapping) or set(raw) != expected_fields:
            raise ArtifactBoundaryError("secondary reducer row schema drift")
        expected_reducer = reducer_ids[position // 256]
        expected_partition = position % 256
        if (
            raw["record_type"]
            != "R11A_V2_SECONDARY_REDUCER_CONSERVATION"
            or raw["reducer_id"] != expected_reducer
            or _integer(raw["partition_ordinal_zero_based"], "secondary partition")
            != expected_partition
        ):
            raise ArtifactBoundaryError("secondary reducer ordering drift")
        source_count = _integer(raw["source_record_count"], "secondary source count")
        destination_count = _integer(
            raw["destination_record_count"], "secondary destination count"
        )
        source_bytes = _integer(raw["source_logical_bytes"], "secondary source bytes")
        destination_bytes = _integer(
            raw["destination_logical_bytes"], "secondary destination bytes"
        )
        multiplicity = raw["exact_multiplicity"]
        if (
            not _exact_multiplicity_matches(
                multiplicity,
                source_count=source_count,
                destination_count=destination_count,
            )
            or source_count != destination_count
            or source_bytes != destination_bytes
        ):
            return None
        validate_sha256(raw["sorted_stream_sha256"], "secondary sorted stream SHA")
        source_totals[expected_reducer] += source_count
    return source_totals


def _aggregate_from_object_rows(
    rows: Sequence[Mapping[str, object]],
) -> tuple[dict[str, int], bool]:
    if len(rows) != 72:
        raise ArtifactBoundaryError("object ledger must contain 72 rows")
    result: dict[str, int] = {
        "selected_object_count": 72,
        "get_object_request_count": 0,
        "first_pass_completed_object_count": 0,
        "second_pass_completed_object_count": 0,
        "first_pass_decompressed_bytes": 0,
        "second_pass_decompressed_bytes": 0,
        "first_pass_record_count": 0,
        "second_pass_record_count": 0,
        "first_pass_event_count": 0,
        "second_pass_event_count": 0,
    }
    for pass_name in ("first_pass", "second_pass"):
        for field in PARSE_CONSERVATION_FIELDS:
            result[f"{pass_name}_{field}"] = 0
    all_complete = True
    for ordinal, row in enumerate(rows):
        validate_object_row_shape(row)
        if _integer(row["object_ordinal_zero_based"], "object ordinal") != ordinal:
            raise ArtifactBoundaryError("object ledger ordering drift")
        target = DEFAULT_SELECTION.targets[ordinal]
        expected_identity = _object(row["expected_identity"], "expected identity")
        if (
            row["object_key"] != target.object_key
            or row["source_path_hour_utc"] != target.source_path_hour_utc
            or _integer(expected_identity["size_bytes"], "expected size")
            != target.expected_size_bytes
            or expected_identity["etag"] != target.expected_etag
            or expected_identity["compressed_sha256"]
            != target.expected_compressed_sha256
        ):
            raise ArtifactBoundaryError(
                "object evidence does not join exactly once to frozen selection"
            )
        request = _object(row["request"], "request")
        result["get_object_request_count"] += _integer(
            request["count"], "request count"
        )
        for pass_name in ("first_pass", "second_pass"):
            value = row[pass_name]
            if value is None:
                all_complete = False
                continue
            observed = _object(value, pass_name)
            result[f"{pass_name}_completed_object_count"] += 1
            for field in ("decompressed_bytes", "record_count", "event_count"):
                result[f"{pass_name}_{field}"] += _integer(
                    observed[field], f"{pass_name}.{field}"
                )
            conservation = _object(
                observed["conservation"], f"{pass_name}.conservation"
            )
            for field in PARSE_CONSERVATION_FIELDS:
                result[f"{pass_name}_{field}"] += _integer(
                    conservation[field], f"{pass_name}.{field}"
                )
        if row["terminal_status"] != "COMPLETE_TWO_LOCAL_PASSES":
            all_complete = False
    return result, all_complete


def _validate_stop_ledger(
    *,
    entries: object,
    terminal: str,
    context_phase: object,
    object_rows: Sequence[Mapping[str, object]],
) -> None:
    if not isinstance(entries, tuple):
        raise ArtifactBoundaryError("stop entries must be array")
    if context_phase not in PHASES:
        raise ArtifactBoundaryError("context execution phase is unknown")
    object_stops: set[tuple[int, str]] = set()
    for sequence, row in enumerate(entries):
        observed = _object(row, "stop row")
        if set(observed) != {
            "sequence_zero_based",
            "diagnostic_id",
            "stop_code",
            "phase",
            "object_ordinal_zero_based",
            "evidence_sha256",
        }:
            raise ArtifactBoundaryError("stop ledger row schema drift")
        if _integer(observed["sequence_zero_based"], "stop sequence") != sequence:
            raise ArtifactBoundaryError("stop ledger sequence drift")
        if observed["diagnostic_id"] != DIAGNOSTIC_ID:
            raise ArtifactBoundaryError("stop diagnostic ID drift")
        if (
            not isinstance(observed["stop_code"], str)
            or not observed["stop_code"]
            or observed["phase"] not in PHASES
            or PHASES.index(str(observed["phase"])) > PHASES.index(str(context_phase))
        ):
            raise ArtifactBoundaryError("stop evidence phase or code drift")
        validate_sha256(observed["evidence_sha256"], "stop evidence SHA")
        ordinal = observed["object_ordinal_zero_based"]
        if ordinal is not None:
            value = _integer(ordinal, "stopped object ordinal")
            if not 0 <= value < 72:
                raise ArtifactBoundaryError("stopped object ordinal outside scope")
            pair = (value, str(observed["stop_code"]))
            if pair in object_stops:
                raise ArtifactBoundaryError("ambiguous duplicate object stop evidence")
            object_stops.add(pair)
    ledger_object_stops = {
        (ordinal, str(row["terminal_error_code"]))
        for ordinal, row in enumerate(object_rows)
        if row["terminal_status"] == "STOPPED"
    }
    if ledger_object_stops != object_stops:
        raise ArtifactBoundaryError("object terminal and stop ledger disagree")
    if terminal == "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE":
        if entries:
            raise ArtifactBoundaryError("RC0 must not contain stop evidence")
    elif terminal == "R11A_V2_DIAGNOSTIC_INCOMPLETE":
        if len(entries) != 1:
            raise ArtifactBoundaryError("RC20 requires one scientific stop reason")
        reason = _object(entries[0], "RC20 stop")
        if (
            reason["stop_code"] != "FULL_SCOPE_TAXONOMY_INCOMPLETE"
            or reason["phase"] != "TAXONOMY"
            or reason["object_ordinal_zero_based"] is not None
        ):
            raise ArtifactBoundaryError("RC20 stop evidence is not scientific-only")
    elif not entries:
        raise ArtifactBoundaryError("RC21 requires fail-closed stop evidence")


def _same_two_pass_aggregate(counts: Mapping[str, int]) -> bool:
    if counts["first_pass_completed_object_count"] != 72:
        return False
    if counts["second_pass_completed_object_count"] != 72:
        return False
    for suffix in (
        "decompressed_bytes",
        "record_count",
        "event_count",
        *PARSE_CONSERVATION_FIELDS,
    ):
        if counts[f"first_pass_{suffix}"] != counts[f"second_pass_{suffix}"]:
            return False
    return True


def _raw_event_partitions_conserve(counts: Mapping[str, int]) -> bool:
    for pass_name in ("first_pass", "second_pass"):
        raw = counts[f"{pass_name}_raw_event_observation_count"]
        if raw != counts[f"{pass_name}_event_count"]:
            return False
        for valid, invalid in (
            ("valid_wallet_occurrence_count", "invalid_wallet_occurrence_count"),
            ("valid_coin_occurrence_count", "invalid_coin_occurrence_count"),
            ("valid_tid_occurrence_count", "invalid_tid_occurrence_count"),
        ):
            if (
                counts[f"{pass_name}_{valid}"]
                + counts[f"{pass_name}_{invalid}"]
                != raw
            ):
                return False
    return True


def _boundary_payload(
    staging: Path,
    limits: R11ALimits,
    runtime_guard: RuntimeGuard,
    meter: WorkspaceMeter,
) -> bytes:
    preboundary = [value for value in staging.iterdir() if value.is_file()]
    preboundary_bytes = sum(value.stat().st_size for value in preboundary)
    metadata_bytes = sum(
        value.stat().st_size
        for value in preboundary
        if value.name not in SCIENCE_CONTAINERS
    )
    elapsed = runtime_guard.elapsed_seconds_floor()
    tracked = meter.known_bytes
    reserved = meter.reserved_bytes
    value = {
        "schema_version": "2.0",
        "record_type": "R11A_V2_PACKAGE_BOUNDARY",
        "diagnostic_id": DIAGNOSTIC_ID,
        "implementation_id": IMPLEMENTATION_ID,
        "preboundary_file_count": len(preboundary),
        "preboundary_bytes": preboundary_bytes,
        "metadata_bytes": metadata_bytes,
        "boundary_elapsed_seconds_floor": elapsed,
        "maximum_runtime_seconds": limits.maximum_runtime_seconds,
        "minimum_upload_window_seconds": limits.minimum_upload_window_seconds,
        "maximum_retained_artifact_bytes": limits.maximum_retained_artifact_bytes,
        "maximum_ephemeral_workspace_bytes": (
            limits.maximum_ephemeral_workspace_bytes
        ),
        "reserved_non_scientific_package_metadata_bytes": (
            limits.reserved_non_scientific_package_metadata_bytes
        ),
        "workspace_tracked_bytes_before_boundary": tracked,
        "workspace_reserved_bytes_before_boundary": reserved,
        "metadata_within_reservation": (
            metadata_bytes + limits.package_boundary_bytes
            <= limits.reserved_non_scientific_package_metadata_bytes
        ),
        "final_staging_within_artifact_limit": (
            preboundary_bytes + limits.package_boundary_bytes
            <= limits.maximum_retained_artifact_bytes
        ),
        "preupload_runtime_within_hard_limit_after_upload_window": (
            elapsed
            < limits.maximum_runtime_seconds
            - limits.minimum_upload_window_seconds
        ),
        "boundary_write_within_workspace_limit": (
            tracked + limits.package_boundary_bytes
            <= limits.maximum_ephemeral_workspace_bytes
            and reserved >= limits.package_boundary_bytes
        ),
    }
    prefix = canonical_json_bytes(value, final_newline=False)
    if len(prefix) + 1 > limits.package_boundary_bytes:
        raise ArtifactBoundaryError("package boundary exceeds exact 1,024 bytes")
    return (
        prefix
        + b" " * (limits.package_boundary_bytes - len(prefix) - 1)
        + b"\n"
    )


def _validate_resource(
    value: Mapping[str, object],
    limits: R11ALimits,
) -> None:
    expected = {
        "schema_version",
        "diagnostic_id",
        "measurements",
        "tracked_workspace_bytes_before_packaging",
        "reserved_workspace_bytes_before_packaging",
        "peak_tracked_workspace_bytes",
        "peak_bounded_workspace_bytes",
        "maximum_ephemeral_workspace_bytes",
        "packaging_elapsed_seconds_floor",
        "package_flags",
    }
    if set(value) != expected:
        raise ArtifactBoundaryError("resource ledger schema drift")
    if (
        value["schema_version"] != "2.0"
        or value["diagnostic_id"] != DIAGNOSTIC_ID
    ):
        raise ArtifactBoundaryError("resource ledger identity drift")
    elapsed = _integer(
        value["packaging_elapsed_seconds_floor"],
        "packaging elapsed seconds",
    )
    tracked = _integer(
        value["tracked_workspace_bytes_before_packaging"],
        "tracked workspace bytes",
    )
    reserved = _integer(
        value["reserved_workspace_bytes_before_packaging"],
        "reserved workspace bytes",
    )
    peak_tracked = _integer(
        value["peak_tracked_workspace_bytes"],
        "peak tracked workspace bytes",
    )
    peak_bounded = _integer(
        value["peak_bounded_workspace_bytes"],
        "peak bounded workspace bytes",
    )
    if value["maximum_ephemeral_workspace_bytes"] != (
        limits.maximum_ephemeral_workspace_bytes
    ):
        raise ArtifactBoundaryError("resource workspace cap drift")
    if tracked + reserved > limits.maximum_ephemeral_workspace_bytes:
        raise ArtifactBoundaryError("resource ledger exceeds workspace cap")
    if not (
        tracked <= peak_tracked <= peak_bounded
        and tracked + reserved <= peak_bounded
        and peak_bounded <= limits.maximum_ephemeral_workspace_bytes
    ):
        raise ArtifactBoundaryError("resource peak accounting is contradictory")
    measurements = value["measurements"]
    if not isinstance(measurements, tuple) or not measurements:
        raise ArtifactBoundaryError("resource measurements must be a nonempty array")
    previous_elapsed = -1
    previous_requests = -1
    measurement_fields = {
        "record_type",
        "phase",
        "elapsed_runtime_seconds_floor",
        "tracked_workspace_bytes",
        "reserved_workspace_bytes",
        "peak_tracked_workspace_bytes",
        "peak_bounded_workspace_bytes",
        "network_request_count",
    }
    for measurement_value in measurements:
        measurement = _object(measurement_value, "resource measurement")
        if not measurement_fields.issubset(measurement):
            raise ArtifactBoundaryError("resource measurement base schema drift")
        if (
            measurement["record_type"]
            != "R11A_V2_RESOURCE_MEASUREMENT"
            or not isinstance(measurement["phase"], str)
            or not measurement["phase"]
        ):
            raise ArtifactBoundaryError("resource measurement identity drift")
        row_elapsed = _integer(
            measurement["elapsed_runtime_seconds_floor"],
            "resource measurement elapsed",
        )
        row_tracked = _integer(
            measurement["tracked_workspace_bytes"],
            "resource measurement tracked bytes",
        )
        row_reserved = _integer(
            measurement["reserved_workspace_bytes"],
            "resource measurement reserved bytes",
        )
        row_peak_tracked = _integer(
            measurement["peak_tracked_workspace_bytes"],
            "resource measurement peak tracked bytes",
        )
        row_peak_bounded = _integer(
            measurement["peak_bounded_workspace_bytes"],
            "resource measurement peak bounded bytes",
        )
        row_requests = _integer(
            measurement["network_request_count"],
            "resource measurement request count",
        )
        if (
            row_elapsed < previous_elapsed
            or row_elapsed > elapsed
            or row_requests < previous_requests
            or row_requests > 72
            or min(row_tracked, row_reserved, row_peak_tracked, row_peak_bounded) < 0
            or not (
                row_tracked <= row_peak_tracked <= row_peak_bounded
                and row_tracked + row_reserved <= row_peak_bounded
                and row_peak_tracked <= peak_tracked
                and row_peak_bounded <= peak_bounded
            )
        ):
            raise ArtifactBoundaryError(
                "resource measurement is temporally or spatially contradictory"
            )
        previous_elapsed = row_elapsed
        previous_requests = row_requests
    flags = _object(value["package_flags"], "package flags")
    expected_flags = {
        "preupload_runtime_within_hard_limit_after_upload_window": (
            elapsed
            < limits.maximum_runtime_seconds
            - limits.minimum_upload_window_seconds
        ),
        "scientific_runtime_completed_before_packaging_reservation": (
            elapsed < limits.maximum_runtime_seconds
        ),
    }
    if {key: flags[key] for key in flags} != expected_flags:
        raise ArtifactBoundaryError("resource package flags are not evidence-derived")


def _validate_boundary(
    path: Path,
    boundary: Mapping[str, object],
    resource: Mapping[str, object],
    limits: R11ALimits,
) -> None:
    if set(boundary) != _BOUNDARY_FIELDS:
        raise ArtifactBoundaryError("package boundary schema drift")
    if boundary["record_type"] != "R11A_V2_PACKAGE_BOUNDARY":
        raise ArtifactBoundaryError("package boundary record type drift")
    if boundary["diagnostic_id"] != DIAGNOSTIC_ID:
        raise ArtifactBoundaryError("package boundary diagnostic ID drift")
    if boundary["implementation_id"] != IMPLEMENTATION_ID:
        raise ArtifactBoundaryError("package boundary implementation ID drift")
    preboundary_files = [
        value for value in path.iterdir() if value.name != BOUNDARY_FILE
    ]
    preboundary_bytes = sum(value.stat().st_size for value in preboundary_files)
    metadata_bytes = sum(
        value.stat().st_size
        for value in preboundary_files
        if value.name not in SCIENCE_CONTAINERS
    )
    formulas = {
        "preboundary_file_count": len(preboundary_files),
        "preboundary_bytes": preboundary_bytes,
        "metadata_bytes": metadata_bytes,
        "maximum_runtime_seconds": limits.maximum_runtime_seconds,
        "minimum_upload_window_seconds": limits.minimum_upload_window_seconds,
        "maximum_retained_artifact_bytes": limits.maximum_retained_artifact_bytes,
        "maximum_ephemeral_workspace_bytes": (
            limits.maximum_ephemeral_workspace_bytes
        ),
        "reserved_non_scientific_package_metadata_bytes": (
            limits.reserved_non_scientific_package_metadata_bytes
        ),
    }
    for key, expected in formulas.items():
        if _integer(boundary[key], key) != expected:
            raise ArtifactBoundaryError(f"package boundary formula drift: {key}")
    elapsed = _integer(
        boundary["boundary_elapsed_seconds_floor"],
        "boundary elapsed",
    )
    tracked = _integer(
        boundary["workspace_tracked_bytes_before_boundary"],
        "boundary tracked workspace",
    )
    reserved = _integer(
        boundary["workspace_reserved_bytes_before_boundary"],
        "boundary reserved workspace",
    )
    expected_flags = {
        "metadata_within_reservation": (
            metadata_bytes + limits.package_boundary_bytes
            <= limits.reserved_non_scientific_package_metadata_bytes
        ),
        "final_staging_within_artifact_limit": (
            preboundary_bytes + limits.package_boundary_bytes
            <= limits.maximum_retained_artifact_bytes
        ),
        "preupload_runtime_within_hard_limit_after_upload_window": (
            elapsed
            < limits.maximum_runtime_seconds
            - limits.minimum_upload_window_seconds
        ),
        "boundary_write_within_workspace_limit": (
            tracked + limits.package_boundary_bytes
            <= limits.maximum_ephemeral_workspace_bytes
            and reserved >= limits.package_boundary_bytes
        ),
    }
    for key, expected in expected_flags.items():
        if boundary[key] is not expected or expected is not True:
            raise ArtifactBoundaryError(
                f"package boundary flag is false or unsupported: {key}"
            )
    resource_elapsed = _integer(
        resource["packaging_elapsed_seconds_floor"],
        "resource packaging elapsed",
    )
    if elapsed < resource_elapsed:
        raise ArtifactBoundaryError("boundary elapsed precedes resource evidence")


def validate_artifact(path: Path, limits: R11ALimits) -> None:
    _core.validate_artifact(path, limits)
    result = _object(
        strict_json_loads(
            cleanup_checked_read_bytes(
                path / RESULT_FILE,
                label="contract result validation",
            )
        ),
        "result",
    )
    conservation = _object(
        strict_json_loads(
            cleanup_checked_read_bytes(
                path / CONSERVATION_FILE,
                label="contract conservation validation",
            )
        ),
        "conservation",
    )
    resource = _object(
        strict_json_loads(
            cleanup_checked_read_bytes(
                path / RESOURCE_LEDGER_FILE,
                label="contract resource validation",
            )
        ),
        "resource",
    )
    context = _object(
        strict_json_loads(
            cleanup_checked_read_bytes(
                path / CONTEXT_FILE,
                label="contract context validation",
            )
        ),
        "context",
    )
    if set(result) != _RESULT_FIELDS or result["schema_version"] != "2.0":
        raise ArtifactBoundaryError("result schema drift")
    scientific_files = _object(result["scientific_files"], "scientific files")
    if set(scientific_files) != set(SCIENCE_CONTAINERS):
        raise ArtifactBoundaryError("scientific file evidence set drift")
    for name in SCIENCE_CONTAINERS:
        evidence = _object(scientific_files[name], f"scientific file {name}")
        if (
            set(evidence) != {"path", "byte_count", "row_count", "sha256"}
            or evidence["path"] != name
            or _integer(evidence["byte_count"], f"{name} byte count") < 0
            or _integer(evidence["row_count"], f"{name} row count") < 0
        ):
            raise ArtifactBoundaryError("scientific file evidence schema drift")
        validate_sha256(evidence["sha256"], f"{name} SHA")
        payload = cleanup_checked_read_bytes(
            path / name,
            label=f"contract scientific validation {name}",
        )
        if (
            _integer(evidence["byte_count"], f"{name} byte count") != len(payload)
            or _integer(evidence["row_count"], f"{name} row count")
            != len(payload.splitlines())
            or evidence["sha256"] != hashlib.sha256(payload).hexdigest()
        ):
            raise ArtifactBoundaryError("scientific file evidence is not exact")
    _validate_context_shape(context)
    expected_conservation_fields = {
        "schema_version",
        "diagnostic_id",
        "implementation_id",
        "aggregate_execution_counts",
        "primary_reducer_summary",
        "unit_universes",
        "join_validation",
        "secondary_reducer_rows",
        "supporting_taxon_counts",
        "terminal_gates",
    }
    if (
        set(conservation) != expected_conservation_fields
        or conservation["schema_version"] != "2.0"
        or conservation["diagnostic_id"] != DIAGNOSTIC_ID
        or conservation["implementation_id"] != IMPLEMENTATION_ID
    ):
        raise ArtifactBoundaryError("conservation schema or identity drift")
    terminal = str(result["terminal_class"])
    return_code = _integer(result["return_code"], "result return code")
    validate_terminal_tuple(
        terminal_class=terminal,
        return_code=return_code,
        scientific_output_status=str(result["scientific_output_status"]),
        root_cause_claim_status=str(result["root_cause_claim_status"]),
    )
    validate_research_conclusion(terminal, result["research_conclusion"])
    rc_file = int(
        cleanup_checked_read_text(
            path / RETURN_CODE_FILE,
            encoding="ascii",
            label="contract return-code validation",
        ).strip()
    )
    if rc_file != return_code:
        raise ArtifactBoundaryError("result and detached return code differ")
    if (
        result["rerun_authorized"] is not False
        or result["R11_CLOSED"] is not False
        or result["R12_READY"] is not False
        or _integer(result["wallet_feature_rows"], "wallet feature rows") != 0
    ):
        raise ArtifactBoundaryError("result opens forbidden authority")
    object_rows = _parse_ndjson(path / OBJECT_LEDGER_FILE)
    recomputed_counts, all_objects_complete = _aggregate_from_object_rows(
        object_rows
    )
    aggregate = _object(
        conservation["aggregate_execution_counts"],
        "aggregate execution counts",
    )
    if set(aggregate) != set(recomputed_counts):
        raise ArtifactBoundaryError("aggregate execution count schema drift")
    for key, expected in recomputed_counts.items():
        if _integer(aggregate[key], key) != expected:
            raise ArtifactBoundaryError(f"aggregate execution count drift: {key}")
    if _integer(context["s3_requests_executed"], "context request count") != (
        recomputed_counts["get_object_request_count"]
    ):
        raise ArtifactBoundaryError("context request count differs from object ledger")
    downloaded = sum(
        _integer(
            _object(row["body"], "body")["bytes_received"],
            "body bytes",
        )
        for row in object_rows
    )
    if _integer(context["object_bytes_downloaded"], "context downloaded bytes") != downloaded:
        raise ArtifactBoundaryError("context downloaded bytes differ from object ledger")
    if context["rerun_authorized"] is not False:
        raise ArtifactBoundaryError("context opens rerun authority")
    measurements = resource["measurements"]
    if not isinstance(measurements, tuple) or not measurements:
        raise ArtifactBoundaryError("resource measurements are absent")
    last_measurement = _object(measurements[-1], "last resource measurement")
    if _integer(
        last_measurement["network_request_count"],
        "last resource request count",
    ) != _integer(context["s3_requests_executed"], "context request count"):
        raise ArtifactBoundaryError(
            "resource measurement and context request count disagree"
        )

    reducer_rows = _parse_ndjson(path / REDUCER_LEDGER_FILE)
    summary = _reducer_summary(reducer_rows)
    declared_summary = _object(
        conservation["primary_reducer_summary"],
        "primary reducer summary",
    )
    if {key: declared_summary[key] for key in declared_summary} != summary:
        raise ArtifactBoundaryError("primary reducer summary drift")

    universe_values = conservation["unit_universes"]
    if not isinstance(universe_values, tuple):
        raise ArtifactBoundaryError("unit universes must be array")
    universe_rows = tuple(
        {key: _object(row, "universe row")[key] for key in _object(row, "universe row")}
        for row in universe_values
    )
    validate_universe_rows(universe_rows)
    join = _validate_join_mapping(conservation["join_validation"])
    supporting = _object(
        conservation["supporting_taxon_counts"],
        "supporting taxon counts",
    )
    if set(supporting) != set(TAXA):
        raise ArtifactBoundaryError("supporting taxon map drift")
    if any(_integer(supporting[taxon], taxon) < 0 for taxon in TAXA):
        raise ArtifactBoundaryError("negative supporting taxon count")
    validate_terminal_gates(conservation["terminal_gates"])
    gates = _object(conservation["terminal_gates"], "terminal gates")
    secondary_summary = _validate_secondary_reducers(
        conservation["secondary_reducer_rows"]
    )
    secondary_complete = secondary_summary is not None

    group_total = sum(_integer(row["group_count"], "group count") for row in universe_rows)
    occurrence_total = sum(
        _integer(row["occurrence_count"], "occurrence count")
        for row in universe_rows
    )
    unclassifiable_group_total = sum(
        _integer(row["unclassifiable_group_count"], "unclassifiable group count")
        for row in universe_rows
    )
    unclassifiable_occurrence_total = sum(
        _integer(
            row["unclassifiable_occurrence_count"],
            "unclassifiable occurrence count",
        )
        for row in universe_rows
    )
    universe_by_name = {
        str(row["unit_universe"]): row for row in universe_rows
    }
    secondary_sources_match = bool(
        secondary_summary is not None
        and secondary_summary["MATERIALIZED_BLOCK_NUMBER"]
        == _integer(
            universe_by_name["ARCHIVE_BLOCK_NUMBER_GROUP"]["occurrence_count"],
            "block universe occurrence count",
        )
        and secondary_summary["PROTOCOL_MATCHED_TRADE_PER_RAW_BLOCK"]
        == _integer(
            universe_by_name[
                "PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE"
            ]["occurrence_count"],
            "protocol universe occurrence count",
        )
        and secondary_summary["EXACT_LEGACY_WEAK_KEY"]
        == _integer(
            summary["legacy_repeat_observation_count"],
            "legacy repeated observation count",
        )
    )
    block_universe = universe_by_name["ARCHIVE_BLOCK_NUMBER_GROUP"]
    legacy_universe = universe_by_name["LEGACY_REPEAT_OCCURRENCE"]
    primary_sources_match = bool(
        summary["block_source_record_count"]
        == recomputed_counts["first_pass_raw_block_observation_count"]
        and summary["legacy_source_record_count"]
        == recomputed_counts["first_pass_raw_event_observation_count"]
        and summary["block_repeat_group_count"]
        == _integer(block_universe["group_count"], "block universe group count")
        and summary["block_repeat_observation_count"]
        == _integer(
            block_universe["occurrence_count"],
            "block universe occurrence count",
        )
        and summary["legacy_repeat_occurrence_count"]
        == _integer(
            legacy_universe["occurrence_count"],
            "legacy universe occurrence count",
        )
        and summary["legacy_repeat_occurrence_count"]
        == _integer(
            legacy_universe["group_count"],
            "legacy universe group count",
        )
    )
    if _integer(join["unit_count"], "join unit count") != group_total:
        raise ArtifactBoundaryError("join unit count differs from universe rows")
    if (
        _integer(
            join["retained_row_reference_count"],
            "retained row reference count",
        )
        != occurrence_total
    ):
        raise ArtifactBoundaryError(
            "retained row reference count differs from universe occurrences"
        )
    if terminal == "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE":
        if (
            not all_objects_complete
            or not _same_two_pass_aggregate(recomputed_counts)
            or unclassifiable_group_total != 0
            or unclassifiable_occurrence_total != 0
            or not primary_sources_match
        ):
            raise ArtifactBoundaryError("complete terminal lacks exact two-pass scope")
        if any(gates[name] is not True for name in TERMINAL_GATE_NAMES):
            raise ArtifactBoundaryError("complete terminal contains false gate")
        if any(join[field] is not True for field in _JOIN_FIELDS[4:]):
            raise ArtifactBoundaryError("complete terminal contains false join proof")
        if summary["all_partitions_complete_and_exact"] is not True:
            raise ArtifactBoundaryError("complete terminal lacks exact reducer multiplicity")
        if not _raw_event_partitions_conserve(recomputed_counts):
            raise ArtifactBoundaryError("complete terminal event partitions do not conserve")
        if not secondary_complete or not secondary_sources_match:
            raise ArtifactBoundaryError("complete terminal lacks secondary reducers")
    elif terminal == "R11A_V2_DIAGNOSTIC_INCOMPLETE":
        scientific_gate = (
            "every_unit_universe_has_zero_unclassifiable_groups_and_occurrences"
        )
        materialization_gates = tuple(
            name for name in TERMINAL_GATE_NAMES if name != scientific_gate
        )
        if (
            not all_objects_complete
            or not _same_two_pass_aggregate(recomputed_counts)
            or summary["all_partitions_complete_and_exact"] is not True
            or not _raw_event_partitions_conserve(recomputed_counts)
            or not secondary_complete
            or not secondary_sources_match
            or not primary_sources_match
            or unclassifiable_group_total <= 0
            or unclassifiable_occurrence_total <= 0
            or any(gates[name] is not True for name in materialization_gates)
            or gates[scientific_gate] is not False
            or any(join[field] is not True for field in _JOIN_FIELDS[4:])
        ):
            raise ArtifactBoundaryError(
                "RC20 is not a fully materialized scientific incompleteness"
            )
    elif terminal in {
        "R11A_V2_ARTIFACT_CAP_EXCEEDED",
        "R11A_V2_FAIL_CLOSED_EARLY_STOP",
    }:
        if any(
            _integer(row["group_count"], "empty group count") != 0
            or _integer(row["occurrence_count"], "empty occurrence count") != 0
            for row in universe_rows
        ):
            raise ArtifactBoundaryError("empty terminal contains taxonomy units")
        if any(_integer(join[field], field) != 0 for field in _JOIN_FIELDS[:4]):
            raise ArtifactBoundaryError("empty terminal contains join rows")
        if any(_integer(supporting[taxon], taxon) != 0 for taxon in TAXA):
            raise ArtifactBoundaryError("empty terminal contains supporting taxa")
        secondary = conservation["secondary_reducer_rows"]
        if not isinstance(secondary, tuple) or secondary:
            raise ArtifactBoundaryError("empty terminal contains secondary reducers")
        if any(join[field] is not True for field in _JOIN_FIELDS[4:]):
            raise ArtifactBoundaryError("empty terminal join truth is contradictory")
        exact_empty_scope = bool(
            all_objects_complete
            and _same_two_pass_aggregate(recomputed_counts)
        )
        expected_empty_gates = {
            "exact_72_object_scope_complete": exact_empty_scope,
            "exact_three_complete_utc_days": False,
            "all_objects_parsed_twice_with_equal_counts_and_commitments": (
                exact_empty_scope
            ),
            "all_primary_reducer_partitions_preserve_exact_multiplicity": (
                summary["all_partitions_complete_and_exact"] is True
            ),
            "raw_block_count_conserves_to_singleton_plus_repeated_observations": False,
            "raw_event_count_conserves_separately_for_tid_coin_and_wallet_validation": False,
            "legacy_repeat_occurrence_count_conserves_to_valid_plus_invalid_tid_repeat_occurrences": False,
            "authoritative_unit_universes_are_exact_and_ordered": False,
            "every_authoritative_unit_receives_exactly_one_primary_taxon": False,
            "supporting_taxa_do_not_increment_primary_counts": False,
            "all_nonnull_proof_and_provenance_foreign_keys_resolve_exactly_once": True,
            "all_retained_rows_reference_exactly_one_unit": True,
            "all_retained_row_counts_match_unit_occurrence_counts": True,
            "all_referenced_projections_are_byte_equal": True,
            "all_taxonomy_counts_recomputed_from_retained_rows": False,
            "every_unit_universe_has_zero_unclassifiable_groups_and_occurrences": False,
            "all_caps_respected": True,
        }
        if dict(gates) != expected_empty_gates:
            raise ArtifactBoundaryError(
                "empty terminal gates contradict the retained execution route"
            )

    _validate_resource(resource, limits)
    boundary_raw = cleanup_checked_read_bytes(
        path / BOUNDARY_FILE,
        label="contract boundary validation",
    )
    boundary = _object(
        strict_json_loads(boundary_raw.rstrip(b" \n") + b"\n"),
        "boundary",
    )
    _validate_boundary(path, boundary, resource, limits)

    stop = _object(
        strict_json_loads(
            cleanup_checked_read_bytes(
                path / STOP_LEDGER_FILE,
                label="contract stop-ledger validation",
            )
        ),
        "stop ledger",
    )
    if (
        set(stop)
        != {"schema_version", "diagnostic_id", "declared_phase_order", "entries"}
        or stop["schema_version"] != "2.0"
        or stop["diagnostic_id"] != DIAGNOSTIC_ID
        or tuple(stop["declared_phase_order"]) != PHASES
    ):
        raise ArtifactBoundaryError("stop ledger schema or identity drift")
    _validate_stop_ledger(
        entries=stop["entries"],
        terminal=terminal,
        context_phase=context["execution_phase"],
        object_rows=object_rows,
    )
    stop_entries = stop["entries"]
    if not isinstance(stop_entries, tuple):
        raise ArtifactBoundaryError("stop entries must be an array")
    if terminal in {
        "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE",
        "R11A_V2_DIAGNOSTIC_INCOMPLETE",
    }:
        if context["execution_phase"] != "ARTIFACT_PACKAGING":
            raise ArtifactBoundaryError(
                "fully materialized terminal context is not at artifact packaging"
            )
    elif (
        not stop_entries
        or _object(stop_entries[-1], "last stop")["phase"]
        != context["execution_phase"]
    ):
        raise ArtifactBoundaryError(
            "early terminal context does not match its final stop phase"
        )


class ArtifactSession(_core.ArtifactSession):
    def _finalize(
        self,
        *,
        state: ExecutionEvidenceState,
        context: Mapping[str, object],
        reducer_rows: Sequence[Mapping[str, object]],
        resource_rows: Sequence[Mapping[str, object]],
        terminal_class: str,
        research_conclusion: str,
        taxonomy_result: TaxonomyResult | None,
        science: tuple[FileEvidence, ...],
    ) -> ArtifactOutcome:
        if self._closed:
            raise ArtifactBoundaryError("artifact session already closed")
        return_code = exact_return_code(terminal_class)
        scientific_status = exact_scientific_status(terminal_class)
        root_cause_status = exact_root_cause_status(terminal_class)
        validate_research_conclusion(terminal_class, research_conclusion)
        object_rows = state.object_rows()
        complete_reducers = complete_reducer_rows(
            reducer_rows,
            terminal_class,
        )
        reducer_summary = _reducer_summary(complete_reducers)
        universe_rows = (
            _zero_universe_rows()
            if taxonomy_result is None
            else taxonomy_result.universe_rows
        )
        validate_universe_rows(universe_rows)
        join_mapping = (
            _zero_join_mapping()
            if taxonomy_result is None
            else dataclasses.asdict(taxonomy_result.join_validation)
        )
        _validate_join_mapping(join_mapping)
        supporting = (
            zero_taxon_counts()
            if taxonomy_result is None
            else dict(taxonomy_result.supporting_taxon_counts)
        )
        if set(supporting) != set(TAXA):
            raise ArtifactBoundaryError("supporting taxon count map drift")
        if any(type(supporting[taxon]) is not int or supporting[taxon] < 0 for taxon in TAXA):
            raise ArtifactBoundaryError("supporting taxon count is invalid")

        counts = state.aggregate_counts()
        same_passes = _same_two_pass_aggregate(counts)
        raw_event_conservation = _raw_event_partitions_conserve(counts)
        group_total = sum(int(row["group_count"]) for row in universe_rows)
        occurrence_total = sum(int(row["occurrence_count"]) for row in universe_rows)
        exact_units = tuple(
            str(row["unit_universe"]) for row in universe_rows
        ) == AUTHORITATIVE_UNIT_UNIVERSES
        primary_conservation = all(
            sum(int(value) for value in row["primary_taxon_group_counts"].values())
            == int(row["group_count"])
            and sum(
                int(value)
                for value in row["primary_taxon_occurrence_counts"].values()
            )
            == int(row["occurrence_count"])
            for row in universe_rows
        )
        taxonomy_present = taxonomy_result is not None
        block_conservation = bool(
            taxonomy_present
            and reducer_summary["all_partitions_complete_and_exact"] is True
            and reducer_summary["block_source_record_count"]
            == counts["first_pass_raw_block_observation_count"]
            and reducer_summary["block_repeat_group_count"]
            == taxonomy_result.repeated_block_group_count
            and reducer_summary["block_repeat_observation_count"]
            == taxonomy_result.repeated_block_observation_count
            and int(reducer_summary["block_singleton_observation_count"]) >= 0
        )
        legacy_conservation = bool(
            taxonomy_present
            and reducer_summary["legacy_source_record_count"]
            == counts["first_pass_raw_event_observation_count"]
            and reducer_summary["legacy_repeat_group_count"]
            == taxonomy_result.legacy_repeat_group_count
            and reducer_summary["legacy_repeat_observation_count"]
            == taxonomy_result.legacy_repeat_observation_count
            and reducer_summary["legacy_repeat_occurrence_count"]
            == taxonomy_result.legacy_repeat_occurrence_count
            and taxonomy_result.legacy_repeat_occurrence_count
            == (
                taxonomy_result.valid_tid_legacy_repeat_occurrence_count
                + taxonomy_result.invalid_tid_legacy_repeat_occurrence_count
            )
        )
        joins_recompute_counts = bool(
            taxonomy_present
            and int(join_mapping["unit_count"]) == group_total
            and int(join_mapping["retained_row_reference_count"])
            == occurrence_total
            and join_mapping[
                "all_retained_row_counts_match_unit_occurrence_counts"
            ]
            is True
        )
        verified_workspace_before_packaging = self.meter.verify_actual_usage()
        runtime_flags = self.runtime_guard.package_flags()
        all_caps = bool(
            directory_size(self.staging)
            + self.limits.reserved_non_scientific_package_metadata_bytes
            <= self.limits.maximum_retained_artifact_bytes
            and verified_workspace_before_packaging
            + self.meter.reserved_bytes
            + self.limits.reserved_non_scientific_package_metadata_bytes
            <= self.limits.maximum_ephemeral_workspace_bytes
            and runtime_flags[
                "preupload_runtime_within_hard_limit_after_upload_window"
            ]
            is True
        )
        terminal_gates = {
            "exact_72_object_scope_complete": state.exact_scope_complete(),
            "exact_three_complete_utc_days": bool(
                taxonomy_present and taxonomy_result.exact_three_utc_days
            ),
            "all_objects_parsed_twice_with_equal_counts_and_commitments": (
                state.exact_scope_complete() and same_passes
            ),
            "all_primary_reducer_partitions_preserve_exact_multiplicity": bool(
                taxonomy_present
                and reducer_summary["all_partitions_complete_and_exact"] is True
            ),
            "raw_block_count_conserves_to_singleton_plus_repeated_observations": (
                block_conservation
            ),
            "raw_event_count_conserves_separately_for_tid_coin_and_wallet_validation": (
                taxonomy_present and raw_event_conservation and same_passes
            ),
            "legacy_repeat_occurrence_count_conserves_to_valid_plus_invalid_tid_repeat_occurrences": (
                legacy_conservation
            ),
            "authoritative_unit_universes_are_exact_and_ordered": (
                taxonomy_present and exact_units
            ),
            "every_authoritative_unit_receives_exactly_one_primary_taxon": (
                taxonomy_present and primary_conservation
            ),
            "supporting_taxa_do_not_increment_primary_counts": bool(
                taxonomy_present and primary_conservation
            ),
            "all_nonnull_proof_and_provenance_foreign_keys_resolve_exactly_once": bool(
                join_mapping[
                    "all_nonnull_proof_references_resolve_exactly_once"
                ]
            ),
            "all_retained_rows_reference_exactly_one_unit": bool(
                join_mapping["all_retained_rows_reference_exactly_one_unit"]
            ),
            "all_retained_row_counts_match_unit_occurrence_counts": bool(
                join_mapping[
                    "all_retained_row_counts_match_unit_occurrence_counts"
                ]
            ),
            "all_referenced_projections_are_byte_equal": bool(
                join_mapping["all_referenced_projections_are_byte_equal"]
            ),
            "all_taxonomy_counts_recomputed_from_retained_rows": (
                joins_recompute_counts
            ),
            "every_unit_universe_has_zero_unclassifiable_groups_and_occurrences": bool(
                taxonomy_present
                and taxonomy_result.unclassifiable_group_count == 0
                and taxonomy_result.unclassifiable_occurrence_count == 0
            ),
            "all_caps_respected": all_caps,
        }
        validate_terminal_gates(terminal_gates)
        secondary_summary = _validate_secondary_reducers(
            ()
            if taxonomy_result is None
            else taxonomy_result.secondary_reducer_rows
        )
        secondary_complete = secondary_summary is not None
        protocol_occurrence_count = (
            0
            if taxonomy_result is None
            else int(
                next(
                    row["occurrence_count"]
                    for row in universe_rows
                    if row["unit_universe"]
                    == "PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE"
                )
            )
        )
        secondary_sources_match = bool(
            taxonomy_result is not None
            and secondary_summary is not None
            and secondary_summary["MATERIALIZED_BLOCK_NUMBER"]
            == taxonomy_result.repeated_block_observation_count
            and secondary_summary["PROTOCOL_MATCHED_TRADE_PER_RAW_BLOCK"]
            == protocol_occurrence_count
            and secondary_summary["EXACT_LEGACY_WEAK_KEY"]
            == taxonomy_result.legacy_repeat_observation_count
        )
        stop_rows = state.stop_rows()
        if terminal_class == "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE":
            if (
                any(value is not True for value in terminal_gates.values())
                or not secondary_complete
                or not secondary_sources_match
                or stop_rows
            ):
                raise ArtifactBoundaryError(
                    "RC0 requires complete materialization and no stop evidence"
                )
        elif terminal_class == "R11A_V2_DIAGNOSTIC_INCOMPLETE":
            scientific_gate = (
                "every_unit_universe_has_zero_unclassifiable_groups_and_occurrences"
            )
            materialization_gates = tuple(
                name for name in TERMINAL_GATE_NAMES if name != scientific_gate
            )
            if (
                any(terminal_gates[name] is not True for name in materialization_gates)
                or terminal_gates[scientific_gate] is not False
                or not secondary_complete
                or not secondary_sources_match
                or any(join_mapping[field] is not True for field in _JOIN_FIELDS[4:])
                or len(stop_rows) != 1
                or stop_rows[0]["stop_code"] != "FULL_SCOPE_TAXONOMY_INCOMPLETE"
                or stop_rows[0]["phase"] != "TAXONOMY"
                or stop_rows[0]["object_ordinal_zero_based"] is not None
            ):
                raise ArtifactBoundaryError(
                    "RC20 requires fully materialized science with one unresolved taxon reason"
                )
        elif not stop_rows:
            raise ArtifactBoundaryError("RC21 requires fail-closed stop evidence")

        conservation = {
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "implementation_id": IMPLEMENTATION_ID,
            "aggregate_execution_counts": counts,
            "primary_reducer_summary": reducer_summary,
            "unit_universes": list(universe_rows),
            "join_validation": join_mapping,
            "secondary_reducer_rows": (
                []
                if taxonomy_result is None
                else list(taxonomy_result.secondary_reducer_rows)
            ),
            "supporting_taxon_counts": supporting,
            "terminal_gates": terminal_gates,
        }
        science_mapping = {
            value.path: value.mapping() for value in science
        }
        result = {
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "implementation_id": IMPLEMENTATION_ID,
            "terminal_class": terminal_class,
            "research_conclusion": research_conclusion,
            "scientific_output_status": scientific_status,
            "root_cause_claim_status": root_cause_status,
            "return_code": return_code,
            "scientific_files": science_mapping,
            "wallet_feature_rows": 0,
            "rerun_authorized": False,
            "R11_CLOSED": False,
            "R12_READY": False,
        }
        full_context = {
            **dict(context),
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "implementation_id": IMPLEMENTATION_ID,
            "execution_phase": state.current_phase,
            "s3_requests_executed": state.network_request_count,
            "object_bytes_downloaded": sum(
                int(row["body"]["bytes_received"]) for row in object_rows
            ),
            "rerun_authorized": False,
        }
        packaging_elapsed = self.runtime_guard.elapsed_seconds_floor()
        resource = {
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "measurements": list(resource_rows),
            "tracked_workspace_bytes_before_packaging": (
                verified_workspace_before_packaging
            ),
            "reserved_workspace_bytes_before_packaging": (
                self.meter.reserved_bytes
            ),
            "peak_tracked_workspace_bytes": self.meter.peak_known_bytes,
            "peak_bounded_workspace_bytes": self.meter.peak_bounded_bytes,
            "maximum_ephemeral_workspace_bytes": (
                self.limits.maximum_ephemeral_workspace_bytes
            ),
            "packaging_elapsed_seconds_floor": packaging_elapsed,
            "package_flags": {
                "preupload_runtime_within_hard_limit_after_upload_window": (
                    packaging_elapsed
                    < self.limits.maximum_runtime_seconds
                    - self.limits.minimum_upload_window_seconds
                ),
                "scientific_runtime_completed_before_packaging_reservation": (
                    packaging_elapsed < self.limits.maximum_runtime_seconds
                ),
            },
        }
        stop = {
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "declared_phase_order": list(PHASES),
            "entries": list(stop_rows),
        }
        metadata = SharedMetadataWriter(
            self.staging,
            self.meter,
            self.limits,
        )
        try:
            metadata.write(CONTEXT_FILE, canonical_json_bytes(full_context))
            metadata.write(RESULT_FILE, canonical_json_bytes(result))
            metadata.write(OBJECT_LEDGER_FILE, _core._ndjson(object_rows))
            metadata.write(
                REDUCER_LEDGER_FILE,
                _core._ndjson(complete_reducers),
            )
            metadata.write(
                CONSERVATION_FILE,
                canonical_json_bytes(conservation),
            )
            metadata.write(
                RESOURCE_LEDGER_FILE,
                canonical_json_bytes(resource),
            )
            metadata.write(STOP_LEDGER_FILE, canonical_json_bytes(stop))
            metadata.write(WALLET_FEATURE_FILE, b"")
            metadata.write(
                RETURN_CODE_FILE,
                f"{return_code}\n".encode("ascii"),
            )
            metadata.write(
                HASH_MANIFEST_FILE,
                _core._manifest_bytes(self.staging),
            )
            boundary = _boundary_payload(
                self.staging,
                self.limits,
                self.runtime_guard,
                self.meter,
            )
            metadata.write(BOUNDARY_FILE, boundary)
            metadata.close()
            final = self.atomic.commit(
                lambda candidate: validate_artifact(
                    candidate,
                    self.limits,
                )
            )
            outcome = ArtifactOutcome(
                final_directory=final,
                terminal_class=terminal_class,
                research_conclusion=research_conclusion,
                return_code=return_code,
                artifact_sha256=hashlib.sha256(
                    b"".join(
                        canonical_json_bytes(
                            {
                                "name": name,
                                "sha256": _hash(final / name),
                            },
                            final_newline=False,
                        )
                        for name in sorted(EXPECTED_ARTIFACT_FILES)
                    )
                ).hexdigest(),
                artifact_bytes=directory_size(final),
            )
            self._closed = True
            return outcome
        except Exception:
            self._rollback_failed_finalization(metadata)
            raise


__all__ = [
    "ArtifactBoundaryError",
    "ArtifactOutcome",
    "ArtifactSession",
    "FileEvidence",
    "ScientificCapExceeded",
    "SharedMetadataWriter",
    "StreamingScientificEmitter",
    "complete_reducer_rows",
    "validate_artifact",
]
