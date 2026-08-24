from __future__ import annotations

import dataclasses
import hashlib
import heapq
import os
import shutil
import struct
import tempfile
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import BinaryIO, Final

from .limits import R11ALimits
from .runtime import RuntimeGuard

_UINT256_MODULUS: Final[int] = 1 << 256
_FRAME_HEADER: Final[struct.Struct] = struct.Struct(">I")
_KEY_HEADER: Final[struct.Struct] = struct.Struct(">I")


class StorageBoundaryError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True, slots=True)
class Reservation:
    reservation_id: int
    maximum_bytes: int
    label: str


class WorkspaceMeter:
    """Single-root workspace accounting with reservation-before-write semantics."""

    def __init__(self, root: Path, limits: R11ALimits, runtime_guard: RuntimeGuard) -> None:
        self.root = root.resolve()
        self.limits = limits
        self.runtime_guard = runtime_guard
        self._known_bytes = 0
        self._reserved_bytes = 0
        self._next_reservation_id = 0
        self._reservations: dict[int, Reservation] = {}

    def bootstrap(self) -> None:
        self.runtime_guard.check_scientific_phase("workspace bootstrap")
        self.root.mkdir(parents=True, exist_ok=True)
        if any(self.root.iterdir()):
            raise StorageBoundaryError("workspace root must start empty")
        free = shutil.disk_usage(self.root).free
        if free < self.limits.minimum_free_workspace_bytes_before_oidc:
            raise StorageBoundaryError("pre-OIDC free workspace is below the frozen threshold")
        self._known_bytes = 0

    @property
    def known_bytes(self) -> int:
        return self._known_bytes

    @property
    def reserved_bytes(self) -> int:
        return self._reserved_bytes

    def _ensure_inside(self, path: Path) -> Path:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise StorageBoundaryError("path escapes the single measured workspace root") from exc
        return resolved

    def reserve(self, maximum_bytes: int, label: str, *, packaging: bool = False) -> Reservation:
        if maximum_bytes < 0:
            raise StorageBoundaryError("cannot reserve a negative byte count")
        if packaging:
            self.runtime_guard.check_packaging_phase(f"reserve {label}")
        else:
            self.runtime_guard.check_scientific_phase(f"reserve {label}")
        if self._known_bytes + self._reserved_bytes + maximum_bytes > self.limits.maximum_ephemeral_workspace_bytes:
            raise StorageBoundaryError(f"workspace reservation would exceed cap: {label}")
        reservation = Reservation(self._next_reservation_id, maximum_bytes, label)
        self._next_reservation_id += 1
        self._reservations[reservation.reservation_id] = reservation
        self._reserved_bytes += maximum_bytes
        return reservation

    def commit(self, reservation: Reservation, actual_bytes: int) -> None:
        observed = self._reservations.pop(reservation.reservation_id, None)
        if observed != reservation:
            raise StorageBoundaryError("unknown or already consumed workspace reservation")
        if actual_bytes < 0 or actual_bytes > reservation.maximum_bytes:
            raise StorageBoundaryError("actual write exceeds reserved workspace bytes")
        self._reserved_bytes -= reservation.maximum_bytes
        self._known_bytes += actual_bytes
        if self._known_bytes + self._reserved_bytes > self.limits.maximum_ephemeral_workspace_bytes:
            raise StorageBoundaryError("workspace cap exceeded after reservation commit")

    def release(self, reservation: Reservation) -> None:
        observed = self._reservations.pop(reservation.reservation_id, None)
        if observed != reservation:
            raise StorageBoundaryError("unknown or already consumed workspace reservation")
        self._reserved_bytes -= reservation.maximum_bytes

    def delete_file(self, path: Path) -> None:
        resolved = self._ensure_inside(path)
        if not resolved.exists():
            return
        if not resolved.is_file():
            raise StorageBoundaryError("delete_file target is not a regular file")
        size = resolved.stat().st_size
        resolved.unlink()
        self._known_bytes -= size
        if self._known_bytes < 0:
            raise StorageBoundaryError("workspace accounting became negative")

    def checked_rmtree(self, path: Path) -> None:
        resolved = self._ensure_inside(path)
        if not resolved.exists():
            return
        total = directory_size(resolved)
        shutil.rmtree(resolved)
        if resolved.exists():
            raise StorageBoundaryError("workspace cleanup did not remove directory")
        self._known_bytes -= total
        if self._known_bytes < 0:
            raise StorageBoundaryError("workspace accounting became negative")

    def account_existing_file(self, path: Path, *, maximum_expected_bytes: int, label: str) -> None:
        resolved = self._ensure_inside(path)
        if not resolved.is_file():
            raise StorageBoundaryError("expected file is absent")
        size = resolved.stat().st_size
        reservation = self.reserve(maximum_expected_bytes, label)
        self.commit(reservation, size)

    def verify_actual_usage(self) -> int:
        self.runtime_guard.check_packaging_phase("verify actual workspace usage")
        actual = directory_size(self.root)
        if actual != self._known_bytes:
            raise StorageBoundaryError(
                f"workspace accounting mismatch: tracked={self._known_bytes} actual={actual}"
            )
        if actual + self._reserved_bytes > self.limits.maximum_ephemeral_workspace_bytes:
            raise StorageBoundaryError("actual workspace usage exceeds cap")
        return actual


