from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
import tempfile
from collections.abc import Iterator, Mapping
from pathlib import Path

# The approved workflow invokes this file directly.  Ensure that direct-script
# execution and package imports use the same repository modules without
# changing any artifact-validation semantics.
_REPOSITORY_ROOT = Path(__file__).absolute().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from research.archive_inventory.r11a_corrective.artifact import (
    validate_artifact,
)
from research.archive_inventory.r11a_corrective.artifact_schema import (
    AUTHORITATIVE_UNIT_UNIVERSES,
    CONSERVATION_FILE,
    CONTEXT_FILE,
    DIAGNOSTIC_ID,
    IMPLEMENTATION_ID,
    RESULT_FILE,
    SCIENCE_CONTAINERS,
    TAXA,
    TERMINAL_GATE_NAMES,
    validate_sha256,
)
from research.archive_inventory.r11a_corrective.canonical import (
    FrozenObject,
    NumberToken,
    canonical_json_bytes,
    strict_json_loads,
)
from research.archive_inventory.r11a_corrective.identity import frame
from research.archive_inventory.r11a_corrective.limits import DEFAULT_LIMITS
from research.archive_inventory.r11a_corrective.proof_semantics_r7 import (
    SemanticProofError,
    validate_semantic_proofs,
)
from research.archive_inventory.r11a_corrective.runtime import RuntimeGuard
from research.archive_inventory.r11a_corrective.storage_r7 import (
    MeteredSQLite,
    WorkspaceMeter,
)
from governance import r11a_stage_common_r4 as _stage
from governance.validate_r11a_runtime_binding_r7 import (
    validate as validate_runtime_binding,
)

UNIT_FILE = "r11a-v2-taxonomy-units.ndjson"
BLOCK_PROOF_FILE = "r11a-v2-exact-block-replay-proofs.ndjson"
PAIR_PROOF_FILE = "r11a-v2-expected-counterparty-pair-proofs.ndjson"
BLOCK_ROWS_FILE = "r11a-v2-block-overlap-matrix.ndjson"
LEGACY_ROWS_FILE = "r11a-v2-duplicate-observations.ndjson"
PROTOCOL_ROWS_FILE = "r11a-v2-protocol-trade-group-members.ndjson"
SCHEMA_ROWS_FILE = "r11a-v2-repeat-intersecting-schema-evidence.ndjson"

EXPECTED_PROOF_TYPE_BY_CONTAINER = {
    BLOCK_PROOF_FILE: "R11A_V2_EXACT_BLOCK_REPLAY_PROOF",
    PAIR_PROOF_FILE: "R11A_V2_EXPECTED_COUNTERPARTY_PAIR_PROOF",
}

EXPECTED_CONTAINER_BY_UNIVERSE = {
    "LEGACY_REPEAT_OCCURRENCE": LEGACY_ROWS_FILE,
    "ARCHIVE_BLOCK_NUMBER_GROUP": BLOCK_ROWS_FILE,
    "PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE": (
        PROTOCOL_ROWS_FILE
    ),
    "REPEAT_INTERSECTING_TID_SCHEMA_VIOLATION": SCHEMA_ROWS_FILE,
    "REPEAT_INTERSECTING_COIN_SCHEMA_VIOLATION": SCHEMA_ROWS_FILE,
    "REPEAT_INTERSECTING_WALLET_SCHEMA_VIOLATION": SCHEMA_ROWS_FILE,
}

