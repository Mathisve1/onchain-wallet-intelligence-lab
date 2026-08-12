from __future__ import annotations

import dataclasses
import sqlite3
from pathlib import Path

from .canonical import FrozenObject, NumberToken, strict_json_loads
from .storage_r7 import MeteredSQLite, WorkspaceMeter

_JOIN_DB_MAX_BYTES = 512_000_000
_BATCH_ROWS = 512


class JoinBoundaryError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True, slots=True)
class JoinValidationResult:
    unit_count: int
    proof_count: int
    proof_reference_count: int
    retained_row_reference_count: int
    all_unit_ids_unique: bool
    all_proof_ids_unique: bool
    all_nonnull_proof_references_resolve_exactly_once: bool
    all_retained_rows_reference_exactly_one_unit: bool
    all_referenced_projections_are_byte_equal: bool
    all_retained_row_counts_match_unit_occurrence_counts: bool


def _projection_occurrence_count(projection: bytes) -> int:
    value = strict_json_loads(projection)
    if not isinstance(value, FrozenObject):
        raise JoinBoundaryError("taxonomy unit projection must be a canonical object")
    count = value["occurrence_count"]
    if not isinstance(count, NumberToken) or not count.is_integer_token:
        raise JoinBoundaryError("taxonomy unit projection occurrence count is not integer")
    observed = int(count.token, 10)
    if observed <= 0:
        raise JoinBoundaryError("taxonomy unit occurrence count must be positive")
    return observed


