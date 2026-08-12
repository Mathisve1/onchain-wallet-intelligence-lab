from __future__ import annotations

import argparse
import hashlib
import sqlite3
import tempfile
from pathlib import Path

from research.archive_inventory.r11a_corrective.artifact import validate_artifact
from research.archive_inventory.r11a_corrective.artifact_schema import (
    AUTHORITATIVE_UNIT_UNIVERSES,
    DIAGNOSTIC_ID,
    IMPLEMENTATION_ID,
    SCIENCE_CONTAINERS,
    TAXA,
)
from research.archive_inventory.r11a_corrective.canonical import (
    FrozenObject,
    NumberToken,
    canonical_json_bytes,
    strict_json_loads,
)
from research.archive_inventory.r11a_corrective.identity import frame
from research.archive_inventory.r11a_corrective.limits import DEFAULT_LIMITS


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
        return int(value.token)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise EvidenceValidationError(f"{label} must be exact integer")


def rows(path: Path) -> tuple[FrozenObject, ...]:
    return tuple(obj(strict_json_loads(raw), path.name) for raw in path.read_bytes().splitlines())


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
        frame(str(row["unit_universe"]).encode("ascii"), value)
    ).hexdigest()
    require(row["taxonomy_unit_id"] == expected_id, "taxonomy unit ID mismatch")
    require(
        row["unit_projection_sha256"] == hashlib.sha256(value).hexdigest(),
        "taxonomy unit projection mismatch",
    )
    return value


def proof_projection(row: FrozenObject) -> tuple[str, bytes]:
    proof_type = str(row["record_type"])
    projection = canonical_json_bytes(row["projection"], final_newline=False)
    expected_id = hashlib.sha256(frame(proof_type.encode("ascii"), projection)).hexdigest()
    require(row["proof_id"] == expected_id, "proof ID mismatch")
    require(
        row["proof_projection_sha256"] == hashlib.sha256(projection).hexdigest(),
        "proof projection mismatch",
    )
    return proof_type, projection


