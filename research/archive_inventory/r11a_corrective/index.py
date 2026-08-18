from __future__ import annotations

import dataclasses
import hashlib
import os
import sqlite3
import struct
from pathlib import Path
from typing import BinaryIO, Final

from .identity import BlockObservation
from .limits import R11ALimits
from .locator_order import canonical_object_locator_ranks
from .selection import DEFAULT_SELECTION
from .storage_r7 import (
    MeteredSQLite,
    SortEvidence,
    WorkspaceMeter,
    encode_keyed_record,
    external_sort_partition,
    iter_equality_group_spools,
    iter_frames,
)

_FRAME_HEADER: Final[struct.Struct] = struct.Struct(">I")
_BLOCK_PAYLOAD: Final[struct.Struct] = struct.Struct(">BQ32s")
_WEAK_PAYLOAD: Final[struct.Struct] = struct.Struct(">BQIQ")
_BLOCK_INDEX_MAX_BYTES: Final[int] = 300_000_000
_WEAK_INDEX_MAX_BYTES: Final[int] = 2_500_000_000
_CANDIDATE_DB_MAX_BYTES: Final[int] = 128_000_000
_PARTITION_BUFFER_BYTES: Final[int] = 64 * 1024


class IndexBoundaryError(RuntimeError):
    pass


