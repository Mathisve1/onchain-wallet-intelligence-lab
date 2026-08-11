from __future__ import annotations

import hashlib
import heapq
import os
import shutil
import sqlite3
import struct
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Iterator

from .limits import R11AV2Limits
from .runtime import R11AV2RuntimeError, RuntimeGuard


class R11AV2StorageError(ValueError):
    """Raised when bounded disk, sorting or atomic-output invariants fail."""


FRAME_HEADER = struct.Struct(">IQ")
SQLITE_BATCH = 2_000


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _tree_size(root: Path) -> int:
    if not root.exists():
        return 0
    total = 0
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except FileNotFoundError:
            continue
        for entry in entries:
            if entry.is_symlink():
                raise R11AV2StorageError(f"symlink forbidden in workspace: {entry.path}")
            if entry.is_dir(follow_symlinks=False):
                stack.append(Path(entry.path))
            elif entry.is_file(follow_symlinks=False):
                total += entry.stat(follow_symlinks=False).st_size
            else:
                raise R11AV2StorageError(f"non-regular workspace entry: {entry.path}")
    return total


@dataclass(slots=True)
class WorkspaceMeter:
    root: Path
    limits: R11AV2Limits
    runtime: RuntimeGuard
    peak_bytes: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.limits.validate_shape()
        self.root = self.root.resolve()

    def bootstrap(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink():
            raise R11AV2StorageError("workspace root cannot be symlink")
        self.checkpoint("workspace bootstrap", phase="measurement")

    def preflight_free_space(self) -> int:
        self.root.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(self.root).free
        if free < self.limits.minimum_free_workspace_bytes_before_oidc:
            raise R11AV2StorageError(
                f"free workspace below pre-OIDC threshold: {free} < {self.limits.minimum_free_workspace_bytes_before_oidc}"
            )
        return free

    def checked_path(self, relative: str | Path) -> Path:
        candidate = (self.root / relative).resolve()
        if not _is_within(candidate, self.root):
            raise R11AV2StorageError("workspace path escapes root")
        return candidate

    def checkpoint(self, label: str, *, phase: str) -> int:
        if phase == "measurement":
            self.runtime.check_measurement(label)
        elif phase == "packaging":
            self.runtime.check_packaging(label)
        elif phase == "pre_upload":
            self.runtime.check_pre_upload(label)
        else:
            raise R11AV2StorageError(f"unknown workspace phase: {phase}")
        current = _tree_size(self.root)
        self.peak_bytes = max(self.peak_bytes, current)
        if current > self.limits.maximum_ephemeral_workspace_bytes:
            raise R11AV2StorageError(
                f"workspace cap exceeded at {label}: {current} > {self.limits.maximum_ephemeral_workspace_bytes}"
            )
        return current

    def reserve(self, additional_bytes: int, label: str, *, phase: str) -> None:
        if type(additional_bytes) is not int or additional_bytes < 0:
            raise R11AV2StorageError("reservation must be nonnegative integer")
        current = self.checkpoint(f"before {label}", phase=phase)
        if current + additional_bytes > self.limits.maximum_ephemeral_workspace_bytes:
            raise R11AV2StorageError(
                f"workspace reservation exceeds cap at {label}: {current}+{additional_bytes}"
            )
        free = shutil.disk_usage(self.root).free
        if free < additional_bytes:
            raise R11AV2StorageError(f"insufficient physical disk for reservation at {label}")

    def after_mutation(self, label: str, *, phase: str) -> None:
        self.checkpoint(f"after {label}", phase=phase)

    def checked_unlink(self, path: Path, *, missing_ok: bool = False, phase: str = "measurement") -> None:
        if not _is_within(path, self.root):
            raise R11AV2StorageError("unlink path escapes workspace")
        try:
            path.unlink()
        except FileNotFoundError:
            if not missing_ok:
                raise
        self.after_mutation(f"unlink {path.name}", phase=phase)

    def checked_rmtree(self, path: Path, *, missing_ok: bool = False, phase: str = "measurement") -> None:
        if not _is_within(path, self.root):
            raise R11AV2StorageError("rmtree path escapes workspace")
        if not path.exists():
            if missing_ok:
                return
            raise FileNotFoundError(path)
        shutil.rmtree(path)
        if path.exists():
            raise R11AV2StorageError(f"checked cleanup left path behind: {path}")
        self.after_mutation(f"rmtree {path.name}", phase=phase)


class MeteredBinaryWriter(AbstractContextManager["MeteredBinaryWriter"]):
    def __init__(self, path: Path, meter: WorkspaceMeter, *, phase: str, label: str) -> None:
        if not _is_within(path, meter.root):
            raise R11AV2StorageError("writer path escapes workspace")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.meter = meter
        self.phase = phase
        self.label = label
        self._handle: BinaryIO = path.open("wb")
        self._closed = False
        self.byte_count = 0
        self.sha256 = hashlib.sha256()

    def write(self, data: bytes) -> None:
        if self._closed:
            raise R11AV2StorageError("write after close")
        if type(data) is not bytes:
            raise R11AV2StorageError("writer accepts bytes only")
        self.meter.reserve(len(data), self.label, phase=self.phase)
        written = self._handle.write(data)
        if written != len(data):
            raise R11AV2StorageError("short local write")
        self.byte_count += written
        self.sha256.update(data)
        self.meter.after_mutation(self.label, phase=self.phase)

    def flush_fsync(self) -> None:
        if self._closed:
            raise R11AV2StorageError("flush after close")
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self.meter.after_mutation(f"fsync {self.label}", phase=self.phase)

    def close(self) -> None:
        if self._closed:
            return
        self.flush_fsync()
        self._handle.close()
        self._closed = True

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            self.close()
        finally:
            if exc is not None and self.path.exists():
                self.meter.checked_unlink(self.path, missing_ok=True, phase=self.phase)
        return False


def encode_frame(key: bytes, payload: bytes) -> bytes:
    if type(key) is not bytes or type(payload) is not bytes:
        raise R11AV2StorageError("frame key and payload must be bytes")
    if not key:
        raise R11AV2StorageError("frame key cannot be empty")
    if len(key) >= 2**32:
        raise R11AV2StorageError("frame key too large")
    return FRAME_HEADER.pack(len(key), len(payload)) + key + payload


def read_frames(path: Path) -> Iterator[tuple[bytes, bytes]]:
    with path.open("rb") as handle:
        while True:
            header = handle.read(FRAME_HEADER.size)
            if not header:
                return
            if len(header) != FRAME_HEADER.size:
                raise R11AV2StorageError(f"truncated frame header: {path}")
            key_length, payload_length = FRAME_HEADER.unpack(header)
            if key_length == 0:
                raise R11AV2StorageError("zero-length frame key")
            key = handle.read(key_length)
            payload = handle.read(payload_length)
            if len(key) != key_length or len(payload) != payload_length:
                raise R11AV2StorageError(f"truncated frame payload: {path}")
            yield key, payload


def frame_bytes(key: bytes, payload: bytes) -> bytes:
    return encode_frame(key, payload)


@dataclass(slots=True)
class FixedPartitionWriter(AbstractContextManager["FixedPartitionWriter"]):
    root: Path
    meter: WorkspaceMeter
    prefix: str
    partition_count: int
    _writers: dict[int, MeteredBinaryWriter] = field(default_factory=dict, init=False)
    record_count: int = field(default=0, init=False)
    logical_bytes: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.partition_count != 256:
            raise R11AV2StorageError("R11A V2 partition count must remain 256")
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, partition: int) -> Path:
        return self.root / f"{self.prefix}-{partition:03d}.frames"

    def write(self, equality_key: bytes, payload: bytes) -> int:
        digest = hashlib.sha256(equality_key).digest()
        partition = digest[0]
        writer = self._writers.get(partition)
        if writer is None:
            writer = MeteredBinaryWriter(
                self.path(partition),
                self.meter,
                phase="measurement",
                label=f"write {self.prefix} partition {partition}",
            )
            self._writers[partition] = writer
        encoded = encode_frame(equality_key, payload)
        writer.write(encoded)
        self.record_count += 1
        self.logical_bytes += len(encoded)
        return partition

    def close(self) -> None:
        errors: list[BaseException] = []
        for writer in self._writers.values():
            try:
                writer.close()
            except BaseException as exc:  # checked cleanup reports every failure
                errors.append(exc)
        self._writers.clear()
        if errors:
            raise R11AV2StorageError(f"partition writer close failures: {errors!r}")

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False


