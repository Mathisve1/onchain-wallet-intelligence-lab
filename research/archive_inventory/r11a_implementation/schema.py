from __future__ import annotations

import hashlib
import re
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Mapping, Sequence


class R11ASchemaError(ValueError):
    """Raised when deterministic evidence serialization is ambiguous."""


EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

SCIENTIFIC_CONTAINERS: tuple[tuple[str, str], ...] = (
    ("taxonomy_unit_ledger", "r11a-taxonomy-units.ndjson"),
    ("complete_block_overlap_matrix", "r11a-block-overlap-matrix.ndjson"),
    ("duplicate_observation_output", "r11a-duplicate-observations.ndjson"),
    ("exact_block_replay_proofs", "r11a-exact-block-replay-proofs.ndjson"),
    ("expected_counterparty_pair_proofs", "r11a-expected-counterparty-pair-proofs.ndjson"),
    ("retained_protocol_trade_group_member_ledger", "r11a-protocol-trade-group-members.ndjson"),
    ("schema_violation_evidence_ledger", "r11a-schema-violation-evidence.ndjson"),
)

METADATA_CONTAINERS: tuple[tuple[str, str], ...] = (
    ("execution_context", "r11a-context.json"),
    ("global_result_and_container_references", "r11a-result.json"),
    ("object_transport_and_two_pass_conservation_ledger", "r11a-object-two-pass-conservation.ndjson"),
    ("reducer_partition_conservation_ledger", "r11a-reducer-partition-conservation.ndjson"),
    ("taxonomy_conservation_ledger", "r11a-taxonomy-conservation.json"),
    ("resource_and_cap_conservation_ledger", "r11a-resource-cap-conservation.json"),
    ("preflight_and_stop_evidence_ledger", "r11a-preflight-stop-evidence.json"),
    ("empty_forbidden_wallet_feature_output", "r11a-wallet-features.ndjson"),
    ("collector_return_code", "r11a.rc"),
)

PACKAGE_CONTAINERS: tuple[tuple[str, str], ...] = (
    ("hash_manifest", "R11A_FILES.sha256"),
    ("package_boundary_record", "r11a-package-boundary.txt"),
)

ALL_CONTAINER_PATHS = tuple(path for _, path in SCIENTIFIC_CONTAINERS + METADATA_CONTAINERS + PACKAGE_CONTAINERS)


def _string_bytes(value: str) -> bytes:
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise R11ASchemaError("surrogate or invalid Unicode string") from exc
    out = bytearray(b'"')
    for byte in encoded:
        if byte == 0x22:
            out.extend(b'\\"')
        elif byte == 0x5C:
            out.extend(b"\\\\")
        elif byte == 0x08:
            out.extend(b"\\b")
        elif byte == 0x0C:
            out.extend(b"\\f")
        elif byte == 0x0A:
            out.extend(b"\\n")
        elif byte == 0x0D:
            out.extend(b"\\r")
        elif byte == 0x09:
            out.extend(b"\\t")
        elif byte < 0x20:
            out.extend(f"\\u00{byte:02x}".encode("ascii"))
        else:
            out.append(byte)
    out.append(0x22)
    return bytes(out)


def _decimal_bytes(value: Decimal) -> bytes:
    if not value.is_finite():
        raise R11ASchemaError("non-finite decimal forbidden")
    if value.is_zero():
        return b"0"
    sign, raw_digits, exponent = value.as_tuple()
    digits = list(raw_digits)
    while digits and digits[-1] == 0:
        digits.pop()
        exponent += 1
    coefficient = "".join(str(item) for item in digits)
    if sign:
        coefficient = "-" + coefficient
    return coefficient.encode("ascii") + b"e" + str(exponent).encode("ascii")


