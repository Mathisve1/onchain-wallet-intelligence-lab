from __future__ import annotations

import dataclasses
import hashlib
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import BinaryIO

from .artifact_schema import (
    AUTHORITATIVE_UNIT_UNIVERSES,
    BOUNDARY_FILE,
    CONSERVATION_FILE,
    CONTEXT_FILE,
    DIAGNOSTIC_ID,
    EXPECTED_ARTIFACT_FILES,
    HASH_MANIFEST_FILE,
    IMPLEMENTATION_ID,
    OBJECT_LEDGER_FILE,
    PHASES,
    REDUCER_LEDGER_FILE,
    RESOURCE_LEDGER_FILE,
    RESULT_FILE,
    RETURN_CODE_FILE,
    SCIENCE_CONTAINERS,
    STOP_LEDGER_FILE,
    WALLET_FEATURE_FILE,
    exact_return_code,
    exact_root_cause_status,
    exact_scientific_status,
    validate_object_row_shape,
    validate_terminal_tuple,
    validate_universe_rows,
)
from .canonical import FrozenObject, NumberToken, canonical_json_bytes, strict_json_loads
from .limits import R11ALimits
from .runtime import ExecutionEvidenceState, RuntimeGuard
from .storage_r7 import AtomicArtifactDirectory, WorkspaceMeter, directory_size
from .taxonomy import EvidenceEmitter, TaxonomyResult

_BUFFER_BYTES = 64 * 1024


class ArtifactBoundaryError(RuntimeError):
    pass


class ScientificCapExceeded(ArtifactBoundaryError):
    pass


@dataclasses.dataclass(frozen=True, slots=True)
class FileEvidence:
    path: str
    byte_count: int
    row_count: int | None
    sha256: str

    def mapping(self) -> dict[str, object]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True, slots=True)
class ArtifactOutcome:
    final_directory: Path
    terminal_class: str
    research_conclusion: str
    return_code: int
    artifact_sha256: str
    artifact_bytes: int