class SharedPartitionWriter:
    """One bounded directory reservation across exactly 256 partition files."""

    def __init__(
        self,
        directory: Path,
        meter: WorkspaceMeter,
        *,
        maximum_total_bytes: int,
        label: str,
    ) -> None:
        self.directory = meter._ensure_inside(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.meter = meter
        self.label = label
        self.reservation = meter.reserve(maximum_total_bytes, label)
        self.maximum_total_bytes = maximum_total_bytes
        self._handles: dict[int, BinaryIO] = {}
        self._buffers = [bytearray() for _ in range(256)]
        self._records = [0] * 256
        self._logical_bytes = [0] * 256
        self._written = 0
        self._closed = False
        meter.checkpoint(self.reservation, self.directory, phase=f"create {label}")

    def _handle(self, partition: int) -> BinaryIO:
        if not 0 <= partition < 256:
            raise IndexBoundaryError("partition outside exact uint8 range")
        handle = self._handles.get(partition)
        if handle is None:
            handle = (self.directory / f"part-{partition:03d}.frames").open("xb")
            self._handles[partition] = handle
        return handle

    def _flush(self, partition: int) -> None:
        buffer = self._buffers[partition]
        if not buffer:
            return
        self.meter.runtime_guard.check_scientific_phase(f"flush {self.label} before")
        handle = self._handle(partition)
        payload = bytes(buffer)
        if handle.write(payload) != len(payload):
            raise IndexBoundaryError("short partition write")
        handle.flush()
        self._written += len(payload)
        buffer.clear()
        self.meter.checkpoint(
            self.reservation,
            self.directory,
            phase=f"flush {self.label} partition {partition}",
        )
        self.meter.runtime_guard.check_scientific_phase(f"flush {self.label} after")

    def write(self, equality_key: bytes, payload: bytes) -> None:
        if self._closed:
            raise IndexBoundaryError("partition writer is closed")
        route = hashlib.sha256(equality_key).digest()[0]
        record = encode_keyed_record(equality_key, payload)
        framed = _FRAME_HEADER.pack(len(record)) + record
        buffered = sum(len(value) for value in self._buffers)
        if self._written + buffered + len(framed) > self.maximum_total_bytes:
            raise IndexBoundaryError(f"{self.label} exceeds frozen reservation")
        self._buffers[route].extend(framed)
        self._records[route] += 1
        self._logical_bytes[route] += len(record)
        if len(self._buffers[route]) >= _PARTITION_BUFFER_BYTES:
            self._flush(route)

    def close(self) -> None:
        if self._closed:
            return
        try:
            for partition in range(256):
                self._flush(partition)
            for partition in range(256):
                handle = self._handles.get(partition)
                if handle is not None:
                    handle.flush()
                    os.fsync(handle.fileno())
                    handle.close()
                else:
                    (self.directory / f"part-{partition:03d}.frames").touch(exist_ok=False)
            self.meter.finalize(
                self.reservation,
                self.directory,
                phase=f"finalize {self.label}",
            )
        except Exception:
            self.abort()
            raise
        self._closed = True

    def abort(self) -> None:
        if self._closed:
            return
        errors: list[BaseException] = []
        for handle in self._handles.values():
            try:
                handle.close()
            except OSError as exc:
                errors.append(exc)
        try:
            if self.directory.exists():
                import shutil

                shutil.rmtree(self.directory)
            if self.directory.exists():
                raise IndexBoundaryError("partition directory cleanup failed")
            self.meter.release_deleted(
                self.reservation,
                self.directory,
                phase=f"abort {self.label}",
            )
        except BaseException as exc:
            errors.append(exc)
        self._closed = True
        if errors:
            raise IndexBoundaryError("partition writer cleanup failed") from errors[0]

    def partition_stats(self) -> tuple[tuple[int, int], ...]:
        if not self._closed:
            raise IndexBoundaryError("partition writer must be closed")
        return tuple(zip(self._records, self._logical_bytes, strict=True))


class CandidateDatabase:
    """Disk-backed exact candidate membership; no global candidate set in RAM."""

    def __init__(self, meter: WorkspaceMeter) -> None:
        self.database = MeteredSQLite(
            meter.root / "candidate-membership.sqlite",
            meter,
            _CANDIDATE_DB_MAX_BYTES,
            "candidate membership database",
        )
        with self.database.transaction("create candidate database") as connection:
            connection.executescript(
                """
                CREATE TABLE repeated_blocks(key BLOB PRIMARY KEY);
                CREATE TABLE repeated_weak(key BLOB PRIMARY KEY);
                """
            )

    def add(self, table: str, key: bytes) -> None:
        if table not in {"repeated_blocks", "repeated_weak"}:
            raise IndexBoundaryError("invalid candidate table")
        with self.database.transaction(f"add {table} candidate") as connection:
            connection.execute(
                f"INSERT INTO {table}(key) VALUES(?)",
                (sqlite3.Binary(key),),
            )

    def contains_block(self, block_number: int) -> bool:
        key = struct.pack(">Q", block_number)
        return self._contains("repeated_blocks", key)

    def contains_weak_hash(self, weak_hash: bytes) -> bool:
        return self._contains("repeated_weak", weak_hash)

    def _contains(self, table: str, key: bytes) -> bool:
        row = self.database.connection.execute(
            f"SELECT 1 FROM {table} WHERE key=?",
            (sqlite3.Binary(key),),
        ).fetchone()
        return row is not None

    def counts(self) -> tuple[int, int]:
        block = self.database.connection.execute("SELECT COUNT(*) FROM repeated_blocks").fetchone()[0]
        weak = self.database.connection.execute("SELECT COUNT(*) FROM repeated_weak").fetchone()[0]
        return int(block), int(weak)

    def close_delete(self) -> None:
        self.database.close_delete()


@dataclasses.dataclass(frozen=True, slots=True)
class CandidateDiscovery:
    candidates: CandidateDatabase
    repeated_block_group_count: int
    repeated_block_observation_count: int
    repeated_weak_group_count: int
    repeated_weak_observation_count: int
    cap_fallback_required: bool
    reducer_rows: tuple[dict[str, object], ...]


@dataclasses.dataclass(slots=True)
class FirstPassIndexes:
    meter: WorkspaceMeter
    limits: R11ALimits
    block_writer: SharedPartitionWriter = dataclasses.field(init=False)
    weak_writer: SharedPartitionWriter = dataclasses.field(init=False)
    _canonical_object_rank: dict[tuple[str, str], int] = dataclasses.field(
        init=False
    )

    def __post_init__(self) -> None:
        if (
            _BLOCK_INDEX_MAX_BYTES
            + _WEAK_INDEX_MAX_BYTES
            + self.limits.maximum_total_compressed_bytes
            >= self.limits.maximum_ephemeral_workspace_bytes
        ):
            raise IndexBoundaryError("first-pass reservations leave no bounded reducer room")
        self._canonical_object_rank = canonical_object_locator_ranks(
            tuple(
                (target.object_key, target.expected_compressed_sha256)
                for target in DEFAULT_SELECTION.targets
            )
        )
        self.block_writer = SharedPartitionWriter(
            self.meter.root / "first-pass-block-index",
            self.meter,
            maximum_total_bytes=_BLOCK_INDEX_MAX_BYTES,
            label="compact block-number index",
        )
        self.weak_writer = SharedPartitionWriter(
            self.meter.root / "first-pass-weak-index",
            self.meter,
            maximum_total_bytes=_WEAK_INDEX_MAX_BYTES,
            label="compact legacy weak-key index",
        )

    def add_block(self, block: BlockObservation, object_ordinal_zero_based: int) -> None:
        if not 0 <= object_ordinal_zero_based < 72:
            raise IndexBoundaryError("object ordinal outside exact scope")
        target = DEFAULT_SELECTION.targets[object_ordinal_zero_based]
        locator_identity = (
            block.raw_locator.object_key,
            block.raw_locator.verified_compressed_sha256,
        )
        if locator_identity != (
            target.object_key,
            target.expected_compressed_sha256,
        ):
            raise IndexBoundaryError(
                "first-pass raw locator differs from frozen target identity"
            )
        try:
            canonical_object_rank = self._canonical_object_rank[locator_identity]
        except KeyError as exc:
            raise IndexBoundaryError(
                "first-pass raw locator is outside canonical object order"
            ) from exc
        self.block_writer.write(
            struct.pack(">Q", block.block_number),
            _BLOCK_PAYLOAD.pack(
                canonical_object_rank,
                block.raw_locator.decompressed_record_ordinal_zero_based,
                hashlib.sha256(block.equality_bytes()).digest(),
            ),
        )
        for event in block.events:
            self.weak_writer.write(
                event.legacy_weak_key_sha256,
                _WEAK_PAYLOAD.pack(
                    canonical_object_rank,
                    block.raw_locator.decompressed_record_ordinal_zero_based,
                    event.raw_locator.event_ordinal_zero_based,
                    block.block_number,
                ),
            )

    def close(self) -> tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]:
        self.block_writer.close()
        self.weak_writer.close()
        return self.block_writer.partition_stats(), self.weak_writer.partition_stats()

    def abort(self) -> None:
        errors: list[BaseException] = []
        for writer in (self.block_writer, self.weak_writer):
            try:
                writer.abort()
            except BaseException as exc:
                errors.append(exc)
        if errors:
            raise IndexBoundaryError("first-pass index cleanup failed") from errors[0]