EXPECTED_RETAINED_FIELDS = {
    BLOCK_ROWS_FILE: {
        "record_type",
        "primary_taxon",
        "block_number",
        "raw_locator",
        "raw_block_key_hex",
        "exact_raw_block_time",
        "ordered_event_count",
        "ordered_event_fingerprint_sha256",
        "raw_record_fingerprint_sha256",
        "raw_record_value",
        "diagnostic_id",
        "taxonomy_unit_id",
        "unit_projection_sha256",
        "retained_row_id",
    },
    LEGACY_ROWS_FILE: {
        "record_type",
        "primary_taxon",
        "supporting_taxa",
        "raw_locator",
        "block_number",
        "exact_raw_local_time",
        "exact_raw_block_time",
        "raw_wallet_value",
        "raw_fill_value",
        "raw_record_fingerprint_sha256",
        "canonical_wallet",
        "exact_raw_coin_string",
        "validated_tid",
        "exact_raw_side_string",
        "full_event_sha256",
        "fill_payload_sha256",
        "schema_errors",
        "selected_fill_payload",
        "diagnostic_id",
        "taxonomy_unit_id",
        "unit_projection_sha256",
        "retained_row_id",
    },
    PROTOCOL_ROWS_FILE: {
        "record_type",
        "primary_taxon",
        "raw_locator",
        "raw_block_key_hex",
        "block_number",
        "exact_raw_block_time",
        "raw_wallet_value",
        "raw_fill_value",
        "raw_record_fingerprint_sha256",
        "raw_record_value",
        "canonical_wallet",
        "exact_raw_coin_string",
        "validated_tid",
        "exact_raw_side_string",
        "full_event_sha256",
        "diagnostic_id",
        "taxonomy_unit_id",
        "unit_projection_sha256",
        "retained_row_id",
    },
    SCHEMA_ROWS_FILE: {
        "record_type",
        "primary_taxon",
        "schema_universe",
        "raw_locator",
        "raw_block_key_hex",
        "raw_wallet_value",
        "raw_fill_value",
        "raw_record_fingerprint_sha256",
        "raw_record_value",
        "block_number",
        "exact_raw_local_time",
        "exact_raw_block_time",
        "canonical_wallet",
        "exact_raw_coin_string",
        "validated_tid",
        "exact_raw_side_string",
        "full_event_sha256",
        "fill_payload_sha256",
        "schema_errors",
        "selected_fill_payload",
        "diagnostic_id",
        "taxonomy_unit_id",
        "unit_projection_sha256",
        "retained_row_id",
    },
}

EXPECTED_RECORD_TYPE_BY_CONTAINER = {
    BLOCK_ROWS_FILE: "R11A_V2_BLOCK_OVERLAP_OBSERVATION",
    LEGACY_ROWS_FILE: "R11A_V2_LEGACY_REPEAT_OCCURRENCE",
    PROTOCOL_ROWS_FILE: "R11A_V2_PROTOCOL_TRADE_GROUP_MEMBER",
    SCHEMA_ROWS_FILE: "R11A_V2_REPEAT_INTERSECTING_SCHEMA_EVIDENCE",
}

PROOF_TYPES = frozenset(EXPECTED_PROOF_TYPE_BY_CONTAINER.values())
_SCHEMA_UNIVERSES = frozenset(
    universe
    for universe in AUTHORITATIVE_UNIT_UNIVERSES
    if universe.startswith("REPEAT_INTERSECTING_")
)


class EvidenceValidationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceValidationError(message)


def obj(value: object, label: str) -> FrozenObject:
    require(isinstance(value, FrozenObject), f"{label} must be object")
    return value  # type: ignore[return-value]


def integer(value: object, label: str) -> int:
    if isinstance(value, NumberToken) and value.is_integer_token:
        return int(value.token, 10)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise EvidenceValidationError(f"{label} must be exact integer")


def text(value: object, label: str) -> str:
    require(isinstance(value, str) and bool(value), f"{label} must be text")
    return value  # type: ignore[return-value]


def sha256_text(value: object, label: str) -> str:
    try:
        return validate_sha256(value, label)
    except ValueError as exc:
        raise EvidenceValidationError(str(exc)) from exc


def iter_rows(path: Path) -> Iterator[FrozenObject]:
    with path.open("rb") as handle:
        for ordinal, raw in enumerate(handle):
            require(raw.endswith(b"\n"), f"{path.name} row {ordinal} lacks newline")
            yield obj(strict_json_loads(raw), f"{path.name}[{ordinal}]")


def canonical_supporting(value: object, label: str) -> tuple[str, ...]:
    require(isinstance(value, tuple), f"{label} must be array")
    observed = tuple(text(item, label) for item in value)
    require(len(set(observed)) == len(observed), f"{label} contains duplicate taxon")
    require(set(observed) <= set(TAXA), f"{label} contains unknown taxon")
    require(
        observed == tuple(sorted(observed, key=TAXA.index)),
        f"{label} is not in frozen taxon order",
    )
    return observed


def supporting_sha(value: tuple[str, ...]) -> str:
    return hashlib.sha256(
        canonical_json_bytes(value, final_newline=False)
    ).hexdigest()


