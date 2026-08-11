from __future__ import annotations

import hashlib
import heapq
import os
import shutil
import struct
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator, Sequence


class StorageError(RuntimeError):
    pass


MODULUS = 1 << 256


@dataclass(frozen=True, slots=True)
class MultisetCommitment:
    count: int = 0
    logical_bytes: int = 0
    xor_sha256: int = 0
    sum_sha256: int = 0
    sum_square_sha256: int = 0

    def add(self, record: bytes) -> "MultisetCommitment":
        digest = int.from_bytes(hashlib.sha256(record).digest(), "big")
        return MultisetCommitment(
            count=self.count + 1,
            logical_bytes=self.logical_bytes + len(record),
            xor_sha256=self.xor_sha256 ^ digest,
            sum_sha256=(self.sum_sha256 + digest) % MODULUS,
            sum_square_sha256=(self.sum_square_sha256 + digest * digest) % MODULUS,
        )

    def as_mapping(self) -> dict[str, object]:
        return {
            "record_count": self.count,
            "logical_bytes": self.logical_bytes,
            "xor_sha256": self.xor_sha256.to_bytes(32, "big").hex(),
            "sum_sha256_mod_2_256": self.sum_sha256.to_bytes(32, "big").hex(),
            "sum_square_sha256_mod_2_256": self.sum_square_sha256.to_bytes(32, "big").hex(),
        }


@dataclass(slots=True)
class RuntimeGuard:
    hard_limit_seconds: int
    packaging_reservation_seconds: int
    upload_reservation_seconds: int
    monotonic_ns: callable = time.monotonic_ns
    _started_ns: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.hard_limit_seconds <= self.packaging_reservation_seconds + self.upload_reservation_seconds:
            raise StorageError("runtime must leave packaging and upload reserves")
        self._started_ns = int(self.monotonic_ns())

    def elapsed_seconds(self) -> float:
        return (int(self.monotonic_ns()) - self._started_ns) / 1_000_000_000

    def check_processing(self, phase: str) -> None:
        limit = self.hard_limit_seconds - self.packaging_reservation_seconds - self.upload_reservation_seconds
        if self.elapsed_seconds() >= limit:
            raise StorageError(f"processing runtime reserve exhausted: {phase}")

    def check_packaging(self, phase: str) -> None:
        limit = self.hard_limit_seconds - self.upload_reservation_seconds
        if self.elapsed_seconds() >= limit:
            raise StorageError(f"upload runtime reserve exhausted: {phase}")


class Workspace:
    def __init__(self, root: Path, maximum_bytes: int, runtime: RuntimeGuard) -> None:
        self.root = root
        self.maximum_bytes = maximum_bytes
        self.runtime = runtime
        self._reserved = 0
        root.mkdir(parents=True, exist_ok=False)

    def _measure(self) -> int:
        total = 0
        for path in self.root.rglob("*"):
            if path.is_file():
                total += path.stat().st_size
        return total

    def reserve(self, byte_count: int, phase: str) -> None:
        if byte_count < 0:
            raise StorageError("negative reservation")
        self.runtime.check_processing(phase)
        actual = self._measure()
        if actual + self._reserved + byte_count > self.maximum_bytes:
            raise StorageError(f"workspace cap would be exceeded: {phase}")
        self._reserved += byte_count

    def consume(self, reserved_bytes: int, phase: str) -> None:
        if reserved_bytes < 0 or reserved_bytes > self._reserved:
            raise StorageError("invalid reservation consumption")
        self._reserved -= reserved_bytes
        self.checkpoint(phase)

    def release(self, reserved_bytes: int) -> None:
        if reserved_bytes < 0 or reserved_bytes > self._reserved:
            raise StorageError("invalid reservation release")
        self._reserved -= reserved_bytes

    def checkpoint(self, phase: str, *, packaging: bool = False) -> int:
        if packaging:
            self.runtime.check_packaging(phase)
        else:
            self.runtime.check_processing(phase)
        actual = self._measure()
        if actual + self._reserved > self.maximum_bytes:
            raise StorageError(f"workspace cap exceeded: {phase}")
        return actual

    def remove_checked(self, path: Path) -> None:
        if not path.exists():
            return
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        if path.exists():
            raise StorageError(f"checked cleanup failed: {path}")
        self.checkpoint("after checked cleanup")


