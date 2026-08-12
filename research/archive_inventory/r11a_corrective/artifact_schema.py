from __future__ import annotations

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


_core._exact_nonnegative_int = _exact_nonnegative_int

DIAGNOSTIC_ID = _core.DIAGNOSTIC_ID
IMPLEMENTATION_ID = _core.IMPLEMENTATION_ID
TERMINAL_RETURN_CODES = _core.TERMINAL_RETURN_CODES
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
validate_sha256 = _core.validate_sha256
zero_taxon_counts = _core.zero_taxon_counts
validate_parse_conservation = _core.validate_parse_conservation
validate_object_row_shape = _core.validate_object_row_shape
validate_universe_rows = _core.validate_universe_rows
validate_terminal_gates = _core.validate_terminal_gates

__all__ = [
    "AUTHORITATIVE_UNIT_UNIVERSES",
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
    "validate_sha256",
    "validate_terminal_gates",
    "validate_terminal_tuple",
    "validate_universe_rows",
    "zero_taxon_counts",
]