@dataclass(frozen=True, slots=True)
class SortResult:
    source_record_count: int
    source_logical_bytes: int
    source_stream_sha256: str
    sorted_record_count: int
    sorted_logical_bytes: int
    sorted_stream_sha256: str
    exact_multiset_verified: bool


def _write_run(
    path: Path,
    rows: list[tuple[bytes, bytes]],
    meter: WorkspaceMeter,
    label: str,
) -> None:
    rows.sort(key=lambda pair: (pair[0], pair[1]))
    with MeteredBinaryWriter(path, meter, phase="measurement", label=label) as writer:
        for key, payload in rows:
            writer.write(encode_frame(key, payload))


def _merge_runs(run_paths: list[Path], output: Path, meter: WorkspaceMeter, label: str) -> None:
    iterators = [iter(read_frames(path)) for path in run_paths]
    heap: list[tuple[bytes, bytes, int]] = []
    for index, iterator in enumerate(iterators):
        try:
            key, payload = next(iterator)
        except StopIteration:
            continue
        heap.append((key, payload, index))
    heapq.heapify(heap)
    with MeteredBinaryWriter(output, meter, phase="measurement", label=label) as writer:
        previous: tuple[bytes, bytes] | None = None
        while heap:
            key, payload, index = heapq.heappop(heap)
            current = (key, payload)
            if previous is not None and current < previous:
                raise R11AV2StorageError("external merge order regression")
            writer.write(encode_frame(key, payload))
            previous = current
            try:
                next_key, next_payload = next(iterators[index])
            except StopIteration:
                continue
            heapq.heappush(heap, (next_key, next_payload, index))


