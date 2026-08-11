from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .canonical import canonical_json_bytes, json_document_bytes
from .storage import AtomicOutputDirectory, ReservedWriter, RuntimeGuard, StorageError, Workspace

SCIENCE_FILES = (
    "r11a-taxonomy-units.ndjson",
    "r11a-block-overlap-matrix.ndjson",
    "r11a-duplicate-observations.ndjson",
    "r11a-exact-block-replay-proofs.ndjson",
    "r11a-expected-counterparty-pair-proofs.ndjson",
    "r11a-protocol-trade-group-members.ndjson",
    "r11a-schema-violation-evidence.ndjson",
)
WALLET_FEATURE_FILE = "r11a-wallet-features.ndjson"


class OutputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class FileEvidence:
    path: str
    sha256: str
    byte_count: int


def _write_bytes(path: Path, data: bytes, workspace: Workspace, phase: str) -> FileEvidence:
    with ReservedWriter(path, workspace) as writer:
        writer.write(data, phase)
    return FileEvidence(path.name, hashlib.sha256(data).hexdigest(), len(data))


def write_ndjson_stream(
    path: Path,
    rows: Iterable[Mapping[str, object]],
    *,
    workspace: Workspace,
    phase: str,
    maximum_bytes: int,
) -> FileEvidence:
    digest = hashlib.sha256()
    byte_count = 0
    with ReservedWriter(path, workspace) as writer:
        for row in rows:
            payload = canonical_json_bytes(row) + b"\n"
            if byte_count + len(payload) > maximum_bytes:
                raise OutputError(f"scientific container cap exceeded: {path.name}")
            writer.write(payload, phase)
            digest.update(payload)
            byte_count += len(payload)
    return FileEvidence(path.name, digest.hexdigest(), byte_count)


def _boundary_record(
    *,
    metadata_bytes: int,
    final_staging_bytes: int,
    artifact_limit: int,
    runtime_elapsed_seconds: int,
    hard_runtime_seconds: int,
    upload_reservation_seconds: int,
    workspace_bytes: int,
    workspace_limit: int,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "metadata_bytes": metadata_bytes,
        "metadata_reservation_bytes": 4 * 1024 * 1024,
        "metadata_within_reservation": metadata_bytes <= 4 * 1024 * 1024,
        "final_staging_bytes": final_staging_bytes,
        "artifact_limit_bytes": artifact_limit,
        "final_staging_within_artifact_limit": final_staging_bytes <= artifact_limit,
        "runtime_elapsed_seconds": runtime_elapsed_seconds,
        "hard_runtime_seconds": hard_runtime_seconds,
        "upload_reservation_seconds": upload_reservation_seconds,
        "preupload_runtime_within_hard_limit_after_upload_window": (
            runtime_elapsed_seconds < hard_runtime_seconds - upload_reservation_seconds
        ),
        "workspace_bytes": workspace_bytes,
        "workspace_limit_bytes": workspace_limit,
        "boundary_write_within_workspace_limit": workspace_bytes <= workspace_limit,
    }


def verify_boundary_record(record: Mapping[str, object]) -> None:
    required = {
        "metadata_within_reservation",
        "final_staging_within_artifact_limit",
        "preupload_runtime_within_hard_limit_after_upload_window",
        "boundary_write_within_workspace_limit",
    }
    if not required.issubset(record):
        raise OutputError("package boundary is missing required booleans")
    if any(record[name] is not True for name in required):
        raise OutputError("package boundary boolean is false")
    if bool(record["metadata_within_reservation"]) != (
        int(record["metadata_bytes"]) <= int(record["metadata_reservation_bytes"])
    ):
        raise OutputError("metadata boundary formula mismatch")
    if bool(record["final_staging_within_artifact_limit"]) != (
        int(record["final_staging_bytes"]) <= int(record["artifact_limit_bytes"])
    ):
        raise OutputError("artifact boundary formula mismatch")
    if bool(record["preupload_runtime_within_hard_limit_after_upload_window"]) != (
        int(record["runtime_elapsed_seconds"])
        < int(record["hard_runtime_seconds"]) - int(record["upload_reservation_seconds"])
    ):
        raise OutputError("runtime boundary formula mismatch")
    if bool(record["boundary_write_within_workspace_limit"]) != (
        int(record["workspace_bytes"]) <= int(record["workspace_limit_bytes"])
    ):
        raise OutputError("workspace boundary formula mismatch")