def unit_projection(row: FrozenObject) -> bytes:
    value = canonical_json_bytes(
        {
            "diagnostic_id": DIAGNOSTIC_ID,
            "unit_universe": row["unit_universe"],
            "key_projection": row["key_projection"],
            "primary_taxon": row["primary_taxon"],
            "occurrence_count": row["occurrence_count"],
        },
        final_newline=False,
    )
    expected_id = hashlib.sha256(
        frame(text(row["unit_universe"], "unit universe").encode("ascii"), value)
    ).hexdigest()
    require(row["taxonomy_unit_id"] == expected_id, "taxonomy unit ID mismatch")
    require(
        row["unit_projection_sha256"] == hashlib.sha256(value).hexdigest(),
        "taxonomy unit projection mismatch",
    )
    return value


def proof_projection(row: FrozenObject, expected_type: str) -> bytes:
    require(row["record_type"] == expected_type, "proof record type drift")
    projection = canonical_json_bytes(row["projection"], final_newline=False)
    expected_id = hashlib.sha256(
        frame(expected_type.encode("ascii"), projection)
    ).hexdigest()
    require(row["proof_id"] == expected_id, "proof ID mismatch")
    require(
        row["proof_projection_sha256"]
        == hashlib.sha256(projection).hexdigest(),
        "proof projection mismatch",
    )
    return projection


def create_database(path: Path, meter: WorkspaceMeter) -> MeteredSQLite:
    database = MeteredSQLite(
        path,
        meter,
        536_870_912,
        "independent evidence join database",
    )
    with database.transaction("create independent evidence schema") as connection:
        connection.executescript(
            """
        CREATE TABLE units(
          id TEXT PRIMARY KEY,
          universe TEXT NOT NULL,
          taxon TEXT NOT NULL,
          occurrences INTEGER NOT NULL CHECK(occurrences>0),
          projection BLOB NOT NULL,
          projection_sha TEXT NOT NULL,
          supporting_sha TEXT NOT NULL
        );
        CREATE TABLE supporting(
          unit_id TEXT NOT NULL,
          ordinal INTEGER NOT NULL,
          taxon TEXT NOT NULL,
          PRIMARY KEY(unit_id,taxon),
          UNIQUE(unit_id,ordinal)
        );
        CREATE TABLE proofs(
          id TEXT PRIMARY KEY,
          type TEXT NOT NULL,
          projection BLOB NOT NULL,
          projection_sha TEXT NOT NULL,
          container TEXT NOT NULL
        );
        CREATE TABLE refs(
          unit_id TEXT NOT NULL,
          proof_id TEXT NOT NULL,
          type TEXT NOT NULL,
          unit_projection_sha TEXT NOT NULL,
          proof_projection_sha TEXT NOT NULL,
          UNIQUE(unit_id,proof_id,type)
        );
        CREATE TABLE retained(
          row_id TEXT PRIMARY KEY,
          unit_id TEXT NOT NULL,
          unit_projection_sha TEXT NOT NULL,
          container TEXT NOT NULL,
          primary_taxon TEXT NOT NULL,
          schema_universe TEXT,
          supporting_sha TEXT
        );
        CREATE INDEX retained_by_unit ON retained(unit_id);
        CREATE INDEX units_by_universe_taxon ON units(universe,taxon);
            """
        )
    return database


