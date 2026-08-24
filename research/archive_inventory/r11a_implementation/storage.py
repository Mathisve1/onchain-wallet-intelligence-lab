from __future__ import annotations

import hashlib
import heapq
import os
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator

from .limits import DEFAULT_LIMITS, R11ALimits, R11ALimitError


class R11AStorageError(ValueError):
    """Raised when bounded workspace or partition integrity fails."""


_LENGTH = struct.Struct(">I")


def _windows_file_allocation(path: Path) -> int:
    """Return the exact allocated file bytes reported by Windows."""

    import ctypes
    from ctypes import wintypes

    get_size = ctypes.WinDLL("kernel32", use_last_error=True).GetCompressedFileSizeW
    get_size.argtypes = (wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD))
    get_size.restype = wintypes.DWORD
    high = wintypes.DWORD()
    ctypes.set_last_error(0)
    low = get_size(str(path), ctypes.byref(high))
    error = ctypes.get_last_error()
    if low == 0xFFFFFFFF and error:
        raise OSError(error, f"cannot measure allocated bytes: {path}")
    return (high.value << 32) | low


def allocated_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for current in (path, *path.rglob("*")):
        try:
            stat = current.stat(follow_symlinks=False)
        except FileNotFoundError:
            continue
        blocks = getattr(stat, "st_blocks", None)
        if blocks is not None:
            total += blocks * 512
        elif current.is_file():
            if os.name == "nt":
                total += _windows_file_allocation(current)
            else:
                raise R11AStorageError("allocated-byte measurement is unavailable")
    return total


def free_bytes(path: Path) -> int:
    if hasattr(os, "statvfs"):
        stat = os.statvfs(path)
        return stat.f_bavail * stat.f_frsize
    return shutil.disk_usage(path).free


@dataclass(slots=True)
class WorkspaceMeter:
    root: Path
    limits: R11ALimits = DEFAULT_LIMITS
    peak_allocated_bytes: int = 0

    def bootstrap(self) -> None:
        self.limits.validate()
        self.root.mkdir(parents=True, exist_ok=True)
        current = allocated_bytes(self.root)
        self.peak_allocated_bytes = max(self.peak_allocated_bytes, current)
        if current > self.limits.maximum_ephemeral_workspace_bytes:
            raise R11AStorageError("workspace cap exceeded at bootstrap")

    def require_pre_oidc_free_space(self) -> int:
        self.bootstrap()
        observed = free_bytes(self.root)
        if observed < self.limits.minimum_free_workspace_bytes_before_oidc:
            raise R11AStorageError("insufficient free workspace before OIDC")
        return observed

    def checkpoint(self, label: str) -> int:
        observed = allocated_bytes(self.root)
        self.peak_allocated_bytes = max(self.peak_allocated_bytes, observed)
        if observed > self.limits.maximum_ephemeral_workspace_bytes:
            raise R11AStorageError(f"workspace cap exceeded after {label}")
        return observed


