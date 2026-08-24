from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import heapq
import os
import shutil
import sqlite3
import struct
from collections.abc import Callable, Iterable, Iterator, Sequence
from pathlib import Path
from typing import BinaryIO, Final, TypeVar

from .limits import R11ALimits
from .runtime import RuntimeGuard

_FRAME_HEADER: Final[struct.Struct] = struct.Struct(">I")
_KEY_HEADER: Final[struct.Struct] = struct.Struct(">I")
_DEFAULT_BUFFER_BYTES: Final[int] = 1 << 20
_SQLITE_OVERHEAD_BYTES: Final[int] = 16 << 20
_T = TypeVar("_T")


class StorageBoundaryError(RuntimeError):
    pass


class CleanupBoundaryError(RuntimeError):
    """Marker for cleanup failures that may never become terminal evidence."""


class StorageCleanupError(StorageBoundaryError, CleanupBoundaryError):
    """A cleanup failure that must never be downgraded to terminal evidence."""


@dataclasses.dataclass(frozen=True, slots=True)
class Reservation:
    reservation_id: int
    maximum_bytes: int
    label: str


@dataclasses.dataclass(slots=True)
class _ReservationState:
    token: Reservation
    accounted_bytes: int = 0


class WorkspaceMeter:
    """Single-root accounting with reservation before, checkpoint after mutation."""

    def __init__(self, root: Path, limits: R11ALimits, runtime_guard: RuntimeGuard) -> None:
        self.root = root.resolve()
        self.limits = limits
        self.runtime_guard = runtime_guard
        self._known_bytes = 0
        self._peak_known_bytes = 0
        self._peak_bounded_bytes = 0
        self._next_id = 0
        self._reservations: dict[int, _ReservationState] = {}
        self._owned_iterators: list[tuple[str, Iterator[object]]] = []
        self._iterator_cleanup_failure: StorageCleanupError | None = None

    def bootstrap(self) -> None:
        self.runtime_guard.check_scientific_phase("workspace bootstrap before")
        self.root.mkdir(parents=True, exist_ok=True)
        if any(self.root.iterdir()):
            raise StorageBoundaryError("workspace root must start empty")
        if shutil.disk_usage(self.root).free < self.limits.minimum_free_workspace_bytes_before_oidc:
            raise StorageBoundaryError("pre-OIDC free workspace is below the frozen threshold")
        self._known_bytes = 0
        self._record_peak()
        self.runtime_guard.check_scientific_phase("workspace bootstrap after")

    @property
    def known_bytes(self) -> int:
        return self._known_bytes

    @property
    def reserved_bytes(self) -> int:
        return sum(
            state.token.maximum_bytes - state.accounted_bytes
            for state in self._reservations.values()
        )

    @property
    def peak_known_bytes(self) -> int:
        return self._peak_known_bytes

    @property
    def peak_bounded_bytes(self) -> int:
        return self._peak_bounded_bytes

    def _record_peak(self) -> None:
        self._peak_known_bytes = max(self._peak_known_bytes, self._known_bytes)
        self._peak_bounded_bytes = max(
            self._peak_bounded_bytes,
            self._known_bytes + self.reserved_bytes,
        )

    def own_iterator(
        self,
        iterator: Iterator[_T],
        *,
        label: str,
    ) -> Iterator[_T]:
        if self._iterator_cleanup_failure is not None:
            raise self._iterator_cleanup_failure
        owned: Iterator[_T]

        def _owned() -> Iterator[_T]:
            try:
                with cleanup_checked_iterator(iterator, label=label) as values:
                    for value in values:
                        yield value
            finally:
                # Exhausted iterators must not accumulate in the strong
                # ownership registry.  Abandoned iterators remain registered
                # until the runner reaches its synchronous cleanup boundary.
                self._owned_iterators = [
                    entry for entry in self._owned_iterators if entry[1] is not owned
                ]

        owned = _owned()
        self._owned_iterators.append((label, owned))
        return owned

    def close_owned_iterators(self) -> None:
        if self._iterator_cleanup_failure is not None:
            raise self._iterator_cleanup_failure
        owned = self._owned_iterators
        self._owned_iterators = []
        errors: list[BaseException] = []
        for label, iterator in reversed(owned):
            close = getattr(iterator, "close", None)
            if close is None:
                continue
            try:
                close()
            except BaseException as exc:
                errors.append(
                    StorageCleanupError(f"{label} iterator cleanup failed")
                )
                errors[-1].__cause__ = exc
        if errors:
            failure = StorageCleanupError("owned iterator cleanup failed")
            self._iterator_cleanup_failure = failure
            raise failure from errors[0]

    def _ensure_inside(self, path: Path) -> Path:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise StorageBoundaryError("path escapes the single measured workspace root") from exc
        return resolved

    def reserve(self, maximum_bytes: int, label: str, *, packaging: bool = False) -> Reservation:
        if type(maximum_bytes) is not int or maximum_bytes < 0:
            raise StorageBoundaryError("workspace reservation must be nonnegative integer")
        self._check_runtime(packaging, f"reserve {label} before")
        if self._known_bytes + self.reserved_bytes + maximum_bytes > self.limits.maximum_ephemeral_workspace_bytes:
            raise StorageBoundaryError(f"workspace reservation would exceed cap: {label}")
        token = Reservation(self._next_id, maximum_bytes, label)
        self._next_id += 1
        self._reservations[token.reservation_id] = _ReservationState(token)
        try:
            self._record_peak()
            self._check_runtime(packaging, f"reserve {label} after")
        except BaseException:
            # The caller never receives the token when the post-reservation
            # boundary fails, so this method must unwind its own ownership.
            self._reservations.pop(token.reservation_id, None)
            raise
        return token

    def _check_runtime(self, packaging: bool, phase: str) -> None:
        if packaging:
            self.runtime_guard.check_packaging_phase(phase)
        else:
            self.runtime_guard.check_scientific_phase(phase)

    @staticmethod
    def _size(path: Path) -> int:
        if not path.exists():
            return 0
        return directory_size(path) if path.is_dir() else path.stat().st_size

    def checkpoint(
        self,
        reservation: Reservation,
        path: Path,
        *,
        packaging: bool = False,
        phase: str,
    ) -> int:
        self._check_runtime(packaging, f"{phase} before checkpoint")
        state = self._reservations.get(reservation.reservation_id)
        if state is None or state.token != reservation:
            raise StorageBoundaryError("unknown workspace reservation")
        resolved = self._ensure_inside(path)
        actual = self._size(resolved)
        if actual > reservation.maximum_bytes:
            raise StorageBoundaryError(f"workspace mutation exceeded reservation: {reservation.label}")
        delta = actual - state.accounted_bytes
        self._known_bytes += delta
        state.accounted_bytes = actual
        if self._known_bytes < 0:
            raise StorageBoundaryError("workspace accounting became negative")
        if self._known_bytes + self.reserved_bytes > self.limits.maximum_ephemeral_workspace_bytes:
            raise StorageBoundaryError("workspace cap exceeded after mutation checkpoint")
        self._record_peak()
        self._check_runtime(packaging, f"{phase} after checkpoint")
        return actual

    def checkpoint_value(
        self,
        reservation: Reservation,
        actual_bytes: int,
        *,
        packaging: bool = False,
        phase: str,
    ) -> int:
        """Checkpoint the exact bytes owned by one shared-directory category.

        A path checkpoint is appropriate only when a reservation exclusively
        owns that path.  Artifact science and metadata intentionally share one
        staging directory, so measuring the directory for both reservations
        would count the same files twice.  Category writers instead supply the
        exact number of bytes they have successfully persisted.
        """

        self._check_runtime(packaging, f"{phase} before checkpoint")
        state = self._reservations.get(reservation.reservation_id)
        if state is None or state.token != reservation:
            raise StorageBoundaryError("unknown category reservation")
        if (
            type(actual_bytes) is not int
            or actual_bytes < 0
            or actual_bytes > reservation.maximum_bytes
        ):
            raise StorageBoundaryError("category bytes exceed reservation")
        self._known_bytes += actual_bytes - state.accounted_bytes
        state.accounted_bytes = actual_bytes
        if self._known_bytes < 0:
            raise StorageBoundaryError("workspace accounting became negative")
        if self._known_bytes + self.reserved_bytes > self.limits.maximum_ephemeral_workspace_bytes:
            raise StorageBoundaryError("workspace cap exceeded after category mutation")
        self._record_peak()
        self._check_runtime(packaging, f"{phase} after checkpoint")
        return actual_bytes

    def finalize(
        self,
        reservation: Reservation,
        path: Path,
        *,
        packaging: bool = False,
        phase: str,
    ) -> int:
        actual = self.checkpoint(
            reservation,
            path,
            packaging=packaging,
            phase=phase,
        )
        state = self._reservations.pop(reservation.reservation_id, None)
        if state is None or state.token != reservation or state.accounted_bytes != actual:
            raise StorageBoundaryError("reservation finalization drift")
        return actual

    def finalize_value(
        self,
        reservation: Reservation,
        actual_bytes: int,
        *,
        packaging: bool = False,
        phase: str,
    ) -> int:
        actual = self.checkpoint_value(
            reservation,
            actual_bytes,
            packaging=packaging,
            phase=phase,
        )
        state = self._reservations.pop(reservation.reservation_id, None)
        if state is None or state.token != reservation or state.accounted_bytes != actual:
            raise StorageBoundaryError("category reservation finalization drift")
        return actual

    def release_deleted(self, reservation: Reservation, path: Path, *, phase: str) -> None:
        resolved = self._ensure_inside(path)
        if resolved.exists():
            raise StorageBoundaryError("reservation release requires deleted path")
        state = self._reservations.pop(reservation.reservation_id, None)
        if state is None or state.token != reservation:
            raise StorageBoundaryError("unknown reservation release")
        self._known_bytes -= state.accounted_bytes
        if self._known_bytes < 0:
            raise StorageBoundaryError("workspace accounting became negative after release")
        self.runtime_guard.check_packaging_phase(f"{phase} after release")

    def release_value(
        self,
        reservation: Reservation,
        *,
        packaging: bool = False,
        phase: str,
    ) -> None:
        """Release a category after its owned files have been removed."""

        self._check_runtime(packaging, f"{phase} before release")
        state = self._reservations.pop(reservation.reservation_id, None)
        if state is None or state.token != reservation:
            raise StorageBoundaryError("unknown category reservation release")
        self._known_bytes -= state.accounted_bytes
        if self._known_bytes < 0:
            raise StorageBoundaryError(
                "workspace accounting became negative after category release"
            )
        self._check_runtime(packaging, f"{phase} after release")

    def delete_file(self, path: Path) -> None:
        try:
            resolved = self._ensure_inside(path)
            self.runtime_guard.check_scientific_phase("delete file before")
            if not resolved.exists():
                return
            if not resolved.is_file() or resolved.is_symlink():
                raise StorageBoundaryError(
                    "delete_file target is not a regular file"
                )
            size = resolved.stat().st_size
            resolved.unlink()
            if resolved.exists():
                raise StorageBoundaryError("file cleanup did not remove target")
            self._known_bytes -= size
            if self._known_bytes < 0:
                raise StorageBoundaryError("workspace accounting became negative")
            self.runtime_guard.check_scientific_phase("delete file after")
        except CleanupBoundaryError:
            raise
        except BaseException as exc:
            raise StorageCleanupError("workspace file cleanup failed") from exc

    def checked_rmtree(self, path: Path) -> None:
        try:
            resolved = self._ensure_inside(path)
            self.runtime_guard.check_packaging_phase("delete directory before")
            if not resolved.exists():
                return
            total = directory_size(resolved)
            shutil.rmtree(resolved)
            if resolved.exists():
                raise StorageBoundaryError(
                    "workspace cleanup did not remove directory"
                )
            self._known_bytes -= total
            if self._known_bytes < 0:
                raise StorageBoundaryError("workspace accounting became negative")
            self.runtime_guard.check_packaging_phase("delete directory after")
        except CleanupBoundaryError:
            raise
        except BaseException as exc:
            raise StorageCleanupError("workspace directory cleanup failed") from exc

    def delete_empty_directory(self, path: Path) -> None:
        """Remove one owned empty directory through the fatal cleanup boundary."""

        try:
            resolved = self._ensure_inside(path)
            self.runtime_guard.check_packaging_phase(
                "delete empty directory before"
            )
            if not resolved.exists():
                return
            if not resolved.is_dir() or resolved.is_symlink():
                raise StorageBoundaryError(
                    "empty-directory cleanup target is not a directory"
                )
            resolved.rmdir()
            if resolved.exists():
                raise StorageBoundaryError(
                    "empty-directory cleanup did not remove target"
                )
            self.runtime_guard.check_packaging_phase(
                "delete empty directory after"
            )
        except CleanupBoundaryError:
            raise
        except BaseException as exc:
            raise StorageCleanupError(
                "workspace empty-directory cleanup failed"
            ) from exc

    def verify_actual_usage(self) -> int:
        self.runtime_guard.check_packaging_phase("verify workspace before")
        actual = directory_size(self.root)
        if actual != self._known_bytes:
            raise StorageBoundaryError(
                f"workspace accounting mismatch: tracked={self._known_bytes} actual={actual}"
            )
        if actual + self.reserved_bytes > self.limits.maximum_ephemeral_workspace_bytes:
            raise StorageBoundaryError("actual workspace usage exceeds cap")
        self._known_bytes = actual
        self._record_peak()
        self.runtime_guard.check_packaging_phase("verify workspace after")
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


