from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterable, Iterator, Mapping
from decimal import Decimal
from pathlib import Path
from typing import BinaryIO, Callable

from .identity import FrozenDict, thaw_json
from .limits import R11AV2Limits


class R11AV2SchemaError(ValueError):
    """Raised when deterministic evidence serialization is ambiguous or invalid."""


EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

SCIENTIFIC_CONTAINERS = (
    "r11a-v2-taxonomy-units.ndjson",
    "r11a-v2-block-overlap-matrix.ndjson",
    "r11a-v2-duplicate-observations.ndjson",
    "r11a-v2-exact-block-replay-proofs.ndjson",
    "r11a-v2-expected-counterparty-pair-proofs.ndjson",
    "r11a-v2-protocol-trade-group-members.ndjson",
    "r11a-v2-repeat-intersecting-schema-evidence.ndjson",
)
METADATA_CONTAINERS = (
    "r11a-v2-context.json",
    "r11a-v2-result.json",
    "r11a-v2-object-ledger.ndjson",
    "r11a-v2-reducer-ledger.ndjson",
    "r11a-v2-conservation.json",
    "r11a-v2-resource-ledger.json",
    "r11a-v2-stop-ledger.json",
    "r11a-v2-wallet-features.ndjson",
    "r11a-v2.rc",
)
PACKAGE_CONTAINERS = (
    "R11A_V2_FILES.sha256",
    "r11a-v2-package-boundary.txt",
)
ALL_CONTAINERS = SCIENTIFIC_CONTAINERS + METADATA_CONTAINERS + PACKAGE_CONTAINERS
BOUNDARY_MAGIC = "R11A_V2_PACKAGE_BOUNDARY_V1"
BOUNDARY_FIELDS = (
    "magic",
    "scientific_output_bytes",
    "other_metadata_bytes_excluding_boundary",
    "boundary_bytes",
    "total_metadata_bytes",
    "final_staging_bytes",
    "scientific_limit_bytes",
    "metadata_reservation_bytes",
    "artifact_limit_bytes",
    "scientific_within_limit",
    "metadata_within_reservation",
    "final_staging_within_limit",
    "elapsed_runtime_milliseconds",
    "hard_runtime_limit_milliseconds",
    "minimum_upload_window_milliseconds",
    "runtime_within_upload_reserve",
    "peak_workspace_bytes",
    "boundary_write_reservation_bytes",
    "workspace_limit_bytes",
    "workspace_within_limit",
)


def _string_bytes(value: str) -> bytes:
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise R11AV2SchemaError("invalid Unicode string") from exc
    output = bytearray(b'"')
    for byte in encoded:
        if byte == 0x22:
            output.extend(b'\\"')
        elif byte == 0x5C:
            output.extend(b"\\\\")
        elif byte == 0x08:
            output.extend(b"\\b")
        elif byte == 0x0C:
            output.extend(b"\\f")
        elif byte == 0x0A:
            output.extend(b"\\n")
        elif byte == 0x0D:
            output.extend(b"\\r")
        elif byte == 0x09:
            output.extend(b"\\t")
        elif byte < 0x20:
            output.extend(f"\\u00{byte:02x}".encode("ascii"))
        else:
            output.append(byte)
    output.append(0x22)
    return bytes(output)


def _decimal_bytes(value: Decimal) -> bytes:
    if not value.is_finite():
        raise R11AV2SchemaError("non-finite Decimal forbidden")
    if value.is_zero():
        return b"0"
    sign, digits, exponent = value.as_tuple()
    mutable = list(digits)
    while mutable and mutable[-1] == 0:
        mutable.pop()
        exponent += 1
    coefficient = "".join(str(item) for item in mutable)
    if sign:
        coefficient = "-" + coefficient
    return coefficient.encode("ascii") + b"e" + str(exponent).encode("ascii")


def iter_deterministic_json(
    value: object,
    *,
    _depth: int = 0,
    _seen: set[int] | None = None,
) -> Iterator[bytes]:
    if _depth > 128:
        raise R11AV2SchemaError("deterministic JSON depth exceeds 128")
    if value is None:
        yield b"null"
        return
    if type(value) is bool:
        yield b"true" if value else b"false"
        return
    if type(value) is int:
        yield str(value).encode("ascii")
        return
    if isinstance(value, Decimal):
        yield _decimal_bytes(value)
        return
    if type(value) is float:
        raise R11AV2SchemaError("binary float forbidden")
    if type(value) is str:
        yield _string_bytes(value)
        return
    if isinstance(value, FrozenDict):
        value = value.to_plain()
    seen = set() if _seen is None else _seen
    if isinstance(value, (list, tuple, Mapping)):
        object_id = id(value)
        if object_id in seen:
            raise R11AV2SchemaError("cycle forbidden")
        seen.add(object_id)
        try:
            if isinstance(value, (list, tuple)):
                yield b"["
                for index, item in enumerate(value):
                    if index:
                        yield b"," 
                    yield from iter_deterministic_json(item, _depth=_depth + 1, _seen=seen)
                yield b"]"
                return
            items = list(value.items())
            if any(type(key) is not str for key, _ in items):
                raise R11AV2SchemaError("mapping keys must be strings")
            items.sort(key=lambda pair: pair[0].encode("utf-8", errors="strict"))
            yield b"{"
            for index, (key, item) in enumerate(items):
                if index:
                    yield b"," 
                yield _string_bytes(key)
                yield b":"
                yield from iter_deterministic_json(item, _depth=_depth + 1, _seen=seen)
            yield b"}"
            return
        finally:
            seen.remove(object_id)
    raise R11AV2SchemaError(f"unsupported deterministic JSON type: {type(value).__name__}")