def load_units(
    artifact: Path,
    database: MeteredSQLite,
) -> int:
    connection = database.connection
    expected_fields = {
        "record_type",
        "diagnostic_id",
        "taxonomy_unit_id",
        "unit_universe",
        "unit_projection_sha256",
        "key_projection",
        "primary_taxon",
        "supporting_taxa",
        "occurrence_count",
        "proof_references",
    }
    count = 0
    with database.transaction("load authoritative taxonomy units"):
        for row in iter_rows(artifact / UNIT_FILE):
            require(set(row) == expected_fields, "taxonomy unit field set drift")
            require(
                row["record_type"] == "R11A_V2_TAXONOMY_UNIT",
                "unit record type drift",
            )
            require(row["diagnostic_id"] == DIAGNOSTIC_ID, "unit diagnostic ID drift")
            universe = text(row["unit_universe"], "unit universe")
            taxon = text(row["primary_taxon"], "primary taxon")
            require(universe in AUTHORITATIVE_UNIT_UNIVERSES, "unknown unit universe")
            require(taxon in TAXA, "unknown primary taxon")
            occurrences = integer(row["occurrence_count"], "unit occurrence count")
            require(occurrences > 0, "unit occurrence count must be positive")
            projection = unit_projection(row)
            projection_digest = hashlib.sha256(projection).hexdigest()
            supporting = canonical_supporting(
                row["supporting_taxa"],
                "unit supporting taxa",
            )
            references = row["proof_references"]
            require(isinstance(references, tuple), "proof references must be array")
            try:
                connection.execute(
                    "INSERT INTO units VALUES(?,?,?,?,?,?,?)",
                    (
                        row["taxonomy_unit_id"],
                        universe,
                        taxon,
                        occurrences,
                        sqlite3.Binary(projection),
                        projection_digest,
                        supporting_sha(supporting),
                    ),
                )
                connection.executemany(
                    "INSERT INTO supporting VALUES(?,?,?)",
                    (
                        (row["taxonomy_unit_id"], ordinal, value)
                        for ordinal, value in enumerate(supporting)
                    ),
                )
                for value in references:
                    reference = obj(value, "proof reference")
                    require(
                        set(reference)
                        == {
                            "proof_type",
                            "proof_id",
                            "proof_projection_sha256",
                        },
                        "proof reference field set drift",
                    )
                    proof_type = text(reference["proof_type"], "proof type")
                    require(proof_type in PROOF_TYPES, "unknown proof reference type")
                    proof_id = sha256_text(reference["proof_id"], "proof ID")
                    proof_sha = sha256_text(
                        reference["proof_projection_sha256"],
                        "proof projection SHA",
                    )
                    connection.execute(
                        "INSERT INTO refs VALUES(?,?,?,?,?)",
                        (
                            row["taxonomy_unit_id"],
                            proof_id,
                            proof_type,
                            projection_digest,
                            proof_sha,
                        ),
                    )
            except sqlite3.IntegrityError as exc:
                raise EvidenceValidationError(
                    "duplicate taxonomy unit, supporting taxon, or proof reference"
                ) from exc
            count += 1
    return count


