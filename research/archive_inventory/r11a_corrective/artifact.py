from __future__ import annotations

import dataclasses
import hashlib
import os
import re
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import BinaryIO, Final

from .canonical import FrozenObject, NumberToken, canonical_json_bytes, strict_json_loads
from .limits import R11ALimits
from .runtime import ExecutionEvidenceState, RuntimeGuard
from .storage import AtomicArtifactDirectory, StorageBoundaryError, WorkspaceMeter, directory_size
from .taxonomy import EvidenceEmitter, TaxonomyResult

SCIENCE_CONTAINERS: Final[tuple[str, ...]] = (
    "r11a-taxonomy-units.ndjson",
    "r11a-block-overlap-matrix.ndjson",
    "r11a-duplicate-observations.ndjson",
    "r11a-exact-block-replay-proofs.ndjson",
    "r11a-expected-counterparty-pair-proofs.ndjson",
    "r11a-protocol-trade-group-members.ndjson",
    "r11a-schema-violation-evidence.ndjson",
)
WALLET_FEATURE_FILE: Final[str] = "r11a-wallet-features.ndjson"
OBJECT_LEDGER_FILE: Final[str] = "r11a-object-ledger.ndjson"
REDUCER_LEDGER_FILE: Final[str] = "r11a-reducer-ledger.ndjson"
STOP_LEDGER_FILE: Final[str] = "r11a-stop-ledger.ndjson"
RESOURCE_LEDGER_FILE: Final[str] = "r11a-resource-ledger.ndjson"
CONTEXT_FILE: Final[str] = "r11a-context.json"
CONSERVATION_FILE: Final[str] = "r11a-taxonomy-conservation.json"
RESULT_FILE: Final[str] = "r11a-result.json"
RETURN_CODE_FILE: Final[str] = "r11a.rc"
HASH_MANIFEST_FILE: Final[str] = "R11A_FILES.sha256"
BOUNDARY_FILE: Final[str] = "R11A_PACKAGE_BOUNDARY.bin"


class ArtifactError(RuntimeError):
    pass


class ScientificCapExceeded(ArtifactError):
    pass


@dataclasses.dataclass(frozen=True, slots=True)
class FileEvidence:
    path: str
    byte_count: int
    row_count: int | None
    sha256: str

    def as_mapping(self) -> dict[str, object]:
        return dataclasses.asdict(self)


class StreamingScientificEmitter(EvidenceEmitter):
    """Seven-container writer with one shared pre-write reservation."""

    def __init__(self, staging: Path, meter: WorkspaceMeter, limits: R11ALimits) -> None:
        self.staging = meter._ensure_inside(staging)
        self.meter = meter
        self.limits = limits
        self.reservation = meter.reserve(
            limits.maximum_retained_scientific_output_bytes,
            "all retained scientific output",
            packaging=True,
        )
        self._handles: dict[str, BinaryIO] = {}
        self._hashes = {name: hashlib.sha256() for name in SCIENCE_CONTAINERS}
        self._rows = {name: 0 for name in SCIENCE_CONTAINERS}
        self._bytes = {name: 0 for name in SCIENCE_CONTAINERS}
        self._total = 0
        self._closed = False
        for name in SCIENCE_CONTAINERS:
            self._handles[name] = (self.staging / name).open("xb")

    def emit(self, container: str, row: Mapping[str, object]) -> None:
        if self._closed:
            raise ArtifactError("scientific emitter is closed")
        if container not in self._handles:
            raise ArtifactError(f"unknown scientific container: {container}")
        self.meter.runtime_guard.check_scientific_phase(f"emit {container}")
        encoded = canonical_json_bytes(row)
        if self._total + len(encoded) > self.limits.maximum_retained_scientific_output_bytes:
            raise ScientificCapExceeded("scientific output reservation would be exceeded")
        written = self._handles[container].write(encoded)
        if written != len(encoded):
            raise ArtifactError("short scientific output write")
        self._hashes[container].update(encoded)
        self._rows[container] += 1
        self._bytes[container] += len(encoded)
        self._total += len(encoded)

    def close(self) -> tuple[FileEvidence, ...]:
        if self._closed:
            raise ArtifactError("scientific emitter already closed")
        try:
            for name in SCIENCE_CONTAINERS:
                handle = self._handles[name]
                handle.flush()
                os.fsync(handle.fileno())
                handle.close()
        except OSError as exc:
            self.abort()
            raise ArtifactError("failed to flush scientific evidence") from exc
        self.meter.commit(self.reservation, self._total)
        self._closed = True
        return tuple(
            FileEvidence(
                path=name,
                byte_count=self._bytes[name],
                row_count=self._rows[name],
                sha256=self._hashes[name].hexdigest(),
            )
            for name in SCIENCE_CONTAINERS
        )

    def abort(self) -> None:
        if self._closed:
            return
        errors: list[BaseException] = []
        for handle in self._handles.values():
            try:
                handle.close()
            except OSError as exc:
                errors.append(exc)
        for name in SCIENCE_CONTAINERS:
            path = self.staging / name
            try:
                if path.exists():
                    path.unlink()
            except OSError as exc:
                errors.append(exc)
        self.meter.release(self.reservation)
        self._closed = True
        if errors:
            raise ArtifactError("scientific emitter cleanup failed") from errors[0]