class DiskJoinLedger:
    """Exact disk-backed IDs, foreign keys, byte projections and multiplicities."""

    def __init__(self, meter: WorkspaceMeter) -> None:
        self.database = MeteredSQLite(
            meter.root / "taxonomy-joins.sqlite",
            meter,
            _JOIN_DB_MAX_BYTES,
            "taxonomy exact join ledger",
        )
        with self.database.transaction("create taxonomy join ledger") as connection:
            connection.executescript(
                """
                CREATE TABLE units(
                  unit_id TEXT PRIMARY KEY,
                  universe TEXT NOT NULL,
                  occurrence_count INTEGER NOT NULL CHECK(occurrence_count > 0),
                  projection BLOB NOT NULL
                );
                CREATE TABLE proofs(
                  proof_id TEXT PRIMARY KEY,
                  proof_type TEXT NOT NULL,
                  projection BLOB NOT NULL
                );
                CREATE TABLE refs(
                  unit_id TEXT NOT NULL,
                  proof_id TEXT NOT NULL,
                  proof_type TEXT NOT NULL,
                  unit_projection BLOB NOT NULL,
                  proof_projection BLOB NOT NULL,
                  UNIQUE(unit_id,proof_id,proof_type)
                );
                CREATE TABLE retained_rows(
                  row_id TEXT PRIMARY KEY,
                  unit_id TEXT NOT NULL,
                  unit_projection BLOB NOT NULL
                );
                CREATE INDEX retained_rows_by_unit ON retained_rows(unit_id);
                """
            )
        self._units: list[tuple[object, ...]] = []
        self._proofs: list[tuple[object, ...]] = []
        self._refs: list[tuple[object, ...]] = []
        self._rows: list[tuple[object, ...]] = []
        self._closed = False

    def _require_open(self) -> None:
        if self._closed:
            raise JoinBoundaryError("taxonomy join ledger is closed")

    def _flush(self) -> None:
        self._require_open()
        if not any((self._units, self._proofs, self._refs, self._rows)):
            return
        try:
            with self.database.transaction("flush taxonomy join rows") as connection:
                connection.executemany(
                    "INSERT INTO units VALUES(?,?,?,?)",
                    self._units,
                )
                connection.executemany(
                    "INSERT INTO proofs VALUES(?,?,?)",
                    self._proofs,
                )
                connection.executemany(
                    "INSERT INTO refs VALUES(?,?,?,?,?)",
                    self._refs,
                )
                connection.executemany(
                    "INSERT INTO retained_rows VALUES(?,?,?)",
                    self._rows,
                )
        except sqlite3.IntegrityError as exc:
            raise JoinBoundaryError(
                "duplicate unit, proof, reference, retained row, or invalid occurrence count"
            ) from exc
        self._units.clear()
        self._proofs.clear()
        self._refs.clear()
        self._rows.clear()

    def _maybe_flush(self) -> None:
        if sum(map(len, (self._units, self._proofs, self._refs, self._rows))) >= _BATCH_ROWS:
            self._flush()

    def add_unit(
        self,
        unit_id: str,
        universe: str,
        occurrence_count: int | bytes,
        projection: bytes | None = None,
    ) -> None:
        self._require_open()
        if projection is None:
            if not isinstance(occurrence_count, bytes):
                raise JoinBoundaryError("three-argument add_unit requires projection bytes")
            projection = occurrence_count
            normalized_count = _projection_occurrence_count(projection)
        else:
            if type(occurrence_count) is not int:
                raise JoinBoundaryError("taxonomy unit occurrence count must be exact integer")
            normalized_count = occurrence_count
        if not unit_id or not universe or normalized_count <= 0 or not projection:
            raise JoinBoundaryError("invalid taxonomy unit evidence")
        if _projection_occurrence_count(projection) != normalized_count:
            raise JoinBoundaryError("unit occurrence count differs from canonical projection")
        self._units.append(
            (unit_id, universe, normalized_count, sqlite3.Binary(projection))
        )
        self._maybe_flush()

    def add_proof(self, proof_id: str, proof_type: str, projection: bytes) -> None:
        self._require_open()
        if not proof_id or not proof_type or not projection:
            raise JoinBoundaryError("invalid taxonomy proof evidence")
        self._proofs.append((proof_id, proof_type, sqlite3.Binary(projection)))
        self._maybe_flush()

    def add_reference(
        self,
        unit_id: str,
        proof_id: str,
        proof_type: str,
        unit_projection: bytes,
        proof_projection: bytes,
    ) -> None:
        self._require_open()
        if not all((unit_id, proof_id, proof_type, unit_projection, proof_projection)):
            raise JoinBoundaryError("invalid taxonomy proof reference")
        self._refs.append(
            (
                unit_id,
                proof_id,
                proof_type,
                sqlite3.Binary(unit_projection),
                sqlite3.Binary(proof_projection),
            )
        )
        self._maybe_flush()

    def add_retained_row(
        self,
        row_id: str,
        unit_id: str,
        unit_projection: bytes,
    ) -> None:
        self._require_open()
        if not row_id or not unit_id or not unit_projection:
            raise JoinBoundaryError("invalid retained taxonomy row reference")
        self._rows.append((row_id, unit_id, sqlite3.Binary(unit_projection)))
        self._maybe_flush()

    def validate(self) -> JoinValidationResult:
        self._flush()
        connection = self.database.connection
        unit_count = int(connection.execute("SELECT COUNT(*) FROM units").fetchone()[0])
        proof_count = int(connection.execute("SELECT COUNT(*) FROM proofs").fetchone()[0])
        reference_count = int(connection.execute("SELECT COUNT(*) FROM refs").fetchone()[0])
        row_count = int(connection.execute("SELECT COUNT(*) FROM retained_rows").fetchone()[0])
        dangling_refs = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM refs r
                LEFT JOIN units u ON u.unit_id=r.unit_id
                LEFT JOIN proofs p ON p.proof_id=r.proof_id AND p.proof_type=r.proof_type
                WHERE u.unit_id IS NULL OR p.proof_id IS NULL
                """
            ).fetchone()[0]
        )
        projection_ref_mismatches = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM refs r
                JOIN units u ON u.unit_id=r.unit_id
                JOIN proofs p ON p.proof_id=r.proof_id AND p.proof_type=r.proof_type
                WHERE r.unit_projection<>u.projection OR r.proof_projection<>p.projection
                """
            ).fetchone()[0]
        )
        dangling_rows = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM retained_rows r
                LEFT JOIN units u ON u.unit_id=r.unit_id
                WHERE u.unit_id IS NULL
                """
            ).fetchone()[0]
        )
        projection_row_mismatches = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM retained_rows r
                JOIN units u ON u.unit_id=r.unit_id
                WHERE r.unit_projection<>u.projection
                """
            ).fetchone()[0]
        )
        multiplicity_mismatches = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM units u
                LEFT JOIN (
                  SELECT unit_id,COUNT(*) AS retained_count
                  FROM retained_rows
                  GROUP BY unit_id
                ) r ON r.unit_id=u.unit_id
                WHERE COALESCE(r.retained_count,0)<>u.occurrence_count
                """
            ).fetchone()[0]
        )
        return JoinValidationResult(
            unit_count=unit_count,
            proof_count=proof_count,
            proof_reference_count=reference_count,
            retained_row_reference_count=row_count,
            all_unit_ids_unique=True,
            all_proof_ids_unique=True,
            all_nonnull_proof_references_resolve_exactly_once=dangling_refs == 0,
            all_retained_rows_reference_exactly_one_unit=dangling_rows == 0,
            all_referenced_projections_are_byte_equal=(
                projection_ref_mismatches == 0 and projection_row_mismatches == 0
            ),
            all_retained_row_counts_match_unit_occurrence_counts=(
                multiplicity_mismatches == 0
            ),
        )

    def close_delete(self) -> None:
        if self._closed:
            return
        self._flush()
        self.database.close_delete()
        self._closed = True

    def abort(self) -> None:
        self.close_delete()