class StreamingScientificEmitter(EvidenceEmitter):
    def __init__(self, staging: Path, meter: WorkspaceMeter, limits: R11ALimits) -> None:
        self.staging = meter._ensure_inside(staging)
        self.meter = meter
        self.reservation = meter.reserve(
            limits.maximum_retained_scientific_output_bytes,
            "all scientific containers",
        )
        self._handles: dict[str, BinaryIO] = {}
        self._buffers = {name: bytearray() for name in SCIENCE_CONTAINERS}
        self._hashes = {name: hashlib.sha256() for name in SCIENCE_CONTAINERS}
        self._bytes = {name: 0 for name in SCIENCE_CONTAINERS}
        self._rows = {name: 0 for name in SCIENCE_CONTAINERS}
        for name in SCIENCE_CONTAINERS:
            self._handles[name] = (self.staging / name).open("xb")
        self._total = 0
        self._closed = False
        meter.checkpoint(self.reservation, self.staging, phase="create scientific containers")

    def _flush(self, name: str) -> None:
        buffer = self._buffers[name]
        if not buffer:
            return
        self.meter.runtime_guard.check_scientific_phase(f"flush {name} before")
        payload = bytes(buffer)
        if self._handles[name].write(payload) != len(payload):
            raise ArtifactBoundaryError("short scientific output write")
        self._handles[name].flush()
        buffer.clear()
        self.meter.checkpoint(
            self.reservation,
            self.staging,
            phase=f"flush {name}",
        )
        self.meter.runtime_guard.check_scientific_phase(f"flush {name} after")

    def emit(self, container: str, row: Mapping[str, object]) -> None:
        if self._closed or container not in self._handles:
            raise ArtifactBoundaryError("invalid scientific emitter state or container")
        encoded = canonical_json_bytes(row)
        if self._total + len(encoded) > self.reservation.maximum_bytes:
            raise ScientificCapExceeded("scientific cap reached before row mutation")
        self._buffers[container].extend(encoded)
        self._hashes[container].update(encoded)
        self._bytes[container] += len(encoded)
        self._rows[container] += 1
        self._total += len(encoded)
        if len(self._buffers[container]) >= _BUFFER_BYTES:
            self._flush(container)

    def close(self) -> tuple[FileEvidence, ...]:
        if self._closed:
            raise ArtifactBoundaryError("scientific emitter already closed")
        try:
            for name in SCIENCE_CONTAINERS:
                self._flush(name)
                handle = self._handles[name]
                handle.flush()
                os.fsync(handle.fileno())
                handle.close()
            self.meter.finalize(
                self.reservation,
                self.staging,
                phase="finalize scientific containers",
            )
        except Exception:
            self.abort()
            raise
        self._closed = True
        return tuple(
            FileEvidence(name, self._bytes[name], self._rows[name], self._hashes[name].hexdigest())
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
        try:
            for name in SCIENCE_CONTAINERS:
                path = self.staging / name
                if path.exists():
                    path.unlink()
            self.meter.release_deleted(
                self.reservation,
                self.staging,
                phase="discard scientific containers",
            )
        except BaseException as exc:
            errors.append(exc)
        self._closed = True
        if errors:
            raise ArtifactBoundaryError("scientific cleanup failed") from errors[0]


class SharedMetadataWriter:
    def __init__(self, staging: Path, meter: WorkspaceMeter, limits: R11ALimits) -> None:
        self.staging = meter._ensure_inside(staging)
        self.meter = meter
        self.reservation = meter.reserve(
            limits.reserved_non_scientific_package_metadata_bytes,
            "all metadata containers",
            packaging=True,
        )
        self._written = 0
        self._closed = False
        meter.checkpoint(
            self.reservation,
            self.staging,
            packaging=True,
            phase="create metadata reservation",
        )

    def write(self, name: str, payload: bytes) -> FileEvidence:
        if self._closed or not name or "/" in name or ".." in name:
            raise ArtifactBoundaryError("invalid metadata path or writer state")
        if self._written + len(payload) > self.reservation.maximum_bytes:
            raise ArtifactBoundaryError("metadata reservation exceeded before write")
        path = self.staging / name
        with path.open("xb") as handle:
            if handle.write(payload) != len(payload):
                raise ArtifactBoundaryError("short metadata write")
            handle.flush()
            os.fsync(handle.fileno())
        self._written += len(payload)
        self.meter.checkpoint(
            self.reservation,
            self.staging,
            packaging=True,
            phase=f"write metadata {name}",
        )
        return FileEvidence(
            name,
            len(payload),
            payload.count(b"\n") if name.endswith(".ndjson") else None,
            hashlib.sha256(payload).hexdigest(),
        )

    def close(self) -> None:
        if self._closed:
            return
        self.meter.finalize(
            self.reservation,
            self.staging,
            packaging=True,
            phase="finalize metadata containers",
        )
        self._closed = True

    def abort(self) -> None:
        if self._closed:
            return
        errors: list[BaseException] = []
        try:
            for path in sorted(self.staging.iterdir(), reverse=True):
                if path.is_file() and path.name not in SCIENCE_CONTAINERS:
                    path.unlink()
            self.meter.release_deleted(
                self.reservation,
                self.staging,
                phase="discard metadata containers",
            )
        except BaseException as exc:
            errors.append(exc)
        self._closed = True
        if errors:
            raise ArtifactBoundaryError("metadata cleanup failed") from errors[0]


def _ndjson(rows: Sequence[Mapping[str, object]]) -> bytes:
    return b"".join(canonical_json_bytes(row) for row in rows)


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def complete_reducer_rows(
    observed: Sequence[Mapping[str, object]], terminal_class: str
) -> tuple[dict[str, object], ...]:
    rows: dict[tuple[str, int], Mapping[str, object]] = {}
    for row in observed:
        key = (str(row["reducer_id"]), int(row["partition_ordinal_zero_based"]))
        if key in rows:
            raise ArtifactBoundaryError("duplicate primary reducer row")
        rows[key] = row
    result: list[dict[str, object]] = []
    for reducer_id in ("BLOCK_NUMBER", "LEGACY_WEAK_KEY_HASH"):
        for partition in range(256):
            value = rows.get((reducer_id, partition))
            if value is None:
                result.append(
                    {
                        "record_type": "R11A_V2_REDUCER_PARTITION_CONSERVATION",
                        "reducer_id": reducer_id,
                        "partition_ordinal_zero_based": partition,
                        "processing_status": terminal_class,
                        "partition_function": "FIRST_BYTE_OF_SHA256_OF_COMPLETE_EQUALITY_KEY_BYTES",
                        "source_record_count": None,
                        "source_logical_bytes": None,
                        "destination_record_count": None,
                        "destination_logical_bytes": None,
                        "exact_multiplicity": None,
                        "sorted_stream_sha256": None,
                        "discovered_repeat_group_count": None,
                        "discovered_repeat_observation_count": None,
                    }
                )
            else:
                result.append(dict(value))
    if len(result) != 512:
        raise ArtifactBoundaryError("primary reducer ledger must contain exactly 512 rows")
    return tuple(result)


def _zero_universe_rows() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "unit_universe": universe,
            "group_count": 0,
            "occurrence_count": 0,
            "primary_taxon_group_counts": {},
            "primary_taxon_occurrence_counts": {},
            "unclassifiable_group_count": 0,
            "unclassifiable_occurrence_count": 0,
        }
        for universe in AUTHORITATIVE_UNIT_UNIVERSES
    )


