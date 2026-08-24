from __future__ import annotations

from collections.abc import Mapping, Sequence

from . import _artifact_schema_core_r7 as _core
from .canonical import NumberToken


def _exact_nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, NumberToken) and value.is_integer_token:
        observed = int(value.token, 10)
    elif type(value) is int:
        observed = value
    else:
        raise _core.ArtifactSchemaError(
            f"{label} must be a nonnegative exact integer"
        )
    if observed < 0:
        raise _core.ArtifactSchemaError(
            f"{label} must be a nonnegative exact integer"
        )
    return observed


def _normalize_exact_integers(value: object) -> object:
    """Convert only strict-decoded lexical JSON integers to Python ints.

    The canonical decoder deliberately retains source number tokens. Schema
    validation, however, must perform arithmetic over exact integers without
    coercing decimals, booleans, floats, or other source values.
    """

    if isinstance(value, NumberToken):
        if not value.is_integer_token:
            return value
        return int(value.token, 10)
    if isinstance(value, Mapping):
        return {
            key: _normalize_exact_integers(observed)
            for key, observed in value.items()
        }
    if isinstance(value, tuple):
        return tuple(_normalize_exact_integers(observed) for observed in value)
    return value


_core._exact_nonnegative_int = _exact_nonnegative_int

DIAGNOSTIC_ID = _core.DIAGNOSTIC_ID
IMPLEMENTATION_ID = _core.IMPLEMENTATION_ID
TERMINAL_RETURN_CODES = _core.TERMINAL_RETURN_CODES
ALLOWED_RESEARCH_CONCLUSIONS = _core.ALLOWED_RESEARCH_CONCLUSIONS
SCIENTIFIC_STATUS_BY_TERMINAL = _core.SCIENTIFIC_STATUS_BY_TERMINAL
ROOT_CAUSE_STATUS_BY_TERMINAL = _core.ROOT_CAUSE_STATUS_BY_TERMINAL
AUTHORITATIVE_UNIT_UNIVERSES = _core.AUTHORITATIVE_UNIT_UNIVERSES
TAXA = _core.TAXA
PARSE_CONSERVATION_FIELDS = _core.PARSE_CONSERVATION_FIELDS
TERMINAL_GATE_NAMES = _core.TERMINAL_GATE_NAMES
SCIENCE_CONTAINERS = _core.SCIENCE_CONTAINERS
CONTEXT_FILE = _core.CONTEXT_FILE
RESULT_FILE = _core.RESULT_FILE
OBJECT_LEDGER_FILE = _core.OBJECT_LEDGER_FILE
REDUCER_LEDGER_FILE = _core.REDUCER_LEDGER_FILE
CONSERVATION_FILE = _core.CONSERVATION_FILE
RESOURCE_LEDGER_FILE = _core.RESOURCE_LEDGER_FILE
STOP_LEDGER_FILE = _core.STOP_LEDGER_FILE
WALLET_FEATURE_FILE = _core.WALLET_FEATURE_FILE
RETURN_CODE_FILE = _core.RETURN_CODE_FILE
HASH_MANIFEST_FILE = _core.HASH_MANIFEST_FILE
BOUNDARY_FILE = _core.BOUNDARY_FILE
METADATA_CONTAINERS = _core.METADATA_CONTAINERS
EXPECTED_ARTIFACT_FILES = _core.EXPECTED_ARTIFACT_FILES
PHASES = _core.PHASES
ArtifactSchemaError = _core.ArtifactSchemaError
exact_return_code = _core.exact_return_code
exact_scientific_status = _core.exact_scientific_status
exact_root_cause_status = _core.exact_root_cause_status
validate_terminal_tuple = _core.validate_terminal_tuple
validate_research_conclusion = _core.validate_research_conclusion
validate_sha256 = _core.validate_sha256
zero_taxon_counts = _core.zero_taxon_counts


def validate_parse_conservation(
    value: Mapping[str, object],
    *,
    record_count: int,
    event_count: int,
    label: str,
) -> None:
    """Validate the exact parse partition through the public runtime facade.

    These arguments are deliberately part of the public ABI: callers must
    bind the conservation counters to the independently observed pass counts.
    Dropping them would turn this facade into a weaker validator than the
    runtime core it exposes.
    """
    normalized = _normalize_exact_integers(value)
    if not isinstance(normalized, Mapping):
        raise ArtifactSchemaError("parse conservation normalization failed")
    _core.validate_parse_conservation(
        normalized,
        record_count=_exact_nonnegative_int(record_count, f"{label}.record_count"),
        event_count=_exact_nonnegative_int(event_count, f"{label}.event_count"),
        label=label,
    )


def validate_object_row_shape(row: Mapping[str, object]) -> None:
    normalized = _normalize_exact_integers(row)
    if not isinstance(normalized, Mapping):
        raise ArtifactSchemaError("object ledger row normalization failed")
    _core.validate_object_row_shape(normalized)


def validate_universe_rows(rows: Sequence[Mapping[str, object]]) -> None:
    normalized = _normalize_exact_integers(tuple(rows))
    if not isinstance(normalized, tuple) or any(
        not isinstance(row, Mapping) for row in normalized
    ):
        raise ArtifactSchemaError("unit conservation normalization failed")
    _core.validate_universe_rows(normalized)  # type: ignore[arg-type]


def validate_terminal_gates(value: object) -> None:
    normalized = _normalize_exact_integers(value)
    _core.validate_terminal_gates(normalized)


__all__ = [
    "AUTHORITATIVE_UNIT_UNIVERSES",
    "ALLOWED_RESEARCH_CONCLUSIONS",
    "ArtifactSchemaError",
    "BOUNDARY_FILE",
    "CONSERVATION_FILE",
    "CONTEXT_FILE",
    "DIAGNOSTIC_ID",
    "EXPECTED_ARTIFACT_FILES",
    "HASH_MANIFEST_FILE",
    "IMPLEMENTATION_ID",
    "METADATA_CONTAINERS",
    "OBJECT_LEDGER_FILE",
    "PARSE_CONSERVATION_FIELDS",
    "PHASES",
    "REDUCER_LEDGER_FILE",
    "RESOURCE_LEDGER_FILE",
    "RESULT_FILE",
    "RETURN_CODE_FILE",
    "ROOT_CAUSE_STATUS_BY_TERMINAL",
    "SCIENCE_CONTAINERS",
    "SCIENTIFIC_STATUS_BY_TERMINAL",
    "STOP_LEDGER_FILE",
    "TAXA",
    "TERMINAL_GATE_NAMES",
    "TERMINAL_RETURN_CODES",
    "WALLET_FEATURE_FILE",
    "exact_return_code",
    "exact_root_cause_status",
    "exact_scientific_status",
    "validate_object_row_shape",
    "validate_parse_conservation",
    "validate_research_conclusion",
    "validate_sha256",
    "validate_terminal_gates",
    "validate_terminal_tuple",
    "validate_universe_rows",
    "zero_taxon_counts",
]
