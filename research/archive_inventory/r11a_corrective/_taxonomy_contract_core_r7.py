from __future__ import annotations

import hashlib
import sqlite3
from collections import Counter
from collections.abc import Iterator, Sequence
from pathlib import Path

from . import _taxonomy_core_r7 as _core
from .canonical import canonical_json_bytes, strict_json_loads
from .join_r7 import DiskJoinLedger
from .locator_order import raw_locator_order_key
from .materialize import MaterializedIndexes
from .storage_r7 import MeteredSQLite, WorkspaceMeter

TaxonomyBoundaryError = _core.TaxonomyBoundaryError
Taxon = _core.Taxon
UnitUniverse = _core.UnitUniverse
EvidenceEmitter = _core.EvidenceEmitter
UniverseConservation = _core.UniverseConservation
ProofReference = _core.ProofReference
TaxonomyResult = _core.TaxonomyResult
BlockProofIndex = _core.BlockProofIndex
ProtocolProofIndex = _core.ProtocolProofIndex

_SCRATCH_DB_MAX_BYTES = 256_000_000
_BATCH_ROWS = 256


class BlockScratch:
    """Reusable, bounded, disk-backed state for one complete block-number group."""

    def __init__(self, meter: WorkspaceMeter) -> None:
        self.database = MeteredSQLite(
            meter.root / "taxonomy-block-scratch.sqlite",
            meter,
            _SCRATCH_DB_MAX_BYTES,
            "taxonomy block equality-group scratch",
        )
        with self.database.transaction("create block equality-group scratch") as connection:
            connection.executescript(
                """
                CREATE TABLE rows(
                  sequence INTEGER PRIMARY KEY,
                  row_json BLOB NOT NULL,
                  raw_block_key BLOB NOT NULL UNIQUE,
                  object_ordinal INTEGER NOT NULL,
                  object_key TEXT NOT NULL,
                  object_key_bytes BLOB NOT NULL,
                  compressed_sha256 BLOB NOT NULL,
                  record_ordinal INTEGER NOT NULL,
                  block_number INTEGER NOT NULL,
                  block_time TEXT NOT NULL,
                  event_count INTEGER NOT NULL,
                  event_fingerprint TEXT NOT NULL,
                  record_fingerprint TEXT NOT NULL
                );
                CREATE INDEX block_order ON rows(
                  object_key_bytes,compressed_sha256,record_ordinal
                );
                """
            )

    def reset(self) -> None:
        with self.database.transaction("reset block equality-group scratch") as connection:
            connection.execute("DELETE FROM rows")

    def load(self, path: Path, meter: WorkspaceMeter) -> int:
        self.reset()
        batch: list[tuple[object, ...]] = []
        sequence = 0
        for row in _core._rows(path, meter, "load block equality-group scratch"):
            object_ordinal, object_key, record_ordinal, event_ordinal = _core._raw_locator(row)
            if event_ordinal is not None:
                raise TaxonomyBoundaryError("block group row unexpectedly has event ordinal")
            locator = _core._object(row["raw_locator"], "raw locator")
            locator_key = raw_locator_order_key(
                object_key=object_key,
                verified_compressed_sha256=_core._text(
                    locator["verified_compressed_sha256"], "compressed SHA"
                ),
                record_ordinal_zero_based=record_ordinal,
                event_ordinal_zero_based=None,
            )
            batch.append(
                (
                    sequence,
                    sqlite3.Binary(canonical_json_bytes(row, final_newline=False)),
                    sqlite3.Binary(
                        bytes.fromhex(
                            _core._text(row["raw_block_key_hex"], "raw block key")
                        )
                    ),
                    object_ordinal,
                    object_key,
                    sqlite3.Binary(locator_key[0]),
                    sqlite3.Binary(locator_key[1]),
                    record_ordinal,
                    _core._integer(row["block_number"], "block number"),
                    _core._text(row["exact_raw_block_time"], "block time"),
                    _core._integer(row["ordered_event_count"], "event count"),
                    _core._text(
                        row["ordered_event_fingerprint_sha256"],
                        "event fingerprint",
                    ),
                    _core._text(
                        row["raw_record_fingerprint_sha256"],
                        "record fingerprint",
                    ),
                )
            )
            sequence += 1
            if len(batch) >= _BATCH_ROWS:
                self._insert(batch)
                batch.clear()
        self._insert(batch)
        return sequence

    def _insert(self, rows: Sequence[tuple[object, ...]]) -> None:
        if not rows:
            return
        try:
            with self.database.transaction("insert block equality-group rows") as connection:
                connection.executemany(
                    "INSERT INTO rows VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    rows,
                )
        except sqlite3.IntegrityError as exc:
            raise TaxonomyBoundaryError("duplicate raw block locator") from exc

    def ordered_rows(self) -> Iterator[sqlite3.Row]:
        self.database.connection.row_factory = sqlite3.Row
        yield from self.database.connection.execute(
            "SELECT * FROM rows ORDER BY object_key_bytes,compressed_sha256,record_ordinal"
        )

    def raw_keys(self) -> Iterator[bytes]:
        for row in self.database.connection.execute(
            "SELECT raw_block_key FROM rows "
            "ORDER BY object_key_bytes,compressed_sha256,record_ordinal"
        ):
            yield bytes(row[0])

    def close_delete(self) -> None:
        self.database.close_delete()