def _manifest_bytes(staging: Path) -> bytes:
    names = sorted(
        (
            value.name
            for value in staging.iterdir()
            if value.is_file() and value.name not in {HASH_MANIFEST_FILE, BOUNDARY_FILE}
        ),
        key=lambda value: value.encode("utf-8"),
    )
    return ("\n".join(f"{_hash(staging / name)}  {name}" for name in names) + "\n").encode(
        "ascii"
    )


def _boundary_payload(
    staging: Path,
    limits: R11ALimits,
    runtime_guard: RuntimeGuard,
) -> bytes:
    preboundary = [value for value in staging.iterdir() if value.is_file()]
    preboundary_bytes = sum(value.stat().st_size for value in preboundary)
    metadata_bytes = sum(
        value.stat().st_size for value in preboundary if value.name not in SCIENCE_CONTAINERS
    )
    flags = runtime_guard.package_flags()
    value = {
        "schema_version": "2.0",
        "record_type": "R11A_V2_PACKAGE_BOUNDARY",
        "diagnostic_id": DIAGNOSTIC_ID,
        "implementation_id": IMPLEMENTATION_ID,
        "preboundary_file_count": len(preboundary),
        "preboundary_bytes": preboundary_bytes,
        "metadata_bytes": metadata_bytes,
        "maximum_retained_artifact_bytes": limits.maximum_retained_artifact_bytes,
        "maximum_ephemeral_workspace_bytes": limits.maximum_ephemeral_workspace_bytes,
        "metadata_within_reservation": metadata_bytes
        <= limits.reserved_non_scientific_package_metadata_bytes,
        "final_staging_within_artifact_limit": preboundary_bytes + limits.package_boundary_bytes
        <= limits.maximum_retained_artifact_bytes,
        "preupload_runtime_within_hard_limit_after_upload_window": flags[
            "preupload_runtime_within_hard_limit_after_upload_window"
        ],
        "boundary_write_within_workspace_limit": preboundary_bytes + limits.package_boundary_bytes
        <= limits.maximum_ephemeral_workspace_bytes,
    }
    prefix = canonical_json_bytes(value, final_newline=False)
    if len(prefix) + 1 > limits.package_boundary_bytes:
        raise ArtifactBoundaryError("package boundary exceeds exact 1,024 bytes")
    return prefix + b" " * (limits.package_boundary_bytes - len(prefix) - 1) + b"\n"


def _object(value: object, label: str) -> FrozenObject:
    if not isinstance(value, FrozenObject):
        raise ArtifactBoundaryError(f"{label} must be object")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, NumberToken) and value.is_integer_token:
        return int(value.token, 10)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ArtifactBoundaryError(f"{label} must be exact integer")


def _parse_ndjson(path: Path) -> tuple[FrozenObject, ...]:
    rows: list[FrozenObject] = []
    for raw in path.read_bytes().splitlines():
        rows.append(_object(strict_json_loads(raw), path.name))
    return tuple(rows)