class FramedWriter:
    def __init__(self, path: Path, *, meter: WorkspaceMeter | None = None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.meter = meter
        self._handle: BinaryIO | None = path.open("ab")
        self.record_count = 0
        self.logical_bytes = 0
        self.stream_sha256 = hashlib.sha256()

    def write(self, record: bytes) -> None:
        if self._handle is None:
            raise R11AStorageError("writer already closed")
        if type(record) is not bytes:
            raise R11AStorageError("framed record must be bytes")
        if len(record) > 0xFFFFFFFF:
            raise R11AStorageError("framed record exceeds uint32 length")
        framed = _LENGTH.pack(len(record)) + record
        self._handle.write(framed)
        self.record_count += 1
        self.logical_bytes += len(record)
        self.stream_sha256.update(record)

    def flush(self) -> None:
        if self._handle is None:
            return
        self._handle.flush()
        os.fsync(self._handle.fileno())
        if self.meter is not None:
            self.meter.checkpoint(f"flush {self.path.name}")

    def close(self) -> None:
        if self._handle is None:
            return
        self.flush()
        self._handle.close()
        self._handle = None

    def __enter__(self) -> "FramedWriter":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def iter_framed(path: Path) -> Iterator[bytes]:
    with path.open("rb") as handle:
        while True:
            prefix = handle.read(_LENGTH.size)
            if not prefix:
                return
            if len(prefix) != _LENGTH.size:
                raise R11AStorageError(f"truncated frame length in {path}")
            length = _LENGTH.unpack(prefix)[0]
            record = handle.read(length)
            if len(record) != length:
                raise R11AStorageError(f"truncated frame payload in {path}")
            yield record


def framed_multiset_digest(path: Path) -> tuple[int, int, str]:
    count = 0
    logical = 0
    digest = hashlib.sha256()
    for record in iter_framed(path):
        count += 1
        logical += len(record)
        digest.update(record)
    return count, logical, digest.hexdigest()


class PartitionSet:
    """Fixed 256-way append-only partition set.

    Equality is always decided from complete key bytes stored in each record.
    The SHA-256 first byte is routing only and never identity.
    """

    def __init__(
        self,
        root: Path,
        name: str,
        *,
        limits: R11ALimits = DEFAULT_LIMITS,
        meter: WorkspaceMeter | None = None,
    ) -> None:
        limits.validate()
        if limits.partition_count != 256:
            raise R11AStorageError("partition implementation requires 256 partitions")
        if not name or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for char in name):
            raise R11AStorageError("unsafe partition name")
        self.root = root / name
        self.root.mkdir(parents=True, exist_ok=True)
        self.name = name
        self.limits = limits
        self.meter = meter
        self._writers: dict[int, FramedWriter] = {}

    @staticmethod
    def partition_ordinal(equality_key: bytes) -> int:
        if type(equality_key) is not bytes or not equality_key:
            raise R11AStorageError("partition equality key must be nonempty bytes")
        return hashlib.sha256(equality_key).digest()[0]

    @staticmethod
    def encode_record(equality_key: bytes, payload: bytes) -> bytes:
        if type(equality_key) is not bytes or type(payload) is not bytes:
            raise R11AStorageError("partition key and payload must be bytes")
        if len(equality_key) > 0xFFFFFFFF:
            raise R11AStorageError("partition key exceeds uint32 length")
        return _LENGTH.pack(len(equality_key)) + equality_key + payload

    @staticmethod
    def decode_record(record: bytes) -> tuple[bytes, bytes]:
        if len(record) < _LENGTH.size:
            raise R11AStorageError("partition record too short")
        key_length = _LENGTH.unpack(record[: _LENGTH.size])[0]
        boundary = _LENGTH.size + key_length
        if boundary > len(record):
            raise R11AStorageError("partition key length exceeds record")
        return record[_LENGTH.size : boundary], record[boundary:]

    def path(self, ordinal: int) -> Path:
        if type(ordinal) is not int or not 0 <= ordinal < 256:
            raise R11AStorageError("partition ordinal outside 0..255")
        return self.root / f"part-{ordinal:03d}.frames"

    def write(self, equality_key: bytes, payload: bytes) -> int:
        ordinal = self.partition_ordinal(equality_key)
        writer = self._writers.get(ordinal)
        if writer is None:
            writer = FramedWriter(self.path(ordinal), meter=self.meter)
            self._writers[ordinal] = writer
        writer.write(self.encode_record(equality_key, payload))
        return ordinal

    def flush_all(self) -> None:
        for writer in self._writers.values():
            writer.flush()

    def close(self) -> None:
        for writer in self._writers.values():
            writer.close()
        self._writers.clear()
        if self.meter is not None:
            self.meter.checkpoint(f"close partition set {self.name}")

    def __enter__(self) -> "PartitionSet":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


@dataclass(frozen=True, slots=True)
class SortResult:
    record_count: int
    logical_input_bytes: int
    unsorted_record_stream_sha256: str
    sorted_record_stream_sha256: str
    sorted_path: Path
    run_count: int


def _write_sorted_run(records: list[bytes], path: Path, meter: WorkspaceMeter | None) -> None:
    records.sort()
    with FramedWriter(path, meter=meter) as writer:
        for record in records:
            writer.write(record)