def _exact_multiset_verify(
    source: Path,
    destination: Path,
    database: Path,
    meter: WorkspaceMeter,
) -> None:
    meter.reserve(max(source.stat().st_size * 2, 4_194_304), "SQLite multiset verifier", phase="measurement")
    if database.exists():
        meter.checked_unlink(database, phase="measurement")
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA temp_store=FILE")
        connection.execute("CREATE TABLE multiplicity (record BLOB PRIMARY KEY, n INTEGER NOT NULL) WITHOUT ROWID")
        batch: list[tuple[bytes]] = []
        for key, payload in read_frames(source):
            batch.append((encode_frame(key, payload),))
            if len(batch) >= SQLITE_BATCH:
                connection.executemany(
                    "INSERT INTO multiplicity(record,n) VALUES(?,1) ON CONFLICT(record) DO UPDATE SET n=n+1",
                    batch,
                )
                connection.commit()
                batch.clear()
                meter.after_mutation("SQLite source multiplicity batch", phase="measurement")
        if batch:
            connection.executemany(
                "INSERT INTO multiplicity(record,n) VALUES(?,1) ON CONFLICT(record) DO UPDATE SET n=n+1",
                batch,
            )
            connection.commit()
            meter.after_mutation("SQLite source multiplicity tail", phase="measurement")
        batch2: list[tuple[bytes]] = []
        for key, payload in read_frames(destination):
            batch2.append((encode_frame(key, payload),))
            if len(batch2) >= SQLITE_BATCH:
                for (record,) in batch2:
                    cursor = connection.execute("UPDATE multiplicity SET n=n-1 WHERE record=? AND n>0", (record,))
                    if cursor.rowcount != 1:
                        raise R11AV2StorageError("sorted destination contains absent or excess record")
                connection.commit()
                batch2.clear()
                meter.after_mutation("SQLite destination multiplicity batch", phase="measurement")
        if batch2:
            for (record,) in batch2:
                cursor = connection.execute("UPDATE multiplicity SET n=n-1 WHERE record=? AND n>0", (record,))
                if cursor.rowcount != 1:
                    raise R11AV2StorageError("sorted destination contains absent or excess record")
            connection.commit()
            meter.after_mutation("SQLite destination multiplicity tail", phase="measurement")
        remaining = connection.execute("SELECT COUNT(*) FROM multiplicity WHERE n != 0").fetchone()[0]
        if remaining != 0:
            raise R11AV2StorageError("sorted destination omitted source multiplicity")
    finally:
        connection.close()
    meter.checked_unlink(database, missing_ok=False, phase="measurement")


def external_sort_partition(
    source: Path,
    destination: Path,
    *,
    scratch: Path,
    meter: WorkspaceMeter,
    memory_limit_bytes: int,
) -> SortResult:
    if memory_limit_bytes < 1:
        raise R11AV2StorageError("sort memory must be positive")
    scratch.mkdir(parents=True, exist_ok=True)
    source_digest = hashlib.sha256()
    source_count = 0
    source_bytes = 0
    rows: list[tuple[bytes, bytes]] = []
    rows_bytes = 0
    runs: list[Path] = []
    for key, payload in read_frames(source):
        encoded = encode_frame(key, payload)
        source_digest.update(encoded)
        source_count += 1
        source_bytes += len(encoded)
        rows.append((key, payload))
        rows_bytes += len(encoded)
        if rows_bytes >= memory_limit_bytes:
            run = scratch / f"run-{len(runs):06d}.frames"
            _write_run(run, rows, meter, f"write sort run {len(runs)}")
            runs.append(run)
            rows = []
            rows_bytes = 0
    if rows or not runs:
        run = scratch / f"run-{len(runs):06d}.frames"
        _write_run(run, rows, meter, f"write sort run {len(runs)}")
        runs.append(run)
    _merge_runs(runs, destination, meter, "merge sorted partition")
    sorted_digest = hashlib.sha256()
    sorted_count = 0
    sorted_bytes = 0
    previous: tuple[bytes, bytes] | None = None
    for key, payload in read_frames(destination):
        current = (key, payload)
        if previous is not None and current < previous:
            raise R11AV2StorageError("destination is not globally sorted")
        encoded = encode_frame(key, payload)
        sorted_digest.update(encoded)
        sorted_count += 1
        sorted_bytes += len(encoded)
        previous = current
    if source_count != sorted_count or source_bytes != sorted_bytes:
        raise R11AV2StorageError("external sort count or byte conservation failed")
    verifier = scratch / "multiset.sqlite"
    _exact_multiset_verify(source, destination, verifier, meter)
    for run in runs:
        meter.checked_unlink(run, missing_ok=False, phase="measurement")
    if scratch.exists() and not any(scratch.iterdir()):
        scratch.rmdir()
        meter.after_mutation("remove empty sort scratch", phase="measurement")
    return SortResult(
        source_record_count=source_count,
        source_logical_bytes=source_bytes,
        source_stream_sha256=source_digest.hexdigest(),
        sorted_record_count=sorted_count,
        sorted_logical_bytes=sorted_bytes,
        sorted_stream_sha256=sorted_digest.hexdigest(),
        exact_multiset_verified=True,
    )