class _MetadataWriter:
    def __init__(self, staging: Path, meter: WorkspaceMeter, limits: R11ALimits) -> None:
        self.staging = meter._ensure_inside(staging)
        self.meter = meter
        self.limits = limits
        self.reservation = meter.reserve(
            limits.reserved_non_scientific_package_metadata_bytes,
            "non-scientific evidence and package metadata",
            packaging=True,
        )
        self._written = 0
        self._closed = False

    def write(self, name: str, data: bytes) -> FileEvidence:
        if self._closed:
            raise ArtifactError("metadata writer is closed")
        if not name or "/" in name or ".." in name:
            raise ArtifactError("unsafe artifact file name")
        self.meter.runtime_guard.check_packaging_phase(f"write metadata {name}")
        if self._written + len(data) > self.reservation.maximum_bytes:
            raise ArtifactError("non-scientific metadata reservation exceeded")
        path = self.staging / name
        with path.open("xb") as handle:
            if handle.write(data) != len(data):
                raise ArtifactError("short metadata write")
            handle.flush()
            os.fsync(handle.fileno())
        self._written += len(data)
        row_count = None
        if name.endswith(".ndjson"):
            row_count = 0 if not data else data.count(b"\n")
        return FileEvidence(name, len(data), row_count, hashlib.sha256(data).hexdigest())

    def close(self) -> None:
        if self._closed:
            return
        self.meter.commit(self.reservation, self._written)
        self._closed = True

    def abort(self) -> None:
        if self._closed:
            return
        self.meter.release(self.reservation)
        self._closed = True


def _ndjson(rows: Sequence[Mapping[str, object]]) -> bytes:
    output = bytearray()
    for row in rows:
        output.extend(canonical_json_bytes(row))
    return bytes(output)


def empty_science(staging: Path, meter: WorkspaceMeter) -> tuple[FileEvidence, ...]:
    evidence: list[FileEvidence] = []
    for name in SCIENCE_CONTAINERS:
        reservation = meter.reserve(0, f"empty science {name}", packaging=True)
        path = staging / name
        path.touch(exist_ok=False)
        meter.commit(reservation, 0)
        evidence.append(FileEvidence(name, 0, 0, hashlib.sha256(b"").hexdigest()))
    return tuple(evidence)