class ReservedWriter:
    def __init__(self, path: Path, workspace: Workspace, mode: str = "wb") -> None:
        if "b" not in mode:
            raise StorageError("ReservedWriter requires binary mode")
        self.path = path
        self.workspace = workspace
        path.parent.mkdir(parents=True, exist_ok=True)
        self.handle: BinaryIO = path.open(mode)
        self.closed = False

    def write(self, data: bytes, phase: str = "bounded write") -> None:
        if self.closed:
            raise StorageError("write after close")
        self.workspace.reserve(len(data), phase)
        try:
            written = self.handle.write(data)
            self.handle.flush()
            if written != len(data):
                raise StorageError("short local write")
        except Exception:
            self.workspace.release(len(data))
            raise
        self.workspace.consume(len(data), phase)

    def close(self) -> None:
        if not self.closed:
            self.handle.flush()
            os.fsync(self.handle.fileno())
            self.handle.close()
            self.closed = True
            self.workspace.checkpoint("after writer close")

    def __enter__(self) -> "ReservedWriter":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


def write_frame(writer: ReservedWriter, payload: bytes) -> None:
    writer.write(struct.pack(">Q", len(payload)) + payload, "framed record write")


def read_frames(path: Path) -> Iterator[bytes]:
    with path.open("rb") as handle:
        while True:
            header = handle.read(8)
            if not header:
                return
            if len(header) != 8:
                raise StorageError("truncated frame header")
            size = struct.unpack(">Q", header)[0]
            payload = handle.read(size)
            if len(payload) != size:
                raise StorageError("truncated frame payload")
            yield payload


@dataclass(frozen=True, slots=True)
class SortResult:
    source_commitment: MultisetCommitment
    destination_commitment: MultisetCommitment
    sorted_stream_sha256: str
    destination: Path


class ExternalSorter:
    def __init__(self, workspace: Workspace, chunk_byte_limit: int = 16 * 1024 * 1024) -> None:
        if chunk_byte_limit <= 0:
            raise StorageError("invalid chunk limit")
        self.workspace = workspace
        self.chunk_byte_limit = chunk_byte_limit

    def sort(self, source: Path, destination: Path) -> SortResult:
        self.workspace.checkpoint("before external sort")
        chunks_dir = self.workspace.root / f"chunks-{destination.name}"
        chunks_dir.mkdir(parents=True, exist_ok=False)
        chunk_paths: list[Path] = []
        source_commit = MultisetCommitment()
        chunk: list[bytes] = []
        chunk_bytes = 0

        def flush_chunk() -> None:
            nonlocal chunk, chunk_bytes
            if not chunk:
                return
            chunk.sort()
            path = chunks_dir / f"{len(chunk_paths):06d}.frames"
            with ReservedWriter(path, self.workspace) as writer:
                for record in chunk:
                    write_frame(writer, record)
            chunk_paths.append(path)
            chunk = []
            chunk_bytes = 0

        for record in read_frames(source):
            self.workspace.runtime.check_processing("external sort source read")
            source_commit = source_commit.add(record)
            if chunk and chunk_bytes + len(record) > self.chunk_byte_limit:
                flush_chunk()
            chunk.append(record)
            chunk_bytes += len(record)
        flush_chunk()

        iterators = [iter(read_frames(path)) for path in chunk_paths]
        heap: list[tuple[bytes, int]] = []
        for index, iterator in enumerate(iterators):
            try:
                heapq.heappush(heap, (next(iterator), index))
            except StopIteration:
                pass
        destination_commit = MultisetCommitment()
        stream_hash = hashlib.sha256()
        with ReservedWriter(destination, self.workspace) as writer:
            while heap:
                self.workspace.runtime.check_processing("external sort merge")
                record, index = heapq.heappop(heap)
                write_frame(writer, record)
                destination_commit = destination_commit.add(record)
                stream_hash.update(record)
                try:
                    heapq.heappush(heap, (next(iterators[index]), index))
                except StopIteration:
                    pass
        if source_commit != destination_commit:
            self.workspace.remove_checked(destination)
            raise StorageError("external sort multiset commitment mismatch")
        self.workspace.remove_checked(chunks_dir)
        return SortResult(source_commit, destination_commit, stream_hash.hexdigest(), destination)