@dataclass(frozen=True, slots=True)
class GroupSpool:
    equality_key: bytes
    path: Path
    record_count: int
    logical_bytes: int

    def rows(self) -> Iterator[tuple[bytes, bytes]]:
        return read_frames(self.path)


def iter_group_spools(
    sorted_path: Path,
    *,
    spool_root: Path,
    meter: WorkspaceMeter,
    maximum_group_bytes: int,
) -> Iterator[GroupSpool]:
    spool_root.mkdir(parents=True, exist_ok=True)
    current_key: bytes | None = None
    writer: MeteredBinaryWriter | None = None
    path: Path | None = None
    count = 0
    logical = 0
    group_ordinal = 0
    try:
        for key, payload in read_frames(sorted_path):
            if current_key is None or key != current_key:
                if writer is not None and path is not None and current_key is not None:
                    writer.close()
                    yield GroupSpool(current_key, path, count, logical)
                    if path.exists():
                        raise R11AV2StorageError("caller must delete each yielded group spool before advancing")
                    group_ordinal += 1
                current_key = key
                path = spool_root / f"group-{group_ordinal:09d}.frames"
                writer = MeteredBinaryWriter(path, meter, phase="measurement", label="write group spool")
                count = 0
                logical = 0
            encoded = encode_frame(key, payload)
            if logical + len(encoded) > maximum_group_bytes:
                raise R11AV2StorageError("single equality-key group exceeds spool cap")
            if writer is None:
                raise R11AV2StorageError("group spool writer absent")
            writer.write(encoded)
            count += 1
            logical += len(encoded)
        if writer is not None and path is not None and current_key is not None:
            writer.close()
            yield GroupSpool(current_key, path, count, logical)
            if path.exists():
                raise R11AV2StorageError("caller must delete final group spool")
    finally:
        if writer is not None:
            writer.close()


class AtomicOutputDirectory(AbstractContextManager["AtomicOutputDirectory"]):
    def __init__(
        self,
        *,
        parent: Path,
        final_name: str,
        meter: WorkspaceMeter,
    ) -> None:
        if not _is_within(parent, meter.root):
            raise R11AV2StorageError("artifact parent escapes metered workspace")
        self.parent = parent
        self.final = parent / final_name
        self.staging = parent / f".{final_name}.staging"
        self.meter = meter
        self._committed = False

    def __enter__(self) -> "AtomicOutputDirectory":
        self.parent.mkdir(parents=True, exist_ok=True)
        if self.final.exists() or self.staging.exists():
            raise R11AV2StorageError("artifact output path already exists")
        self.staging.mkdir()
        self.meter.after_mutation("create artifact staging", phase="packaging")
        return self

    def commit(self) -> Path:
        if self._committed:
            raise R11AV2StorageError("artifact already committed")
        self.meter.checkpoint("before artifact rename", phase="packaging")
        os.replace(self.staging, self.final)
        try:
            self.meter.after_mutation("artifact rename", phase="packaging")
        except BaseException:
            if self.final.exists():
                shutil.rmtree(self.final)
            if self.final.exists():
                raise R11AV2StorageError("failed to remove final artifact after post-rename failure")
            self.meter.after_mutation("rollback failed artifact rename", phase="packaging")
            raise
        self._committed = True
        return self.final

    def __exit__(self, exc_type, exc, tb) -> bool:
        cleanup_error: BaseException | None = None
        if not self._committed and self.staging.exists():
            try:
                self.meter.checked_rmtree(self.staging, phase="packaging")
            except BaseException as cleanup_exc:
                cleanup_error = cleanup_exc
        if exc is None and cleanup_error is not None:
            raise R11AV2StorageError(f"artifact staging cleanup failed: {cleanup_error}")
        return False