def complete_reducer_ledger(
    observed_rows: Sequence[Mapping[str, object]],
    *,
    terminal_processing_status: str,
) -> tuple[dict[str, object], ...]:
    by_key: dict[tuple[str, int], Mapping[str, object]] = {}
    for row in observed_rows:
        reducer_id = str(row["reducer_id"])
        partition = int(row["partition_ordinal_zero_based"])
        key = (reducer_id, partition)
        if key in by_key:
            raise ArtifactError("duplicate reducer ledger row")
        by_key[key] = row
    output: list[dict[str, object]] = []
    for reducer_id in ("BLOCK_NUMBER", "LEGACY_WEAK_KEY_HASH"):
        for partition in range(256):
            row = by_key.get((reducer_id, partition))
            if row is None:
                output.append(
                    {
                        "record_type": "REDUCER_PARTITION_CONSERVATION",
                        "reducer_id": reducer_id,
                        "partition_ordinal_zero_based": partition,
                        "processing_status": terminal_processing_status,
                        "partition_function": "FIRST_BYTE_OF_SHA256_OF_COMPLETE_EQUALITY_KEY_BYTES",
                        "source_multiset_commitment": None,
                        "destination_multiset_commitment": None,
                        "sorted_stream_sha256": None,
                        "source_file_bytes": None,
                        "sorted_file_bytes": None,
                        "discovered_repeat_group_count": None,
                        "discovered_repeat_observation_count": None,
                        "retained_repeat_group_count": None,
                        "retained_repeat_observation_count": None,
                        "omitted_due_to_cap_group_count": None,
                        "omitted_due_to_cap_observation_count": None,
                    }
                )
            else:
                copied = dict(row)
                copied["processing_status"] = "COMPLETE"
                output.append(copied)
    if len(output) != 512:
        raise ArtifactError("reducer ledger must contain exactly 512 rows")
    return tuple(output)


def _file_hash_manifest(staging: Path, names: Sequence[str]) -> bytes:
    lines: list[str] = []
    for name in sorted(names, key=lambda value: value.encode("utf-8")):
        if name in {HASH_MANIFEST_FILE, BOUNDARY_FILE}:
            raise ArtifactError("manifest input contains a self-referential package file")
        data = (staging / name).read_bytes()
        lines.append(f"{hashlib.sha256(data).hexdigest()}  {name}")
    return ("\n".join(lines) + "\n").encode("ascii")


def _boundary_bytes(
    *,
    preboundary_file_count: int,
    preboundary_bytes: int,
    metadata_bytes: int,
    total_bytes_before_boundary: int,
    limits: R11ALimits,
) -> bytes:
    record = {
        "schema_version": "1.0",
        "record_type": "R11A_PACKAGE_BOUNDARY",
        "preboundary_file_count": preboundary_file_count,
        "preboundary_bytes": preboundary_bytes,
        "metadata_bytes": metadata_bytes,
        "total_bytes_before_boundary": total_bytes_before_boundary,
        "maximum_retained_artifact_bytes": limits.maximum_retained_artifact_bytes,
        "maximum_ephemeral_workspace_bytes": limits.maximum_ephemeral_workspace_bytes,
        "metadata_within_reservation": 1,
        "final_staging_within_artifact_limit": 1,
        "preupload_runtime_within_hard_limit_after_upload_window": 1,
        "boundary_write_within_workspace_limit": 1,
    }
    prefix = canonical_json_bytes(record, final_newline=False)
    if len(prefix) + 1 > limits.package_boundary_bytes:
        raise ArtifactError("package boundary JSON exceeds 1024 bytes")
    return prefix + b" " * (limits.package_boundary_bytes - len(prefix) - 1) + b"\n"


def _int(value: object, label: str) -> int:
    if isinstance(value, NumberToken) and value.is_integer_token:
        return int(value.token, 10)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ArtifactError(f"{label} must be an integer")


def _object(value: object, label: str) -> FrozenObject:
    if not isinstance(value, FrozenObject):
        raise ArtifactError(f"{label} must be an object")
    return value