def validate_artifact(path: Path, limits: R11ALimits) -> None:
    limits.validate()
    observed = {value.name for value in path.iterdir() if value.is_file()}
    if observed != EXPECTED_ARTIFACT_FILES:
        raise ArtifactBoundaryError("artifact file set drift")
    if any(value.is_dir() or value.is_symlink() for value in path.iterdir()):
        raise ArtifactBoundaryError("artifact contains directory or symlink")
    if directory_size(path) > limits.maximum_retained_artifact_bytes:
        raise ArtifactBoundaryError("artifact exceeds retained cap")
    context = _object(strict_json_loads((path / CONTEXT_FILE).read_bytes()), "context")
    result = _object(strict_json_loads((path / RESULT_FILE).read_bytes()), "result")
    if context["diagnostic_id"] != DIAGNOSTIC_ID or result["diagnostic_id"] != DIAGNOSTIC_ID:
        raise ArtifactBoundaryError("diagnostic ID drift")
    if context["implementation_id"] != IMPLEMENTATION_ID or result["implementation_id"] != IMPLEMENTATION_ID:
        raise ArtifactBoundaryError("implementation ID drift")
    terminal = str(result["terminal_class"])
    return_code = int((path / RETURN_CODE_FILE).read_text(encoding="ascii").strip())
    validate_terminal_tuple(
        terminal_class=terminal,
        return_code=return_code,
        scientific_output_status=str(result["scientific_output_status"]),
        root_cause_claim_status=str(result["root_cause_claim_status"]),
    )
    object_rows = _parse_ndjson(path / OBJECT_LEDGER_FILE)
    if len(object_rows) != 72:
        raise ArtifactBoundaryError("object ledger row count drift")
    for ordinal, row in enumerate(object_rows):
        mapping = {key: row[key] for key in row}
        validate_object_row_shape(mapping)
        if _integer(row["object_ordinal_zero_based"], "object ordinal") != ordinal:
            raise ArtifactBoundaryError("object ledger ordering drift")
    if len(_parse_ndjson(path / REDUCER_LEDGER_FILE)) != 512:
        raise ArtifactBoundaryError("reducer ledger row count drift")
    if (path / WALLET_FEATURE_FILE).stat().st_size != 0:
        raise ArtifactBoundaryError("wallet features must remain exact zero bytes")
    status = str(result["scientific_output_status"])
    if status == "EMPTY":
        if any((path / name).stat().st_size != 0 for name in SCIENCE_CONTAINERS):
            raise ArtifactBoundaryError("empty terminal contains scientific bytes")
    elif status == "COMPLETE":
        scientific = _object(result["scientific_files"], "scientific files")
        for name in SCIENCE_CONTAINERS:
            evidence = _object(scientific[name], f"scientific.{name}")
            if _integer(evidence["byte_count"], "scientific bytes") != (path / name).stat().st_size:
                raise ArtifactBoundaryError("scientific byte count mismatch")
            if evidence["sha256"] != _hash(path / name):
                raise ArtifactBoundaryError("scientific SHA mismatch")
    else:
        raise ArtifactBoundaryError("unknown scientific output status")
    conservation = _object(
        strict_json_loads((path / CONSERVATION_FILE).read_bytes()),
        "conservation",
    )
    universe_rows_raw = conservation["unit_universes"]
    if not isinstance(universe_rows_raw, tuple):
        raise ArtifactBoundaryError("unit universes must be array")
    validate_universe_rows(
        tuple({key: _object(row, "universe row")[key] for key in _object(row, "universe row")} for row in universe_rows_raw)
    )
    gates = _object(conservation["terminal_gates"], "terminal gates")
    if terminal == "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE":
        if not gates or any(value is not True for value in gates.values()):
            raise ArtifactBoundaryError("complete terminal has false conservation gate")
    stop_ledger = _object(strict_json_loads((path / STOP_LEDGER_FILE).read_bytes()), "stop ledger")
    if tuple(stop_ledger["declared_phase_order"]) != PHASES:
        raise ArtifactBoundaryError("stop phase order drift")
    resource = _object(
        strict_json_loads((path / RESOURCE_LEDGER_FILE).read_bytes()),
        "resource ledger",
    )
    boundary_raw = (path / BOUNDARY_FILE).read_bytes()
    if len(boundary_raw) != limits.package_boundary_bytes or not boundary_raw.endswith(b"\n"):
        raise ArtifactBoundaryError("boundary size drift")
    boundary = _object(
        strict_json_loads(boundary_raw.rstrip(b" \n") + b"\n"),
        "boundary",
    )
    for flag in (
        "metadata_within_reservation",
        "final_staging_within_artifact_limit",
        "preupload_runtime_within_hard_limit_after_upload_window",
        "boundary_write_within_workspace_limit",
    ):
        if boundary[flag] is not True:
            raise ArtifactBoundaryError(f"package boundary flag false: {flag}")
    preboundary_files = [value for value in path.iterdir() if value.name != BOUNDARY_FILE]
    preboundary_bytes = sum(value.stat().st_size for value in preboundary_files)
    metadata_bytes = sum(
        value.stat().st_size for value in preboundary_files if value.name not in SCIENCE_CONTAINERS
    )
    formulas = {
        "preboundary_file_count": len(preboundary_files),
        "preboundary_bytes": preboundary_bytes,
        "metadata_bytes": metadata_bytes,
    }
    for key, expected in formulas.items():
        if _integer(boundary[key], key) != expected:
            raise ArtifactBoundaryError(f"boundary formula mismatch: {key}")
    if metadata_bytes > limits.reserved_non_scientific_package_metadata_bytes:
        raise ArtifactBoundaryError("metadata exceeds reservation")
    if directory_size(path) > limits.maximum_retained_artifact_bytes:
        raise ArtifactBoundaryError("boundary final artifact cap mismatch")
    if resource["package_flags"]["preupload_runtime_within_hard_limit_after_upload_window"] is not True:
        raise ArtifactBoundaryError("resource ledger does not support runtime boundary")
    manifest_lines = (path / HASH_MANIFEST_FILE).read_text(encoding="ascii").splitlines()
    expected_manifest_names = sorted(
        EXPECTED_ARTIFACT_FILES - {HASH_MANIFEST_FILE, BOUNDARY_FILE},
        key=lambda value: value.encode("utf-8"),
    )
    observed_manifest_names: list[str] = []
    for line in manifest_lines:
        digest, name = line.split("  ", 1)
        if digest != _hash(path / name):
            raise ArtifactBoundaryError("manifest digest mismatch")
        observed_manifest_names.append(name)
    if observed_manifest_names != expected_manifest_names:
        raise ArtifactBoundaryError("manifest file coverage drift")


