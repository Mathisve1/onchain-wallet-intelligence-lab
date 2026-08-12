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


def validate_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ArtifactSchemaError(f"{label} must be lowercase SHA-256")
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
    if type(expected_identity["size_bytes"]) is not int or expected_identity["size_bytes"] <= 0:
        raise ArtifactSchemaError("expected size invalid")
    if not isinstance(expected_identity["etag"], str):
        raise ArtifactSchemaError("expected etag invalid")
    validate_sha256(expected_identity["compressed_sha256"], "expected compressed SHA")
    request = row["request"]
    if not isinstance(request, Mapping) or set(request) != {"count", "status"}:
        raise ArtifactSchemaError("request evidence schema drift")
    if request["count"] not in {0, 1}:
        raise ArtifactSchemaError("request count outside one-request envelope")
    response = row["response"]
    if response is not None:
        if not isinstance(response, Mapping) or set(response) != {
            "http_status",
            "etag",
            "content_length",
            "requester_charged",
        }:
            raise ArtifactSchemaError("response metadata schema drift")
    body = row["body"]
    if not isinstance(body, Mapping) or set(body) != {
        "status",
        "bytes_received",
        "observed_compressed_sha256",
    }:
        raise ArtifactSchemaError("body evidence schema drift")
    if type(body["bytes_received"]) is not int or body["bytes_received"] < 0:
        raise ArtifactSchemaError("body byte count invalid")
    if body["observed_compressed_sha256"] is not None:
        validate_sha256(body["observed_compressed_sha256"], "observed compressed SHA")
    for name in ("first_pass", "second_pass"):
        value = row[name]
        if value is None:
            continue
        if not isinstance(value, Mapping) or set(value) != {
            "status",
            "decompressed_bytes",
            "record_count",
            "event_count",
            "decompressed_stream_sha256",
            "conservation",
        }:
            raise ArtifactSchemaError(f"{name} evidence schema drift")
        for field in ("decompressed_bytes", "record_count", "event_count"):
            if type(value[field]) is not int or value[field] < 0:
                raise ArtifactSchemaError(f"{name}.{field} invalid")
        validate_sha256(value["decompressed_stream_sha256"], f"{name} stream SHA")
        if not isinstance(value["conservation"], Mapping):
            raise ArtifactSchemaError(f"{name}.conservation must be object")


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
        for field in (
            "group_count",
            "occurrence_count",
            "unclassifiable_group_count",
            "unclassifiable_occurrence_count",
        ):
            value = row[field]
            if type(value) is not int or value < 0:
                raise ArtifactSchemaError(f"invalid universe conservation count: {field}")
        for field in ("primary_taxon_group_counts", "primary_taxon_occurrence_counts"):
            mapping = row[field]
            if not isinstance(mapping, Mapping) or set(mapping) - set(TAXA):
                raise ArtifactSchemaError("taxonomy count map contains unknown taxon")
            if any(type(value) is not int or value < 0 for value in mapping.values()):
                raise ArtifactSchemaError("taxonomy count map contains invalid count")
