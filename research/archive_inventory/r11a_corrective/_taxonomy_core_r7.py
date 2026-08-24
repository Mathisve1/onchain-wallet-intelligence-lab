from __future__ import annotations

import dataclasses
import enum
import hashlib
import sqlite3
import struct
import sys
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Protocol

from .artifact_schema import (
    AUTHORITATIVE_UNIT_UNIVERSES,
    DIAGNOSTIC_ID,
    TAXA,
)
from .canonical import FrozenObject, NumberToken, canonical_json_bytes, strict_json_loads
from .identity import frame
from .join_r7 import DiskJoinLedger, JoinValidationResult
from .locator_order import raw_locator_order_key
from .materialize import MaterializedIndexes
from .storage_r7 import (
    CleanupBoundaryError,
    MeteredSQLite,
    WorkspaceMeter,
    cleanup_checked_iterator,
    external_sort_partition,
    iter_equality_group_spools,
    iter_frames,
)

_SCRATCH_DB_MAX_BYTES = 256_000_000
_PROOF_DB_MAX_BYTES = 256_000_000


class TaxonomyBoundaryError(RuntimeError):
    pass


class TaxonomyCleanupError(TaxonomyBoundaryError, CleanupBoundaryError):
    """A taxonomy cleanup failure may never become terminal evidence."""


class Taxon(str, enum.Enum):
    TID_SCOPE_FALSE_POSITIVE = "TID_SCOPE_FALSE_POSITIVE"
    EXPECTED_COUNTERPARTY_PAIR = "EXPECTED_COUNTERPARTY_PAIR"
    EXACT_BLOCK_REPLAY_ACROSS_OBJECTS = "EXACT_BLOCK_REPLAY_ACROSS_OBJECTS"
    EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY = (
        "EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY"
    )
    CONFLICTING_BLOCK_REPLAY = "CONFLICTING_BLOCK_REPLAY"
    CONFLICTING_USER_FILL = "CONFLICTING_USER_FILL"
    INTRA_BLOCK_REPEAT = "INTRA_BLOCK_REPEAT"
    TID_SCHEMA_VIOLATION = "TID_SCHEMA_VIOLATION"
    UNCLASSIFIABLE = "UNCLASSIFIABLE"


class UnitUniverse(str, enum.Enum):
    LEGACY_REPEAT_OCCURRENCE = "LEGACY_REPEAT_OCCURRENCE"
    ARCHIVE_BLOCK_NUMBER_GROUP = "ARCHIVE_BLOCK_NUMBER_GROUP"
    PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE = (
        "PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE"
    )
    REPEAT_INTERSECTING_TID_SCHEMA_VIOLATION = (
        "REPEAT_INTERSECTING_TID_SCHEMA_VIOLATION"
    )
    REPEAT_INTERSECTING_COIN_SCHEMA_VIOLATION = (
        "REPEAT_INTERSECTING_COIN_SCHEMA_VIOLATION"
    )
    REPEAT_INTERSECTING_WALLET_SCHEMA_VIOLATION = (
        "REPEAT_INTERSECTING_WALLET_SCHEMA_VIOLATION"
    )


if tuple(value.value for value in UnitUniverse) != AUTHORITATIVE_UNIT_UNIVERSES:
    raise RuntimeError("authoritative unit universe declaration drift")
if tuple(value.value for value in Taxon) != TAXA:
    raise RuntimeError("taxon declaration drift")


class EvidenceEmitter(Protocol):
    def emit(self, container: str, row: Mapping[str, object]) -> None: ...


@dataclasses.dataclass(slots=True)
class UniverseConservation:
    group_count: int = 0
    occurrence_count: int = 0
    group_taxa: Counter[str] = dataclasses.field(default_factory=Counter)
    occurrence_taxa: Counter[str] = dataclasses.field(default_factory=Counter)

    def add(self, taxon: Taxon, occurrence_count: int) -> None:
        if occurrence_count <= 0:
            raise TaxonomyBoundaryError("taxonomy occurrence count must be positive")
        self.group_count += 1
        self.occurrence_count += occurrence_count
        self.group_taxa[taxon.value] += 1
        self.occurrence_taxa[taxon.value] += occurrence_count

    def mapping(self, universe: UnitUniverse) -> dict[str, object]:
        if sum(self.group_taxa.values()) != self.group_count:
            raise TaxonomyBoundaryError("primary group taxonomy does not conserve units")
        if sum(self.occurrence_taxa.values()) != self.occurrence_count:
            raise TaxonomyBoundaryError("primary occurrence taxonomy does not conserve units")
        return {
            "unit_universe": universe.value,
            "group_count": self.group_count,
            "occurrence_count": self.occurrence_count,
            "primary_taxon_group_counts": {
                taxon: self.group_taxa[taxon] for taxon in TAXA
            },
            "primary_taxon_occurrence_counts": {
                taxon: self.occurrence_taxa[taxon] for taxon in TAXA
            },
            "unclassifiable_group_count": self.group_taxa[Taxon.UNCLASSIFIABLE.value],
            "unclassifiable_occurrence_count": self.occurrence_taxa[
                Taxon.UNCLASSIFIABLE.value
            ],
        }


@dataclasses.dataclass(frozen=True, slots=True)
class ProofReference:
    proof_type: str
    proof_id: str
    proof_projection: bytes


@dataclasses.dataclass(frozen=True, slots=True)
class TaxonomyResult:
    universe_rows: tuple[dict[str, object], ...]
    secondary_reducer_rows: tuple[dict[str, object], ...]
    join_validation: JoinValidationResult
    repeated_block_group_count: int
    repeated_block_observation_count: int
    legacy_repeat_group_count: int
    legacy_repeat_observation_count: int
    legacy_repeat_occurrence_count: int
    valid_tid_legacy_repeat_occurrence_count: int
    invalid_tid_legacy_repeat_occurrence_count: int
    supporting_taxon_counts: dict[str, int]
    exact_three_utc_days: bool

    @property
    def unclassifiable_group_count(self) -> int:
        return sum(int(row["unclassifiable_group_count"]) for row in self.universe_rows)

    @property
    def unclassifiable_occurrence_count(self) -> int:
        return sum(int(row["unclassifiable_occurrence_count"]) for row in self.universe_rows)


def _object(value: object, label: str) -> FrozenObject:
    if not isinstance(value, FrozenObject):
        raise TaxonomyBoundaryError(f"{label} must be object")
    return value


def _array(value: object, label: str) -> tuple[object, ...]:
    if not isinstance(value, tuple):
        raise TaxonomyBoundaryError(f"{label} must be array")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise TaxonomyBoundaryError(f"{label} must be text")
    return value


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _integer(value: object, label: str) -> int:
    if isinstance(value, NumberToken) and value.is_integer_token:
        return int(value.token, 10)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise TaxonomyBoundaryError(f"{label} must be exact integer")


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise TaxonomyBoundaryError(f"{label} must be boolean")
    return value