class ArtifactSession:
    def __init__(
        self,
        workspace: Path,
        meter: WorkspaceMeter,
        limits: R11ALimits,
        runtime_guard: RuntimeGuard,
    ) -> None:
        self.workspace = workspace
        self.meter = meter
        self.limits = limits
        self.runtime_guard = runtime_guard
        self.atomic = AtomicArtifactDirectory(workspace, meter, "r11a-v2-artifact")
        self.staging = self.atomic.__enter__()
        self.emitter = StreamingScientificEmitter(self.staging, meter, limits)
        self._closed = False

    def _discard_science_and_create_empty(self) -> tuple[FileEvidence, ...]:
        self.emitter.abort()
        replacement = StreamingScientificEmitter(self.staging, self.meter, self.limits)
        return replacement.close()

    def _finalize(
        self,
        *,
        state: ExecutionEvidenceState,
        context: Mapping[str, object],
        reducer_rows: Sequence[Mapping[str, object]],
        resource_rows: Sequence[Mapping[str, object]],
        terminal_class: str,
        research_conclusion: str,
        taxonomy_result: TaxonomyResult | None,
        science: tuple[FileEvidence, ...],
    ) -> ArtifactOutcome:
        if self._closed:
            raise ArtifactBoundaryError("artifact session already closed")
        return_code = exact_return_code(terminal_class)
        scientific_status = exact_scientific_status(terminal_class)
        root_cause_status = exact_root_cause_status(terminal_class)
        object_rows = state.object_rows()
        complete_reducers = complete_reducer_rows(reducer_rows, terminal_class)
        universe_rows = (
            _zero_universe_rows()
            if taxonomy_result is None
            else taxonomy_result.universe_rows
        )
        join_mapping: dict[str, object] = {
            "unit_count": 0,
            "proof_count": 0,
            "proof_reference_count": 0,
            "retained_row_reference_count": 0,
            "all_unit_ids_unique": True,
            "all_proof_ids_unique": True,
            "all_nonnull_proof_references_resolve_exactly_once": True,
            "all_retained_rows_reference_exactly_one_unit": True,
            "all_referenced_projections_are_byte_equal": True,
        }
        if taxonomy_result is not None:
            join_mapping = dataclasses.asdict(taxonomy_result.join_validation)
        terminal_gates = {
            "exact_72_object_scope_complete": state.exact_scope_complete(),
            "exact_three_complete_utc_days": bool(
                taxonomy_result is not None and taxonomy_result.exact_three_utc_days
            ),
            "all_objects_parsed_twice_with_equal_counts_and_commitments": state.exact_scope_complete(),
            "raw_block_count_conserves_to_singleton_plus_repeated_observations": False,
            "raw_event_count_conserves_separately_for_tid_coin_and_wallet_validation": False,
            "legacy_repeat_occurrence_count_conserves_to_valid_plus_invalid_tid_repeat_occurrences": False,
            "every_authoritative_unit_receives_exactly_one_primary_taxon": taxonomy_result is not None,
            "supporting_taxa_do_not_increment_primary_counts": taxonomy_result is not None,
            "all_nonnull_proof_and_provenance_foreign_keys_resolve_exactly_once": bool(
                join_mapping["all_nonnull_proof_references_resolve_exactly_once"]
            ),
            "all_referenced_projections_are_byte_equal": bool(
                join_mapping["all_referenced_projections_are_byte_equal"]
            ),
            "all_taxonomy_counts_recomputed_from_retained_rows": taxonomy_result is not None,
            "every_unit_universe_has_zero_unclassifiable_groups_and_occurrences": bool(
                taxonomy_result is not None
                and taxonomy_result.unclassifiable_group_count == 0
                and taxonomy_result.unclassifiable_occurrence_count == 0
            ),
            "all_caps_respected": directory_size(self.staging)
            <= self.limits.maximum_retained_artifact_bytes,
        }
        counts = state.aggregate_counts()
        if taxonomy_result is not None:
            first_blocks = counts["first_pass_record_count"]
            first_events = counts["first_pass_event_count"]
            terminal_gates[
                "raw_block_count_conserves_to_singleton_plus_repeated_observations"
            ] = (
                taxonomy_result.repeated_block_observation_count <= first_blocks
                and first_blocks
                == (first_blocks - taxonomy_result.repeated_block_observation_count)
                + taxonomy_result.repeated_block_observation_count
            )
            # Parser-level valid/invalid partitions are validated before this point.
            terminal_gates[
                "raw_event_count_conserves_separately_for_tid_coin_and_wallet_validation"
            ] = first_events == counts["second_pass_event_count"]
            terminal_gates[
                "legacy_repeat_occurrence_count_conserves_to_valid_plus_invalid_tid_repeat_occurrences"
            ] = taxonomy_result.legacy_repeat_occurrence_count == (
                taxonomy_result.valid_tid_legacy_repeat_occurrence_count
                + taxonomy_result.invalid_tid_legacy_repeat_occurrence_count
            )
        if terminal_class == "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE" and any(
            value is not True for value in terminal_gates.values()
        ):
            raise ArtifactBoundaryError("complete terminal requested with false gates")
        conservation = {
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "implementation_id": IMPLEMENTATION_ID,
            "aggregate_execution_counts": counts,
            "unit_universes": list(universe_rows),
            "join_validation": join_mapping,
            "secondary_reducer_rows": (
                [] if taxonomy_result is None else list(taxonomy_result.secondary_reducer_rows)
            ),
            "supporting_taxon_counts": (
                {} if taxonomy_result is None else taxonomy_result.supporting_taxon_counts
            ),
            "terminal_gates": terminal_gates,
        }
        science_mapping = {value.path: value.mapping() for value in science}
        result = {
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "implementation_id": IMPLEMENTATION_ID,
            "terminal_class": terminal_class,
            "research_conclusion": research_conclusion,
            "scientific_output_status": scientific_status,
            "root_cause_claim_status": root_cause_status,
            "return_code": return_code,
            "scientific_files": science_mapping,
            "wallet_feature_rows": 0,
            "rerun_authorized": False,
            "R11_CLOSED": False,
            "R12_READY": False,
        }
        full_context = {
            **dict(context),
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "implementation_id": IMPLEMENTATION_ID,
            "execution_phase": state.current_phase,
            "s3_requests_executed": state.network_request_count,
            "object_bytes_downloaded": sum(
                int(row["body"]["bytes_received"]) for row in object_rows
            ),
            "rerun_authorized": False,
        }
        resource = {
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "measurements": list(resource_rows),
            "tracked_workspace_bytes_before_packaging": self.meter.known_bytes,
            "reserved_workspace_bytes_before_packaging": self.meter.reserved_bytes,
            "maximum_ephemeral_workspace_bytes": self.limits.maximum_ephemeral_workspace_bytes,
            "package_flags": self.runtime_guard.package_flags(),
        }
        stop = {
            "schema_version": "2.0",
            "diagnostic_id": DIAGNOSTIC_ID,
            "declared_phase_order": list(PHASES),
            "entries": list(state.stop_rows()),
        }
        metadata = SharedMetadataWriter(self.staging, self.meter, self.limits)
        try:
            metadata.write(CONTEXT_FILE, canonical_json_bytes(full_context))
            metadata.write(RESULT_FILE, canonical_json_bytes(result))
            metadata.write(OBJECT_LEDGER_FILE, _ndjson(object_rows))
            metadata.write(REDUCER_LEDGER_FILE, _ndjson(complete_reducers))
            metadata.write(CONSERVATION_FILE, canonical_json_bytes(conservation))
            metadata.write(RESOURCE_LEDGER_FILE, canonical_json_bytes(resource))
            metadata.write(STOP_LEDGER_FILE, canonical_json_bytes(stop))
            metadata.write(WALLET_FEATURE_FILE, b"")
            metadata.write(RETURN_CODE_FILE, f"{return_code}\n".encode("ascii"))
            metadata.write(HASH_MANIFEST_FILE, _manifest_bytes(self.staging))
            boundary = _boundary_payload(self.staging, self.limits, self.runtime_guard)
            metadata.write(BOUNDARY_FILE, boundary)
            metadata.close()
            final = self.atomic.commit(lambda path: validate_artifact(path, self.limits))
            self._closed = True
            return ArtifactOutcome(
                final_directory=final,
                terminal_class=terminal_class,
                research_conclusion=research_conclusion,
                return_code=return_code,
                artifact_sha256=hashlib.sha256(
                    b"".join(
                        canonical_json_bytes(
                            {"name": name, "sha256": _hash(final / name)},
                            final_newline=False,
                        )
                        for name in sorted(EXPECTED_ARTIFACT_FILES)
                    )
                ).hexdigest(),
                artifact_bytes=directory_size(final),
            )
        except Exception:
            metadata.abort()
            raise

    def finalize_empty(
        self,
        *,
        state: ExecutionEvidenceState,
        context: Mapping[str, object],
        reducer_rows: Sequence[Mapping[str, object]],
        resource_rows: Sequence[Mapping[str, object]],
        terminal_class: str,
        research_conclusion: str,
    ) -> ArtifactOutcome:
        if exact_scientific_status(terminal_class) != "EMPTY":
            raise ArtifactBoundaryError("finalize_empty requires empty terminal class")
        science = self._discard_science_and_create_empty()
        return self._finalize(
            state=state,
            context=context,
            reducer_rows=reducer_rows,
            resource_rows=resource_rows,
            terminal_class=terminal_class,
            research_conclusion=research_conclusion,
            taxonomy_result=None,
            science=science,
        )

    def finalize_full(
        self,
        *,
        state: ExecutionEvidenceState,
        context: Mapping[str, object],
        reducer_rows: Sequence[Mapping[str, object]],
        resource_rows: Sequence[Mapping[str, object]],
        terminal_class: str,
        research_conclusion: str,
        taxonomy_result: TaxonomyResult,
    ) -> ArtifactOutcome:
        if exact_scientific_status(terminal_class) != "COMPLETE":
            raise ArtifactBoundaryError("finalize_full requires complete science terminal")
        science = self.emitter.close()
        return self._finalize(
            state=state,
            context=context,
            reducer_rows=reducer_rows,
            resource_rows=resource_rows,
            terminal_class=terminal_class,
            research_conclusion=research_conclusion,
            taxonomy_result=taxonomy_result,
            science=science,
        )

    def abort(self) -> None:
        if self._closed:
            return
        errors: list[BaseException] = []
        try:
            self.emitter.abort()
        except BaseException as exc:
            errors.append(exc)
        try:
            self.atomic.__exit__(Exception, ArtifactBoundaryError("abort"), None)
        except BaseException as exc:
            errors.append(exc)
        self._closed = True
        if errors:
            raise ArtifactBoundaryError("artifact session abort failed") from errors[0]