def deterministic_json_bytes(value: object) -> bytes:
    return b"".join(iter_deterministic_json(value))


def deterministic_json_document(value: object) -> bytes:
    return deterministic_json_bytes(value) + b"\n"


def write_json_document(
    handle: BinaryIO,
    value: object,
    *,
    before_write: Callable[[int], None] | None = None,
    after_write: Callable[[], None] | None = None,
) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    for chunk in iter_deterministic_json(value):
        if before_write is not None:
            before_write(len(chunk))
        handle.write(chunk)
        digest.update(chunk)
        count += len(chunk)
        if after_write is not None:
            after_write()
    if before_write is not None:
        before_write(1)
    handle.write(b"\n")
    digest.update(b"\n")
    count += 1
    if after_write is not None:
        after_write()
    return count, digest.hexdigest()


def write_ndjson(
    handle: BinaryIO,
    rows: Iterable[Mapping[str, object]],
    *,
    before_write: Callable[[int], None] | None = None,
    after_write: Callable[[], None] | None = None,
) -> tuple[int, int, str]:
    digest = hashlib.sha256()
    byte_count = 0
    row_count = 0
    for row in rows:
        if not isinstance(row, Mapping):
            raise R11AV2SchemaError("NDJSON row must be a mapping")
        for chunk in iter_deterministic_json(row):
            if before_write is not None:
                before_write(len(chunk))
            handle.write(chunk)
            digest.update(chunk)
            byte_count += len(chunk)
            if after_write is not None:
                after_write()
        if before_write is not None:
            before_write(1)
        handle.write(b"\n")
        digest.update(b"\n")
        byte_count += 1
        row_count += 1
        if after_write is not None:
            after_write()
    return row_count, byte_count, digest.hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def file_reference(path: Path, *, logical_status: str | None = None) -> dict[str, object]:
    if path.name not in ALL_CONTAINERS:
        raise R11AV2SchemaError(f"unregistered artifact path: {path.name}")
    result: dict[str, object] = {
        "path": path.name,
        "sha256": file_sha256(path),
        "byte_count": path.stat().st_size,
    }
    if logical_status is not None:
        result["logical_status"] = logical_status
    return result


def render_hash_manifest(root: Path) -> bytes:
    entries = []
    for name in sorted(set(ALL_CONTAINERS) - set(PACKAGE_CONTAINERS)):
        path = root / name
        if not path.is_file():
            raise R11AV2SchemaError(f"artifact file absent from manifest: {name}")
        entries.append(f"{file_sha256(path)}  {name}")
    return ("\n".join(entries) + "\n").encode("ascii")


def verify_hash_manifest(root: Path) -> None:
    manifest = root / "R11A_V2_FILES.sha256"
    expected = render_hash_manifest(root)
    if not manifest.is_file() or manifest.read_bytes() != expected:
        raise R11AV2SchemaError("artifact hash manifest mismatch")


def _n20(value: int) -> str:
    if type(value) is not int or not 0 <= value < 10**20:
        raise R11AV2SchemaError("boundary integer outside 20-digit range")
    return f"{value:020d}"