def validate_science(artifact: Path) -> None:
    result = obj(strict_json_loads((artifact / "r11a-v2-result.json").read_bytes()), "result")
    if result["scientific_output_status"] == "EMPTY":
        return
    with tempfile.TemporaryDirectory(prefix="r11a-v2-evidence-") as temporary:
        connection = sqlite3.connect(Path(temporary) / "joins.sqlite")
        connection.executescript(
            """
            CREATE TABLE units(id TEXT PRIMARY KEY,universe TEXT NOT NULL,taxon TEXT NOT NULL,occurrences INTEGER NOT NULL,projection BLOB NOT NULL);
            CREATE TABLE proofs(id TEXT PRIMARY KEY,type TEXT NOT NULL,projection BLOB NOT NULL);
            CREATE TABLE refs(unit_id TEXT NOT NULL,proof_id TEXT NOT NULL,type TEXT NOT NULL,unit_projection_sha TEXT NOT NULL,proof_projection_sha TEXT NOT NULL,UNIQUE(unit_id,proof_id,type));
            CREATE TABLE retained(row_id TEXT PRIMARY KEY,unit_id TEXT NOT NULL,unit_projection_sha TEXT NOT NULL,container TEXT NOT NULL);
            """
        )
        unit_rows = rows(artifact / "r11a-v2-taxonomy-units.ndjson")
        for row in unit_rows:
            require(row["record_type"] == "R11A_V2_TAXONOMY_UNIT", "unit record type drift")
            require(row["diagnostic_id"] == DIAGNOSTIC_ID, "unit diagnostic ID drift")
            require(row["unit_universe"] in AUTHORITATIVE_UNIT_UNIVERSES, "unknown unit universe")
            require(row["primary_taxon"] in TAXA, "unknown primary taxon")
            projection = unit_projection(row)
            try:
                connection.execute(
                    "INSERT INTO units VALUES(?,?,?,?,?)",
                    (
                        row["taxonomy_unit_id"],
                        row["unit_universe"],
                        row["primary_taxon"],
                        integer(row["occurrence_count"], "unit occurrence count"),
                        sqlite3.Binary(projection),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise EvidenceValidationError("duplicate taxonomy unit ID") from exc
            references = row["proof_references"]
            require(isinstance(references, tuple), "proof references must be array")
            for value in references:
                reference = obj(value, "proof reference")
                try:
                    connection.execute(
                        "INSERT INTO refs VALUES(?,?,?,?,?)",
                        (
                            row["taxonomy_unit_id"],
                            reference["proof_id"],
                            reference["proof_type"],
                            row["unit_projection_sha256"],
                            reference["proof_projection_sha256"],
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise EvidenceValidationError("duplicate proof reference") from exc
        for name in (
            "r11a-v2-exact-block-replay-proofs.ndjson",
            "r11a-v2-expected-counterparty-pair-proofs.ndjson",
        ):
            for row in rows(artifact / name):
                require(row["diagnostic_id"] == DIAGNOSTIC_ID, "proof diagnostic ID drift")
                proof_type, projection = proof_projection(row)
                try:
                    connection.execute(
                        "INSERT INTO proofs VALUES(?,?,?)",
                        (row["proof_id"], proof_type, sqlite3.Binary(projection)),
                    )
                except sqlite3.IntegrityError as exc:
                    raise EvidenceValidationError("duplicate proof ID") from exc
        retained_names = (
            "r11a-v2-block-overlap-matrix.ndjson",
            "r11a-v2-duplicate-observations.ndjson",
            "r11a-v2-protocol-trade-group-members.ndjson",
            "r11a-v2-repeat-intersecting-schema-evidence.ndjson",
        )
        for name in retained_names:
            for row in rows(artifact / name):
                require(row["diagnostic_id"] == DIAGNOSTIC_ID, "retained row diagnostic ID drift")
                without_id = {key: row[key] for key in row if key != "retained_row_id"}
                expected = hashlib.sha256(canonical_json_bytes(without_id, final_newline=False)).hexdigest()
                require(row["retained_row_id"] == expected, "retained row ID mismatch")
                try:
                    connection.execute(
                        "INSERT INTO retained VALUES(?,?,?,?)",
                        (
                            row["retained_row_id"],
                            row["taxonomy_unit_id"],
                            row["unit_projection_sha256"],
                            name,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise EvidenceValidationError("duplicate retained row ID") from exc
        connection.commit()
        dangling_refs = connection.execute(
            """
            SELECT COUNT(*) FROM refs r
            LEFT JOIN units u ON u.id=r.unit_id
            LEFT JOIN proofs p ON p.id=r.proof_id AND p.type=r.type
            WHERE u.id IS NULL OR p.id IS NULL OR r.unit_projection_sha<>lower(hex(sha256(u.projection)))
            """
        ) if False else None
        # SQLite has no built-in SHA-256. Perform exact BLOB joins and compare the
        # already independently recomputed projection digests in Python below.
        for unit_id, proof_id, proof_type, unit_sha, proof_sha in connection.execute(
            "SELECT unit_id,proof_id,type,unit_projection_sha,proof_projection_sha FROM refs"
        ):
            unit = connection.execute("SELECT projection FROM units WHERE id=?", (unit_id,)).fetchone()
            proof = connection.execute(
                "SELECT projection FROM proofs WHERE id=? AND type=?", (proof_id, proof_type)
            ).fetchone()
            require(unit is not None and proof is not None, "dangling proof foreign key")
            require(hashlib.sha256(bytes(unit[0])).hexdigest() == unit_sha, "unit projection FK mismatch")
            require(hashlib.sha256(bytes(proof[0])).hexdigest() == proof_sha, "proof projection FK mismatch")
        for unit_id, projection_sha in connection.execute(
            "SELECT unit_id,unit_projection_sha FROM retained"
        ):
            unit = connection.execute("SELECT projection FROM units WHERE id=?", (unit_id,)).fetchone()
            require(unit is not None, "retained row has dangling unit FK")
            require(hashlib.sha256(bytes(unit[0])).hexdigest() == projection_sha, "retained projection mismatch")
        conservation = obj(
            strict_json_loads((artifact / "r11a-v2-conservation.json").read_bytes()),
            "conservation",
        )
        expected_rows = conservation["unit_universes"]
        require(isinstance(expected_rows, tuple), "unit conservation must be array")
        observed_universes = tuple(
            row[0] for row in connection.execute("SELECT DISTINCT universe FROM units ORDER BY universe")
        )
        declared_nonempty = tuple(
            row["unit_universe"]
            for row in expected_rows
            if integer(obj(row, "universe row")["group_count"], "group count") > 0
        )
        require(set(observed_universes) == set(declared_nonempty), "unit universe retention mismatch")
        for value in expected_rows:
            row = obj(value, "universe row")
            universe = str(row["unit_universe"])
            group_count = connection.execute(
                "SELECT COUNT(*) FROM units WHERE universe=?", (universe,)
            ).fetchone()[0]
            occurrence_count = connection.execute(
                "SELECT COALESCE(SUM(occurrences),0) FROM units WHERE universe=?", (universe,)
            ).fetchone()[0]
            require(group_count == integer(row["group_count"], "group count"), "group count mismatch")
            require(
                occurrence_count == integer(row["occurrence_count"], "occurrence count"),
                "occurrence count mismatch",
            )
            for taxon in TAXA:
                observed_group = connection.execute(
                    "SELECT COUNT(*) FROM units WHERE universe=? AND taxon=?",
                    (universe, taxon),
                ).fetchone()[0]
                observed_occurrence = connection.execute(
                    "SELECT COALESCE(SUM(occurrences),0) FROM units WHERE universe=? AND taxon=?",
                    (universe, taxon),
                ).fetchone()[0]
                declared_groups = obj(row["primary_taxon_group_counts"], "group taxon counts")
                declared_occurrences = obj(
                    row["primary_taxon_occurrence_counts"], "occurrence taxon counts"
                )
                declared_group = (
                    integer(declared_groups[taxon], taxon) if taxon in declared_groups else 0
                )
                declared_occurrence = (
                    integer(declared_occurrences[taxon], taxon)
                    if taxon in declared_occurrences
                    else 0
                )
                require(observed_group == declared_group, "primary group taxon count mismatch")
                require(
                    observed_occurrence == declared_occurrence,
                    "primary occurrence taxon count mismatch",
                )
        legacy_units = connection.execute(
            "SELECT COUNT(*) FROM units WHERE universe='LEGACY_REPEAT_OCCURRENCE'"
        ).fetchone()[0]
        duplicate_rows = connection.execute(
            "SELECT COUNT(*) FROM retained WHERE container='r11a-v2-duplicate-observations.ndjson'"
        ).fetchone()[0]
        require(legacy_units == duplicate_rows, "legacy occurrence and duplicate row counts differ")
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate one exact R11A V2 artifact")
    parser.add_argument("artifact", type=Path)
    arguments = parser.parse_args(argv)
    validate_artifact(arguments.artifact, DEFAULT_LIMITS)
    validate_science(arguments.artifact)
    print("R11A_V2_EXECUTION_ARTIFACT_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