def deterministic_json_bytes(
    value: object,
    *,
    sort_mapping_keys: bool = False,
    _depth: int = 0,
    _seen: set[int] | None = None,
) -> bytes:
    if _depth > 128:
        raise R11ASchemaError("deterministic JSON nesting depth exceeds 128")
    if value is None:
        return b"null"
    if type(value) is bool:
        return b"true" if value else b"false"
    if type(value) is int:
        return str(value).encode("ascii")
    if isinstance(value, Decimal):
        return _decimal_bytes(value)
    if type(value) is float:
        raise R11ASchemaError("binary float forbidden")
    if type(value) is str:
        return _string_bytes(value)
    seen = set() if _seen is None else _seen
    if isinstance(value, (list, tuple, Mapping)):
        object_id = id(value)
        if object_id in seen:
            raise R11ASchemaError("cycle forbidden")
        seen.add(object_id)
        try:
            if isinstance(value, (list, tuple)):
                return b"[" + b",".join(
                    deterministic_json_bytes(
                        item,
                        sort_mapping_keys=sort_mapping_keys,
                        _depth=_depth + 1,
                        _seen=seen,
                    )
                    for item in value
                ) + b"]"
            items = list(value.items())
            if any(type(key) is not str for key, _ in items):
                raise R11ASchemaError("mapping keys must be strings")
            if sort_mapping_keys:
                items.sort(key=lambda pair: pair[0].encode("utf-8", errors="strict"))
            encoded_items = []
            for key, item in items:
                encoded_items.append(
                    _string_bytes(key)
                    + b":"
                    + deterministic_json_bytes(
                        item,
                        sort_mapping_keys=sort_mapping_keys,
                        _depth=_depth + 1,
                        _seen=seen,
                    )
                )
            return b"{" + b",".join(encoded_items) + b"}"
        finally:
            seen.remove(object_id)
    raise R11ASchemaError(f"unsupported deterministic JSON type: {type(value).__name__}")


def deterministic_json_document(value: object, *, sort_mapping_keys: bool = False) -> bytes:
    return deterministic_json_bytes(value, sort_mapping_keys=sort_mapping_keys) + b"\n"


def deterministic_ndjson(rows: Iterable[Mapping[str, object]]) -> bytes:
    output = bytearray()
    for row in rows:
        if not isinstance(row, Mapping):
            raise R11ASchemaError("NDJSON row must be mapping")
        output.extend(deterministic_json_bytes(row))
        output.append(0x0A)
    return bytes(output)


def file_reference(path: str, data: bytes, *, logical_status: str | None = None) -> dict[str, object]:
    if path not in ALL_CONTAINER_PATHS:
        raise R11ASchemaError(f"unregistered artifact path: {path}")
    result: dict[str, object] = {
        "path": path,
        "sha256": hashlib.sha256(data).hexdigest(),
        "byte_count": len(data),
    }
    if logical_status is not None:
        result["logical_status"] = logical_status
    return result


def render_hash_manifest(files: Mapping[str, bytes]) -> bytes:
    forbidden = {"R11A_FILES.sha256", "r11a-package-boundary.txt"}
    if forbidden & set(files):
        raise R11ASchemaError("manifest input must exclude itself and package boundary")
    unexpected = set(files) - set(ALL_CONTAINER_PATHS)
    if unexpected:
        raise R11ASchemaError(f"unregistered manifest entries: {sorted(unexpected)}")
    rows = [f"{hashlib.sha256(files[path]).hexdigest()}  {path}" for path in sorted(files)]
    return ("\n".join(rows) + "\n").encode("ascii")


def verify_hash_manifest(manifest: bytes, files: Mapping[str, bytes]) -> None:
    seen: set[str] = set()
    lines = manifest.decode("ascii", errors="strict").splitlines()
    if lines != sorted(lines, key=lambda line: line.split("  ", 1)[1]):
        raise R11ASchemaError("hash manifest is not path sorted")
    for line in lines:
        digest, separator, path = line.partition("  ")
        if separator != "  " or SHA256_RE.fullmatch(digest) is None:
            raise R11ASchemaError("invalid hash manifest row")
        if path in seen or path not in files:
            raise R11ASchemaError("duplicate or unknown hash manifest path")
        if hashlib.sha256(files[path]).hexdigest() != digest:
            raise R11ASchemaError(f"hash manifest mismatch: {path}")
        seen.add(path)
    if seen != set(files):
        raise R11ASchemaError("hash manifest file set mismatch")