@contextlib.contextmanager
def cleanup_checked_binary_reader(
    path: Path,
    *,
    label: str,
) -> Iterator[BinaryIO]:
    """Open a reader whose close failure retains fatal cleanup precedence."""

    handle: BinaryIO | None = None
    try:
        handle = path.open("rb")
        yield handle
    finally:
        if handle is not None:
            try:
                handle.close()
            except BaseException as exc:
                raise StorageCleanupError(f"{label} reader cleanup failed") from exc


@contextlib.contextmanager
def cleanup_checked_binary_writer(
    path: Path,
    *,
    label: str,
) -> Iterator[BinaryIO]:
    """Open an exclusive writer whose close failure remains fatal."""

    handle: BinaryIO | None = None
    try:
        handle = path.open("xb")
        yield handle
    finally:
        if handle is not None:
            try:
                handle.close()
            except BaseException as exc:
                raise StorageCleanupError(f"{label} writer cleanup failed") from exc


def cleanup_checked_read_bytes(path: Path, *, label: str) -> bytes:
    with cleanup_checked_binary_reader(path, label=label) as handle:
        return handle.read()


def cleanup_checked_read_text(
    path: Path,
    *,
    encoding: str,
    label: str,
) -> str:
    return cleanup_checked_read_bytes(path, label=label).decode(encoding)


