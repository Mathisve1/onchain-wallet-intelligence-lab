from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Final

DIAGNOSTIC_ID: Final[str] = "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-002"
IMPLEMENTATION_ID: Final[str] = (
    "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-CORRECTIVE-R7"
)

TERMINAL_RETURN_CODES: Final[dict[str, int]] = {
    "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE": 0,
    "R11A_V2_DIAGNOSTIC_INCOMPLETE": 20,
    "R11A_V2_ARTIFACT_CAP_EXCEEDED": 21,
    "R11A_V2_FAIL_CLOSED_EARLY_STOP": 21,
}

SCIENTIFIC_STATUS_BY_TERMINAL: Final[dict[str, str]] = {
    "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE": "COMPLETE",
    "R11A_V2_DIAGNOSTIC_INCOMPLETE": "COMPLETE",
    "R11A_V2_ARTIFACT_CAP_EXCEEDED": "EMPTY",
    "R11A_V2_FAIL_CLOSED_EARLY_STOP": "EMPTY",
}

ROOT_CAUSE_STATUS_BY_TERMINAL: Final[dict[str, str]] = {
    "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE": "PROVEN_COMPLETE_TAXONOMY_ONLY",
    "R11A_V2_DIAGNOSTIC_INCOMPLETE": "NOT_PROVEN",
    "R11A_V2_ARTIFACT_CAP_EXCEEDED": "NOT_PROVEN",
    "R11A_V2_FAIL_CLOSED_EARLY_STOP": "NOT_PROVEN",
}

ALLOWED_RESEARCH_CONCLUSIONS: Final[dict[str, frozenset[str]]] = {
    "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE": frozenset(
        {"PROVEN_COMPLETE_TAXONOMY_ONLY"}
    ),
    "R11A_V2_DIAGNOSTIC_INCOMPLETE": frozenset(
        {"ROOT_CAUSE_NOT_FULLY_PROVEN_NO_REPAIR_AUTHORIZED"}
    ),
    "R11A_V2_ARTIFACT_CAP_EXCEEDED": frozenset(
        {"ROOT_CAUSE_NOT_PROVEN_EMPTY_CAP_FALLBACK"}
    ),
    "R11A_V2_FAIL_CLOSED_EARLY_STOP": frozenset(
        {
            "ROOT_CAUSE_NOT_PROVEN_FAIL_CLOSED_EMPTY_ARTIFACT",
            "ROOT_CAUSE_NOT_PROVEN_NETWORK_FAIL_CLOSED_EMPTY_ARTIFACT",
        }
    ),
}

AUTHORITATIVE_UNIT_UNIVERSES: Final[tuple[str, ...]] = (
    "LEGACY_REPEAT_OCCURRENCE",
    "ARCHIVE_BLOCK_NUMBER_GROUP",
    "PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE",
    "REPEAT_INTERSECTING_TID_SCHEMA_VIOLATION",
    "REPEAT_INTERSECTING_COIN_SCHEMA_VIOLATION",
    "REPEAT_INTERSECTING_WALLET_SCHEMA_VIOLATION",
)