def load_proofs(
    artifact: Path,
    database: MeteredSQLite,
) -> int:
    connection = database.connection
    expected_fields = {
        "record_type",
        "diagnostic_id",
        "proof_id",
        "proof_projection_sha256",
        "projection",
    }
    count = 0
    with database.transaction("load proof universe"):
        for container, expected_type in EXPECTED_PROOF_TYPE_BY_CONTAINER.items():
            for row in iter_rows(artifact / container):
                require(set(row) == expected_fields, "proof field set drift")
                require(row["diagnostic_id"] == DIAGNOSTIC_ID, "proof diagnostic ID drift")
                projection = proof_projection(row, expected_type)
                digest = hashlib.sha256(projection).hexdigest()
                try:
                    connection.execute(
                        "INSERT INTO proofs VALUES(?,?,?,?,?)",
                        (
                            row["proof_id"],
                            expected_type,
                            sqlite3.Binary(projection),
                            digest,
                            container,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise EvidenceValidationError("duplicate proof ID") from exc
                count += 1
    return count


def load_retained(
    artifact: Path,
    database: MeteredSQLite,
) -> int:
    connection = database.connection
    count = 0
    with database.transaction("load retained semantic evidence"):
        for container, expected_fields in EXPECTED_RETAINED_FIELDS.items():
            expected_record_type = EXPECTED_RECORD_TYPE_BY_CONTAINER[container]
            for row in iter_rows(artifact / container):
                require(set(row) == expected_fields, f"{container} field set drift")
                require(row["diagnostic_id"] == DIAGNOSTIC_ID, "retained diagnostic ID drift")
                require(row["record_type"] == expected_record_type, "retained record type drift")
                taxon = text(row["primary_taxon"], "retained primary taxon")
                require(taxon in TAXA, "retained row contains unknown primary taxon")
                unit_id = sha256_text(row["taxonomy_unit_id"], "taxonomy unit ID")
                unit_sha = sha256_text(
                    row["unit_projection_sha256"],
                    "retained unit projection SHA",
                )
                without_id = {
                    key: row[key] for key in row if key != "retained_row_id"
                }
                expected_row_id = hashlib.sha256(
                    canonical_json_bytes(without_id, final_newline=False)
                ).hexdigest()
                require(
                    row["retained_row_id"] == expected_row_id,
                    "retained row ID mismatch",
                )
                schema_universe: str | None = None
                observed_supporting_sha: str | None = None
                if container == SCHEMA_ROWS_FILE:
                    schema_universe = text(
                        row["schema_universe"],
                        "schema universe",
                    )
                    require(
                        schema_universe in _SCHEMA_UNIVERSES,
                        "retained schema evidence has unknown universe",
                    )
                if container == LEGACY_ROWS_FILE:
                    observed_supporting_sha = supporting_sha(
                        canonical_supporting(
                            row["supporting_taxa"],
                            "retained supporting taxa",
                        )
                    )
                try:
                    connection.execute(
                        "INSERT INTO retained VALUES(?,?,?,?,?,?,?)",
                        (
                            row["retained_row_id"],
                            unit_id,
                            unit_sha,
                            container,
                            taxon,
                            schema_universe,
                            observed_supporting_sha,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise EvidenceValidationError("duplicate retained row ID") from exc
                count += 1
    return count


def validate_foreign_keys(connection: sqlite3.Connection) -> None:
    for unit_id, proof_id, proof_type, unit_sha, proof_sha in connection.execute(
        "SELECT unit_id,proof_id,type,unit_projection_sha,proof_projection_sha FROM refs"
    ):
        unit = connection.execute(
            "SELECT projection_sha FROM units WHERE id=?",
            (unit_id,),
        ).fetchone()
        proof = connection.execute(
            "SELECT projection_sha FROM proofs WHERE id=? AND type=?",
            (proof_id, proof_type),
        ).fetchone()
        require(unit is not None, "proof reference has dangling unit foreign key")
        require(proof is not None, "proof reference has dangling proof foreign key")
        require(unit[0] == unit_sha, "proof reference unit projection mismatch")
        require(proof[0] == proof_sha, "proof reference proof projection mismatch")

    unreferenced_proofs = int(
        connection.execute(
            """
            SELECT COUNT(*) FROM proofs p
            LEFT JOIN refs r ON r.proof_id=p.id AND r.type=p.type
            WHERE r.proof_id IS NULL
            """
        ).fetchone()[0]
    )
    require(unreferenced_proofs == 0, "artifact contains unreferenced proof")

    for (
        unit_id,
        unit_sha,
        container,
        primary_taxon,
        schema_universe,
        retained_supporting_sha,
    ) in connection.execute(
        """
        SELECT unit_id,unit_projection_sha,container,primary_taxon,
               schema_universe,supporting_sha
        FROM retained
        """
    ):
        unit = connection.execute(
            "SELECT universe,taxon,projection_sha,supporting_sha FROM units WHERE id=?",
            (unit_id,),
        ).fetchone()
        require(unit is not None, "retained row has dangling unit foreign key")
        universe, taxon, expected_projection_sha, expected_supporting_sha = unit
        require(unit_sha == expected_projection_sha, "retained unit projection mismatch")
        require(primary_taxon == taxon, "retained row primary taxon differs from unit")
        require(
            container == EXPECTED_CONTAINER_BY_UNIVERSE[universe],
            "retained row is stored in wrong universe container",
        )
        if universe in _SCHEMA_UNIVERSES:
            require(schema_universe == universe, "schema retained row universe mismatch")
        else:
            require(schema_universe is None, "non-schema retained row has schema universe")
        if universe == "LEGACY_REPEAT_OCCURRENCE":
            require(
                retained_supporting_sha == expected_supporting_sha,
                "legacy retained supporting taxa differ from unit",
            )
        else:
            require(
                retained_supporting_sha is None,
                "non-legacy retained row has supporting taxa",
            )

    multiplicity_mismatches = int(
        connection.execute(
            """
            SELECT COUNT(*) FROM units u
            LEFT JOIN (
              SELECT unit_id,COUNT(*) AS retained_count
              FROM retained GROUP BY unit_id
            ) r ON r.unit_id=u.id
            WHERE COALESCE(r.retained_count,0)<>u.occurrences
            """
        ).fetchone()[0]
    )
    require(
        multiplicity_mismatches == 0,
        "retained row multiplicity differs from unit occurrence count",
    )


def validate_conservation(
    artifact: Path,
    connection: sqlite3.Connection,
    *,
    unit_count: int,
    proof_count: int,
    retained_count: int,
) -> None:
    result = obj(
        strict_json_loads((artifact / RESULT_FILE).read_bytes()),
        "result",
    )
    terminal = text(result["terminal_class"], "terminal class")
    conservation = obj(
        strict_json_loads((artifact / CONSERVATION_FILE).read_bytes()),
        "conservation",
    )
    join = obj(conservation["join_validation"], "join validation")
    reference_count = int(connection.execute("SELECT COUNT(*) FROM refs").fetchone()[0])
    expected_join = {
        "unit_count": unit_count,
        "proof_count": proof_count,
        "proof_reference_count": reference_count,
        "retained_row_reference_count": retained_count,
        "all_unit_ids_unique": True,
        "all_proof_ids_unique": True,
        "all_nonnull_proof_references_resolve_exactly_once": True,
        "all_retained_rows_reference_exactly_one_unit": True,
        "all_referenced_projections_are_byte_equal": True,
        "all_retained_row_counts_match_unit_occurrence_counts": True,
    }
    observed_join = {
        key: (
            integer(join[key], key)
            if key
            in {
                "unit_count",
                "proof_count",
                "proof_reference_count",
                "retained_row_reference_count",
            }
            else join[key]
        )
        for key in join
    }
    require(
        all(
            type(observed_join[key]) is bool
            for key in set(expected_join)
            - {
                "unit_count",
                "proof_count",
                "proof_reference_count",
                "retained_row_reference_count",
            }
        ),
        "declared join validation flag is not boolean",
    )
    require(
        observed_join == expected_join,
        "declared join validation differs from independent recomputation",
    )

    universe_values = conservation["unit_universes"]
    require(isinstance(universe_values, tuple), "unit conservation must be array")
    require(
        tuple(obj(value, "universe row")["unit_universe"] for value in universe_values)
        == AUTHORITATIVE_UNIT_UNIVERSES,
        "unit universe ordering drift",
    )
    unclassifiable_group_total = 0
    unclassifiable_occurrence_total = 0
    for value in universe_values:
        row = obj(value, "universe row")
        universe = text(row["unit_universe"], "unit universe")
        observed_group_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM units WHERE universe=?",
                (universe,),
            ).fetchone()[0]
        )
        observed_occurrence_count = int(
            connection.execute(
                "SELECT COALESCE(SUM(occurrences),0) FROM units WHERE universe=?",
                (universe,),
            ).fetchone()[0]
        )
        require(
            observed_group_count == integer(row["group_count"], "group count"),
            "universe group count mismatch",
        )
        require(
            observed_occurrence_count
            == integer(row["occurrence_count"], "occurrence count"),
            "universe occurrence count mismatch",
        )
        declared_groups = obj(
            row["primary_taxon_group_counts"],
            "primary group taxon counts",
        )
        declared_occurrences = obj(
            row["primary_taxon_occurrence_counts"],
            "primary occurrence taxon counts",
        )
        require(set(declared_groups) == set(TAXA), "group taxon map drift")
        require(set(declared_occurrences) == set(TAXA), "occurrence taxon map drift")
        for taxon in TAXA:
            observed_group = int(
                connection.execute(
                    "SELECT COUNT(*) FROM units WHERE universe=? AND taxon=?",
                    (universe, taxon),
                ).fetchone()[0]
            )
            observed_occurrence = int(
                connection.execute(
                    "SELECT COALESCE(SUM(occurrences),0) FROM units WHERE universe=? AND taxon=?",
                    (universe, taxon),
                ).fetchone()[0]
            )
            require(
                observed_group == integer(declared_groups[taxon], taxon),
                "primary group taxon count mismatch",
            )
            require(
                observed_occurrence
                == integer(declared_occurrences[taxon], taxon),
                "primary occurrence taxon count mismatch",
            )
        observed_unclassifiable_groups = int(
            connection.execute(
                "SELECT COUNT(*) FROM units WHERE universe=? AND taxon='UNCLASSIFIABLE'",
                (universe,),
            ).fetchone()[0]
        )
        observed_unclassifiable_occurrences = int(
            connection.execute(
                "SELECT COALESCE(SUM(occurrences),0) FROM units "
                "WHERE universe=? AND taxon='UNCLASSIFIABLE'",
                (universe,),
            ).fetchone()[0]
        )
        require(
            observed_unclassifiable_groups
            == integer(
                row["unclassifiable_group_count"],
                "unclassifiable group count",
            ),
            "unclassifiable group count mismatch",
        )
        require(
            observed_unclassifiable_occurrences
            == integer(
                row["unclassifiable_occurrence_count"],
                "unclassifiable occurrence count",
            ),
            "unclassifiable occurrence count mismatch",
        )
        unclassifiable_group_total += observed_unclassifiable_groups
        unclassifiable_occurrence_total += observed_unclassifiable_occurrences

    gates = obj(conservation["terminal_gates"], "terminal gates")
    require(set(gates) == set(TERMINAL_GATE_NAMES), "terminal gate set drift")
    require(
        all(type(gates[name]) is bool for name in TERMINAL_GATE_NAMES),
        "terminal gate value is not boolean",
    )
    scientific_gate = (
        "every_unit_universe_has_zero_unclassifiable_groups_and_occurrences"
    )
    if terminal == "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE":
        require(
            unclassifiable_group_total == 0
            and unclassifiable_occurrence_total == 0
            and all(gates[name] is True for name in TERMINAL_GATE_NAMES),
            "RC0 terminal gates contradict independently recomputed science",
        )
    elif terminal == "R11A_V2_DIAGNOSTIC_INCOMPLETE":
        require(
            unclassifiable_group_total > 0
            and unclassifiable_occurrence_total > 0
            and gates[scientific_gate] is False
            and all(
                gates[name] is True
                for name in TERMINAL_GATE_NAMES
                if name != scientific_gate
            ),
            "RC20 terminal gates contradict independently recomputed science",
        )

    supporting = obj(
        conservation["supporting_taxon_counts"],
        "supporting taxon counts",
    )
    require(set(supporting) == set(TAXA), "supporting taxon map drift")
    for taxon in TAXA:
        observed = int(
            connection.execute(
                "SELECT COUNT(*) FROM supporting WHERE taxon=?",
                (taxon,),
            ).fetchone()[0]
        )
        require(
            observed == integer(supporting[taxon], taxon),
            "supporting taxon count mismatch",
        )


def validate_result_row_counts(
    artifact: Path,
    row_counts: Mapping[str, int],
) -> None:
    result = obj(
        strict_json_loads((artifact / RESULT_FILE).read_bytes()),
        "result",
    )
    require(result["diagnostic_id"] == DIAGNOSTIC_ID, "result diagnostic ID drift")
    require(result["implementation_id"] == IMPLEMENTATION_ID, "result implementation ID drift")
    scientific = obj(result["scientific_files"], "scientific files")
    require(set(scientific) == set(SCIENCE_CONTAINERS), "scientific file map drift")
    for name in SCIENCE_CONTAINERS:
        evidence = obj(scientific[name], f"scientific file {name}")
        require(
            integer(evidence["row_count"], f"{name} row count")
            == row_counts[name],
            f"{name} declared row count mismatch",
        )


def validate_science(artifact: Path) -> None:
    result = obj(
        strict_json_loads((artifact / RESULT_FILE).read_bytes()),
        "result",
    )
    if result["scientific_output_status"] == "EMPTY":
        row_counts = {
            name: sum(1 for _ in iter_rows(artifact / name))
            for name in SCIENCE_CONTAINERS
        }
        require(all(value == 0 for value in row_counts.values()), "empty artifact has science rows")
        validate_result_row_counts(artifact, row_counts)
        return

    row_counts = {name: 0 for name in SCIENCE_CONTAINERS}
    with tempfile.TemporaryDirectory(
        prefix=".r11a-v2-evidence-",
        dir=artifact.parent,
    ) as temporary:
        guard = RuntimeGuard(DEFAULT_LIMITS)
        meter = WorkspaceMeter(Path(temporary), DEFAULT_LIMITS, guard)
        meter.bootstrap()
        database = create_database(meter.root / "joins.sqlite", meter)
        connection = database.connection
        try:
            unit_count = load_units(artifact, database)
            row_counts[UNIT_FILE] = unit_count
            proof_count = load_proofs(artifact, database)
            row_counts[BLOCK_PROOF_FILE] = int(
                connection.execute(
                    "SELECT COUNT(*) FROM proofs WHERE container=?",
                    (BLOCK_PROOF_FILE,),
                ).fetchone()[0]
            )
            row_counts[PAIR_PROOF_FILE] = int(
                connection.execute(
                    "SELECT COUNT(*) FROM proofs WHERE container=?",
                    (PAIR_PROOF_FILE,),
                ).fetchone()[0]
            )
            retained_count = load_retained(artifact, database)
            for name in (
                BLOCK_ROWS_FILE,
                LEGACY_ROWS_FILE,
                PROTOCOL_ROWS_FILE,
                SCHEMA_ROWS_FILE,
            ):
                row_counts[name] = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM retained WHERE container=?",
                        (name,),
                    ).fetchone()[0]
                )
            require(
                sum(row_counts[name] for name in EXPECTED_PROOF_TYPE_BY_CONTAINER)
                == proof_count,
                "proof container count drift",
            )
            require(
                sum(
                    row_counts[name]
                    for name in EXPECTED_RETAINED_FIELDS
                )
                == retained_count,
                "retained container count drift",
            )
            validate_foreign_keys(connection)
            try:
                validate_semantic_proofs(artifact)
            except SemanticProofError as exc:
                raise EvidenceValidationError(
                    f"independent semantic proof recomputation failed: {exc}"
                ) from exc
            validate_conservation(
                artifact,
                connection,
                unit_count=unit_count,
                proof_count=proof_count,
                retained_count=retained_count,
            )
            validate_result_row_counts(artifact, row_counts)
        finally:
            database.close_delete()