def _rows(path: Path, meter: WorkspaceMeter, phase: str) -> Iterator[FrozenObject]:
    return meter.own_iterator(
        _iter_rows(path, meter, phase),
        label="materialized-row stream",
    )


def _iter_rows(
    path: Path,
    meter: WorkspaceMeter,
    phase: str,
) -> Iterator[FrozenObject]:
    reader = iter_frames(path, runtime_guard=meter.runtime_guard, phase=phase)
    with cleanup_checked_iterator(reader, label="materialized frame reader"):
        for payload in reader:
            yield _object(strict_json_loads(payload), "materialized row")


def _raw_locator(row: FrozenObject) -> tuple[int, str, int, int | None]:
    locator = _object(row["raw_locator"], "raw locator")
    object_ordinal = _integer(row["object_ordinal_zero_based"], "object ordinal")
    object_key = _text(locator["object_key"], "object key")
    record_ordinal = _integer(
        locator["decompressed_record_ordinal_zero_based"], "record ordinal"
    )
    event_ordinal = (
        _integer(locator["event_ordinal_zero_based"], "event ordinal")
        if "event_ordinal_zero_based" in locator
        else None
    )
    return object_ordinal, object_key, record_ordinal, event_ordinal


def _unit_projection(
    universe: UnitUniverse,
    key_projection: Mapping[str, object],
    taxon: Taxon,
    occurrence_count: int,
) -> bytes:
    return canonical_json_bytes(
        {
            "diagnostic_id": DIAGNOSTIC_ID,
            "unit_universe": universe.value,
            "key_projection": key_projection,
            "primary_taxon": taxon.value,
            "occurrence_count": occurrence_count,
        },
        final_newline=False,
    )


def _emit_unit(
    *,
    emitter: EvidenceEmitter,
    joins: DiskJoinLedger,
    conservation: UniverseConservation,
    universe: UnitUniverse,
    key_projection: Mapping[str, object],
    taxon: Taxon,
    occurrence_count: int,
    proof_references: Sequence[ProofReference] = (),
    supporting_taxa: Sequence[Taxon] = (),
) -> tuple[str, bytes]:
    projection = _unit_projection(universe, key_projection, taxon, occurrence_count)
    unit_id = hashlib.sha256(frame(universe.value.encode("ascii"), projection)).hexdigest()
    joins.add_unit(unit_id, universe.value, projection)
    conservation.add(taxon, occurrence_count)
    emitter.emit(
        "r11a-v2-taxonomy-units.ndjson",
        {
            "record_type": "R11A_V2_TAXONOMY_UNIT",
            "diagnostic_id": DIAGNOSTIC_ID,
            "taxonomy_unit_id": unit_id,
            "unit_universe": universe.value,
            "unit_projection_sha256": hashlib.sha256(projection).hexdigest(),
            "key_projection": key_projection,
            "primary_taxon": taxon.value,
            "supporting_taxa": [value.value for value in supporting_taxa],
            "occurrence_count": occurrence_count,
            "proof_references": [
                {
                    "proof_type": reference.proof_type,
                    "proof_id": reference.proof_id,
                    "proof_projection_sha256": hashlib.sha256(
                        reference.proof_projection
                    ).hexdigest(),
                }
                for reference in proof_references
            ],
        },
    )
    for reference in proof_references:
        joins.add_reference(
            unit_id,
            reference.proof_id,
            reference.proof_type,
            projection,
            reference.proof_projection,
        )
    return unit_id, projection


def _emit_referenced_row(
    *,
    emitter: EvidenceEmitter,
    joins: DiskJoinLedger,
    container: str,
    unit_id: str,
    unit_projection: bytes,
    row: Mapping[str, object],
) -> None:
    mapping = {
        **row,
        "diagnostic_id": DIAGNOSTIC_ID,
        "taxonomy_unit_id": unit_id,
        "unit_projection_sha256": hashlib.sha256(unit_projection).hexdigest(),
    }
    row_id = hashlib.sha256(canonical_json_bytes(mapping, final_newline=False)).hexdigest()
    mapping["retained_row_id"] = row_id
    joins.add_retained_row(row_id, unit_id, unit_projection)
    emitter.emit(container, mapping)


def _proof(
    *,
    proof_type: str,
    projection_mapping: Mapping[str, object],
    emitter: EvidenceEmitter,
    joins: DiskJoinLedger,
    container: str,
) -> ProofReference:
    projection = canonical_json_bytes(projection_mapping, final_newline=False)
    proof_id = hashlib.sha256(frame(proof_type.encode("ascii"), projection)).hexdigest()
    joins.add_proof(proof_id, proof_type, projection)
    emitter.emit(
        container,
        {
            "record_type": proof_type,
            "diagnostic_id": DIAGNOSTIC_ID,
            "proof_id": proof_id,
            "proof_projection_sha256": hashlib.sha256(projection).hexdigest(),
            "projection": projection_mapping,
        },
    )
    return ProofReference(proof_type, proof_id, projection)


class BlockProofIndex:
    def __init__(self, meter: WorkspaceMeter) -> None:
        self.database = MeteredSQLite(
            meter.root / "block-proof-index.sqlite",
            meter,
            _PROOF_DB_MAX_BYTES,
            "block proof index",
        )
        with self.database.initializing_transaction(
            "create block proof index"
        ) as connection:
            connection.executescript(
                """
                CREATE TABLE groups(
                  block_number INTEGER PRIMARY KEY,
                  taxon TEXT NOT NULL,
                  proof_id TEXT,
                  proof_projection BLOB
                );
                CREATE TABLE locators(
                  raw_block_key BLOB PRIMARY KEY,
                  block_number INTEGER NOT NULL
                );
                """
            )

    def add_group(
        self,
        *,
        block_number: int,
        taxon: Taxon,
        proof: ProofReference | None,
        raw_block_keys: Sequence[bytes],
    ) -> None:
        try:
            with self.database.transaction("record block proof group") as connection:
                connection.execute(
                    "INSERT INTO groups VALUES(?,?,?,?)",
                    (
                        block_number,
                        taxon.value,
                        None if proof is None else proof.proof_id,
                        None if proof is None else sqlite3.Binary(proof.proof_projection),
                    ),
                )
                connection.executemany(
                    "INSERT INTO locators VALUES(?,?)",
                    ((sqlite3.Binary(value), block_number) for value in raw_block_keys),
                )
        except sqlite3.IntegrityError as exc:
            raise TaxonomyBoundaryError("duplicate block group or raw block locator") from exc

    def lookup(
        self, block_number: int, raw_block_key: bytes
    ) -> tuple[str | None, ProofReference | None, bool]:
        group = self.database.connection.execute(
            "SELECT taxon,proof_id,proof_projection FROM groups WHERE block_number=?",
            (block_number,),
        ).fetchone()
        if group is None:
            return None, None, True
        locator = self.database.connection.execute(
            "SELECT 1 FROM locators WHERE raw_block_key=? AND block_number=?",
            (sqlite3.Binary(raw_block_key), block_number),
        ).fetchone()
        if locator is None:
            return str(group[0]), None, False
        proof = None
        if group[1] is not None:
            proof = ProofReference(
                "R11A_V2_EXACT_BLOCK_REPLAY_PROOF",
                str(group[1]),
                bytes(group[2]),
            )
        return str(group[0]), proof, True

    def close_delete(self) -> None:
        self.database.close_delete()


