from __future__ import annotations

import dataclasses
import hashlib
import os
import struct
from pathlib import Path
from typing import BinaryIO, Final

from .identity import BlockObservation
from .limits import R11ALimits
from .storage import (
    MultisetCommitment,
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


class IndexError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True, slots=True)
class CandidateDiscovery:
    repeated_block_numbers: frozenset[int]
    repeated_weak_hashes: frozenset[bytes]
    repeated_block_group_count: int
    repeated_block_observation_count: int
    repeated_weak_group_count: int
    repeated_weak_observation_count: int
    cap_fallback_required: bool
    reducer_rows: tuple[dict[str, object], ...]


class SharedPartitionWriter:
    """One pre-write reservation shared across exactly 256 partition files."""

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
        self.reservation = meter.reserve(maximum_total_bytes, label)
        self.maximum_total_bytes = maximum_total_bytes
        self._handles: dict[int, BinaryIO] = {}
        self._written = 0
        self._commitments = [MultisetCommitment() for _ in range(256)]
        self._closed = False

    @property
    def written_bytes(self) -> int:
        return self._written

    def _handle(self, partition: int) -> BinaryIO:
        if not 0 <= partition < 256:
            raise IndexError("partition outside uint8 routing space")
        handle = self._handles.get(partition)
        if handle is None:
            handle = (self.directory / f"part-{partition:03d}.frames").open("xb")
            self._handles[partition] = handle
        return handle

    def write(self, equality_key: bytes, payload: bytes) -> None:
        if self._closed:
            raise IndexError("partition writer is closed")
        self.meter.runtime_guard.check_scientific_phase("write compact first-pass index")
        route = hashlib.sha256(equality_key).digest()[0]
        record = encode_keyed_record(equality_key, payload)
        framed_size = _FRAME_HEADER.size + len(record)
        if self._written + framed_size > self.maximum_total_bytes:
            raise IndexError("compact candidate index exceeds frozen workspace reservation")
        handle = self._handle(route)
        if handle.write(_FRAME_HEADER.pack(len(record))) != _FRAME_HEADER.size:
            raise IndexError("short partition header write")
        if handle.write(record) != len(record):
            raise IndexError("short partition record write")
        self._written += framed_size
        self._commitments[route].add(record)

    def close(self) -> None:
        if self._closed:
            return
        try:
            for _, handle in sorted(self._handles.items()):
                handle.flush()
                os.fsync(handle.fileno())
                handle.close()
            for partition in range(256):
                path = self.directory / f"part-{partition:03d}.frames"
                if not path.exists():
                    path.touch(exist_ok=False)
        except Exception:
            self.abort()
            raise
        self.meter.commit(self.reservation, self._written)
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
        if self.directory.exists():
            try:
                for path in sorted(self.directory.iterdir()):
                    if path.is_file():
                        path.unlink()
                self.directory.rmdir()
            except OSError as exc:
                errors.append(exc)
        self.meter.release(self.reservation)
        self._closed = True
        if errors:
            raise IndexError("partition writer cleanup failed") from errors[0]

    def commitments(self) -> tuple[dict[str, object], ...]:
        if not self._closed:
            raise IndexError("partition writer is not closed")
        return tuple(commitment.as_mapping() for commitment in self._commitments)


@dataclasses.dataclass(slots=True)
class FirstPassIndexes:
    meter: WorkspaceMeter
    limits: R11ALimits
    block_writer: SharedPartitionWriter = dataclasses.field(init=False)
    weak_writer: SharedPartitionWriter = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        # Together with the exact 2.108 GB compressed corpus these reservations keep
        # the known+reserved workspace below 5 GiB and retain per-partition sort room.
        if _BLOCK_INDEX_MAX_BYTES + _WEAK_INDEX_MAX_BYTES + self.limits.maximum_total_compressed_bytes >= self.limits.maximum_ephemeral_workspace_bytes:
            raise IndexError("compact index reservations leave no bounded sort workspace")
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
            label="compact legacy weak-key hash index",
        )

    def add_block(self, block: BlockObservation, object_ordinal_zero_based: int) -> None:
        if not 0 <= object_ordinal_zero_based < 72:
            raise IndexError("object ordinal outside exact R11A selection")
        block_key = struct.pack(">Q", block.block_number)
        self.block_writer.write(
            block_key,
            _BLOCK_PAYLOAD.pack(
                object_ordinal_zero_based,
                block.raw_locator.decompressed_record_ordinal_zero_based,
                hashlib.sha256(block.equality_bytes()).digest(),
            ),
        )
        for event in block.events:
            self.weak_writer.write(
                event.legacy_weak_key_sha256,
                _WEAK_PAYLOAD.pack(
                    object_ordinal_zero_based,
                    block.raw_locator.decompressed_record_ordinal_zero_based,
                    event.raw_locator.event_ordinal_zero_based,
                    block.block_number,
                ),
            )

    def close(self) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
        self.block_writer.close()
        self.weak_writer.close()
        return self.block_writer.commitments(), self.weak_writer.commitments()

    def abort(self) -> None:
        errors: list[BaseException] = []
        for writer in (self.block_writer, self.weak_writer):
            try:
                writer.abort()
            except BaseException as exc:
                errors.append(exc)
        if errors:
            raise IndexError("first-pass index cleanup failed") from errors[0]