def _count_group(path: Path, meter: WorkspaceMeter) -> int:
    return sum(
        1
        for _ in iter_frames(
            path,
            runtime_guard=meter.runtime_guard,
            phase="count exact reducer group",
        )
    )


def _discover(
    *,
    reducer_id: str,
    source_directory: Path,
    partition_stats: tuple[tuple[int, int], ...],
    candidates: CandidateDatabase,
    candidate_table: str,
    meter: WorkspaceMeter,
    maximum_groups: int,
    maximum_observations: int,
) -> tuple[int, int, bool, tuple[dict[str, object], ...]]:
    total_groups = 0
    total_observations = 0
    fallback = False
    rows: list[dict[str, object]] = []
    for partition in range(256):
        source = source_directory / f"part-{partition:03d}.frames"
        source_records, source_logical = partition_stats[partition]
        destination = meter.root / f"sorted-{reducer_id.lower()}-{partition:03d}.frames"
        temporary = meter.root / f"sort-{reducer_id.lower()}-{partition:03d}"
        evidence: SortEvidence = external_sort_partition(
            source,
            destination,
            temporary,
            meter,
            source_record_count=source_records,
            source_logical_bytes=source_logical,
            maximum_source_bytes=source.stat().st_size,
        )
        partition_groups = 0
        partition_observations = 0
        spool = meter.root / f"groups-{reducer_id.lower()}-{partition:03d}"
        for group in iter_equality_group_spools(
            destination,
            spool,
            meter,
            maximum_group_spool_bytes=meter.limits.maximum_equality_group_spool_bytes,
        ):
            count = _count_group(group.path, meter)
            if count <= 1:
                continue
            partition_groups += 1
            partition_observations += count
            total_groups += 1
            total_observations += count
            if total_groups > maximum_groups or total_observations > maximum_observations:
                fallback = True
            elif not fallback:
                candidates.add(candidate_table, group.equality_key)
        rows.append(
            {
                "record_type": "R11A_V2_REDUCER_PARTITION_CONSERVATION",
                "reducer_id": reducer_id,
                "partition_ordinal_zero_based": partition,
                "processing_status": "COMPLETE",
                "partition_function": "FIRST_BYTE_OF_SHA256_OF_COMPLETE_EQUALITY_KEY_BYTES",
                "source_record_count": source_records,
                "source_logical_bytes": source_logical,
                "destination_record_count": evidence.output_records,
                "destination_logical_bytes": evidence.output_logical_bytes,
                "exact_multiplicity": evidence.exact_multiplicity,
                "sorted_stream_sha256": evidence.sorted_stream_sha256,
                "discovered_repeat_group_count": partition_groups,
                "discovered_repeat_observation_count": partition_observations,
            }
        )
        meter.delete_file(destination)
        meter.delete_file(source)
    if source_directory.exists():
        source_directory.rmdir()
    return total_groups, total_observations, fallback, tuple(rows)


def discover_candidates(
    indexes: FirstPassIndexes,
    block_stats: tuple[tuple[int, int], ...],
    weak_stats: tuple[tuple[int, int], ...],
) -> CandidateDiscovery:
    candidates = CandidateDatabase(indexes.meter)
    try:
        block_groups, block_observations, block_fallback, block_rows = _discover(
            reducer_id="BLOCK_NUMBER",
            source_directory=indexes.meter.root / "first-pass-block-index",
            partition_stats=block_stats,
            candidates=candidates,
            candidate_table="repeated_blocks",
            meter=indexes.meter,
            maximum_groups=indexes.limits.maximum_repeated_block_groups_retained,
            maximum_observations=indexes.limits.maximum_repeated_observations_retained,
        )
        weak_groups, weak_observations, weak_fallback, weak_rows = _discover(
            reducer_id="LEGACY_WEAK_KEY_HASH",
            source_directory=indexes.meter.root / "first-pass-weak-index",
            partition_stats=weak_stats,
            candidates=candidates,
            candidate_table="repeated_weak",
            meter=indexes.meter,
            maximum_groups=indexes.limits.maximum_repeated_legacy_key_groups_retained,
            maximum_observations=indexes.limits.maximum_repeated_observations_retained,
        )
        return CandidateDiscovery(
            candidates=candidates,
            repeated_block_group_count=block_groups,
            repeated_block_observation_count=block_observations,
            repeated_weak_group_count=weak_groups,
            repeated_weak_observation_count=weak_observations,
            cap_fallback_required=block_fallback or weak_fallback,
            reducer_rows=block_rows + weak_rows,
        )
    except Exception:
        candidates.close_delete()
        raise