def _pad_boundary(document: bytes, target_bytes: int = 1024) -> bytes:
    if not document.endswith(b"\n"):
        raise OutputError("boundary document must end with newline")
    if len(document) > target_bytes:
        raise OutputError("boundary record exceeds fixed size")
    return document[:-1] + b" " * (target_bytes - len(document)) + b"\n"


def build_failure_package(
    *,
    workspace: Workspace,
    final_directory: Path,
    context: Mapping[str, object],
    object_rows: Sequence[Mapping[str, object]],
    reducer_rows: Sequence[Mapping[str, object]],
    stop_rows: Sequence[Mapping[str, object]],
    resource_rows: Sequence[Mapping[str, object]],
    result: Mapping[str, object],
    return_code: int,
    artifact_limit_bytes: int,
) -> tuple[FileEvidence, ...]:
    """Always produce the same complete, empty-science fail-closed package."""

    if return_code == 0:
        raise OutputError("failure package requires a non-zero return code")
    evidences: list[FileEvidence] = []
    with AtomicOutputDirectory(workspace, final_directory) as atomic:
        root = atomic.staging
        for name in SCIENCE_FILES + (WALLET_FEATURE_FILE,):
            evidences.append(_write_bytes(root / name, b"", workspace, "empty failure science write"))
        metadata_documents = {
            "r11a-context.json": context,
            "r11a-object-ledger.ndjson": list(object_rows),
            "r11a-reducer-ledger.ndjson": list(reducer_rows),
            "r11a-stop-ledger.ndjson": list(stop_rows),
            "r11a-resource-ledger.ndjson": list(resource_rows),
            "r11a-result.json": result,
        }
        for name, value in metadata_documents.items():
            data = (
                b"".join(canonical_json_bytes(row) + b"\n" for row in value)
                if name.endswith(".ndjson")
                else json_document_bytes(value)
            )
            evidences.append(_write_bytes(root / name, data, workspace, "failure metadata write"))
        rc_data = f"{return_code}\n".encode("ascii")
        evidences.append(_write_bytes(root / "r11a.rc", rc_data, workspace, "failure return code write"))
        manifest_lines = [f"{item.sha256}  {item.path}\n" for item in sorted(evidences, key=lambda item: item.path)]
        manifest = "".join(manifest_lines).encode("ascii")
        evidences.append(_write_bytes(root / "R11A_FILES.sha256", manifest, workspace, "failure manifest write"))
        metadata_bytes = sum(item.byte_count for item in evidences)
        final_staging_bytes = sum(path.stat().st_size for path in root.iterdir() if path.is_file())
        workspace_bytes = workspace.checkpoint("before failure package boundary", packaging=True)
        runtime_elapsed = int(workspace.runtime.elapsed_seconds())
        boundary = _boundary_record(
            metadata_bytes=metadata_bytes,
            final_staging_bytes=final_staging_bytes,
            artifact_limit=artifact_limit_bytes,
            runtime_elapsed_seconds=runtime_elapsed,
            hard_runtime_seconds=workspace.runtime.hard_limit_seconds,
            upload_reservation_seconds=workspace.runtime.upload_reservation_seconds,
            workspace_bytes=workspace_bytes,
            workspace_limit=workspace.maximum_bytes,
        )
        verify_boundary_record(boundary)
        boundary_bytes = _pad_boundary(json_document_bytes(boundary))
        evidences.append(_write_bytes(root / "r11a-package-boundary.json", boundary_bytes, workspace, "failure boundary write"))
        final_staging_bytes = sum(path.stat().st_size for path in root.iterdir() if path.is_file())
        if final_staging_bytes > artifact_limit_bytes:
            raise OutputError("failure artifact exceeds artifact cap")
        atomic.commit()
    return tuple(evidences)


def validate_empty_science_package(root: Path) -> None:
    for name in SCIENCE_FILES + (WALLET_FEATURE_FILE,):
        path = root / name
        if not path.is_file() or path.read_bytes() != b"":
            raise OutputError(f"failure package science is not exact zero bytes: {name}")
    boundary_path = root / "r11a-package-boundary.json"
    raw = boundary_path.read_bytes()
    if len(raw) != 1024:
        raise OutputError("package boundary is not exactly 1024 bytes")
    import json

    record = json.loads(raw.decode("utf-8"))
    verify_boundary_record(record)