@contextlib.contextmanager
def cleanup_checked_iterator(
    iterator: Iterator[_T],
    *,
    label: str,
) -> Iterator[Iterator[_T]]:
    """Own a closeable iterator and synchronously surface its cleanup errors."""

    try:
        yield iterator
    finally:
        close = getattr(iterator, "close", None)
        if close is not None:
            try:
                close()
            except CleanupBoundaryError:
                raise
            except BaseException as exc:
                raise StorageCleanupError(f"{label} iterator cleanup failed") from exc


class ReservedBinaryWriter:
    """Bounded buffered file writer; each disk flush is a metered mutation."""

    def __init__(
        self,
        path: Path,
        meter: WorkspaceMeter,
        *,
        maximum_bytes: int,
        label: str,
        packaging: bool = False,
        buffer_bytes: int = _DEFAULT_BUFFER_BYTES,
    ) -> None:
        if buffer_bytes <= 0:
            raise StorageBoundaryError("writer buffer must be positive")
        self.path = meter._ensure_inside(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.meter = meter
        self.packaging = packaging
        self._buffer = bytearray()
        self._buffer_limit = buffer_bytes
        self._written = 0
        self._closed = False
        self._cleanup_failure: StorageCleanupError | None = None
        reservation = meter.reserve(maximum_bytes, label, packaging=packaging)
        path_existed = False
        try:
            path_existed = self.path.exists()
            handle = self.path.open("xb")
        except BaseException:
            errors: list[BaseException] = []
            try:
                if not path_existed and self.path.exists():
                    self.path.unlink()
            except BaseException as exc:
                errors.append(exc)
            try:
                meter.release_value(
                    reservation,
                    packaging=packaging,
                    phase=f"abort construction {label}",
                )
            except BaseException as exc:
                errors.append(exc)
            self._closed = True
            if errors:
                raise StorageCleanupError(
                    "reserved writer construction cleanup failed"
                ) from errors[0]
            raise
        self.reservation = reservation
        self._handle: BinaryIO = handle

    @property
    def written_bytes(self) -> int:
        return self._written + len(self._buffer)

    def write(self, data: bytes) -> None:
        if self._closed:
            raise StorageBoundaryError("write after close")
        if self.written_bytes + len(data) > self.reservation.maximum_bytes:
            raise StorageBoundaryError("writer exceeded pre-reserved byte bound")
        self._buffer.extend(data)
        if len(self._buffer) >= self._buffer_limit:
            self.flush()

    def flush(self) -> None:
        if self._closed or not self._buffer:
            return
        self.meter._check_runtime(self.packaging, f"write {self.reservation.label} before")
        payload = bytes(self._buffer)
        written = self._handle.write(payload)
        if written != len(payload):
            raise StorageBoundaryError("short local file write")
        self._handle.flush()
        self._written += written
        self._buffer.clear()
        self.meter.checkpoint(
            self.reservation,
            self.path,
            packaging=self.packaging,
            phase=f"write {self.reservation.label}",
        )

    def close(self) -> None:
        if self._closed:
            if self._cleanup_failure is not None:
                raise self._cleanup_failure
            return
        try:
            self.flush()
            self._handle.flush()
            os.fsync(self._handle.fileno())
            try:
                self._handle.close()
            except BaseException as exc:
                raise StorageCleanupError(
                    "reserved writer handle cleanup failed"
                ) from exc
            self.meter.finalize(
                self.reservation,
                self.path,
                packaging=self.packaging,
                phase=f"finalize {self.reservation.label}",
            )
        except BaseException as failure:
            try:
                self.abort()
            except BaseException as cleanup_failure:
                raise StorageCleanupError(
                    "reserved writer close cleanup failed"
                ) from cleanup_failure
            if isinstance(failure, StorageCleanupError):
                self._cleanup_failure = failure
            raise
        self._closed = True

    def abort(self) -> None:
        if self._closed:
            if self._cleanup_failure is not None:
                raise self._cleanup_failure
            return
        errors: list[BaseException] = []
        try:
            self._handle.close()
        except BaseException as exc:
            errors.append(exc)
        path_absent = False
        try:
            if self.path.exists():
                self.path.unlink()
            if self.path.exists():
                raise StorageBoundaryError("writer abort did not remove file")
            path_absent = True
        except BaseException as exc:
            errors.append(exc)
        if path_absent:
            try:
                self.meter.release_value(
                    self.reservation,
                    packaging=self.packaging,
                    phase=f"abort {self.reservation.label}",
                )
            except BaseException as exc:
                errors.append(exc)
        self._closed = True
        if errors:
            failure = StorageCleanupError("writer cleanup failed")
            self._cleanup_failure = failure
            raise failure from errors[0]

    def __enter__(self) -> "ReservedBinaryWriter":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is None:
            self.close()
        else:
            self.abort()


def encode_keyed_record(key: bytes, payload: bytes) -> bytes:
    if len(key) > 0xFFFFFFFF:
        raise StorageBoundaryError("sort key exceeds uint32")
    return _KEY_HEADER.pack(len(key)) + key + payload


def decode_keyed_record(record: bytes) -> tuple[bytes, bytes]:
    if len(record) < _KEY_HEADER.size:
        raise StorageBoundaryError("truncated keyed record")
    key_length = _KEY_HEADER.unpack_from(record, 0)[0]
    end = _KEY_HEADER.size + key_length
    if end > len(record):
        raise StorageBoundaryError("truncated keyed record key")
    return record[_KEY_HEADER.size:end], record[end:]


def write_frame(writer: ReservedBinaryWriter, record: bytes) -> None:
    if len(record) > 0xFFFFFFFF:
        raise StorageBoundaryError("framed record exceeds uint32")
    writer.write(_FRAME_HEADER.pack(len(record)))
    writer.write(record)


def iter_frames(path: Path, *, runtime_guard: RuntimeGuard, phase: str) -> Iterator[bytes]:
    runtime_guard.check_scientific_phase(f"{phase} before open")
    with cleanup_checked_binary_reader(path, label="framed stream") as handle:
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
    runtime_guard.check_scientific_phase(f"{phase} after close")


@dataclasses.dataclass(frozen=True, slots=True)
class ExactMultiplicityEvidence:
    source_record_count: int
    destination_record_count: int
    source_distinct_blob_count: int
    destination_distinct_blob_count: int
    exact_sqlite_blob_multiplicity_verified: bool

    def as_mapping(self) -> dict[str, object]:
        return dataclasses.asdict(self)


class ExactSQLiteMultiplicityLedger:
    """Authoritative exact BLOB+multiplicity equality proof for one partition."""

    def __init__(self, path: Path, meter: WorkspaceMeter, maximum_source_bytes: int) -> None:
        self.path = meter._ensure_inside(path)
        self.meter = meter
        maximum = maximum_source_bytes * 3 + _SQLITE_OVERHEAD_BYTES
        self.database = MeteredSQLite(
            self.path,
            meter,
            maximum,
            "exact SQLite multiplicity ledger",
        )
        self.connection = self.database.connection
        with self.database.initializing_transaction(
            "create exact SQLite ledger"
        ) as connection:
            connection.execute(
                "CREATE TABLE source("
                "payload BLOB PRIMARY KEY,"
                "multiplicity INTEGER NOT NULL CHECK(multiplicity>0))"
            )
            connection.execute(
                "CREATE TABLE destination("
                "payload BLOB PRIMARY KEY,"
                "multiplicity INTEGER NOT NULL CHECK(multiplicity>0))"
            )
        self._source_count = 0
        self._destination_count = 0
        self._closed = False

    def _add_batch(self, table: str, values: Sequence[bytes]) -> None:
        if not values:
            return
        if table not in {"source", "destination"}:
            raise StorageBoundaryError("invalid multiplicity table")
        self.meter.runtime_guard.check_scientific_phase(f"SQLite {table} mutation before")
        with self.database.transaction(f"SQLite {table} transaction") as connection:
            connection.executemany(
                f"INSERT INTO {table}(payload,multiplicity) VALUES(?,1) "
                f"ON CONFLICT(payload) DO UPDATE SET multiplicity=multiplicity+1",
                ((sqlite3.Binary(value),) for value in values),
            )
        if table == "source":
            self._source_count += len(values)
        else:
            self._destination_count += len(values)

    def add_source_batch(self, values: Sequence[bytes]) -> None:
        self._add_batch("source", values)

    def add_destination_batch(self, values: Sequence[bytes]) -> None:
        self._add_batch("destination", values)

    def validate(self) -> ExactMultiplicityEvidence:
        self.meter.runtime_guard.check_scientific_phase("validate exact multiplicity before")
        mismatch = self.connection.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT s.payload FROM source s
              LEFT JOIN destination d ON d.payload=s.payload
              WHERE d.payload IS NULL OR d.multiplicity<>s.multiplicity
              UNION ALL
              SELECT d.payload FROM destination d
              LEFT JOIN source s ON s.payload=d.payload
              WHERE s.payload IS NULL
            )
            """
        ).fetchone()[0]
        source_distinct = self.connection.execute("SELECT COUNT(*) FROM source").fetchone()[0]
        destination_distinct = self.connection.execute("SELECT COUNT(*) FROM destination").fetchone()[0]
        if mismatch != 0 or self._source_count != self._destination_count:
            raise StorageBoundaryError("external sort exact BLOB multiplicity mismatch")
        self.meter.runtime_guard.check_scientific_phase("validate exact multiplicity after")
        return ExactMultiplicityEvidence(
            source_record_count=self._source_count,
            destination_record_count=self._destination_count,
            source_distinct_blob_count=int(source_distinct),
            destination_distinct_blob_count=int(destination_distinct),
            exact_sqlite_blob_multiplicity_verified=True,
        )

    def close_delete(self) -> None:
        if self._closed:
            return
        self.database.close_delete()
        self._closed = True


@dataclasses.dataclass(frozen=True, slots=True)
class SortEvidence:
    input_records: int
    output_records: int
    input_logical_bytes: int
    output_logical_bytes: int
    exact_multiplicity: dict[str, object]
    sorted_stream_sha256: str
    output_bytes: int

    def validate(self) -> None:
        if self.input_records != self.output_records:
            raise StorageBoundaryError("external sort changed record count")
        if self.input_logical_bytes != self.output_logical_bytes:
            raise StorageBoundaryError("external sort changed logical byte count")
        if self.exact_multiplicity.get("exact_sqlite_blob_multiplicity_verified") is not True:
            raise StorageBoundaryError("external sort exact multiplicity proof absent")
        if len(self.sorted_stream_sha256) != 64:
            raise StorageBoundaryError("sorted stream SHA-256 malformed")


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
    source_record_count: int,
    source_logical_bytes: int,
    maximum_source_bytes: int,
) -> SortEvidence:
    guard = meter.runtime_guard
    temporary_directory = meter._ensure_inside(temporary_directory)
    temporary_created = False
    ledger: ExactSQLiteMultiplicityLedger | None = None
    runs: list[Path] = []
    readers: list[Iterator[bytes]] = []
    batch: list[bytes] = []
    batch_bytes = 0

    def flush_batch() -> None:
        nonlocal batch, batch_bytes
        if not batch:
            return
        if ledger is None:
            raise StorageBoundaryError("external sort ledger is absent")
        guard.check_scientific_phase("sort chunk before")
        ledger.add_source_batch(batch)
        batch.sort(key=_record_sort_key)
        maximum = sum(_FRAME_HEADER.size + len(record) for record in batch)
        run = temporary_directory / f"run-{len(runs):06d}.frames"
        with ReservedBinaryWriter(run, meter, maximum_bytes=maximum, label="sort run") as writer:
            for record in batch:
                write_frame(writer, record)
        runs.append(run)
        batch = []
        batch_bytes = 0
        guard.check_scientific_phase("sort chunk after")

    try:
        temporary_directory.mkdir(parents=True, exist_ok=False)
        temporary_created = True
        ledger = ExactSQLiteMultiplicityLedger(
            temporary_directory / "exact-multiplicity.sqlite",
            meter,
            maximum_source_bytes,
        )
        source_reader = iter_frames(
            source,
            runtime_guard=guard,
            phase="read unsorted partition",
        )
        readers.append(source_reader)
        for record in source_reader:
            batch.append(record)
            batch_bytes += _FRAME_HEADER.size + len(record)
            if batch_bytes >= meter.limits.maximum_sort_chunk_bytes:
                flush_batch()
        flush_batch()

        output_records = 0
        output_logical = 0
        sorted_stream = hashlib.sha256()
        destination_batch: list[bytes] = []
        with ReservedBinaryWriter(
            destination,
            meter,
            maximum_bytes=maximum_source_bytes,
            label="sorted partition",
        ) as writer:
            iterators = [
                iter_frames(path, runtime_guard=guard, phase="merge sort runs")
                for path in runs
            ]
            readers.extend(iterators)
            heap: list[_HeapItem] = []
            for index, iterator in enumerate(iterators):
                try:
                    record = next(iterator)
                except StopIteration:
                    continue
                heapq.heappush(heap, _HeapItem(_record_sort_key(record), index, record))
            while heap:
                guard.check_scientific_phase("merge sorted partition before")
                item = heapq.heappop(heap)
                write_frame(writer, item.record)
                destination_batch.append(item.record)
                if len(destination_batch) >= 1024:
                    ledger.add_destination_batch(destination_batch)
                    destination_batch.clear()
                output_records += 1
                output_logical += len(item.record)
                sorted_stream.update(_FRAME_HEADER.pack(len(item.record)))
                sorted_stream.update(item.record)
                try:
                    next_record = next(iterators[item.run_index])
                except StopIteration:
                    continue
                heapq.heappush(
                    heap,
                    _HeapItem(_record_sort_key(next_record), item.run_index, next_record),
                )
                guard.check_scientific_phase("merge sorted partition after")
            ledger.add_destination_batch(destination_batch)
        exact = ledger.validate()
        evidence = SortEvidence(
            input_records=source_record_count,
            output_records=output_records,
            input_logical_bytes=source_logical_bytes,
            output_logical_bytes=output_logical,
            exact_multiplicity=exact.as_mapping(),
            sorted_stream_sha256=sorted_stream.hexdigest(),
            output_bytes=destination.stat().st_size,
        )
        evidence.validate()
        return evidence
    finally:
        errors: list[BaseException] = []
        for reader in reversed(readers):
            close = getattr(reader, "close", None)
            if close is None:
                continue
            try:
                close()
            except BaseException as exc:
                errors.append(exc)
        for path in reversed(runs):
            try:
                if path.exists():
                    meter.delete_file(path)
            except BaseException as exc:
                errors.append(exc)
        if ledger is not None:
            try:
                ledger.close_delete()
            except BaseException as exc:
                errors.append(exc)
        if temporary_created:
            try:
                meter.delete_empty_directory(temporary_directory)
            except BaseException as exc:
                errors.append(exc)
        if errors:
            raise StorageCleanupError("external sort cleanup failed") from errors[0]


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
    return meter.own_iterator(
        _iter_equality_group_spools(
            sorted_partition,
            spool_directory,
            meter,
            maximum_group_spool_bytes=maximum_group_spool_bytes,
        ),
        label="equality-group spools",
    )


def _iter_equality_group_spools(
    sorted_partition: Path,
    spool_directory: Path,
    meter: WorkspaceMeter,
    *,
    maximum_group_spool_bytes: int,
) -> Iterator[EqualityGroupSpool]:
    spool_directory = meter._ensure_inside(spool_directory)
    spool_created = False
    current_key: bytes | None = None
    writer: ReservedBinaryWriter | None = None
    path: Path | None = None
    yielded_path: Path | None = None
    source_reader: Iterator[bytes] | None = None
    count = 0
    payload_bytes = 0
    group_index = 0

    def finish() -> EqualityGroupSpool | None:
        nonlocal writer, path, count, payload_bytes
        if writer is None or path is None or current_key is None:
            return None
        writer.close()
        value = EqualityGroupSpool(current_key, path, count, payload_bytes)
        writer = None
        path = None
        count = 0
        payload_bytes = 0
        return value

    try:
        spool_directory.mkdir(parents=True, exist_ok=False)
        spool_created = True
        source_reader = iter_frames(
            sorted_partition,
            runtime_guard=meter.runtime_guard,
            phase="group sorted partition",
        )
        for framed in source_reader:
            key, payload = decode_keyed_record(framed)
            if current_key is None or key != current_key:
                completed = finish()
                if completed is not None:
                    yielded_path = completed.path
                    yield completed
                    meter.delete_file(yielded_path)
                    yielded_path = None
                current_key = key
                path = spool_directory / f"group-{group_index:09d}.frames"
                group_index += 1
                writer = ReservedBinaryWriter(
                    path,
                    meter,
                    maximum_bytes=maximum_group_spool_bytes,
                    label="equality group spool",
                )
            if writer is None:
                raise StorageBoundaryError("group writer not initialized")
            write_frame(writer, payload)
            count += 1
            payload_bytes += len(payload)
        completed = finish()
        if completed is not None:
            yielded_path = completed.path
            yield completed
            meter.delete_file(yielded_path)
            yielded_path = None
    finally:
        errors: list[BaseException] = []
        if writer is not None:
            try:
                writer.abort()
            except BaseException as exc:
                errors.append(exc)
        for owned_path in (yielded_path, path):
            if owned_path is None:
                continue
            try:
                if owned_path.exists():
                    meter.delete_file(owned_path)
            except BaseException as exc:
                errors.append(exc)
        if source_reader is not None:
            close = getattr(source_reader, "close", None)
            if close is not None:
                try:
                    close()
                except BaseException as exc:
                    errors.append(exc)
        if spool_created:
            try:
                if spool_directory.exists() and any(spool_directory.iterdir()):
                    meter.checked_rmtree(spool_directory)
                else:
                    meter.delete_empty_directory(spool_directory)
            except BaseException as exc:
                errors.append(exc)
        if errors:
            raise StorageCleanupError(
                "equality-group spool cleanup failed"
            ) from errors[0]


class MeteredSQLite:
    """Disk-backed bounded state. Every committed transaction is checkpointed."""

    def __init__(self, path: Path, meter: WorkspaceMeter, maximum_bytes: int, label: str) -> None:
        self.path = meter._ensure_inside(path)
        self.meter = meter
        if any(sidecar.exists() for sidecar in self._sidecar_paths()):
            raise StorageBoundaryError("metered SQLite path already exists")
        self.reservation = meter.reserve(maximum_bytes, label)
        self.connection: sqlite3.Connection | None = None
        self._closed = False
        self._cleanup_failure: StorageCleanupError | None = None
        try:
            self.connection = sqlite3.connect(self.path)
            self.connection.execute("PRAGMA journal_mode=DELETE")
            self.connection.execute("PRAGMA synchronous=FULL")
            # SQLite temp state is memory-only; every persistent database and
            # journal byte therefore remains below the one measured root.
            self.connection.execute("PRAGMA temp_store=MEMORY")
            self._checkpoint_sqlite_bytes("initialize metered SQLite")
        except BaseException:
            errors: list[BaseException] = []
            if self.connection is not None:
                try:
                    self.connection.close()
                except BaseException as exc:
                    errors.append(exc)
            for sidecar in self._sidecar_paths():
                try:
                    if sidecar.exists():
                        sidecar.unlink()
                except BaseException as exc:
                    errors.append(exc)
            try:
                sidecars_remain = any(
                    sidecar.exists() for sidecar in self._sidecar_paths()
                )
            except BaseException as exc:
                errors.append(exc)
                sidecars_remain = True
            if sidecars_remain:
                errors.append(
                    StorageBoundaryError(
                        "metered SQLite initialization cleanup left sidecars"
                    )
                )
            else:
                try:
                    self.meter.release_value(
                        self.reservation,
                        phase="abort metered SQLite initialization",
                    )
                except BaseException as exc:
                    errors.append(exc)
            self._closed = True
            if errors:
                raise StorageCleanupError(
                    "metered SQLite initialization cleanup failed"
                ) from errors[0]
            raise

    def _sidecar_paths(self) -> tuple[Path, ...]:
        return (
            self.path,
            Path(f"{self.path}-journal"),
            Path(f"{self.path}-wal"),
            Path(f"{self.path}-shm"),
        )

    def _sqlite_bytes(self) -> int:
        total = 0
        for path in self._sidecar_paths():
            self.meter._ensure_inside(path)
            if path.exists():
                if not path.is_file() or path.is_symlink():
                    raise StorageBoundaryError("SQLite sidecar is not a regular file")
                total += path.stat().st_size
        return total

    def _checkpoint_sqlite_bytes(self, phase: str) -> int:
        return self.meter.checkpoint_value(
            self.reservation,
            self._sqlite_bytes(),
            phase=phase,
        )

    @contextlib.contextmanager
    def transaction(self, phase: str):  # type: ignore[no-untyped-def]
        if self.connection is None:
            raise StorageBoundaryError("metered SQLite connection is unavailable")
        self.meter.runtime_guard.check_scientific_phase(f"{phase} before")
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            yield self.connection
            # DELETE-mode rollback journals remain present until commit.  The
            # pre-commit checkpoint therefore records the transient peak.
            self._checkpoint_sqlite_bytes(f"{phase} precommit")
            self.connection.commit()
        except BaseException:
            errors: list[BaseException] = []
            try:
                self.connection.rollback()
            except BaseException as exc:
                errors.append(exc)
            try:
                self._checkpoint_sqlite_bytes(f"{phase} rollback")
            except BaseException as exc:
                errors.append(exc)
            if errors:
                raise StorageCleanupError(
                    "metered SQLite transaction rollback failed"
                ) from errors[0]
            raise
        self._checkpoint_sqlite_bytes(f"{phase} committed")
        self.meter.runtime_guard.check_scientific_phase(f"{phase} after")

    @contextlib.contextmanager
    def initializing_transaction(self, phase: str):  # type: ignore[no-untyped-def]
        """Construct a schema or delete the newly acquired database on failure."""

        try:
            with self.transaction(phase) as connection:
                yield connection
        except BaseException:
            try:
                self.close_delete()
            except BaseException as cleanup_failure:
                raise StorageCleanupError(
                    "metered SQLite schema construction cleanup failed"
                ) from cleanup_failure
            raise

    def checkpoint(self, phase: str) -> None:
        if self.connection is None:
            raise StorageBoundaryError("metered SQLite connection is unavailable")
        self._checkpoint_sqlite_bytes(f"{phase} precommit")
        self.connection.commit()
        self._checkpoint_sqlite_bytes(f"{phase} committed")

    def close_delete(self) -> None:
        if self._closed:
            if self._cleanup_failure is not None:
                raise self._cleanup_failure
            return
        errors: list[BaseException] = []
        if self.connection is not None:
            try:
                self.connection.close()
            except BaseException as exc:
                errors.append(exc)
        for path in self._sidecar_paths():
            try:
                if path.exists():
                    path.unlink()
            except BaseException as exc:
                errors.append(exc)
        try:
            sidecars_remain = any(
                path.exists() for path in self._sidecar_paths()
            )
        except BaseException as exc:
            errors.append(exc)
            sidecars_remain = True
        if sidecars_remain:
            errors.append(
                StorageBoundaryError("metered SQLite cleanup left sidecars")
            )
        else:
            try:
                self.meter.release_value(
                    self.reservation,
                    phase="delete metered SQLite",
                )
            except BaseException as exc:
                errors.append(exc)
        self._closed = True
        if errors:
            failure = StorageCleanupError("metered SQLite cleanup failed")
            self._cleanup_failure = failure
            raise failure from errors[0]


class AtomicArtifactDirectory:
    """Validate in staging; rename is atomic; post-rename failure is removed."""

    def __init__(self, workspace: Path, meter: WorkspaceMeter, final_name: str) -> None:
        if not final_name or "/" in final_name or ".." in final_name:
            raise StorageBoundaryError("unsafe final artifact directory name")
        self.meter = meter
        self.workspace = meter._ensure_inside(workspace)
        self.final_path = meter._ensure_inside(self.workspace / final_name)
        self.staging_path = meter._ensure_inside(self.workspace / f".{final_name}.staging")
        self._committed = False
        self._rollback_attempted = False
        self._rollback_complete = False
        self._rollback_failure: BaseException | None = None

    @property
    def rollback_attempted(self) -> bool:
        return self._rollback_attempted

    @property
    def rollback_failure(self) -> BaseException | None:
        return self._rollback_failure

    def __enter__(self) -> Path:
        if self.final_path.exists() or self.staging_path.exists():
            raise StorageBoundaryError("artifact output path already exists")
        self.staging_path.mkdir(parents=True)
        return self.staging_path

    def commit(self, validate: Callable[[Path], None]) -> Path:
        if self._committed:
            raise StorageBoundaryError("artifact directory already committed")
        try:
            self.meter.runtime_guard.check_packaging_phase("artifact validation before")
            validate(self.staging_path)
            if directory_size(self.staging_path) > self.meter.limits.maximum_retained_artifact_bytes:
                raise StorageBoundaryError("artifact staging exceeds retained cap")
            self.meter.verify_actual_usage()
            self.staging_path.rename(self.final_path)
            self.meter.runtime_guard.check_packaging_phase("artifact rename after")
            self.meter.verify_actual_usage()
        except Exception as failure:
            try:
                self.rollback()
            except BaseException as rollback_failure:
                raise StorageCleanupError(
                    "atomic artifact commit rollback failed"
                ) from rollback_failure
            raise
        self._committed = True
        return self.final_path

    def rollback(self) -> None:
        """Retry physical cleanup without erasing a prior rollback failure."""

        if self._rollback_failure is not None:
            raise StorageCleanupError(
                "atomic artifact rollback previously failed"
            ) from self._rollback_failure
        if self._rollback_complete:
            return
        if self._rollback_attempted:
            raise StorageCleanupError("atomic artifact rollback state is invalid")
        self._rollback_attempted = True
        self._committed = False
        try:
            for path in (self.final_path, self.staging_path):
                if path.exists():
                    self.meter.checked_rmtree(path)
            if self.final_path.exists() or self.staging_path.exists():
                raise StorageBoundaryError(
                    "atomic artifact rollback left transaction paths"
                )
            self.meter.verify_actual_usage()
        except BaseException as failure:
            self._rollback_failure = failure
            raise StorageCleanupError(
                "atomic artifact rollback failed"
            ) from failure
        self._rollback_complete = True

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._committed:
            return
        self.rollback()