def validate_package_boundary(path: Path, limits: R11ALimits) -> None:
    raw = path.read_bytes()
    if len(raw) != limits.package_boundary_bytes or not raw.endswith(b"\n"):
        raise ArtifactError("package boundary must be exactly 1024 bytes with final newline")
    document = raw.rstrip(b" \n") + b"\n"
    value = _object(strict_json_loads(document), "package boundary")
    for key in (
        "metadata_within_reservation",
        "final_staging_within_artifact_limit",
        "preupload_runtime_within_hard_limit_after_upload_window",
        "boundary_write_within_workspace_limit",
    ):
        if _int(value[key], key) != 1:
            raise ArtifactError(f"package boundary success flag is not one: {key}")
    if _int(value["maximum_retained_artifact_bytes"], "artifact cap") != limits.maximum_retained_artifact_bytes:
        raise ArtifactError("package boundary artifact cap drift")
    if _int(value["maximum_ephemeral_workspace_bytes"], "workspace cap") != limits.maximum_ephemeral_workspace_bytes:
        raise ArtifactError("package boundary workspace cap drift")


def _validate_manifest(staging: Path) -> None:
    manifest = (staging / HASH_MANIFEST_FILE).read_text(encoding="ascii").splitlines()
    observed: set[str] = set()
    previous: bytes | None = None
    for line in manifest:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if match is None:
            raise ArtifactError("malformed internal SHA-256 manifest line")
        digest, name = match.groups()
        encoded = name.encode("utf-8")
        if previous is not None and encoded <= previous:
            raise ArtifactError("internal manifest is not uniquely UTF-8 sorted")
        previous = encoded
        if name in observed or name in {HASH_MANIFEST_FILE, BOUNDARY_FILE}:
            raise ArtifactError("duplicate or self-referential internal manifest path")
        observed.add(name)
        path = staging / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ArtifactError("internal manifest digest mismatch")
    expected = {
        path.name
        for path in staging.iterdir()
        if path.is_file() and path.name not in {HASH_MANIFEST_FILE, BOUNDARY_FILE}
    }
    if observed != expected:
        raise ArtifactError("internal manifest file set mismatch")


def validate_artifact_directory(path: Path, limits: R11ALimits) -> None:
    expected_fixed = {
        *SCIENCE_CONTAINERS,
        WALLET_FEATURE_FILE,
        OBJECT_LEDGER_FILE,
        REDUCER_LEDGER_FILE,
        STOP_LEDGER_FILE,
        RESOURCE_LEDGER_FILE,
        CONTEXT_FILE,
        CONSERVATION_FILE,
        RESULT_FILE,
        RETURN_CODE_FILE,
        HASH_MANIFEST_FILE,
        BOUNDARY_FILE,
    }
    observed = {candidate.name for candidate in path.iterdir() if candidate.is_file()}
    if observed != expected_fixed:
        raise ArtifactError(f"artifact file set mismatch: {sorted(observed ^ expected_fixed)}")
    if any(candidate.is_dir() or candidate.is_symlink() for candidate in path.iterdir()):
        raise ArtifactError("artifact directory may contain only regular files")
    if directory_size(path) > limits.maximum_retained_artifact_bytes:
        raise ArtifactError("artifact exceeds 128 MiB cap")
    if (path / WALLET_FEATURE_FILE).read_bytes() != b"":
        raise ArtifactError("R11A wallet-feature output must remain exactly empty")
    result = _object(strict_json_loads((path / RESULT_FILE).read_bytes()), "result")
    science_status = result["scientific_container_status"]
    if science_status == "EMPTY_EARLY_STOP_OR_CAP_FALLBACK":
        if any((path / name).stat().st_size != 0 for name in SCIENCE_CONTAINERS):
            raise ArtifactError("early-stop or cap-fallback artifact contains scientific rows")
    elif science_status == "FULLY_MATERIALIZED":
        declared = _object(result["scientific_files"], "scientific_files")
        for name in SCIENCE_CONTAINERS:
            row = _object(declared[name], f"scientific_files.{name}")
            data = (path / name).read_bytes()
            if _int(row["byte_count"], "scientific byte_count") != len(data):
                raise ArtifactError("scientific byte count mismatch")
            if row["sha256"] != hashlib.sha256(data).hexdigest():
                raise ArtifactError("scientific SHA-256 mismatch")
    else:
        raise ArtifactError("unknown scientific_container_status")
    object_rows = (path / OBJECT_LEDGER_FILE).read_bytes().splitlines()
    reducer_rows = (path / REDUCER_LEDGER_FILE).read_bytes().splitlines()
    if len(object_rows) != 72:
        raise ArtifactError("object ledger must contain exactly 72 rows")
    if len(reducer_rows) != 512:
        raise ArtifactError("reducer ledger must contain exactly 512 rows")
    _validate_manifest(path)
    validate_package_boundary(path / BOUNDARY_FILE, limits)