def render_package_boundary(
    *,
    scientific_output_bytes: int,
    other_metadata_bytes_excluding_boundary: int,
    elapsed_runtime_milliseconds: int,
    peak_workspace_bytes: int,
    boundary_write_reservation_bytes: int,
    limits: R11AV2Limits,
) -> bytes:
    limits.validate_shape()
    boundary_bytes = limits.package_boundary_bytes
    total_metadata = other_metadata_bytes_excluding_boundary + boundary_bytes
    final_staging = scientific_output_bytes + total_metadata
    values = (
        BOUNDARY_MAGIC,
        _n20(scientific_output_bytes),
        _n20(other_metadata_bytes_excluding_boundary),
        _n20(boundary_bytes),
        _n20(total_metadata),
        _n20(final_staging),
        _n20(limits.maximum_retained_scientific_output_bytes),
        _n20(limits.reserved_non_scientific_package_metadata_bytes),
        _n20(limits.maximum_retained_artifact_bytes),
        "1" if scientific_output_bytes <= limits.maximum_retained_scientific_output_bytes else "0",
        "1" if total_metadata <= limits.reserved_non_scientific_package_metadata_bytes else "0",
        "1" if final_staging <= limits.maximum_retained_artifact_bytes else "0",
        _n20(elapsed_runtime_milliseconds),
        _n20(limits.maximum_runtime_seconds * 1000),
        _n20(limits.minimum_upload_window_seconds * 1000),
        "1" if elapsed_runtime_milliseconds <= (limits.maximum_runtime_seconds - limits.minimum_upload_window_seconds) * 1000 else "0",
        _n20(peak_workspace_bytes),
        _n20(boundary_write_reservation_bytes),
        _n20(limits.maximum_ephemeral_workspace_bytes),
        "1" if peak_workspace_bytes + boundary_write_reservation_bytes <= limits.maximum_ephemeral_workspace_bytes else "0",
    )
    raw = "|".join(values).encode("ascii")
    if len(raw) > boundary_bytes - 1:
        raise R11AV2SchemaError("boundary record exceeds fixed width")
    return raw + b" " * (boundary_bytes - 1 - len(raw)) + b"\n"


def verify_package_boundary(data: bytes, *, limits: R11AV2Limits) -> dict[str, int]:
    limits.validate_shape()
    if len(data) != limits.package_boundary_bytes or not data.endswith(b"\n"):
        raise R11AV2SchemaError("package boundary has wrong byte length")
    text = data[:-1].rstrip(b" ").decode("ascii", errors="strict")
    fields = text.split("|")
    if len(fields) != len(BOUNDARY_FIELDS) or fields[0] != BOUNDARY_MAGIC:
        raise R11AV2SchemaError("package boundary schema drift")
    integers = [int(fields[index]) for index in (1, 2, 3, 4, 5, 6, 7, 8, 12, 13, 14, 16, 17, 18)]
    (
        scientific,
        other_metadata,
        boundary_bytes,
        total_metadata,
        final_staging,
        scientific_limit,
        metadata_limit,
        artifact_limit,
        elapsed_ms,
        hard_ms,
        upload_ms,
        peak_workspace,
        boundary_reservation,
        workspace_limit,
    ) = integers
    if boundary_bytes != limits.package_boundary_bytes:
        raise R11AV2SchemaError("boundary byte projection drift")
    if total_metadata != other_metadata + boundary_bytes:
        raise R11AV2SchemaError("boundary metadata formula drift")
    if final_staging != scientific + total_metadata:
        raise R11AV2SchemaError("boundary staging formula drift")
    if scientific_limit != limits.maximum_retained_scientific_output_bytes:
        raise R11AV2SchemaError("boundary scientific limit drift")
    if metadata_limit != limits.reserved_non_scientific_package_metadata_bytes:
        raise R11AV2SchemaError("boundary metadata limit drift")
    if artifact_limit != limits.maximum_retained_artifact_bytes:
        raise R11AV2SchemaError("boundary artifact limit drift")
    if hard_ms != limits.maximum_runtime_seconds * 1000 or upload_ms != limits.minimum_upload_window_seconds * 1000:
        raise R11AV2SchemaError("boundary runtime limits drift")
    if workspace_limit != limits.maximum_ephemeral_workspace_bytes:
        raise R11AV2SchemaError("boundary workspace limit drift")
    expected_flags = (
        scientific <= scientific_limit,
        total_metadata <= metadata_limit,
        final_staging <= artifact_limit,
        elapsed_ms <= hard_ms - upload_ms,
        peak_workspace + boundary_reservation <= workspace_limit,
    )
    observed_flags = tuple(fields[index] == "1" for index in (9, 10, 11, 15, 19))
    if observed_flags != expected_flags or not all(observed_flags):
        raise R11AV2SchemaError("package boundary contains false or inconsistent gate")
    return {
        "scientific_output_bytes": scientific,
        "total_metadata_bytes": total_metadata,
        "final_staging_bytes": final_staging,
        "elapsed_runtime_milliseconds": elapsed_ms,
        "peak_workspace_bytes": peak_workspace,
    }


def ensure_flat_registered_artifact(root: Path) -> None:
    if not root.is_dir():
        raise R11AV2SchemaError("artifact root absent")
    entries = list(root.iterdir())
    if any(not entry.is_file() for entry in entries):
        raise R11AV2SchemaError("artifact contains subdirectory or non-file entry")
    observed = {entry.name for entry in entries}
    expected = set(ALL_CONTAINERS)
    if observed != expected:
        raise R11AV2SchemaError(f"artifact entry set drift: missing={sorted(expected-observed)} extra={sorted(observed-expected)}")


def write_bytes_fsynced(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