def directory_size(path: Path) -> int:
    total = 0
    for root, directories, files in os.walk(path):
        directories.sort()
        files.sort()
        for name in files:
            candidate = Path(root) / name
            if candidate.is_symlink():
                raise StorageBoundaryError("symlinks are forbidden in measured workspace")
            total += candidate.stat().st_size
    return total


class ReservedBinaryWriter:
    def __init__(
        self,
        path: Path,
        meter: WorkspaceMeter,
        *,
        maximum_bytes: int,
        label: str,
        packaging: bool = False,
    ) -> None:
        self.path = meter._ensure_inside(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.meter = meter
        self.reservation = meter.reserve(maximum_bytes, label, packaging=packaging)
        self._handle: BinaryIO = self.path.open("xb")
        self._written = 0
        self._closed = False

    @property
    def written_bytes(self) -> int:
        return self._written

    def write(self, data: bytes, *, packaging: bool = False) -> None:
        if self._closed:
            raise StorageBoundaryError("write after close")
        if self._written + len(data) > self.reservation.maximum_bytes:
            raise StorageBoundaryError("writer exceeded its pre-reserved byte bound")
        if packaging:
            self.meter.runtime_guard.check_packaging_phase(f"write {self.reservation.label}")
        else:
            self.meter.runtime_guard.check_scientific_phase(f"write {self.reservation.label}")
        written = self._handle.write(data)
        if written != len(data):
            raise StorageBoundaryError("short local file write")
        self._written += written

    def close(self) -> None:
        if self._closed:
            return
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self._handle.close()
        self.meter.commit(self.reservation, self._written)
        self._closed = True

    def abort(self) -> None:
        if self._closed:
            return
        try:
            self._handle.close()
        finally:
            if self.path.exists():
                self.path.unlink()
            self.meter.release(self.reservation)
            self._closed = True

    def __enter__(self) -> "ReservedBinaryWriter":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is None:
            self.close()
        else:
            self.abort()


@dataclasses.dataclass(slots=True)
class MultisetCommitment:
    record_count: int = 0
    logical_bytes: int = 0
    xor_sha256: int = 0
    sum_sha256_mod_2_256: int = 0
    sum_square_sha256_mod_2_256: int = 0

    def add(self, record: bytes) -> None:
        digest_int = int.from_bytes(hashlib.sha256(record).digest(), "big")
        self.record_count += 1
        self.logical_bytes += len(record)
        self.xor_sha256 ^= digest_int
        self.sum_sha256_mod_2_256 = (self.sum_sha256_mod_2_256 + digest_int) % _UINT256_MODULUS
        self.sum_square_sha256_mod_2_256 = (
            self.sum_square_sha256_mod_2_256 + (digest_int * digest_int)
        ) % _UINT256_MODULUS

    def as_mapping(self) -> dict[str, object]:
        return {
            "record_count": self.record_count,
            "logical_bytes": self.logical_bytes,
            "xor_sha256": self.xor_sha256.to_bytes(32, "big").hex(),
            "sum_sha256_mod_2_256": self.sum_sha256_mod_2_256.to_bytes(32, "big").hex(),
            "sum_square_sha256_mod_2_256": self.sum_square_sha256_mod_2_256.to_bytes(
                32, "big"
            ).hex(),
        }


@dataclasses.dataclass(frozen=True, slots=True)
class SortEvidence:
    input_records: int
    output_records: int
    input_logical_bytes: int
    output_logical_bytes: int
    source_commitment: dict[str, object]
    destination_commitment: dict[str, object]
    sorted_stream_sha256: str
    output_bytes: int

    def validate(self) -> None:
        values = (
            self.input_records,
            self.output_records,
            self.input_logical_bytes,
            self.output_logical_bytes,
            self.output_bytes,
        )
        if any(type(value) is not int or value < 0 for value in values):
            raise StorageBoundaryError("sort evidence counts and bytes must be nonnegative integers")
        if self.input_records != self.output_records:
            raise StorageBoundaryError("external sort changed record count")
        if self.input_logical_bytes != self.output_logical_bytes:
            raise StorageBoundaryError("external sort changed logical byte count")
        if int(self.source_commitment.get("record_count", -1)) != self.input_records:
            raise StorageBoundaryError("source commitment record count mismatch")
        if int(self.destination_commitment.get("record_count", -1)) != self.output_records:
            raise StorageBoundaryError("destination commitment record count mismatch")
        if int(self.source_commitment.get("logical_bytes", -1)) != self.input_logical_bytes:
            raise StorageBoundaryError("source commitment logical byte mismatch")
        if int(self.destination_commitment.get("logical_bytes", -1)) != self.output_logical_bytes:
            raise StorageBoundaryError("destination commitment logical byte mismatch")
        if self.source_commitment != self.destination_commitment:
            raise StorageBoundaryError("external sort changed the exact record multiset")
        if len(self.sorted_stream_sha256) != 64:
            raise StorageBoundaryError("sorted stream SHA-256 format invalid")
        if self.output_bytes < self.output_logical_bytes:
            raise StorageBoundaryError("framed output bytes cannot be smaller than logical bytes")



def encode_keyed_record(key: bytes, payload: bytes) -> bytes:
    if len(key) > 0xFFFFFFFF:
        raise StorageBoundaryError("sort key exceeds uint32")
    return _KEY_HEADER.pack(len(key)) + key + payload


def decode_keyed_record(record: bytes) -> tuple[bytes, bytes]:
    if len(record) < _KEY_HEADER.size:
        raise StorageBoundaryError("truncated keyed record")
    key_length = _KEY_HEADER.unpack_from(record, 0)[0]
    offset = _KEY_HEADER.size
    end = offset + key_length
    if end > len(record):
        raise StorageBoundaryError("truncated keyed record key")
    return record[offset:end], record[end:]


def write_frame(handle: ReservedBinaryWriter, record: bytes) -> None:
    if len(record) > 0xFFFFFFFF:
        raise StorageBoundaryError("framed record exceeds uint32")
    handle.write(_FRAME_HEADER.pack(len(record)))
    handle.write(record)


def iter_frames(path: Path, *, runtime_guard: RuntimeGuard, phase: str) -> Iterator[bytes]:
    with path.open("rb") as handle:
        while True:
            runtime_guard.check_scientific_phase(phase)
            header = handle.read(_FRAME_HEADER.size)
            if not header:
                break
            if len(header) != _FRAME_HEADER.size:
                raise StorageBoundaryError("truncated frame header")
            length = _FRAME_HEADER.unpack(header)[0]
            record = handle.read(length)
            if len(record) != length:
                raise StorageBoundaryError("truncated framed record")
            yield record
        if handle.read(1):
            raise StorageBoundaryError("unexpected bytes after framed stream")


class PartitionedRecordWriter:
    def __init__(
        self,
        directory: Path,
        meter: WorkspaceMeter,
        *,
        partition_count: int,
        maximum_total_bytes: int,
        label: str,
    ) -> None:
        if partition_count != 256:
            raise StorageBoundaryError("R11A partition count must remain 256")
        self.directory = meter._ensure_inside(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.meter = meter
        self.partition_count = partition_count
        self.maximum_total_bytes = maximum_total_bytes
        self.label = label
        self._writers: dict[int, ReservedBinaryWriter] = {}
        self._commitments = [MultisetCommitment() for _ in range(partition_count)]
        self._allocated_per_partition = max(1, maximum_total_bytes // partition_count)
        self._closed = False

    def _writer(self, partition: int) -> ReservedBinaryWriter:
        writer = self._writers.get(partition)
        if writer is None:
            writer = ReservedBinaryWriter(
                self.directory / f"part-{partition:03d}.frames",
                self.meter,
                maximum_bytes=self._allocated_per_partition,
                label=f"{self.label} partition {partition}",
            )
            self._writers[partition] = writer
        return writer

    def write(self, equality_key: bytes, payload: bytes) -> None:
        if self._closed:
            raise StorageBoundaryError("partitioned writer is closed")
        route = hashlib.sha256(equality_key).digest()[0]
        record = encode_keyed_record(equality_key, payload)
        write_frame(self._writer(route), record)
        self._commitments[route].add(record)

    def close(self) -> None:
        if self._closed:
            return
        for partition in range(self.partition_count):
            writer = self._writers.get(partition)
            if writer is not None:
                writer.close()
            else:
                with ReservedBinaryWriter(
                    self.directory / f"part-{partition:03d}.frames",
                    self.meter,
                    maximum_bytes=0,
                    label=f"{self.label} empty partition {partition}",
                ):
                    pass
        self._closed = True

    def commitments(self) -> tuple[dict[str, object], ...]:
        if not self._closed:
            raise StorageBoundaryError("partitioned writer must be closed before commitments")
        return tuple(commitment.as_mapping() for commitment in self._commitments)


@dataclasses.dataclass(frozen=True, slots=True)
class _HeapItem:
    sort_key: tuple[bytes, bytes]
    run_index: int
    record: bytes

    def __lt__(self, other: "_HeapItem") -> bool:
        return (self.sort_key, self.run_index) < (other.sort_key, other.run_index)


def _record_sort_key(record: bytes) -> tuple[bytes, bytes]:
    key, _ = decode_keyed_record(record)
    return key, record


def external_sort_partition(
    source: Path,
    destination: Path,
    temporary_directory: Path,
    meter: WorkspaceMeter,
    *,
    source_commitment: dict[str, object],
    maximum_source_bytes: int,
) -> SortEvidence:
    runtime_guard = meter.runtime_guard
    temporary_directory = meter._ensure_inside(temporary_directory)
    temporary_directory.mkdir(parents=True, exist_ok=False)
    runs: list[Path] = []
    batch: list[bytes] = []
    batch_bytes = 0

    def flush_batch() -> None:
        nonlocal batch, batch_bytes
        if not batch:
            return
        runtime_guard.check_scientific_phase("sort chunk")
        batch.sort(key=_record_sort_key)
        maximum = sum(_FRAME_HEADER.size + len(record) for record in batch)
        path = temporary_directory / f"run-{len(runs):06d}.frames"
        with ReservedBinaryWriter(path, meter, maximum_bytes=maximum, label="sort run") as writer:
            for record in batch:
                write_frame(writer, record)
        runs.append(path)
        batch = []
        batch_bytes = 0

    for record in iter_frames(source, runtime_guard=runtime_guard, phase="read unsorted partition"):
        batch.append(record)
        batch_bytes += _FRAME_HEADER.size + len(record)
        if batch_bytes >= meter.limits.maximum_sort_chunk_bytes:
            flush_batch()
    flush_batch()

    destination_commitment = MultisetCommitment()
    sorted_stream = hashlib.sha256()
    maximum_destination = min(
        maximum_source_bytes,
        int(source_commitment["logical_bytes"]) + int(source_commitment["record_count"]) * _FRAME_HEADER.size,
    )
    with ReservedBinaryWriter(
        destination,
        meter,
        maximum_bytes=maximum_destination,
        label="sorted partition",
    ) as writer:
        handles = [iter_frames(path, runtime_guard=runtime_guard, phase="merge sort runs") for path in runs]
        heap: list[_HeapItem] = []
        for index, iterator in enumerate(handles):
            try:
                record = next(iterator)
            except StopIteration:
                continue
            heapq.heappush(heap, _HeapItem(_record_sort_key(record), index, record))
        while heap:
            runtime_guard.check_scientific_phase("merge sorted partition")
            item = heapq.heappop(heap)
            write_frame(writer, item.record)
            destination_commitment.add(item.record)
            sorted_stream.update(_FRAME_HEADER.pack(len(item.record)))
            sorted_stream.update(item.record)
            try:
                next_record = next(handles[item.run_index])
            except StopIteration:
                continue
            heapq.heappush(
                heap,
                _HeapItem(_record_sort_key(next_record), item.run_index, next_record),
            )

    destination_mapping = destination_commitment.as_mapping()
    evidence = SortEvidence(
        input_records=int(source_commitment["record_count"]),
        output_records=int(destination_mapping["record_count"]),
        input_logical_bytes=int(source_commitment["logical_bytes"]),
        output_logical_bytes=int(destination_mapping["logical_bytes"]),
        source_commitment=source_commitment,
        destination_commitment=destination_mapping,
        sorted_stream_sha256=sorted_stream.hexdigest(),
        output_bytes=destination.stat().st_size,
    )
    evidence.validate()
    for path in runs:
        meter.delete_file(path)
    if temporary_directory.exists():
        temporary_directory.rmdir()
    return evidence


@dataclasses.dataclass(frozen=True, slots=True)
class EqualityGroupSpool:
    equality_key: bytes
    path: Path
    record_count: int
    payload_bytes: int


def iter_equality_group_spools(
    sorted_partition: Path,
    spool_directory: Path,
    meter: WorkspaceMeter,
    *,
    maximum_group_spool_bytes: int,
) -> Iterator[EqualityGroupSpool]:
    spool_directory = meter._ensure_inside(spool_directory)
    spool_directory.mkdir(parents=True, exist_ok=True)
    current_key: bytes | None = None
    writer: ReservedBinaryWriter | None = None
    path: Path | None = None
    count = 0
    payload_bytes = 0
    group_index = 0

    def finish() -> EqualityGroupSpool | None:
        nonlocal writer, path, count, payload_bytes, current_key
        if writer is None or path is None or current_key is None:
            return None
        writer.close()
        result = EqualityGroupSpool(current_key, path, count, payload_bytes)
        writer = None
        path = None
        count = 0
        payload_bytes = 0
        return result

    for framed in iter_frames(
        sorted_partition,
        runtime_guard=meter.runtime_guard,
        phase="group sorted partition",
    ):
        key, payload = decode_keyed_record(framed)
        if current_key is None or key != current_key:
            completed = finish()
            if completed is not None:
                yield completed
                meter.delete_file(completed.path)
            current_key = key
            path = spool_directory / f"group-{group_index:09d}.frames"
            group_index += 1
            writer = ReservedBinaryWriter(
                path,
                meter,
                maximum_bytes=maximum_group_spool_bytes,
                label="equality group spool",
            )
        assert writer is not None
        write_frame(writer, payload)
        count += 1
        payload_bytes += len(payload)
    completed = finish()
    if completed is not None:
        yield completed
        meter.delete_file(completed.path)
    if spool_directory.exists():
        spool_directory.rmdir()


class AtomicArtifactDirectory:
    """All checks happen in staging; rename is the final fallible operation."""

    def __init__(self, workspace: Path, meter: WorkspaceMeter, final_name: str) -> None:
        if not final_name or "/" in final_name or ".." in final_name:
            raise StorageBoundaryError("unsafe final artifact directory name")
        self.meter = meter
        self.workspace = meter._ensure_inside(workspace)
        self.final_path = meter._ensure_inside(self.workspace / final_name)
        self.staging_path = meter._ensure_inside(self.workspace / f".{final_name}.staging")
        self._committed = False

    def __enter__(self) -> Path:
        if self.final_path.exists() or self.staging_path.exists():
            raise StorageBoundaryError("artifact output path already exists")
        self.staging_path.mkdir(parents=True)
        return self.staging_path

    def commit(self, validate: Callable[[Path], None]) -> Path:
        if self._committed:
            raise StorageBoundaryError("artifact directory already committed")
        self.meter.runtime_guard.check_packaging_phase("validate artifact staging")
        validate(self.staging_path)
        staging_bytes = directory_size(self.staging_path)
        if staging_bytes > self.meter.limits.maximum_retained_artifact_bytes:
            raise StorageBoundaryError("artifact staging exceeds retained artifact cap")
        self.meter.verify_actual_usage()
        self.staging_path.rename(self.final_path)
        self._committed = True
        return self.final_path

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._committed:
            return
        if self.staging_path.exists():
            self.meter.checked_rmtree(self.staging_path)
        if self.final_path.exists():
            self.meter.checked_rmtree(self.final_path)