TAXA: Final[tuple[str, ...]] = (
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

PARSE_CONSERVATION_FIELDS: Final[tuple[str, ...]] = (
    "raw_block_observation_count",
    "raw_event_observation_count",
    "valid_wallet_occurrence_count",
    "invalid_wallet_occurrence_count",
    "valid_coin_occurrence_count",
    "invalid_coin_occurrence_count",
    "valid_tid_occurrence_count",
    "invalid_tid_occurrence_count",
    "protocol_trade_identity_occurrence_count",
    "wallet_fill_identity_occurrence_count",
    "local_time_path_prefix_match_count",
    "block_time_path_prefix_match_count",
    "block_time_previous_prefix_match_count",
    "block_time_other_prefix_count",
)

TERMINAL_GATE_NAMES: Final[tuple[str, ...]] = (
    "exact_72_object_scope_complete",
    "exact_three_complete_utc_days",
    "all_objects_parsed_twice_with_equal_counts_and_commitments",
    "all_primary_reducer_partitions_preserve_exact_multiplicity",
    "raw_block_count_conserves_to_singleton_plus_repeated_observations",
    "raw_event_count_conserves_separately_for_tid_coin_and_wallet_validation",
    "legacy_repeat_occurrence_count_conserves_to_valid_plus_invalid_tid_repeat_occurrences",
    "authoritative_unit_universes_are_exact_and_ordered",
    "every_authoritative_unit_receives_exactly_one_primary_taxon",
    "supporting_taxa_do_not_increment_primary_counts",
    "all_nonnull_proof_and_provenance_foreign_keys_resolve_exactly_once",
    "all_retained_rows_reference_exactly_one_unit",
    "all_retained_row_counts_match_unit_occurrence_counts",
    "all_referenced_projections_are_byte_equal",
    "all_taxonomy_counts_recomputed_from_retained_rows",
    "every_unit_universe_has_zero_unclassifiable_groups_and_occurrences",
    "all_caps_respected",
)

SCIENCE_CONTAINERS: Final[tuple[str, ...]] = (
    "r11a-v2-taxonomy-units.ndjson",
    "r11a-v2-block-overlap-matrix.ndjson",
    "r11a-v2-duplicate-observations.ndjson",
    "r11a-v2-exact-block-replay-proofs.ndjson",
    "r11a-v2-expected-counterparty-pair-proofs.ndjson",
    "r11a-v2-protocol-trade-group-members.ndjson",
    "r11a-v2-repeat-intersecting-schema-evidence.ndjson",
)

CONTEXT_FILE: Final[str] = "r11a-v2-context.json"
RESULT_FILE: Final[str] = "r11a-v2-result.json"
OBJECT_LEDGER_FILE: Final[str] = "r11a-v2-object-ledger.ndjson"
REDUCER_LEDGER_FILE: Final[str] = "r11a-v2-reducer-ledger.ndjson"
CONSERVATION_FILE: Final[str] = "r11a-v2-conservation.json"
RESOURCE_LEDGER_FILE: Final[str] = "r11a-v2-resource-ledger.json"
STOP_LEDGER_FILE: Final[str] = "r11a-v2-stop-ledger.json"
WALLET_FEATURE_FILE: Final[str] = "r11a-v2-wallet-features.ndjson"
RETURN_CODE_FILE: Final[str] = "r11a-v2.rc"
HASH_MANIFEST_FILE: Final[str] = "R11A_V2_FILES.sha256"
BOUNDARY_FILE: Final[str] = "r11a-v2-package-boundary.txt"

METADATA_CONTAINERS: Final[tuple[str, ...]] = (
    CONTEXT_FILE,
    RESULT_FILE,
    OBJECT_LEDGER_FILE,
    REDUCER_LEDGER_FILE,
    CONSERVATION_FILE,
    RESOURCE_LEDGER_FILE,
    STOP_LEDGER_FILE,
    WALLET_FEATURE_FILE,
    RETURN_CODE_FILE,
    HASH_MANIFEST_FILE,
    BOUNDARY_FILE,
)

EXPECTED_ARTIFACT_FILES: Final[frozenset[str]] = frozenset(
    (*SCIENCE_CONTAINERS, *METADATA_CONTAINERS)
)

PHASES: Final[tuple[str, ...]] = (
    "PRE_OIDC_STATIC_GATE",
    "OIDC_ROLE_ASSUMPTION",
    "STS_PRINCIPAL_VALIDATION",
    "POST_STS_PRECOLLECTOR",
    "S3_DOWNLOAD",
    "FIRST_LOCAL_PASS",
    "PRIMARY_REDUCERS",
    "SECOND_LOCAL_PASS",
    "MATERIALIZATION",
    "TAXONOMY",
    "ARTIFACT_PACKAGING",
    "PREUPLOAD_VALIDATION",
    "COMPLETE",
)

_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{64}\Z")


class ArtifactSchemaError(ValueError):
    pass


def exact_return_code(terminal_class: str) -> int:
    try:
        return TERMINAL_RETURN_CODES[terminal_class]
    except KeyError as exc:
        raise ArtifactSchemaError(f"unknown terminal class: {terminal_class}") from exc


def exact_scientific_status(terminal_class: str) -> str:
    try:
        return SCIENTIFIC_STATUS_BY_TERMINAL[terminal_class]
    except KeyError as exc:
        raise ArtifactSchemaError(f"unknown terminal class: {terminal_class}") from exc


def exact_root_cause_status(terminal_class: str) -> str:
    try:
        return ROOT_CAUSE_STATUS_BY_TERMINAL[terminal_class]
    except KeyError as exc:
        raise ArtifactSchemaError(f"unknown terminal class: {terminal_class}") from exc


def validate_terminal_tuple(
    *,
    terminal_class: str,
    return_code: int,
    scientific_output_status: str,
    root_cause_claim_status: str,
) -> None:
    if return_code != exact_return_code(terminal_class):
        raise ArtifactSchemaError("terminal class and return code drift")
    if scientific_output_status != exact_scientific_status(terminal_class):
        raise ArtifactSchemaError("terminal class and scientific status drift")
    if root_cause_claim_status != exact_root_cause_status(terminal_class):
        raise ArtifactSchemaError("terminal class and root-cause status drift")


def validate_research_conclusion(terminal_class: str, conclusion: object) -> None:
    allowed = ALLOWED_RESEARCH_CONCLUSIONS.get(terminal_class)
    if allowed is None or conclusion not in allowed:
        raise ArtifactSchemaError(
            "research conclusion is not allowed for terminal class"
        )


def validate_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ArtifactSchemaError(f"{label} must be lowercase SHA-256")
    return value


def _exact_nonnegative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ArtifactSchemaError(f"{label} must be a nonnegative exact integer")
    return value


def zero_taxon_counts() -> dict[str, int]:
    return {taxon: 0 for taxon in TAXA}


def validate_parse_conservation(
    value: object,
    *,
    record_count: int,
    event_count: int,
    label: str,
) -> None:
    if not isinstance(value, Mapping) or set(value) != set(PARSE_CONSERVATION_FIELDS):
        raise ArtifactSchemaError(f"{label} conservation field set drift")
    counts = {
        field: _exact_nonnegative_int(value[field], f"{label}.{field}")
        for field in PARSE_CONSERVATION_FIELDS
    }
    if counts["raw_block_observation_count"] != record_count:
        raise ArtifactSchemaError(f"{label} raw-block count differs from record count")
    if counts["raw_event_observation_count"] != event_count:
        raise ArtifactSchemaError(f"{label} raw-event count differs from event count")
    raw_events = counts["raw_event_observation_count"]
    for valid_field, invalid_field, dimension in (
        ("valid_wallet_occurrence_count", "invalid_wallet_occurrence_count", "wallet"),
        ("valid_coin_occurrence_count", "invalid_coin_occurrence_count", "coin"),
        ("valid_tid_occurrence_count", "invalid_tid_occurrence_count", "TID"),
    ):
        if counts[valid_field] + counts[invalid_field] != raw_events:
            raise ArtifactSchemaError(f"{label} {dimension} partition does not conserve events")
    if counts["protocol_trade_identity_occurrence_count"] > min(
        counts["valid_tid_occurrence_count"],
        counts["valid_coin_occurrence_count"],
    ):
        raise ArtifactSchemaError(f"{label} protocol identities exceed valid components")
    if (
        counts["wallet_fill_identity_occurrence_count"]
        > counts["protocol_trade_identity_occurrence_count"]
    ):
        raise ArtifactSchemaError(f"{label} wallet-fill identities exceed protocol identities")
    raw_blocks = counts["raw_block_observation_count"]
    if counts["local_time_path_prefix_match_count"] != raw_blocks:
        raise ArtifactSchemaError(f"{label} local-time/path conservation failure")
    if (
        counts["block_time_path_prefix_match_count"]
        + counts["block_time_previous_prefix_match_count"]
        + counts["block_time_other_prefix_count"]
        != raw_blocks
    ):
        raise ArtifactSchemaError(f"{label} block-time partition does not conserve records")
    if counts["block_time_other_prefix_count"] != 0:
        raise ArtifactSchemaError(f"{label} contains block-time evidence outside frozen boundary")


def _validate_pass(value: object, name: str) -> Mapping[str, object] | None:
    if value is None:
        return None
    expected = {
        "status",
        "decompressed_bytes",
        "record_count",
        "event_count",
        "decompressed_stream_sha256",
        "conservation",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ArtifactSchemaError(f"{name} evidence schema drift")
    if value["status"] != "COMPLETE":
        raise ArtifactSchemaError(f"{name} status is not COMPLETE")
    decompressed = _exact_nonnegative_int(
        value["decompressed_bytes"], f"{name}.decompressed_bytes"
    )
    record_count = _exact_nonnegative_int(value["record_count"], f"{name}.record_count")
    event_count = _exact_nonnegative_int(value["event_count"], f"{name}.event_count")
    if decompressed == 0 and (record_count != 0 or event_count != 0):
        raise ArtifactSchemaError(f"{name} zero bytes with nonzero parsed evidence")
    validate_sha256(value["decompressed_stream_sha256"], f"{name} stream SHA")
    validate_parse_conservation(
        value["conservation"],
        record_count=record_count,
        event_count=event_count,
        label=name,
    )
    return value


def validate_object_row_shape(row: Mapping[str, object]) -> None:
    expected = {
        "record_type",
        "diagnostic_id",
        "object_ordinal_zero_based",
        "object_key",
        "source_path_hour_utc",
        "expected_identity",
        "request",
        "response",
        "body",
        "first_pass",
        "second_pass",
        "terminal_status",
        "terminal_error_code",
    }
    if set(row) != expected:
        raise ArtifactSchemaError("object ledger row field set drift")
    if row["record_type"] != "R11A_V2_OBJECT_EXECUTION_EVIDENCE":
        raise ArtifactSchemaError("object ledger record_type drift")
    if row["diagnostic_id"] != DIAGNOSTIC_ID:
        raise ArtifactSchemaError("object ledger diagnostic ID drift")
    ordinal = row["object_ordinal_zero_based"]
    if type(ordinal) is not int or not 0 <= ordinal < 72:
        raise ArtifactSchemaError("object ledger ordinal outside exact scope")
    if not isinstance(row["object_key"], str) or not row["object_key"]:
        raise ArtifactSchemaError("object ledger object key missing")
    if not isinstance(row["source_path_hour_utc"], str):
        raise ArtifactSchemaError("object ledger source hour missing")

    expected_identity = row["expected_identity"]
    if not isinstance(expected_identity, Mapping) or set(expected_identity) != {
        "size_bytes",
        "etag",
        "compressed_sha256",
    }:
        raise ArtifactSchemaError("expected object identity schema drift")
    expected_size = _exact_nonnegative_int(
        expected_identity["size_bytes"], "expected size"
    )
    if expected_size <= 0:
        raise ArtifactSchemaError("expected size must be positive")
    if not isinstance(expected_identity["etag"], str):
        raise ArtifactSchemaError("expected etag invalid")
    expected_sha = validate_sha256(
        expected_identity["compressed_sha256"], "expected compressed SHA"
    )

    request = row["request"]
    if not isinstance(request, Mapping) or set(request) != {"count", "status"}:
        raise ArtifactSchemaError("request evidence schema drift")
    request_count = request["count"]
    if type(request_count) is not int or request_count not in {0, 1}:
        raise ArtifactSchemaError("request count outside one-request envelope")
    if request["status"] not in {
        "NOT_REQUESTED",
        "REQUEST_SENT",
        "RESPONSE_METADATA_RECEIVED",
        "COMPLETE",
    }:
        raise ArtifactSchemaError("unknown request status")

    response = row["response"]
    if response is not None:
        if not isinstance(response, Mapping) or set(response) != {
            "http_status",
            "etag",
            "content_length",
            "requester_charged",
        }:
            raise ArtifactSchemaError("response metadata schema drift")
        if request_count != 1:
            raise ArtifactSchemaError("response exists without one request")
        if type(response["http_status"]) is not int:
            raise ArtifactSchemaError("response HTTP status is not exact integer")
        if response["etag"] is not None and not isinstance(response["etag"], str):
            raise ArtifactSchemaError("response ETag type drift")
        if response["content_length"] is not None:
            _exact_nonnegative_int(response["content_length"], "response content length")
        if response["requester_charged"] is not None and not isinstance(
            response["requester_charged"], str
        ):
            raise ArtifactSchemaError("requester-charged type drift")

    body = row["body"]
    if not isinstance(body, Mapping) or set(body) != {
        "status",
        "bytes_received",
        "observed_compressed_sha256",
    }:
        raise ArtifactSchemaError("body evidence schema drift")
    if body["status"] not in {"NOT_STARTED", "STREAMING", "COMPLETE"}:
        raise ArtifactSchemaError("unknown body status")
    body_bytes = _exact_nonnegative_int(body["bytes_received"], "body byte count")
    if body_bytes > expected_size:
        raise ArtifactSchemaError("body byte count exceeds expected size")
    observed_sha = body["observed_compressed_sha256"]
    if observed_sha is not None:
        validate_sha256(observed_sha, "observed compressed SHA")

    first = _validate_pass(row["first_pass"], "first_pass")
    second = _validate_pass(row["second_pass"], "second_pass")
    terminal = row["terminal_status"]
    if terminal not in {"PENDING", "STOPPED", "COMPLETE_TWO_LOCAL_PASSES"}:
        raise ArtifactSchemaError("unknown object terminal status")
    error_code = row["terminal_error_code"]
    if error_code is not None and (not isinstance(error_code, str) or not error_code):
        raise ArtifactSchemaError("terminal error code type drift")

    if request_count == 0:
        if (
            request["status"] != "NOT_REQUESTED"
            or response is not None
            or body["status"] != "NOT_STARTED"
            or body_bytes != 0
            or observed_sha is not None
            or first is not None
            or second is not None
        ):
            raise ArtifactSchemaError("unrequested object contains later-phase evidence")
    if response is None and body["status"] != "NOT_STARTED":
        raise ArtifactSchemaError("body evidence exists before response metadata")
    if body["status"] == "COMPLETE":
        if (
            request["status"] != "COMPLETE"
            or response is None
            or response["http_status"] != 200
            or response["etag"] != expected_identity["etag"]
            or response["content_length"] != expected_size
            or response["requester_charged"] != "requester"
            or body_bytes != expected_size
            or observed_sha != expected_sha
        ):
            raise ArtifactSchemaError(
                "complete response/body integrity does not match frozen target"
            )
    elif observed_sha is not None:
        raise ArtifactSchemaError("observed compressed SHA before complete body")
    if first is not None and body["status"] != "COMPLETE":
        raise ArtifactSchemaError("first pass exists before complete body")
    if second is not None:
        if first is None or dict(second) != dict(first):
            raise ArtifactSchemaError("second pass is absent or differs from first pass")
    if terminal == "COMPLETE_TWO_LOCAL_PASSES":
        if second is None or error_code is not None:
            raise ArtifactSchemaError("complete object lacks exact two-pass evidence")
    elif terminal == "STOPPED":
        if error_code is None:
            raise ArtifactSchemaError("stopped object lacks terminal error code")
    elif error_code is not None:
        raise ArtifactSchemaError("non-stopped object contains terminal error code")


def validate_universe_rows(rows: Sequence[Mapping[str, object]]) -> None:
    observed = [row.get("unit_universe") for row in rows]
    if tuple(observed) != AUTHORITATIVE_UNIT_UNIVERSES:
        raise ArtifactSchemaError("authoritative unit universe order or membership drift")
    for row in rows:
        expected = {
            "unit_universe",
            "group_count",
            "occurrence_count",
            "primary_taxon_group_counts",
            "primary_taxon_occurrence_counts",
            "unclassifiable_group_count",
            "unclassifiable_occurrence_count",
        }
        if set(row) != expected:
            raise ArtifactSchemaError("unit conservation row schema drift")
        group_count = _exact_nonnegative_int(row["group_count"], "group_count")
        occurrence_count = _exact_nonnegative_int(
            row["occurrence_count"], "occurrence_count"
        )
        unclassifiable_groups = _exact_nonnegative_int(
            row["unclassifiable_group_count"], "unclassifiable_group_count"
        )
        unclassifiable_occurrences = _exact_nonnegative_int(
            row["unclassifiable_occurrence_count"],
            "unclassifiable_occurrence_count",
        )
        group_taxa = row["primary_taxon_group_counts"]
        occurrence_taxa = row["primary_taxon_occurrence_counts"]
        if not isinstance(group_taxa, Mapping) or set(group_taxa) != set(TAXA):
            raise ArtifactSchemaError("primary group taxon map is not exact")
        if not isinstance(occurrence_taxa, Mapping) or set(occurrence_taxa) != set(TAXA):
            raise ArtifactSchemaError("primary occurrence taxon map is not exact")
        for taxon in TAXA:
            _exact_nonnegative_int(group_taxa[taxon], f"group taxon {taxon}")
            _exact_nonnegative_int(
                occurrence_taxa[taxon], f"occurrence taxon {taxon}"
            )
        if sum(group_taxa.values()) != group_count:
            raise ArtifactSchemaError("primary group taxon counts do not conserve units")
        if sum(occurrence_taxa.values()) != occurrence_count:
            raise ArtifactSchemaError(
                "primary occurrence taxon counts do not conserve occurrences"
            )
        if group_taxa["UNCLASSIFIABLE"] != unclassifiable_groups:
            raise ArtifactSchemaError("unclassifiable group count drift")
        if occurrence_taxa["UNCLASSIFIABLE"] != unclassifiable_occurrences:
            raise ArtifactSchemaError("unclassifiable occurrence count drift")


def validate_terminal_gates(value: object) -> None:
    if not isinstance(value, Mapping) or set(value) != set(TERMINAL_GATE_NAMES):
        raise ArtifactSchemaError("terminal gate set drift")
    if any(type(value[name]) is not bool for name in TERMINAL_GATE_NAMES):
        raise ArtifactSchemaError("terminal gate value is not boolean")