@dataclass(frozen=True, slots=True)
class GroupSpool:
    equality_key: bytes
    multiplicity: int
    path: Path

    def records(self) -> Iterator[bytes]:
        return read_frames(self.path)


def group_sorted_records(
    sorted_path: Path,
    *,
    workspace: Workspace,
    key_of: callable,
    maximum_in_memory_group_bytes: int = 1 * 1024 * 1024,
) -> Iterator[GroupSpool]:
    group_dir = workspace.root / f"groups-{sorted_path.name}"
    group_dir.mkdir(parents=True, exist_ok=False)
    current_key: bytes | None = None
    current: list[bytes] = []
    current_bytes = 0
    current_writer: ReservedWriter | None = None
    current_path: Path | None = None
    multiplicity = 0
    group_index = 0

    def finish() -> GroupSpool | None:
        nonlocal current, current_bytes, current_writer, current_path, multiplicity, group_index
        if current_key is None:
            return None
        path = current_path or (group_dir / f"{group_index:08d}.frames")
        if current_writer is None:
            with ReservedWriter(path, workspace) as writer:
                for item in current:
                    write_frame(writer, item)
        else:
            current_writer.close()
        result = GroupSpool(current_key, multiplicity, path)
        group_index += 1
        current = []
        current_bytes = 0
        current_writer = None
        current_path = None
        multiplicity = 0
        return result

    try:
        for record in read_frames(sorted_path):
            key = key_of(record)
            if not isinstance(key, bytes):
                raise StorageError("group key must be bytes")
            if current_key is not None and key != current_key:
                result = finish()
                if result is not None:
                    yield result
                current_key = key
            elif current_key is None:
                current_key = key
            multiplicity += 1
            if current_writer is None and current_bytes + len(record) <= maximum_in_memory_group_bytes:
                current.append(record)
                current_bytes += len(record)
            else:
                if current_writer is None:
                    current_path = group_dir / f"{group_index:08d}.frames"
                    current_writer = ReservedWriter(current_path, workspace)
                    for item in current:
                        write_frame(current_writer, item)
                    current.clear()
                    current_bytes = 0
                write_frame(current_writer, record)
        result = finish()
        if result is not None:
            yield result
    finally:
        if current_writer is not None and not current_writer.closed:
            current_writer.close()
        if group_dir.exists():
            workspace.remove_checked(group_dir)


class AtomicOutputDirectory:
    def __init__(self, workspace: Workspace, final_directory: Path) -> None:
        try:
            final_directory.relative_to(workspace.root)
        except ValueError as exc:
            raise StorageError("final artifact must be inside the metered workspace") from exc
        self.workspace = workspace
        self.final = final_directory
        self.staging = Path(tempfile.mkdtemp(prefix="artifact-staging-", dir=workspace.root))
        self.committed = False

    def commit(self) -> None:
        if self.committed:
            raise StorageError("artifact already committed")
        if self.final.exists():
            raise StorageError("final artifact already exists")
        self.workspace.checkpoint("before atomic artifact rename", packaging=True)
        os.replace(self.staging, self.final)
        try:
            self.workspace.checkpoint("after atomic artifact rename", packaging=True)
        except Exception:
            if self.final.exists():
                shutil.rmtree(self.final)
            if self.final.exists():
                raise StorageError("failed to remove artifact after post-rename failure")
            raise
        self.committed = True

    def __enter__(self) -> "AtomicOutputDirectory":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if not self.committed and self.staging.exists():
            shutil.rmtree(self.staging)
            if self.staging.exists():
                raise StorageError("failed to remove artifact staging directory")