class EventScratch(_core.GroupScratch):
    """Reusable disk-backed state for protocol and legacy event equality groups."""


def _classify_blocks(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    joins: DiskJoinLedger,
    conservation: UniverseConservation,
    scratch: BlockScratch,
) -> tuple[BlockProofIndex, list[dict[str, object]], int, int]:
    index = BlockProofIndex(meter)
    reducer_rows: list[dict[str, object]] = []
    group_count = 0
    observation_count = 0
    try:
        for partition, sorted_path, reducer_row in _core._sort_partitions(
            reducer_id="MATERIALIZED_BLOCK_NUMBER",
            directory=materialized.block_directory,
            stats=materialized.block_stats,
            meter=meter,
        ):
            reducer_rows.append(reducer_row)
            spool = meter.root / f"taxonomy-block-groups-{partition:03d}"
            for group in _core.iter_equality_group_spools(
                sorted_path,
                spool,
                meter,
                maximum_group_spool_bytes=meter.limits.maximum_equality_group_spool_bytes,
            ):
                count = scratch.load(group.path, meter)
                if count <= 1:
                    raise TaxonomyBoundaryError(
                        "materialized repeated block group is singleton"
                    )
                connection = scratch.database.connection
                distinct_blocks = int(
                    connection.execute(
                        "SELECT COUNT(DISTINCT block_number) FROM rows"
                    ).fetchone()[0]
                )
                if distinct_blocks != 1:
                    raise TaxonomyBoundaryError("block-number equality-group drift")
                block_number = int(
                    connection.execute(
                        "SELECT block_number FROM rows ORDER BY sequence LIMIT 1"
                    ).fetchone()[0]
                )
                distinct_objects = int(
                    connection.execute(
                        "SELECT COUNT(DISTINCT object_key) FROM rows"
                    ).fetchone()[0]
                )
                invariant_count = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM (
                          SELECT 1 FROM rows
                          GROUP BY block_time,event_count,event_fingerprint
                        )
                        """
                    ).fetchone()[0]
                )
                if invariant_count > 1:
                    taxon = Taxon.CONFLICTING_BLOCK_REPLAY
                elif distinct_objects >= 2:
                    taxon = Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS
                else:
                    taxon = Taxon.UNCLASSIFIABLE

                locator_hasher = hashlib.sha256()
                locator_count = 0
                for observed in scratch.ordered_rows():
                    locator_projection = {
                        "object_ordinal_zero_based": int(observed["object_ordinal"]),
                        "object_key": str(observed["object_key"]),
                        "record_ordinal_zero_based": int(observed["record_ordinal"]),
                        "raw_block_key_sha256": hashlib.sha256(
                            bytes(observed["raw_block_key"])
                        ).hexdigest(),
                    }
                    locator_hasher.update(
                        _core.frame(
                            canonical_json_bytes(
                                locator_projection,
                                final_newline=False,
                            )
                        )
                    )
                    locator_count += 1
                if locator_count != count:
                    raise TaxonomyBoundaryError(
                        "block locator projection does not conserve observations"
                    )

                invariant = connection.execute(
                    """
                    SELECT block_time,event_count,event_fingerprint
                    FROM rows ORDER BY sequence LIMIT 1
                    """
                ).fetchone()
                if invariant is None:
                    raise TaxonomyBoundaryError("block group lacks invariant evidence")
                proof = None
                if taxon is Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS:
                    proof = _core._proof(
                        proof_type="R11A_V2_EXACT_BLOCK_REPLAY_PROOF",
                        projection_mapping={
                            "block_number": block_number,
                            "raw_block_locator_count": locator_count,
                            "distinct_source_object_count": distinct_objects,
                            "ordered_raw_locator_projection_sha256": (
                                locator_hasher.hexdigest()
                            ),
                            "exact_raw_block_time": str(invariant[0]),
                            "ordered_event_count": int(invariant[1]),
                            "ordered_event_fingerprint_sha256": str(invariant[2]),
                        },
                        emitter=emitter,
                        joins=joins,
                        container="r11a-v2-exact-block-replay-proofs.ndjson",
                    )

                key_projection = {
                    "block_number": block_number,
                    "raw_block_locator_count": locator_count,
                    "ordered_raw_locator_projection_sha256": (
                        locator_hasher.hexdigest()
                    ),
                }
                unit_id, unit_projection = _core._emit_unit(
                    emitter=emitter,
                    joins=joins,
                    conservation=conservation,
                    universe=UnitUniverse.ARCHIVE_BLOCK_NUMBER_GROUP,
                    key_projection=key_projection,
                    taxon=taxon,
                    occurrence_count=count,
                    proof_references=() if proof is None else (proof,),
                )
                retained_count = 0
                for observed in scratch.ordered_rows():
                    source = _core._object(
                        strict_json_loads(bytes(observed["row_json"])),
                        "block row",
                    )
                    _core._emit_referenced_row(
                        emitter=emitter,
                        joins=joins,
                        container="r11a-v2-block-overlap-matrix.ndjson",
                        unit_id=unit_id,
                        unit_projection=unit_projection,
                        row={
                            "record_type": "R11A_V2_BLOCK_OVERLAP_OBSERVATION",
                            "primary_taxon": taxon.value,
                            "block_number": source["block_number"],
                            "raw_locator": source["raw_locator"],
                            "raw_block_key_hex": source["raw_block_key_hex"],
                            "exact_raw_block_time": source["exact_raw_block_time"],
                            "ordered_event_count": source["ordered_event_count"],
                            "ordered_event_fingerprint_sha256": source[
                                "ordered_event_fingerprint_sha256"
                            ],
                            "raw_record_fingerprint_sha256": source[
                                "raw_record_fingerprint_sha256"
                            ],
                            "raw_record_value": source["raw_record_value"],
                        },
                    )
                    retained_count += 1
                if retained_count != count:
                    raise TaxonomyBoundaryError(
                        "retained block rows do not conserve observations"
                    )
                index.add_group(
                    block_number=block_number,
                    taxon=taxon,
                    proof=proof,
                    raw_block_keys=scratch.raw_keys(),  # type: ignore[arg-type]
                )
                group_count += 1
                observation_count += count
            meter.delete_file(sorted_path)
            meter.delete_file(
                materialized.block_directory / f"part-{partition:03d}.frames"
            )
        if materialized.block_directory.exists():
            materialized.block_directory.rmdir()
        return index, reducer_rows, group_count, observation_count
    except Exception:
        index.close_delete()
        raise


def classify_materialized_candidates(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    *,
    exact_three_utc_days: bool,
) -> TaxonomyResult:
    if materialized.cap_fallback_required:
        raise TaxonomyBoundaryError(
            "truncated materialization cannot enter taxonomy"
        )
    joins = DiskJoinLedger(meter)
    block_scratch = BlockScratch(meter)
    event_scratch = EventScratch(meter)
    conservations = {
        universe: UniverseConservation() for universe in UnitUniverse
    }
    block_index: BlockProofIndex | None = None
    protocol_index: ProtocolProofIndex | None = None
    try:
        (
            block_index,
            block_reducer_rows,
            block_group_count,
            block_observation_count,
        ) = _classify_blocks(
            materialized,
            meter,
            emitter,
            joins,
            conservations[UnitUniverse.ARCHIVE_BLOCK_NUMBER_GROUP],
            block_scratch,
        )
        (
            protocol_index,
            protocol_reducer_rows,
            protocol_support,
        ) = _core._classify_protocol(
            materialized,
            meter,
            emitter,
            joins,
            conservations[
                UnitUniverse.PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE
            ],
            event_scratch,
        )
        (
            legacy_reducer_rows,
            legacy_group_count,
            legacy_observation_count,
            valid_tid_repeat_count,
            invalid_tid_repeat_count,
            legacy_support,
        ) = _core._classify_legacy(
            materialized,
            meter,
            emitter,
            joins,
            conservations,
            event_scratch,
            block_index,
            protocol_index,
        )
        join_validation = joins.validate()
        universe_rows = tuple(
            conservations[universe].mapping(universe)
            for universe in UnitUniverse
        )
        supporting: Counter[str] = protocol_support + legacy_support
        return TaxonomyResult(
            universe_rows=universe_rows,
            secondary_reducer_rows=tuple(
                block_reducer_rows
                + protocol_reducer_rows
                + legacy_reducer_rows
            ),
            join_validation=join_validation,
            repeated_block_group_count=block_group_count,
            repeated_block_observation_count=block_observation_count,
            legacy_repeat_group_count=legacy_group_count,
            legacy_repeat_observation_count=legacy_observation_count,
            legacy_repeat_occurrence_count=(
                legacy_observation_count - legacy_group_count
            ),
            valid_tid_legacy_repeat_occurrence_count=valid_tid_repeat_count,
            invalid_tid_legacy_repeat_occurrence_count=invalid_tid_repeat_count,
            supporting_taxon_counts={
                taxon: supporting[taxon] for taxon in _core.TAXA
            },
            exact_three_utc_days=exact_three_utc_days,
        )
    finally:
        errors: list[BaseException] = []
        for value in (
            protocol_index,
            block_index,
            event_scratch,
            block_scratch,
            joins,
        ):
            if value is None:
                continue
            try:
                value.close_delete()  # type: ignore[attr-defined]
            except BaseException as exc:
                errors.append(exc)
        if errors:
            raise TaxonomyBoundaryError(
                "taxonomy cleanup failed"
            ) from errors[0]


__all__ = [
    "BlockScratch",
    "EventScratch",
    "EvidenceEmitter",
    "ProofReference",
    "Taxon",
    "TaxonomyBoundaryError",
    "TaxonomyResult",
    "UnitUniverse",
    "UniverseConservation",
    "classify_materialized_candidates",
]