def _group_count(spool_path: Path, meter: WorkspaceMeter) -> int:
    return sum(
        1
        for _ in iter_frames(
            spool_path,
            runtime_guard=meter.runtime_guard,
            phase="count primary reducer equality group",
        )
    )


def _discover_repeated_groups(
    *,
    reducer_id: str,
    directory: Path,
    source_commitments: tuple[dict[str, object], ...],
    meter: WorkspaceMeter,
    limits: R11ALimits,
    maximum_groups: int,
    maximum_observations: int,
) -> tuple[frozenset[bytes], int, int, bool, tuple[dict[str, object], ...]]:
    retained_keys: set[bytes] = set()
    repeated_group_count = 0
    repeated_observation_count = 0
    cap_fallback = False
    rows: list[dict[str, object]] = []

    for partition in range(256):
        meter.runtime_guard.check_scientific_phase(
            f"discover {reducer_id} partition {partition}"
        )
        source = directory / f"part-{partition:03d}.frames"
        sorted_path = meter.root / f"sorted-{reducer_id.lower()}-{partition:03d}.frames"
        temporary = meter.root / f"sort-temp-{reducer_id.lower()}-{partition:03d}"
        source_size = source.stat().st_size
        evidence: SortEvidence = external_sort_partition(
            source,
            sorted_path,
            temporary,
            meter,
            source_commitment=source_commitments[partition],
            maximum_source_bytes=source_size,
        )
        partition_groups = 0
        partition_observations = 0
        spool_directory = meter.root / f"group-spool-{reducer_id.lower()}-{partition:03d}"
        for group in iter_equality_group_spools(
            sorted_path,
            spool_directory,
            meter,
            maximum_group_spool_bytes=limits.maximum_equality_group_spool_bytes,
        ):
            count = _group_count(group.path, meter)
            if count <= 1:
                continue
            partition_groups += 1
            partition_observations += count
            repeated_group_count += 1
            repeated_observation_count += count
            if repeated_group_count <= maximum_groups and repeated_observation_count <= maximum_observations:
                retained_keys.add(group.equality_key)
            else:
                cap_fallback = True
        rows.append(
            {
                "record_type": "REDUCER_PARTITION_CONSERVATION",
                "reducer_id": reducer_id,
                "partition_ordinal_zero_based": partition,
                "processing_status": "COMPLETE",
                "partition_function": "FIRST_BYTE_OF_SHA256_OF_COMPLETE_EQUALITY_KEY_BYTES",
                "source_multiset_commitment": evidence.source_commitment,
                "destination_multiset_commitment": evidence.destination_commitment,
                "sorted_stream_sha256": evidence.sorted_stream_sha256,
                "source_file_bytes": source_size,
                "sorted_file_bytes": evidence.output_bytes,
                "discovered_repeat_group_count": partition_groups,
                "discovered_repeat_observation_count": partition_observations,
                "retained_repeat_group_count": partition_groups,
                "retained_repeat_observation_count": partition_observations,
                "omitted_due_to_cap_group_count": 0,
                "omitted_due_to_cap_observation_count": 0,
            }
        )
        meter.delete_file(sorted_path)
        meter.delete_file(source)
    if directory.exists():
        directory.rmdir()
    if cap_fallback:
        retained_keys.clear()
        for row in rows:
            row["retained_repeat_group_count"] = 0
            row["retained_repeat_observation_count"] = 0
            row["omitted_due_to_cap_group_count"] = row["discovered_repeat_group_count"]
            row["omitted_due_to_cap_observation_count"] = row[
                "discovered_repeat_observation_count"
            ]
    return (
        frozenset(retained_keys),
        repeated_group_count,
        repeated_observation_count,
        cap_fallback,
        tuple(rows),
    )


def discover_candidates(
    indexes: FirstPassIndexes,
    block_commitments: tuple[dict[str, object], ...],
    weak_commitments: tuple[dict[str, object], ...],
) -> CandidateDiscovery:
    limits = indexes.limits
    block_keys, block_groups, block_observations, block_cap, block_rows = _discover_repeated_groups(
        reducer_id="BLOCK_NUMBER",
        directory=indexes.meter.root / "first-pass-block-index",
        source_commitments=block_commitments,
        meter=indexes.meter,
        limits=limits,
        maximum_groups=limits.maximum_repeated_block_groups_retained,
        maximum_observations=limits.maximum_repeated_observations_retained,
    )
    weak_keys, weak_groups, weak_observations, weak_cap, weak_rows = _discover_repeated_groups(
        reducer_id="LEGACY_WEAK_KEY_HASH",
        directory=indexes.meter.root / "first-pass-weak-index",
        source_commitments=weak_commitments,
        meter=indexes.meter,
        limits=limits,
        maximum_groups=limits.maximum_repeated_legacy_key_groups_retained,
        maximum_observations=limits.maximum_repeated_observations_retained,
    )
    repeated_block_numbers = frozenset(struct.unpack(">Q", key)[0] for key in block_keys)
    return CandidateDiscovery(
        repeated_block_numbers=repeated_block_numbers,
        repeated_weak_hashes=weak_keys,
        repeated_block_group_count=block_groups,
        repeated_block_observation_count=block_observations,
        repeated_weak_group_count=weak_groups,
        repeated_weak_observation_count=weak_observations,
        cap_fallback_required=block_cap or weak_cap,
        reducer_rows=block_rows + weak_rows,
    )