@dataclasses.dataclass(frozen=True, slots=True)
class ArtifactOutcome:
    final_directory: Path
    terminal_class: str
    research_conclusion: str
    return_code: int
    scientific_container_status: str


def build_artifact(
    *,
    workspace: Path,
    meter: WorkspaceMeter,
    limits: R11ALimits,
    state: ExecutionEvidenceState,
    context: Mapping[str, object],
    reducer_rows: Sequence[Mapping[str, object]],
    resource_rows: Sequence[Mapping[str, object]],
    terminal_class: str,
    research_conclusion: str,
    return_code: int,
    taxonomy_result: TaxonomyResult | None,
    scientific_emitter: StreamingScientificEmitter | None,
    force_empty_science: bool,
) -> ArtifactOutcome:
    atomic = AtomicArtifactDirectory(workspace, meter, "r11a-artifact")
    with atomic as staging:
        metadata = _MetadataWriter(staging, meter, limits)
        try:
            if force_empty_science:
                if scientific_emitter is not None:
                    scientific_emitter.abort()
                science_evidence = empty_science(staging, meter)
                scientific_status = "EMPTY_EARLY_STOP_OR_CAP_FALLBACK"
            else:
                if scientific_emitter is None or taxonomy_result is None:
                    raise ArtifactError("fully materialized artifact requires science and taxonomy")
                science_evidence = scientific_emitter.close()
                scientific_status = "FULLY_MATERIALIZED"
            wallet_evidence = metadata.write(WALLET_FEATURE_FILE, b"")
            object_evidence = metadata.write(OBJECT_LEDGER_FILE, _ndjson(state.object_rows()))
            complete_reducers = complete_reducer_ledger(
                reducer_rows,
                terminal_processing_status=(
                    "NOT_STARTED_OR_INCOMPLETE" if force_empty_science else "COMPLETE"
                ),
            )
            reducer_evidence = metadata.write(REDUCER_LEDGER_FILE, _ndjson(complete_reducers))
            stop_evidence = metadata.write(STOP_LEDGER_FILE, _ndjson(state.stop_rows()))
            resource_evidence = metadata.write(RESOURCE_LEDGER_FILE, _ndjson(tuple(resource_rows)))
            context_evidence = metadata.write(CONTEXT_FILE, canonical_json_bytes(context))
            conservation_mapping: dict[str, object]
            if taxonomy_result is None:
                conservation_mapping = {
                    "status": "NOT_AVAILABLE_EARLY_STOP_OR_CAP_FALLBACK",
                    "universe_rows": [],
                    "all_proof_references_resolve": False,
                    "all_unit_ids_unique": False,
                    "all_duplicate_rows_reference_one_unit": False,
                }
            else:
                conservation_mapping = {
                    "status": "COMPUTED",
                    "universe_rows": list(taxonomy_result.conservation_rows),
                    "secondary_sort_rows": list(taxonomy_result.secondary_sort_rows),
                    "block_proof_count": taxonomy_result.block_proof_count,
                    "pair_proof_count": taxonomy_result.pair_proof_count,
                    "proof_reference_count": taxonomy_result.proof_reference_count,
                    "all_proof_references_resolve": taxonomy_result.all_proof_references_resolve,
                    "all_unit_ids_unique": taxonomy_result.all_unit_ids_unique,
                    "all_duplicate_rows_reference_one_unit": taxonomy_result.all_duplicate_rows_reference_one_unit,
                    "terminal_unclassifiable_group_count": taxonomy_result.terminal_unclassifiable_group_count,
                    "terminal_unclassifiable_occurrence_count": taxonomy_result.terminal_unclassifiable_occurrence_count,
                }
            conservation_evidence = metadata.write(
                CONSERVATION_FILE, canonical_json_bytes(conservation_mapping)
            )
            result_mapping = {
                "schema_version": "1.0",
                "diagnostic_id": "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-001",
                "terminal_class": terminal_class,
                "research_conclusion": research_conclusion,
                "scientific_container_status": scientific_status,
                "exact_scope_complete": state.exact_scope_complete(),
                "aggregate_object_counts": state.aggregate_counts(),
                "scientific_files": {
                    row.path: row.as_mapping() for row in science_evidence
                },
                "wallet_feature_file": wallet_evidence.as_mapping(),
                "object_ledger": object_evidence.as_mapping(),
                "reducer_ledger": reducer_evidence.as_mapping(),
                "stop_ledger": stop_evidence.as_mapping(),
                "resource_ledger": resource_evidence.as_mapping(),
                "context": context_evidence.as_mapping(),
                "taxonomy_conservation": conservation_evidence.as_mapping(),
                "return_code": return_code,
                "deduplication_performed": False,
                "block_replay_suppression_performed": False,
                "wallet_feature_publication_performed": False,
                "wallet_ranking_performed": False,
                "pnl_or_alpha_analysis_performed": False,
                "copyability_analysis_performed": False,
                "strategy_inference_performed": False,
                "trading_authority_opened": False,
            }
            result_evidence = metadata.write(RESULT_FILE, canonical_json_bytes(result_mapping))
            rc_evidence = metadata.write(RETURN_CODE_FILE, f"{return_code}\n".encode("ascii"))
            metadata.close()

            premanifest_names = [
                *SCIENCE_CONTAINERS,
                WALLET_FEATURE_FILE,
                OBJECT_LEDGER_FILE,
                REDUCER_LEDGER_FILE,
                STOP_LEDGER_FILE,
                RESOURCE_LEDGER_FILE,
                CONTEXT_FILE,
                CONSERVATION_FILE,
                RESULT_FILE,
                RETURN_CODE_FILE,
            ]
            manifest = _file_hash_manifest(staging, premanifest_names)
            manifest_reservation = meter.reserve(len(manifest), "hash manifest", packaging=True)
            (staging / HASH_MANIFEST_FILE).write_bytes(manifest)
            meter.commit(manifest_reservation, len(manifest))
            metadata_bytes = sum(
                (staging / name).stat().st_size
                for name in premanifest_names
                if name not in SCIENCE_CONTAINERS
            ) + len(manifest)
            preboundary_bytes = directory_size(staging)
            boundary = _boundary_bytes(
                preboundary_file_count=len(premanifest_names) + 1,
                preboundary_bytes=preboundary_bytes,
                metadata_bytes=metadata_bytes,
                total_bytes_before_boundary=preboundary_bytes,
                limits=limits,
            )
            boundary_reservation = meter.reserve(len(boundary), "package boundary", packaging=True)
            (staging / BOUNDARY_FILE).write_bytes(boundary)
            meter.commit(boundary_reservation, len(boundary))
            meter.verify_actual_usage()
            final = atomic.commit(lambda candidate: validate_artifact_directory(candidate, limits))
        except Exception:
            metadata.abort()
            raise
    return ArtifactOutcome(
        final_directory=final,
        terminal_class=terminal_class,
        research_conclusion=research_conclusion,
        return_code=return_code,
        scientific_container_status=scientific_status,
    )