BOUNDARY_FIELDS = (
    "schema_version_R11A_PACKAGE_BOUNDARY_V1",
    "scientific_output_bytes",
    "other_metadata_bytes_excluding_this_record",
    "this_record_bytes",
    "total_metadata_bytes",
    "final_staging_bytes",
    "reserved_metadata_limit_bytes",
    "artifact_limit_bytes",
    "metadata_within_reservation",
    "final_staging_within_artifact_limit",
    "preupload_elapsed_runtime_milliseconds",
    "hard_runtime_limit_milliseconds",
    "minimum_upload_window_milliseconds",
    "preupload_runtime_within_hard_limit_after_upload_window",
    "preupload_peak_workspace_bytes",
    "filesystem_allocation_unit_bytes",
    "boundary_overwrite_allocation_reservation_bytes",
    "workspace_limit_bytes",
    "boundary_write_within_workspace_limit",
)


def _n20(value: int) -> str:
    if type(value) is not int or not 0 <= value < 10**20:
        raise R11ASchemaError("boundary integer outside 20-digit range")
    return f"{value:020d}"


def render_package_boundary(
    *,
    scientific_output_bytes: int,
    other_metadata_bytes_excluding_this_record: int,
    reserved_metadata_limit_bytes: int,
    artifact_limit_bytes: int,
    preupload_elapsed_runtime_milliseconds: int,
    hard_runtime_limit_milliseconds: int,
    minimum_upload_window_milliseconds: int,
    preupload_peak_workspace_bytes: int,
    filesystem_allocation_unit_bytes: int,
    boundary_overwrite_allocation_reservation_bytes: int,
    workspace_limit_bytes: int,
) -> bytes:
    total_metadata = other_metadata_bytes_excluding_this_record + 1024
    final_staging = scientific_output_bytes + total_metadata
    fields = (
        "R11A_PACKAGE_BOUNDARY_V1",
        _n20(scientific_output_bytes),
        _n20(other_metadata_bytes_excluding_this_record),
        _n20(1024),
        _n20(total_metadata),
        _n20(final_staging),
        _n20(reserved_metadata_limit_bytes),
        _n20(artifact_limit_bytes),
        "1" if total_metadata <= reserved_metadata_limit_bytes else "0",
        "1" if final_staging <= artifact_limit_bytes else "0",
        _n20(preupload_elapsed_runtime_milliseconds),
        _n20(hard_runtime_limit_milliseconds),
        _n20(minimum_upload_window_milliseconds),
        "1" if preupload_elapsed_runtime_milliseconds <= hard_runtime_limit_milliseconds - minimum_upload_window_milliseconds else "0",
        _n20(preupload_peak_workspace_bytes),
        _n20(filesystem_allocation_unit_bytes),
        _n20(boundary_overwrite_allocation_reservation_bytes),
        _n20(workspace_limit_bytes),
        "1" if preupload_peak_workspace_bytes + boundary_overwrite_allocation_reservation_bytes <= workspace_limit_bytes else "0",
    )
    raw = "|".join(fields).encode("ascii")
    if len(raw) > 1023:
        raise R11ASchemaError("package boundary fields exceed fixed record")
    return raw + b" " * (1023 - len(raw)) + b"\n"


def verify_package_boundary(data: bytes) -> None:
    if len(data) != 1024 or not data.endswith(b"\n"):
        raise R11ASchemaError("package boundary must be fixed 1024 bytes")
    text = data[:-1].rstrip(b" ").decode("ascii", errors="strict")
    fields = text.split("|")
    if len(fields) != len(BOUNDARY_FIELDS) or fields[0] != "R11A_PACKAGE_BOUNDARY_V1":
        raise R11ASchemaError("package boundary schema drift")
    if any(value not in {"0", "1"} for value in (fields[8], fields[9], fields[13], fields[18])):
        raise R11ASchemaError("package boundary boolean drift")


def write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("wb") as handle:
        handle.write(data)
        handle.flush()
    temp.replace(path)