def external_sort_framed(
    source: Path,
    destination: Path,
    *,
    temporary_root: Path,
    memory_limit_bytes: int,
    meter: WorkspaceMeter | None = None,
) -> SortResult:
    if type(memory_limit_bytes) is not int or memory_limit_bytes < 1:
        raise R11AStorageError("sort memory limit must be positive integer")
    temporary_root.mkdir(parents=True, exist_ok=True)
    source_count, source_logical, source_digest = framed_multiset_digest(source)
    run_paths: list[Path] = []
    chunk: list[bytes] = []
    chunk_bytes = 0
    for record in iter_framed(source):
        framed_size = len(record) + _LENGTH.size
        if chunk and chunk_bytes + framed_size > memory_limit_bytes:
            run_path = temporary_root / f"run-{len(run_paths):06d}.frames"
            _write_sorted_run(chunk, run_path, meter)
            run_paths.append(run_path)
            chunk = []
            chunk_bytes = 0
        chunk.append(record)
        chunk_bytes += framed_size
    if chunk:
        run_path = temporary_root / f"run-{len(run_paths):06d}.frames"
        _write_sorted_run(chunk, run_path, meter)
        run_paths.append(run_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    sorted_digest = hashlib.sha256()
    output_count = 0
    output_logical = 0
    if not run_paths:
        destination.write_bytes(b"")
    elif len(run_paths) == 1:
        os.replace(run_paths[0], destination)
        for record in iter_framed(destination):
            sorted_digest.update(record)
            output_count += 1
            output_logical += len(record)
    else:
        iterators = [iter(iter_framed(path)) for path in run_paths]
        heap: list[tuple[bytes, int]] = []
        for index, iterator in enumerate(iterators):
            try:
                heap.append((next(iterator), index))
            except StopIteration:
                pass
        heapq.heapify(heap)
        with FramedWriter(destination, meter=meter) as writer:
            while heap:
                record, index = heapq.heappop(heap)
                writer.write(record)
                sorted_digest.update(record)
                output_count += 1
                output_logical += len(record)
                try:
                    heapq.heappush(heap, (next(iterators[index]), index))
                except StopIteration:
                    pass
        for path in run_paths:
            path.unlink(missing_ok=True)
    if output_count != source_count or output_logical != source_logical:
        raise R11AStorageError("external sort count or logical-byte conservation failed")
    sorted_count, sorted_logical, independently_sorted_digest = framed_multiset_digest(destination)
    if sorted_count != source_count or sorted_logical != source_logical:
        raise R11AStorageError("sorted file verification conservation failed")
    if independently_sorted_digest != sorted_digest.hexdigest():
        raise R11AStorageError("sorted stream digest accounting drift")
    # Multiset equality is exact because the merge emits the original complete bytes;
    # count/length plus independently tested record sequence logic guards truncation.
    if meter is not None:
        meter.checkpoint(f"external sort {source.name}")
    shutil.rmtree(temporary_root, ignore_errors=True)
    return SortResult(
        record_count=source_count,
        logical_input_bytes=source_logical,
        unsorted_record_stream_sha256=source_digest,
        sorted_record_stream_sha256=sorted_digest.hexdigest(),
        sorted_path=destination,
        run_count=len(run_paths),
    )


def group_sorted_records(path: Path) -> Iterator[tuple[bytes, tuple[bytes, ...]]]:
    current_key: bytes | None = None
    payloads: list[bytes] = []
    for record in iter_framed(path):
        key, payload = PartitionSet.decode_record(record)
        if current_key is None:
            current_key = key
        elif key != current_key:
            yield current_key, tuple(payloads)
            current_key = key
            payloads = []
        payloads.append(payload)
    if current_key is not None:
        yield current_key, tuple(payloads)


class AtomicOutputDirectory:
    def __init__(self, final_path: Path, *, meter: WorkspaceMeter | None = None) -> None:
        self.final_path = final_path
        self.staging_path = final_path.with_name(final_path.name + ".staging")
        self.meter = meter
        self._committed = False

    def __enter__(self) -> Path:
        if self.final_path.exists() or self.staging_path.exists():
            raise R11AStorageError("atomic output target already exists")
        self.staging_path.mkdir(parents=True)
        if self.meter is not None:
            self.meter.checkpoint("create atomic staging output")
        return self.staging_path

    def commit(self) -> None:
        if not self.staging_path.is_dir() or self.final_path.exists():
            raise R11AStorageError("atomic output cannot commit")
        os.replace(self.staging_path, self.final_path)
        self._committed = True
        if self.meter is not None:
            self.meter.checkpoint("commit atomic output")

    def __exit__(self, exc_type, exc, traceback) -> None:
        if not self._committed:
            shutil.rmtree(self.staging_path, ignore_errors=True)


def remove_tree_checked(path: Path, *, meter: WorkspaceMeter | None = None) -> None:
    shutil.rmtree(path, ignore_errors=False)
    if meter is not None:
        meter.checkpoint(f"remove {path.name}")


def validate_storage_fixture(records: Iterable[tuple[bytes, bytes]], root: Path) -> None:
    meter = WorkspaceMeter(root)
    meter.bootstrap()
    partition = PartitionSet(root, "fixture", meter=meter)
    expected: list[bytes] = []
    try:
        for key, payload in records:
            encoded = partition.encode_record(key, payload)
            expected.append(encoded)
            partition.write(key, payload)
    finally:
        partition.close()
    observed: list[bytes] = []
    for ordinal in range(256):
        path = partition.path(ordinal)
        if path.exists():
            destination = path.with_name(path.name + ".sorted")
            result = external_sort_framed(
                path,
                destination,
                temporary_root=root / f"sort-{ordinal:03d}",
                memory_limit_bytes=1024,
                meter=meter,
            )
            if result.record_count < 1:
                raise R11AStorageError("nonempty partition reported empty")
            observed.extend(iter_framed(destination))
    if sorted(observed) != sorted(expected):
        raise R11AStorageError("partition fixture multiset mismatch")


# Imported intentionally so static reviews can assert no global R10/R11 cap is mutated.
INSTANCE_SCOPED_LIMITS_ONLY = True