def validate_aligned_execution_artifact(
    artifact: Path,
    *,
    root: Path = _REPOSITORY_ROOT,
) -> None:
    """Validate an artifact and bind every post-OIDC context to R7 authority.

    Minimal pre-OIDC failure artifacts deliberately remain independently
    verifiable when the runtime-binding gate itself failed.  Any bound context
    contains ``approval_id`` and must match the complete aligned runtime chain
    and the exact raw repository bytes before its science is accepted.
    """

    validate_artifact(artifact, DEFAULT_LIMITS)
    context = obj(
        strict_json_loads((artifact / CONTEXT_FILE).read_bytes()),
        "artifact context",
    )
    bound_context = "approval_id" in context
    runtime_required = (
        bound_context or context["execution_phase"] != "PRE_OIDC_STATIC_GATE"
    )
    binding: Mapping[str, object] | None = None
    if runtime_required:
        dispatch_sha = text(context["dispatch_sha"], "artifact dispatch SHA")
        run_attempt = integer(
            context["workflow_run_attempt"],
            "artifact workflow run attempt",
        )
        binding = validate_runtime_binding(dispatch_sha, run_attempt, root=root)
    if bound_context:
        require(binding is not None, "bound artifact lacks aligned runtime binding")
        release = _stage.load(root, _stage.RELEASE_RELATIVE)
        activation = _stage.load(root, _stage.ACTIVATION_RELATIVE)
        pricing = _stage.load(root, _stage.PRICING_TARGET_RELATIVE)
        expected = {
            "approval_id": _stage.APPROVAL_ID,
            "approval_text_sha256": _stage.sha256(root, _stage.APPROVAL_TEXT_RELATIVE),
            "execution_release_id": release["execution_release_id"],
            "execution_release_blob_sha256": _stage.sha256(root, _stage.RELEASE_RELATIVE),
            "activation_id": activation["activation_id"],
            "implementation_contract_sha256": _stage.sha256(root, _stage.IMPLEMENTATION_RELATIVE),
            "workflow_sha256": _stage.sha256(root, _stage.WORKFLOW_RELATIVE),
            "collector_sha256": _stage.sha256(root, _stage.RUNNER_RELATIVE),
            "validator_sha256": _stage.sha256(root, _stage.ARTIFACT_VALIDATOR_RELATIVE),
            "selection_sha256": _stage.sha256(root, _stage.SELECTION_RELATIVE),
            "pricing_snapshot_sha256": _stage.sha256(root, _stage.PRICING_TARGET_RELATIVE),
            "single_use_window_start_utc": binding["single_use_window_start_utc"],
        }
        for key, expected_value in expected.items():
            require(
                context[key] == expected_value,
                f"artifact bound context drift: {key}",
            )
        require(
            integer(
                context["pricing_projection_eur_micros"],
                "artifact pricing projection",
            )
            == pricing["projected_eur_micros_at_frozen_maximum"],
            "artifact bound context drift: pricing_projection_eur_micros",
        )
    validate_science(artifact)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Independently validate one exact R11A R7 artifact"
    )
    parser.add_argument("artifact", type=Path)
    arguments = parser.parse_args(argv)
    validate_aligned_execution_artifact(arguments.artifact)
    print("R11A_V2_EXECUTION_ARTIFACT_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