class ProtocolProofIndex:
    def __init__(self, meter: WorkspaceMeter) -> None:
        self.database = MeteredSQLite(
            meter.root / "protocol-proof-index.sqlite",
            meter,
            _PROOF_DB_MAX_BYTES,
            "protocol proof index",
        )
        with self.database.initializing_transaction(
            "create protocol proof index"
        ) as connection:
            connection.execute(
                "CREATE TABLE groups(group_key BLOB PRIMARY KEY,taxon TEXT NOT NULL,proof_id TEXT,proof_projection BLOB)"
            )

    def add(
        self,
        group_key: bytes,
        taxon: Taxon,
        proof: ProofReference | None,
    ) -> None:
        try:
            with self.database.transaction("record protocol proof") as connection:
                connection.execute(
                    "INSERT INTO groups VALUES(?,?,?,?)",
                    (
                        sqlite3.Binary(group_key),
                        taxon.value,
                        None if proof is None else proof.proof_id,
                        None if proof is None else sqlite3.Binary(proof.proof_projection),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise TaxonomyBoundaryError("duplicate protocol group") from exc

    def lookup(self, group_key: bytes) -> tuple[str | None, ProofReference | None]:
        row = self.database.connection.execute(
            "SELECT taxon,proof_id,proof_projection FROM groups WHERE group_key=?",
            (sqlite3.Binary(group_key),),
        ).fetchone()
        if row is None:
            return None, None
        proof = None
        if row[1] is not None:
            proof = ProofReference(
                "R11A_V2_EXPECTED_COUNTERPARTY_PAIR_PROOF",
                str(row[1]),
                bytes(row[2]),
            )
        return str(row[0]), proof

    def close_delete(self) -> None:
        self.database.close_delete()


class GroupScratch:
    """One reusable disk-backed equality-group state; no unbounded Python sets."""

    def __init__(self, meter: WorkspaceMeter) -> None:
        self._owned_iterators: list[tuple[str, Iterator[sqlite3.Row]]] = []
        self._cleanup_failure: TaxonomyCleanupError | None = None
        self.database = MeteredSQLite(
            meter.root / "taxonomy-group-scratch.sqlite",
            meter,
            _SCRATCH_DB_MAX_BYTES,
            "taxonomy group scratch",
        )
        with self.database.initializing_transaction(
            "create taxonomy group scratch"
        ) as connection:
            connection.executescript(
                """
                CREATE TABLE events(
                  sequence INTEGER PRIMARY KEY,
                  row_json BLOB NOT NULL,
                  object_ordinal INTEGER NOT NULL,
                  object_key TEXT NOT NULL,
                  object_key_bytes BLOB NOT NULL,
                  compressed_sha256 BLOB NOT NULL,
                  record_ordinal INTEGER NOT NULL,
                  event_ordinal INTEGER NOT NULL,
                  raw_block_key BLOB NOT NULL,
                  block_number INTEGER NOT NULL,
                  protocol_key BLOB,
                  wallet_fill_key BLOB,
                  wallet TEXT,
                  coin TEXT,
                  tid INTEGER,
                  side TEXT,
                  event_hash TEXT NOT NULL,
                  tid_valid INTEGER NOT NULL,
                  coin_valid INTEGER NOT NULL,
                  wallet_valid INTEGER NOT NULL,
                  block_taxon TEXT,
                  block_proof_id TEXT,
                  block_proof_projection BLOB,
                  block_locator_resolved INTEGER NOT NULL DEFAULT 1
                );
                CREATE INDEX event_order ON events(
                  object_key_bytes,compressed_sha256,record_ordinal,event_ordinal
                );
                CREATE INDEX wallet_fill ON events(wallet_fill_key);
                CREATE INDEX raw_block ON events(raw_block_key);
                """
            )

    def reset(self) -> None:
        with self.database.transaction("reset taxonomy group scratch") as connection:
            connection.execute("DELETE FROM events")

    def load_events(
        self,
        path: Path,
        meter: WorkspaceMeter,
        block_proofs: BlockProofIndex | None = None,
    ) -> int:
        self.reset()
        batch: list[tuple[object, ...]] = []
        sequence = 0
        for row in _rows(path, meter, "load equality group scratch"):
            object_ordinal, object_key, record_ordinal, event_ordinal = _raw_locator(row)
            if event_ordinal is None:
                raise TaxonomyBoundaryError("event group row lacks event ordinal")
            locator = _object(row["raw_locator"], "raw locator")
            locator_key = raw_locator_order_key(
                object_key=object_key,
                verified_compressed_sha256=_text(
                    locator["verified_compressed_sha256"], "compressed SHA"
                ),
                record_ordinal_zero_based=record_ordinal,
                event_ordinal_zero_based=event_ordinal,
            )
            raw_block_key = bytes.fromhex(_text(row["raw_block_key_hex"], "raw block key"))
            block_taxon: str | None = None
            block_proof_id: str | None = None
            block_projection: bytes | None = None
            locator_resolved = True
            if block_proofs is not None:
                block_taxon, proof, locator_resolved = block_proofs.lookup(
                    _integer(row["block_number"], "block number"),
                    raw_block_key,
                )
                if proof is not None:
                    block_proof_id = proof.proof_id
                    block_projection = proof.proof_projection
            protocol_text = _optional_text(row["protocol_trade_key_hex"])
            wallet_fill_text = _optional_text(row["wallet_fill_key_hex"])
            batch.append(
                (
                    sequence,
                    sqlite3.Binary(canonical_json_bytes(row, final_newline=False)),
                    object_ordinal,
                    object_key,
                    sqlite3.Binary(locator_key[0]),
                    sqlite3.Binary(locator_key[1]),
                    record_ordinal,
                    event_ordinal,
                    sqlite3.Binary(raw_block_key),
                    _integer(row["block_number"], "block number"),
                    None if protocol_text is None else sqlite3.Binary(bytes.fromhex(protocol_text)),
                    None if wallet_fill_text is None else sqlite3.Binary(bytes.fromhex(wallet_fill_text)),
                    _optional_text(row["canonical_wallet"]),
                    _optional_text(row["exact_raw_coin_string"]),
                    None if row["validated_tid"] is None else _integer(row["validated_tid"], "tid"),
                    _optional_text(row["exact_raw_side_string"]),
                    _text(row["full_event_sha256"], "event hash"),
                    int(_boolean(row["tid_schema_valid"], "tid valid")),
                    int(_boolean(row["coin_schema_valid"], "coin valid")),
                    int(_boolean(row["wallet_schema_valid"], "wallet valid")),
                    block_taxon,
                    block_proof_id,
                    None if block_projection is None else sqlite3.Binary(block_projection),
                    int(locator_resolved),
                )
            )
            sequence += 1
            if len(batch) >= 256:
                self._insert(batch)
                batch.clear()
        self._insert(batch)
        return sequence

    def _insert(self, rows: Sequence[tuple[object, ...]]) -> None:
        if not rows:
            return
        with self.database.transaction("insert taxonomy group rows") as connection:
            connection.executemany(
                "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )

    def iter_ordered(self) -> Iterator[sqlite3.Row]:
        if self._cleanup_failure is not None:
            raise self._cleanup_failure
        owned: Iterator[sqlite3.Row]

        def _owned() -> Iterator[sqlite3.Row]:
            try:
                with cleanup_checked_iterator(
                    self._iter_ordered(),
                    label="taxonomy group SQLite cursor",
                ) as rows:
                    for row in rows:
                        yield row
            finally:
                self._owned_iterators = [
                    entry for entry in self._owned_iterators if entry[1] is not owned
                ]

        owned = _owned()
        self._owned_iterators.append(("taxonomy group SQLite cursor", owned))
        return owned

    def _iter_ordered(self) -> Iterator[sqlite3.Row]:
        self.database.connection.row_factory = sqlite3.Row
        cursor: sqlite3.Cursor | None = None
        try:
            cursor = self.database.connection.execute(
                "SELECT * FROM events ORDER BY "
                "object_key_bytes,compressed_sha256,record_ordinal,event_ordinal"
            )
            for row in cursor:
                yield row
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except BaseException as exc:
                    raise TaxonomyCleanupError(
                        "taxonomy group SQLite cursor cleanup failed"
                    ) from exc

    def close_delete(self) -> None:
        if self._cleanup_failure is not None:
            raise self._cleanup_failure
        original_failure = sys.exception()
        owned = self._owned_iterators
        self._owned_iterators = []
        errors: list[BaseException] = []
        for _, iterator in reversed(owned):
            try:
                iterator.close()
            except BaseException as exc:
                errors.append(exc)
        try:
            self.database.close_delete()
        except BaseException as exc:
            errors.append(exc)
        if errors:
            tail = original_failure
            for error in reversed(errors):
                if tail is not None and (
                    error.__context__ is None
                    or isinstance(error.__context__, GeneratorExit)
                ):
                    error.__context__ = tail
                tail = error
            failure = TaxonomyCleanupError("taxonomy group scratch cleanup failed")
            self._cleanup_failure = failure
            raise failure from errors[0]


def _sort_partitions(
    *,
    reducer_id: str,
    directory: Path,
    stats: tuple[tuple[int, int], ...],
    meter: WorkspaceMeter,
) -> Iterator[tuple[int, Path, dict[str, object]]]:
    for partition in range(256):
        source = directory / f"part-{partition:03d}.frames"
        source_records, source_logical = stats[partition]
        destination = meter.root / f"taxonomy-{reducer_id.lower()}-{partition:03d}.frames"
        temporary = meter.root / f"taxonomy-sort-{reducer_id.lower()}-{partition:03d}"
        evidence = external_sort_partition(
            source,
            destination,
            temporary,
            meter,
            source_record_count=source_records,
            source_logical_bytes=source_logical,
            maximum_source_bytes=source.stat().st_size,
        )
        yield partition, destination, {
            "record_type": "R11A_V2_SECONDARY_REDUCER_CONSERVATION",
            "reducer_id": reducer_id,
            "partition_ordinal_zero_based": partition,
            "source_record_count": source_records,
            "source_logical_bytes": source_logical,
            "destination_record_count": evidence.output_records,
            "destination_logical_bytes": evidence.output_logical_bytes,
            "exact_multiplicity": evidence.exact_multiplicity,
            "sorted_stream_sha256": evidence.sorted_stream_sha256,
        }


def _classify_blocks(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    joins: DiskJoinLedger,
    conservation: UniverseConservation,
    scratch: GroupScratch,
) -> tuple[BlockProofIndex, list[dict[str, object]], int, int]:
    index = BlockProofIndex(meter)
    reducer_rows: list[dict[str, object]] = []
    groups = 0
    observations = 0
    try:
        for partition, sorted_path, reducer_row in _sort_partitions(
            reducer_id="MATERIALIZED_BLOCK_NUMBER",
            directory=materialized.block_directory,
            stats=materialized.block_stats,
            meter=meter,
        ):
            reducer_rows.append(reducer_row)
            spool = meter.root / f"taxonomy-block-groups-{partition:03d}"
            for group in iter_equality_group_spools(
                sorted_path,
                spool,
                meter,
                maximum_group_spool_bytes=meter.limits.maximum_equality_group_spool_bytes,
            ):
                scratch.reset()
                block_rows: list[FrozenObject] = []
                for row in _rows(group.path, meter, "read block group"):
                    block_rows.append(row)
                    if len(block_rows) > meter.limits.maximum_repeated_observations_retained:
                        raise TaxonomyBoundaryError("block group exceeds retained observation cap")
                if len(block_rows) <= 1:
                    raise TaxonomyBoundaryError("materialized repeated block group is singleton")
                raw_keys = [
                    bytes.fromhex(_text(row["raw_block_key_hex"], "raw block key"))
                    for row in block_rows
                ]
                if len({value for value in raw_keys}) != len(raw_keys):
                    raise TaxonomyBoundaryError("duplicate raw block locator in block group")
                block_number = _integer(block_rows[0]["block_number"], "block number")
                if any(_integer(row["block_number"], "block number") != block_number for row in block_rows):
                    raise TaxonomyBoundaryError("block-number equality group drift")
                invariants = {
                    (
                        _text(row["exact_raw_block_time"], "block time"),
                        _integer(row["ordered_event_count"], "event count"),
                        _text(row["ordered_event_fingerprint_sha256"], "event fingerprint"),
                    )
                    for row in block_rows
                }
                source_objects = {_raw_locator(row)[1] for row in block_rows}
                if len(invariants) > 1:
                    taxon = Taxon.CONFLICTING_BLOCK_REPLAY
                elif len(source_objects) >= 2:
                    taxon = Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS
                else:
                    taxon = Taxon.UNCLASSIFIABLE
                ordered_locators = [
                    {
                        "object_ordinal_zero_based": _raw_locator(row)[0],
                        "object_key": _raw_locator(row)[1],
                        "record_ordinal_zero_based": _raw_locator(row)[2],
                        "raw_block_key_sha256": hashlib.sha256(raw_key).hexdigest(),
                    }
                    for row, raw_key in sorted(
                        zip(block_rows, raw_keys, strict=True),
                        key=lambda pair: raw_locator_order_key(
                            object_key=_raw_locator(pair[0])[1],
                            verified_compressed_sha256=_text(
                                _object(pair[0]["raw_locator"], "raw locator")[
                                    "verified_compressed_sha256"
                                ],
                                "compressed SHA",
                            ),
                            record_ordinal_zero_based=_raw_locator(pair[0])[2],
                            event_ordinal_zero_based=None,
                        ),
                    )
                ]
                locator_commitment = hashlib.sha256(
                    canonical_json_bytes(ordered_locators, final_newline=False)
                ).hexdigest()
                invariant = sorted(invariants)[0]
                proof = None
                if taxon is Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS:
                    proof = _proof(
                        proof_type="R11A_V2_EXACT_BLOCK_REPLAY_PROOF",
                        projection_mapping={
                            "block_number": block_number,
                            "raw_block_locator_count": len(raw_keys),
                            "distinct_source_object_count": len(source_objects),
                            "ordered_raw_locator_projection_sha256": locator_commitment,
                            "exact_raw_block_time": invariant[0],
                            "ordered_event_count": invariant[1],
                            "ordered_event_fingerprint_sha256": invariant[2],
                        },
                        emitter=emitter,
                        joins=joins,
                        container="r11a-v2-exact-block-replay-proofs.ndjson",
                    )
                key_projection = {
                    "block_number": block_number,
                    "raw_block_locator_count": len(raw_keys),
                    "ordered_raw_locator_projection_sha256": locator_commitment,
                }
                unit_id, unit_projection = _emit_unit(
                    emitter=emitter,
                    joins=joins,
                    conservation=conservation,
                    universe=UnitUniverse.ARCHIVE_BLOCK_NUMBER_GROUP,
                    key_projection=key_projection,
                    taxon=taxon,
                    occurrence_count=len(block_rows),
                    proof_references=() if proof is None else (proof,),
                )
                for row in block_rows:
                    _emit_referenced_row(
                        emitter=emitter,
                        joins=joins,
                        container="r11a-v2-block-overlap-matrix.ndjson",
                        unit_id=unit_id,
                        unit_projection=unit_projection,
                        row={
                            "record_type": "R11A_V2_BLOCK_OVERLAP_OBSERVATION",
                            "primary_taxon": taxon.value,
                            "block_number": row["block_number"],
                            "raw_locator": row["raw_locator"],
                            "raw_block_key_hex": row["raw_block_key_hex"],
                            "exact_raw_block_time": row["exact_raw_block_time"],
                            "ordered_event_count": row["ordered_event_count"],
                            "ordered_event_fingerprint_sha256": row[
                                "ordered_event_fingerprint_sha256"
                            ],
                            "raw_record_fingerprint_sha256": row[
                                "raw_record_fingerprint_sha256"
                            ],
                            "raw_record_value": row["raw_record_value"],
                        },
                    )
                index.add_group(
                    block_number=block_number,
                    taxon=taxon,
                    proof=proof,
                    raw_block_keys=raw_keys,
                )
                groups += 1
                observations += len(block_rows)
            meter.delete_file(sorted_path)
            meter.delete_file(materialized.block_directory / f"part-{partition:03d}.frames")
        meter.delete_empty_directory(materialized.block_directory)
        return index, reducer_rows, groups, observations
    except Exception:
        index.close_delete()
        raise


def _classify_protocol(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    joins: DiskJoinLedger,
    conservation: UniverseConservation,
    scratch: GroupScratch,
) -> tuple[ProtocolProofIndex, list[dict[str, object]], Counter[str]]:
    index = ProtocolProofIndex(meter)
    reducer_rows: list[dict[str, object]] = []
    supporting = Counter()
    try:
        for partition, sorted_path, reducer_row in _sort_partitions(
            reducer_id="PROTOCOL_MATCHED_TRADE_PER_RAW_BLOCK",
            directory=materialized.protocol_directory,
            stats=materialized.protocol_stats,
            meter=meter,
        ):
            reducer_rows.append(reducer_row)
            spool = meter.root / f"taxonomy-protocol-groups-{partition:03d}"
            for group in iter_equality_group_spools(
                sorted_path,
                spool,
                meter,
                maximum_group_spool_bytes=meter.limits.maximum_equality_group_spool_bytes,
            ):
                count = scratch.load_events(group.path, meter)
                connection = scratch.database.connection
                if count <= 0:
                    raise TaxonomyBoundaryError("empty protocol group")
                summary = connection.execute(
                    """
                    SELECT COUNT(*),COUNT(DISTINCT wallet),COUNT(DISTINCT side),
                           MIN(event_ordinal),MAX(event_ordinal),
                           COUNT(DISTINCT event_ordinal),COUNT(DISTINCT wallet_fill_key),
                           SUM(wallet IS NULL OR side IS NULL OR protocol_key IS NULL OR wallet_fill_key IS NULL)
                    FROM events
                    """
                ).fetchone()
                side_rows = tuple(
                    value[0]
                    for value in connection.execute(
                        "SELECT DISTINCT side FROM events WHERE side IS NOT NULL ORDER BY side"
                    )
                )
                expected = (
                    int(summary[0]) == 2
                    and int(summary[1]) == 2
                    and side_rows == ("A", "B")
                    and int(summary[4]) == int(summary[3]) + 1
                    and int(summary[5]) == 2
                    and int(summary[6]) == 2
                    and int(summary[7]) == 0
                )
                taxon = Taxon.EXPECTED_COUNTERPARTY_PAIR if expected else Taxon.UNCLASSIFIABLE
                ordered_projection = hashlib.sha256()
                raw_block_key: bytes | None = None
                protocol_key: bytes | None = None
                for row in scratch.iter_ordered():
                    current_block = bytes(row["raw_block_key"])
                    current_protocol = bytes(row["protocol_key"])
                    if raw_block_key is None:
                        raw_block_key = current_block
                        protocol_key = current_protocol
                    elif raw_block_key != current_block or protocol_key != current_protocol:
                        raise TaxonomyBoundaryError("protocol-per-block equality group drift")
                    source = _object(
                        strict_json_loads(bytes(row["row_json"])),
                        "protocol row",
                    )
                    ordered_projection.update(
                        canonical_json_bytes(
                            {
                                "raw_locator": source["raw_locator"],
                                "raw_block_key_hex": source["raw_block_key_hex"],
                                "block_number": source["block_number"],
                                "exact_raw_block_time": source[
                                    "exact_raw_block_time"
                                ],
                                "raw_wallet_value": source["raw_wallet_value"],
                                "raw_fill_value": source["raw_fill_value"],
                                "raw_record_fingerprint_sha256": source[
                                    "raw_record_fingerprint_sha256"
                                ],
                                "canonical_wallet": source["canonical_wallet"],
                                "exact_raw_coin_string": source[
                                    "exact_raw_coin_string"
                                ],
                                "validated_tid": source["validated_tid"],
                                "exact_raw_side_string": source[
                                    "exact_raw_side_string"
                                ],
                                "full_event_sha256": source[
                                    "full_event_sha256"
                                ],
                            },
                            final_newline=False,
                        )
                    )
                if raw_block_key is None or protocol_key is None:
                    raise TaxonomyBoundaryError("protocol group lacks exact key")
                proof = None
                if expected:
                    proof = _proof(
                        proof_type="R11A_V2_EXPECTED_COUNTERPARTY_PAIR_PROOF",
                        projection_mapping={
                            "raw_block_key_sha256": hashlib.sha256(raw_block_key).hexdigest(),
                            "protocol_trade_key_sha256": hashlib.sha256(protocol_key).hexdigest(),
                            "member_count": count,
                            "ordered_member_projection_sha256": ordered_projection.hexdigest(),
                        },
                        emitter=emitter,
                        joins=joins,
                        container="r11a-v2-expected-counterparty-pair-proofs.ndjson",
                    )
                    supporting[Taxon.EXPECTED_COUNTERPARTY_PAIR.value] += 1
                key_projection = {
                    "raw_block_key_sha256": hashlib.sha256(raw_block_key).hexdigest(),
                    "protocol_trade_key_sha256": hashlib.sha256(protocol_key).hexdigest(),
                }
                unit_id, unit_projection = _emit_unit(
                    emitter=emitter,
                    joins=joins,
                    conservation=conservation,
                    universe=UnitUniverse.PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE,
                    key_projection=key_projection,
                    taxon=taxon,
                    occurrence_count=count,
                    proof_references=() if proof is None else (proof,),
                )
                for row in scratch.iter_ordered():
                    source = _object(strict_json_loads(bytes(row["row_json"])), "protocol member")
                    _emit_referenced_row(
                        emitter=emitter,
                        joins=joins,
                        container="r11a-v2-protocol-trade-group-members.ndjson",
                        unit_id=unit_id,
                        unit_projection=unit_projection,
                        row={
                            "record_type": "R11A_V2_PROTOCOL_TRADE_GROUP_MEMBER",
                            "primary_taxon": taxon.value,
                            "raw_locator": source["raw_locator"],
                            "raw_block_key_hex": source["raw_block_key_hex"],
                            "block_number": source["block_number"],
                            "exact_raw_block_time": source["exact_raw_block_time"],
                            "raw_wallet_value": source["raw_wallet_value"],
                            "raw_fill_value": source["raw_fill_value"],
                            "raw_record_fingerprint_sha256": source[
                                "raw_record_fingerprint_sha256"
                            ],
                            "raw_record_value": (
                                source["raw_record_value"]
                                if source["raw_record_evidence_owner"]
                                == "PROTOCOL"
                                else None
                            ),
                            "canonical_wallet": source["canonical_wallet"],
                            "exact_raw_coin_string": source[
                                "exact_raw_coin_string"
                            ],
                            "validated_tid": source["validated_tid"],
                            "exact_raw_side_string": source["exact_raw_side_string"],
                            "full_event_sha256": source["full_event_sha256"],
                        },
                    )
                index.add(group.equality_key, taxon, proof)
            meter.delete_file(sorted_path)
            meter.delete_file(materialized.protocol_directory / f"part-{partition:03d}.frames")
        meter.delete_empty_directory(materialized.protocol_directory)
        return index, reducer_rows, supporting
    except Exception:
        index.close_delete()
        raise


def _schema_unit(
    *,
    universe: UnitUniverse,
    taxon: Taxon,
    source: FrozenObject,
    emitter: EvidenceEmitter,
    joins: DiskJoinLedger,
    conservation: UniverseConservation,
) -> None:
    key_projection = {
        "raw_locator": source["raw_locator"],
        "legacy_weak_key_sha256": hashlib.sha256(
            bytes.fromhex(_text(source["legacy_weak_key_hex"], "legacy weak key"))
        ).hexdigest(),
    }
    unit_id, unit_projection = _emit_unit(
        emitter=emitter,
        joins=joins,
        conservation=conservation,
        universe=universe,
        key_projection=key_projection,
        taxon=taxon,
        occurrence_count=1,
    )
    _emit_referenced_row(
        emitter=emitter,
        joins=joins,
        container="r11a-v2-repeat-intersecting-schema-evidence.ndjson",
        unit_id=unit_id,
        unit_projection=unit_projection,
        row={
            "record_type": "R11A_V2_REPEAT_INTERSECTING_SCHEMA_EVIDENCE",
            "primary_taxon": taxon.value,
            "schema_universe": universe.value,
            "raw_locator": source["raw_locator"],
            "raw_block_key_hex": source["raw_block_key_hex"],
            "raw_wallet_value": source["raw_wallet_value"],
            "raw_fill_value": source["raw_fill_value"],
            "raw_record_fingerprint_sha256": source[
                "raw_record_fingerprint_sha256"
            ],
            "raw_record_value": (
                source["raw_record_value"]
                if source["raw_record_evidence_owner"] == universe.value
                else None
            ),
            "block_number": source["block_number"],
            "exact_raw_local_time": source["exact_raw_local_time"],
            "exact_raw_block_time": source["exact_raw_block_time"],
            "canonical_wallet": source["canonical_wallet"],
            "exact_raw_coin_string": source["exact_raw_coin_string"],
            "validated_tid": source["validated_tid"],
            "exact_raw_side_string": source["exact_raw_side_string"],
            "full_event_sha256": source["full_event_sha256"],
            "fill_payload_sha256": source["fill_payload_sha256"],
            "schema_errors": source["schema_errors"],
            "selected_fill_payload": source["selected_fill_payload"],
        },
    )


def _wallet_fill_metrics(connection: sqlite3.Connection, wallet_fill_key: bytes) -> dict[str, object]:
    summary = connection.execute(
        """
        SELECT COUNT(*),COUNT(DISTINCT event_hash),COUNT(DISTINCT raw_block_key),
               SUM(block_taxon IS NOT NULL AND block_taxon<>?),
               SUM(block_taxon IS NOT NULL AND block_locator_resolved=0),
               COUNT(DISTINCT CASE WHEN block_proof_id IS NOT NULL THEN block_proof_id END),
               SUM(block_taxon=? AND block_proof_id IS NULL)
        FROM events WHERE wallet_fill_key=?
        """,
        (
            Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS.value,
            Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS.value,
            sqlite3.Binary(wallet_fill_key),
        ),
    ).fetchone()
    intra = connection.execute(
        """
        SELECT 1 FROM events WHERE wallet_fill_key=?
        GROUP BY raw_block_key,event_hash
        HAVING COUNT(DISTINCT event_ordinal)>1
        LIMIT 1
        """,
        (sqlite3.Binary(wallet_fill_key),),
    ).fetchone()
    proof_row = connection.execute(
        """
        SELECT block_proof_id,block_proof_projection FROM events
        WHERE wallet_fill_key=? AND block_proof_id IS NOT NULL
        GROUP BY block_proof_id,block_proof_projection
        ORDER BY block_proof_id LIMIT 1
        """,
        (sqlite3.Binary(wallet_fill_key),),
    ).fetchone()
    return {
        "count": int(summary[0]),
        "event_hash_count": int(summary[1]),
        "raw_block_count": int(summary[2]),
        "conflicting_or_unclassifiable_block_count": int(summary[3] or 0),
        "unresolved_block_locator_count": int(summary[4] or 0),
        "distinct_proof_count": int(summary[5]),
        "missing_exact_proof_count": int(summary[6] or 0),
        "intra_block_repeat": intra is not None,
        "proof": None if proof_row is None else ProofReference(
            "R11A_V2_EXACT_BLOCK_REPLAY_PROOF",
            str(proof_row[0]),
            bytes(proof_row[1]),
        ),
    }


def _classify_legacy(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    joins: DiskJoinLedger,
    conservations: Mapping[UnitUniverse, UniverseConservation],
    scratch: GroupScratch,
    block_proofs: BlockProofIndex,
    protocol_proofs: ProtocolProofIndex,
) -> tuple[list[dict[str, object]], int, int, int, int, Counter[str]]:
    reducer_rows: list[dict[str, object]] = []
    group_count = 0
    observation_count = 0
    valid_tid_repeat_occurrences = 0
    invalid_tid_repeat_occurrences = 0
    supporting = Counter()
    for partition, sorted_path, reducer_row in _sort_partitions(
        reducer_id="EXACT_LEGACY_WEAK_KEY",
        directory=materialized.weak_directory,
        stats=materialized.weak_stats,
        meter=meter,
    ):
        reducer_rows.append(reducer_row)
        spool = meter.root / f"taxonomy-legacy-groups-{partition:03d}"
        for group in iter_equality_group_spools(
            sorted_path,
            spool,
            meter,
            maximum_group_spool_bytes=meter.limits.maximum_equality_group_spool_bytes,
        ):
            count = scratch.load_events(group.path, meter, block_proofs)
            if count <= 1:
                raise TaxonomyBoundaryError("materialized legacy repeat group is singleton")
            group_count += 1
            observation_count += count
            connection = scratch.database.connection
            group_summary = connection.execute(
                """
                SELECT COUNT(DISTINCT protocol_key),
                       SUM(protocol_key IS NULL OR wallet_fill_key IS NULL OR tid_valid=0 OR coin_valid=0 OR wallet_valid=0),
                       SUM(block_taxon IN (?,?) OR block_locator_resolved=0)
                FROM events
                """,
                (
                    Taxon.CONFLICTING_BLOCK_REPLAY.value,
                    Taxon.UNCLASSIFIABLE.value,
                ),
            ).fetchone()
            conflicting_wallet_group = connection.execute(
                """
                SELECT 1 FROM events WHERE wallet_fill_key IS NOT NULL
                GROUP BY wallet_fill_key HAVING COUNT(DISTINCT event_hash)>1 LIMIT 1
                """
            ).fetchone() is not None
            scope_group_complete = (
                int(group_summary[0]) >= 2
                and int(group_summary[1] or 0) == 0
                and int(group_summary[2] or 0) == 0
                and not conflicting_wallet_group
            )
            first_sequence = int(
                connection.execute(
                    "SELECT sequence FROM events ORDER BY "
                    "object_key_bytes,compressed_sha256,record_ordinal,event_ordinal "
                    "LIMIT 1"
                ).fetchone()[0]
            )
            for row in scratch.iter_ordered():
                source = _object(strict_json_loads(bytes(row["row_json"])), "legacy row")
                tid_valid = bool(row["tid_valid"])
                coin_valid = bool(row["coin_valid"])
                wallet_valid = bool(row["wallet_valid"])
                if not tid_valid:
                    _schema_unit(
                        universe=UnitUniverse.REPEAT_INTERSECTING_TID_SCHEMA_VIOLATION,
                        taxon=Taxon.TID_SCHEMA_VIOLATION,
                        source=source,
                        emitter=emitter,
                        joins=joins,
                        conservation=conservations[
                            UnitUniverse.REPEAT_INTERSECTING_TID_SCHEMA_VIOLATION
                        ],
                    )
                if not coin_valid:
                    _schema_unit(
                        universe=UnitUniverse.REPEAT_INTERSECTING_COIN_SCHEMA_VIOLATION,
                        taxon=Taxon.UNCLASSIFIABLE,
                        source=source,
                        emitter=emitter,
                        joins=joins,
                        conservation=conservations[
                            UnitUniverse.REPEAT_INTERSECTING_COIN_SCHEMA_VIOLATION
                        ],
                    )
                if not wallet_valid:
                    _schema_unit(
                        universe=UnitUniverse.REPEAT_INTERSECTING_WALLET_SCHEMA_VIOLATION,
                        taxon=Taxon.UNCLASSIFIABLE,
                        source=source,
                        emitter=emitter,
                        joins=joins,
                        conservation=conservations[
                            UnitUniverse.REPEAT_INTERSECTING_WALLET_SCHEMA_VIOLATION
                        ],
                    )
                if int(row["sequence"]) == first_sequence:
                    continue
                if tid_valid:
                    valid_tid_repeat_occurrences += 1
                else:
                    invalid_tid_repeat_occurrences += 1
                proof_references: list[ProofReference] = []
                supporting_taxa: list[Taxon] = []
                protocol_key = None if row["protocol_key"] is None else bytes(row["protocol_key"])
                raw_block_key = bytes(row["raw_block_key"])
                if protocol_key is not None:
                    protocol_taxon, protocol_proof = protocol_proofs.lookup(
                        frame(raw_block_key, protocol_key)
                    )
                    if protocol_taxon == Taxon.EXPECTED_COUNTERPARTY_PAIR.value:
                        supporting_taxa.append(Taxon.EXPECTED_COUNTERPARTY_PAIR)
                        supporting[Taxon.EXPECTED_COUNTERPARTY_PAIR.value] += 1
                        if protocol_proof is not None:
                            proof_references.append(protocol_proof)
                wallet_fill_key = None if row["wallet_fill_key"] is None else bytes(row["wallet_fill_key"])
                metrics = None if wallet_fill_key is None else _wallet_fill_metrics(
                    connection, wallet_fill_key
                )
                if not tid_valid:
                    taxon = Taxon.TID_SCHEMA_VIOLATION
                elif not wallet_valid or not coin_valid or protocol_key is None or wallet_fill_key is None:
                    taxon = Taxon.UNCLASSIFIABLE
                elif metrics is None:
                    taxon = Taxon.UNCLASSIFIABLE
                elif int(metrics["event_hash_count"]) > 1:
                    taxon = Taxon.CONFLICTING_USER_FILL
                elif bool(metrics["intra_block_repeat"]):
                    taxon = Taxon.INTRA_BLOCK_REPEAT
                elif (
                    int(metrics["count"]) > 1
                    and int(metrics["event_hash_count"]) == 1
                    and int(metrics["raw_block_count"]) > 1
                    and int(metrics["conflicting_or_unclassifiable_block_count"]) == 0
                    and int(metrics["unresolved_block_locator_count"]) == 0
                    and int(metrics["distinct_proof_count"]) == 1
                    and int(metrics["missing_exact_proof_count"]) == 0
                    and metrics["proof"] is not None
                ):
                    taxon = Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY
                    proof_references.append(metrics["proof"])  # type: ignore[arg-type]
                elif scope_group_complete:
                    taxon = Taxon.TID_SCOPE_FALSE_POSITIVE
                else:
                    taxon = Taxon.UNCLASSIFIABLE
                key_projection = {
                    "legacy_weak_key_sha256": hashlib.sha256(group.equality_key).hexdigest(),
                    "raw_locator": source["raw_locator"],
                    "complete_group_observation_count": count,
                    "complete_wallet_fill_group_key_sha256": None if wallet_fill_key is None else hashlib.sha256(wallet_fill_key).hexdigest(),
                }
                unit_id, unit_projection = _emit_unit(
                    emitter=emitter,
                    joins=joins,
                    conservation=conservations[UnitUniverse.LEGACY_REPEAT_OCCURRENCE],
                    universe=UnitUniverse.LEGACY_REPEAT_OCCURRENCE,
                    key_projection=key_projection,
                    taxon=taxon,
                    occurrence_count=1,
                    proof_references=tuple(
                        {value.proof_id: value for value in proof_references}.values()
                    ),
                    supporting_taxa=tuple(supporting_taxa),
                )
                _emit_referenced_row(
                    emitter=emitter,
                    joins=joins,
                    container="r11a-v2-duplicate-observations.ndjson",
                    unit_id=unit_id,
                    unit_projection=unit_projection,
                    row={
                        "record_type": "R11A_V2_LEGACY_REPEAT_OCCURRENCE",
                        "primary_taxon": taxon.value,
                        "supporting_taxa": [value.value for value in supporting_taxa],
                        "raw_locator": source["raw_locator"],
                        "raw_wallet_value": source["raw_wallet_value"],
                        "raw_fill_value": source["raw_fill_value"],
                        "raw_record_fingerprint_sha256": source[
                            "raw_record_fingerprint_sha256"
                        ],
                        "block_number": source["block_number"],
                        "exact_raw_local_time": source["exact_raw_local_time"],
                        "exact_raw_block_time": source["exact_raw_block_time"],
                        "canonical_wallet": source["canonical_wallet"],
                        "exact_raw_coin_string": source["exact_raw_coin_string"],
                        "validated_tid": source["validated_tid"],
                        "exact_raw_side_string": source["exact_raw_side_string"],
                        "full_event_sha256": source["full_event_sha256"],
                        "fill_payload_sha256": source["fill_payload_sha256"],
                        "schema_errors": source["schema_errors"],
                        "selected_fill_payload": source["selected_fill_payload"],
                    },
                )
        meter.delete_file(sorted_path)
        meter.delete_file(materialized.weak_directory / f"part-{partition:03d}.frames")
    meter.delete_empty_directory(materialized.weak_directory)
    return (
        reducer_rows,
        group_count,
        observation_count,
        valid_tid_repeat_occurrences,
        invalid_tid_repeat_occurrences,
        supporting,
    )


def classify_materialized_candidates(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    *,
    exact_three_utc_days: bool,
) -> TaxonomyResult:
    if materialized.cap_fallback_required:
        raise TaxonomyBoundaryError("truncated materialization cannot enter taxonomy")
    joins: DiskJoinLedger | None = None
    scratch: GroupScratch | None = None
    conservations = {universe: UniverseConservation() for universe in UnitUniverse}
    block_index: BlockProofIndex | None = None
    protocol_index: ProtocolProofIndex | None = None
    try:
        joins = DiskJoinLedger(meter)
        scratch = GroupScratch(meter)
        block_index, block_rows, block_groups, block_observations = _classify_blocks(
            materialized,
            meter,
            emitter,
            joins,
            conservations[UnitUniverse.ARCHIVE_BLOCK_NUMBER_GROUP],
            scratch,
        )
        protocol_index, protocol_rows, protocol_support = _classify_protocol(
            materialized,
            meter,
            emitter,
            joins,
            conservations[
                UnitUniverse.PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE
            ],
            scratch,
        )
        (
            legacy_rows,
            legacy_groups,
            legacy_observations,
            valid_tid_repeat,
            invalid_tid_repeat,
            legacy_support,
        ) = _classify_legacy(
            materialized,
            meter,
            emitter,
            joins,
            conservations,
            scratch,
            block_index,
            protocol_index,
        )
        join_validation = joins.validate()
        universe_rows = tuple(
            conservations[universe].mapping(universe) for universe in UnitUniverse
        )
        supporting = protocol_support + legacy_support
        return TaxonomyResult(
            universe_rows=universe_rows,
            secondary_reducer_rows=tuple(block_rows + protocol_rows + legacy_rows),
            join_validation=join_validation,
            repeated_block_group_count=block_groups,
            repeated_block_observation_count=block_observations,
            legacy_repeat_group_count=legacy_groups,
            legacy_repeat_observation_count=legacy_observations,
            legacy_repeat_occurrence_count=legacy_observations - legacy_groups,
            valid_tid_legacy_repeat_occurrence_count=valid_tid_repeat,
            invalid_tid_legacy_repeat_occurrence_count=invalid_tid_repeat,
            supporting_taxon_counts={taxon: supporting[taxon] for taxon in TAXA},
            exact_three_utc_days=exact_three_utc_days,
        )
    finally:
        original_failure = sys.exception()
        errors: list[BaseException] = []
        for value in (protocol_index, block_index, scratch, joins):
            if value is None:
                continue
            try:
                if value is joins and original_failure is not None:
                    # Exceptional unwind discards buffered semantic evidence;
                    # physical abort failures remain sticky and fatal.
                    joins.abort()
                else:
                    value.close_delete()  # type: ignore[attr-defined]
            except BaseException as exc:
                errors.append(exc)
        if errors:
            tail = original_failure
            for error in reversed(errors):
                if tail is not None and error.__context__ is None:
                    error.__context__ = tail
                tail = error
            raise TaxonomyCleanupError("taxonomy cleanup failed") from errors[0]
