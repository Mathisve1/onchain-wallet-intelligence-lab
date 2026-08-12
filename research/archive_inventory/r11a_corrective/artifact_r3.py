from __future__ import annotations

import dataclasses
import hashlib
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import BinaryIO, Final

from .canonical import FrozenObject, NumberToken, canonical_json_bytes, strict_json_loads
from .limits import R11ALimits
from .runtime import ExecutionEvidenceState
from .storage import AtomicArtifactDirectory, WorkspaceMeter, directory_size
from .taxonomy_r4 import EvidenceEmitter, TaxonomyResult

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


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1 << 20)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


class StreamingScientificEmitter(EvidenceEmitter):
    def __init__(self, staging: Path, meter: WorkspaceMeter, limits: R11ALimits) -> None:
        self.staging = meter._ensure_inside(staging)
        self.meter = meter
        self.limits = limits
        self.reservation = meter.reserve(
            limits.maximum_retained_scientific_output_bytes,
            "all retained scientific output",
        )
        self._handles: dict[str, BinaryIO] = {
            name: (self.staging / name).open("xb") for name in SCIENCE_CONTAINERS
        }
        self._hashes = {name: hashlib.sha256() for name in SCIENCE_CONTAINERS}
        self._rows = {name: 0 for name in SCIENCE_CONTAINERS}
        self._bytes = {name: 0 for name in SCIENCE_CONTAINERS}
        self._total = 0
        self._closed = False
        self._committed = False

    def emit(self, container: str, row: Mapping[str, object]) -> None:
        if self._closed or container not in self._handles:
            raise ArtifactError("invalid scientific emitter state or container")
        self.meter.runtime_guard.check_scientific_phase(f"emit {container}")
        encoded = canonical_json_bytes(row)
        if self._total + len(encoded) > self.reservation.maximum_bytes:
            raise ScientificCapExceeded("scientific output cap reached before row write")
        if self._handles[container].write(encoded) != len(encoded):
            raise ArtifactError("short scientific row write")
        self._hashes[container].update(encoded)
        self._rows[container] += 1
        self._bytes[container] += len(encoded)
        self._total += len(encoded)

    def close(self) -> tuple[FileEvidence, ...]:
        if self._closed:
            raise ArtifactError("scientific emitter already closed")
        try:
            for handle in self._handles.values():
                handle.flush()
                os.fsync(handle.fileno())
                handle.close()
        except OSError as exc:
            self.abort()
            raise ArtifactError("scientific output flush failed") from exc
        self.meter.commit(self.reservation, self._total)
        self._closed = True
        self._committed = True
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
            raise ArtifactError("scientific output cleanup failed") from errors[0]


class MetadataWriter:
    def __init__(self, staging: Path, meter: WorkspaceMeter, limits: R11ALimits) -> None:
        self.staging = meter._ensure_inside(staging)
        self.meter = meter
        self.reservation = meter.reserve(
            limits.reserved_non_scientific_package_metadata_bytes,
            "non-scientific evidence and package metadata",
            packaging=True,
        )
        self._written = 0
        self._paths: list[Path] = []
        self._closed = False
        self._committed = False

    def write(self, name: str, data: bytes) -> FileEvidence:
        if self._closed or not name or "/" in name or ".." in name:
            raise ArtifactError("invalid metadata writer state or path")
        self.meter.runtime_guard.check_packaging_phase(f"write {name}")
        if self._written + len(data) > self.reservation.maximum_bytes:
            raise ArtifactError("metadata reservation exceeded before write")
        path = self.staging / name
        with path.open("xb") as handle:
            if handle.write(data) != len(data):
                raise ArtifactError("short metadata write")
            handle.flush()
            os.fsync(handle.fileno())
        self._paths.append(path)
        self._written += len(data)
        row_count = data.count(b"\n") if name.endswith(".ndjson") else None
        return FileEvidence(name, len(data), row_count, hashlib.sha256(data).hexdigest())

    def close(self) -> None:
        if self._closed:
            return
        self.meter.commit(self.reservation, self._written)
        self._closed = True
        self._committed = True

    def abort(self) -> None:
        if self._closed:
            return
        errors: list[BaseException] = []
        for path in reversed(self._paths):
            try:
                if path.exists():
                    path.unlink()
            except OSError as exc:
                errors.append(exc)
        self.meter.release(self.reservation)
        self._closed = True
        if errors:
            raise ArtifactError("metadata cleanup failed") from errors[0]


def _ndjson(rows: Sequence[Mapping[str, object]]) -> bytes:
    result = bytearray()
    for row in rows:
        result.extend(canonical_json_bytes(row))
    return bytes(result)


def complete_reducer_rows(
    observed_rows: Sequence[Mapping[str, object]], terminal_status: str
) -> tuple[dict[str, object], ...]:
    observed: dict[tuple[str, int], Mapping[str, object]] = {}
    for row in observed_rows:
        key = (str(row["reducer_id"]), int(row["partition_ordinal_zero_based"]))
        if key in observed:
            raise ArtifactError("duplicate primary reducer row")
        observed[key] = row
    rows: list[dict[str, object]] = []
    for reducer_id in ("BLOCK_NUMBER", "LEGACY_WEAK_KEY_HASH"):
        for partition in range(256):
            row = observed.get((reducer_id, partition))
            if row is None:
                rows.append(
                    {
                        "record_type": "REDUCER_PARTITION_CONSERVATION",
                        "reducer_id": reducer_id,
                        "partition_ordinal_zero_based": partition,
                        "processing_status": terminal_status,
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
                rows.append(copied)
    if len(rows) != 512:
        raise ArtifactError("primary reducer ledger must contain 512 rows")
    return tuple(rows)


def _integer(value: object, label: str) -> int:
    if isinstance(value, NumberToken) and value.is_integer_token:
        return int(value.token, 10)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ArtifactError(f"{label} must be an exact integer")


def _object(value: object, label: str) -> FrozenObject:
    if not isinstance(value, FrozenObject):
        raise ArtifactError(f"{label} must be an object")
    return value


def _manifest_bytes(staging: Path, names: Sequence[str]) -> bytes:
    lines: list[str] = []
    for name in sorted(names, key=lambda item: item.encode("utf-8")):
        lines.append(f"{_hash_file(staging / name)}  {name}")
    return ("\n".join(lines) + "\n").encode("ascii")


def _boundary_bytes(
    *,
    preboundary_file_count: int,
    preboundary_bytes: int,
    metadata_bytes: int,
    limits: R11ALimits,
) -> bytes:
    value = {
        "schema_version": "1.0",
        "record_type": "R11A_PACKAGE_BOUNDARY",
        "preboundary_file_count": preboundary_file_count,
        "preboundary_bytes": preboundary_bytes,
        "metadata_bytes": metadata_bytes,
        "total_bytes_before_boundary": preboundary_bytes,
        "maximum_retained_artifact_bytes": limits.maximum_retained_artifact_bytes,
        "maximum_ephemeral_workspace_bytes": limits.maximum_ephemeral_workspace_bytes,
        "metadata_within_reservation": 1,
        "final_staging_within_artifact_limit": 1,
        "preupload_runtime_within_hard_limit_after_upload_window": 1,
        "boundary_write_within_workspace_limit": 1,
    }
    prefix = canonical_json_bytes(value, final_newline=False)
    if len(prefix) + 1 > limits.package_boundary_bytes:
        raise ArtifactError("package boundary payload exceeds fixed record")
    return prefix + b" " * (limits.package_boundary_bytes - len(prefix) - 1) + b"\n"


def validate_boundary(path: Path, limits: R11ALimits) -> None:
    raw = path.read_bytes()
    if len(raw) != limits.package_boundary_bytes or not raw.endswith(b"\n"):
        raise ArtifactError("package boundary size or newline mismatch")
    value = _object(strict_json_loads(raw.rstrip(b" \n") + b"\n"), "package boundary")
    for key in (
        "metadata_within_reservation",
        "final_staging_within_artifact_limit",
        "preupload_runtime_within_hard_limit_after_upload_window",
        "boundary_write_within_workspace_limit",
    ):
        if _integer(value[key], key) != 1:
            raise ArtifactError(f"package boundary flag is not one: {key}")
    if _integer(value["maximum_retained_artifact_bytes"], "artifact cap") != limits.maximum_retained_artifact_bytes:
        raise ArtifactError("package boundary artifact cap drift")
    if _integer(value["maximum_ephemeral_workspace_bytes"], "workspace cap") != limits.maximum_ephemeral_workspace_bytes:
        raise ArtifactError("package boundary workspace cap drift")
    preboundary_files = tuple(
        candidate
        for candidate in path.parent.iterdir()
        if candidate.is_file() and candidate.name != BOUNDARY_FILE
    )
    actual_preboundary_bytes = sum(candidate.stat().st_size for candidate in preboundary_files)
    actual_metadata_bytes = sum(
        candidate.stat().st_size
        for candidate in preboundary_files
        if candidate.name not in SCIENCE_CONTAINERS
    )
    if _integer(value["preboundary_file_count"], "preboundary file count") != len(preboundary_files):
        raise ArtifactError("package boundary file-count formula mismatch")
    if _integer(value["preboundary_bytes"], "preboundary bytes") != actual_preboundary_bytes:
        raise ArtifactError("package boundary preboundary-byte formula mismatch")
    if _integer(value["total_bytes_before_boundary"], "total bytes before boundary") != actual_preboundary_bytes:
        raise ArtifactError("package boundary total-byte formula mismatch")
    if _integer(value["metadata_bytes"], "metadata bytes") != actual_metadata_bytes:
        raise ArtifactError("package boundary metadata-byte formula mismatch")
    if directory_size(path.parent) != actual_preboundary_bytes + limits.package_boundary_bytes:
        raise ArtifactError("package boundary final directory-size formula mismatch")



def validate_artifact(path: Path, limits: R11ALimits) -> None:
    expected = {
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
    observed = {item.name for item in path.iterdir() if item.is_file()}
    if observed != expected or any(item.is_dir() or item.is_symlink() for item in path.iterdir()):
        raise ArtifactError("artifact file set or file type mismatch")
    if directory_size(path) > limits.maximum_retained_artifact_bytes:
        raise ArtifactError("artifact exceeds retained cap")
    if (path / WALLET_FEATURE_FILE).stat().st_size != 0:
        raise ArtifactError("wallet feature output is not exactly empty")
    if len((path / OBJECT_LEDGER_FILE).read_bytes().splitlines()) != 72:
        raise ArtifactError("object ledger must contain exactly 72 rows")
    if len((path / REDUCER_LEDGER_FILE).read_bytes().splitlines()) != 512:
        raise ArtifactError("reducer ledger must contain exactly 512 rows")

    result = _object(strict_json_loads((path / RESULT_FILE).read_bytes()), "result")
    status = result["scientific_container_status"]
    if status == "EMPTY_EARLY_STOP_OR_CAP_FALLBACK":
        if any((path / name).stat().st_size != 0 for name in SCIENCE_CONTAINERS):
            raise ArtifactError("empty terminal contains scientific bytes")
    elif status == "FULLY_MATERIALIZED":
        files = _object(result["scientific_files"], "scientific_files")
        for name in SCIENCE_CONTAINERS:
            evidence = _object(files[name], f"scientific_files.{name}")
            if _integer(evidence["byte_count"], "byte_count") != (path / name).stat().st_size:
                raise ArtifactError("scientific byte-count mismatch")
            if evidence["sha256"] != _hash_file(path / name):
                raise ArtifactError("scientific SHA-256 mismatch")
    else:
        raise ArtifactError("unknown scientific container status")

    terminal = result["terminal_class"]
    conservation = _object(
        strict_json_loads((path / CONSERVATION_FILE).read_bytes()), "conservation"
    )
    if terminal == "R11A_ROOT_CAUSE_TAXONOMY_COMPLETE":
        if result["exact_scope_complete"] is not True or conservation["status"] != "COMPUTED":
            raise ArtifactError("complete taxonomy lacks complete scope or conservation")
        for key in (
            "all_proof_references_resolve",
            "all_unit_ids_unique",
            "all_duplicate_rows_reference_one_unit",
        ):
            if conservation[key] is not True:
                raise ArtifactError(f"complete taxonomy failed conservation flag: {key}")
        if _integer(conservation["terminal_unclassifiable_group_count"], "unclassifiable groups") != 0:
            raise ArtifactError("complete taxonomy contains unclassifiable groups")
        if _integer(conservation["terminal_unclassifiable_occurrence_count"], "unclassifiable occurrences") != 0:
            raise ArtifactError("complete taxonomy contains unclassifiable occurrences")
        universe_rows = conservation["universe_rows"]
        if not isinstance(universe_rows, tuple) or len(universe_rows) != 4:
            raise ArtifactError("complete taxonomy must conserve four unit universes")

    manifest_lines = (path / HASH_MANIFEST_FILE).read_text(encoding="ascii").splitlines()
    names: list[str] = []
    previous: bytes | None = None
    for line in manifest_lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if match is None:
            raise ArtifactError("malformed internal hash manifest")
        digest, name = match.groups()
        encoded = name.encode("utf-8")
        if previous is not None and encoded <= previous:
            raise ArtifactError("internal manifest is not unique UTF-8 order")
        previous = encoded
        if name in {HASH_MANIFEST_FILE, BOUNDARY_FILE} or _hash_file(path / name) != digest:
            raise ArtifactError("internal manifest path or hash mismatch")
        names.append(name)
    expected_manifest = sorted(
        expected - {HASH_MANIFEST_FILE, BOUNDARY_FILE}, key=lambda item: item.encode("utf-8")
    )
    if names != expected_manifest:
        raise ArtifactError("internal manifest file set mismatch")
    validate_boundary(path / BOUNDARY_FILE, limits)


@dataclasses.dataclass(frozen=True, slots=True)
class ArtifactOutcome:
    final_directory: Path
    terminal_class: str
    research_conclusion: str
    return_code: int
    scientific_container_status: str


class ArtifactSession:
    """Science is emitted inside the final staging directory before metadata sealing."""

    def __init__(self, workspace: Path, meter: WorkspaceMeter, limits: R11ALimits) -> None:
        self.workspace = meter._ensure_inside(workspace)
        self.meter = meter
        self.limits = limits
        self.atomic = AtomicArtifactDirectory(self.workspace, meter, "r11a-artifact")
        self.staging = self.atomic.__enter__()
        self.science = StreamingScientificEmitter(self.staging, meter, limits)
        self.metadata = MetadataWriter(self.staging, meter, limits)
        self._finished = False

    @property
    def emitter(self) -> StreamingScientificEmitter:
        return self.science

    def _finalize(
        self,
        *,
        state: ExecutionEvidenceState,
        context: Mapping[str, object],
        reducer_rows: Sequence[Mapping[str, object]],
        resource_rows: Sequence[Mapping[str, object]],
        terminal_class: str,
        research_conclusion: str,
        return_code: int,
        taxonomy_result: TaxonomyResult | None,
        empty_science: bool,
    ) -> ArtifactOutcome:
        if self._finished:
            raise ArtifactError("artifact session already finalized")
        try:
            if empty_science:
                self.science.abort()
                science_evidence: tuple[FileEvidence, ...] = tuple(
                    self.metadata.write(name, b"") for name in SCIENCE_CONTAINERS
                )
                science_status = "EMPTY_EARLY_STOP_OR_CAP_FALLBACK"
            else:
                if taxonomy_result is None:
                    raise ArtifactError("materialized science requires taxonomy result")
                science_evidence = self.science.close()
                science_status = "FULLY_MATERIALIZED"

            wallet = self.metadata.write(WALLET_FEATURE_FILE, b"")
            object_ledger = self.metadata.write(OBJECT_LEDGER_FILE, _ndjson(state.object_rows()))
            reducer_ledger = self.metadata.write(
                REDUCER_LEDGER_FILE,
                _ndjson(
                    complete_reducer_rows(
                        reducer_rows,
                        "NOT_STARTED_OR_INCOMPLETE" if empty_science else "COMPLETE",
                    )
                ),
            )
            stop_ledger = self.metadata.write(STOP_LEDGER_FILE, _ndjson(state.stop_rows()))
            resource_ledger = self.metadata.write(RESOURCE_LEDGER_FILE, _ndjson(resource_rows))
            context_evidence = self.metadata.write(CONTEXT_FILE, canonical_json_bytes(context))

            if taxonomy_result is None:
                conservation = {
                    "status": "NOT_AVAILABLE_EARLY_STOP_OR_CAP_FALLBACK",
                    "universe_rows": [],
                    "secondary_sort_rows": [],
                    "block_proof_count": 0,
                    "pair_proof_count": 0,
                    "proof_reference_count": 0,
                    "all_proof_references_resolve": False,
                    "all_unit_ids_unique": False,
                    "all_duplicate_rows_reference_one_unit": False,
                    "terminal_unclassifiable_group_count": 0,
                    "terminal_unclassifiable_occurrence_count": 0,
                }
            else:
                conservation = {
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
            conservation_evidence = self.metadata.write(
                CONSERVATION_FILE, canonical_json_bytes(conservation)
            )
            result = {
                "schema_version": "1.0",
                "diagnostic_id": "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-001",
                "terminal_class": terminal_class,
                "research_conclusion": research_conclusion,
                "scientific_container_status": science_status,
                "exact_scope_complete": state.exact_scope_complete(),
                "aggregate_object_counts": state.aggregate_counts(),
                "scientific_files": {row.path: row.as_mapping() for row in science_evidence},
                "wallet_feature_file": wallet.as_mapping(),
                "object_ledger": object_ledger.as_mapping(),
                "reducer_ledger": reducer_ledger.as_mapping(),
                "stop_ledger": stop_ledger.as_mapping(),
                "resource_ledger": resource_ledger.as_mapping(),
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
            self.metadata.write(RESULT_FILE, canonical_json_bytes(result))
            self.metadata.write(RETURN_CODE_FILE, f"{return_code}\n".encode("ascii"))
            manifest_names = [
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
            manifest = _manifest_bytes(self.staging, manifest_names)
            self.metadata.write(HASH_MANIFEST_FILE, manifest)
            metadata_bytes = sum(
                (self.staging / name).stat().st_size
                for name in manifest_names
                if name not in SCIENCE_CONTAINERS
            ) + len(manifest)
            preboundary_bytes = directory_size(self.staging)
            self.metadata.write(
                BOUNDARY_FILE,
                _boundary_bytes(
                    preboundary_file_count=len(manifest_names) + 1,
                    preboundary_bytes=preboundary_bytes,
                    metadata_bytes=metadata_bytes,
                    limits=self.limits,
                ),
            )
            self.metadata.close()
            self.meter.verify_actual_usage()
            final = self.atomic.commit(lambda path: validate_artifact(path, self.limits))
            self._finished = True
            return ArtifactOutcome(
                final_directory=final,
                terminal_class=terminal_class,
                research_conclusion=research_conclusion,
                return_code=return_code,
                scientific_container_status=science_status,
            )
        except Exception:
            try:
                self.metadata.abort()
            finally:
                if not self.science._closed:
                    self.science.abort()
                self.atomic.__exit__(Exception, Exception("artifact failure"), None)
            raise

    def finalize_full(
        self,
        *,
        state: ExecutionEvidenceState,
        context: Mapping[str, object],
        reducer_rows: Sequence[Mapping[str, object]],
        resource_rows: Sequence[Mapping[str, object]],
        terminal_class: str,
        research_conclusion: str,
        return_code: int,
        taxonomy_result: TaxonomyResult,
    ) -> ArtifactOutcome:
        return self._finalize(
            state=state,
            context=context,
            reducer_rows=reducer_rows,
            resource_rows=resource_rows,
            terminal_class=terminal_class,
            research_conclusion=research_conclusion,
            return_code=return_code,
            taxonomy_result=taxonomy_result,
            empty_science=False,
        )

    def finalize_empty(
        self,
        *,
        state: ExecutionEvidenceState,
        context: Mapping[str, object],
        reducer_rows: Sequence[Mapping[str, object]],
        resource_rows: Sequence[Mapping[str, object]],
        terminal_class: str,
        research_conclusion: str,
        return_code: int = 21,
    ) -> ArtifactOutcome:
        return self._finalize(
            state=state,
            context=context,
            reducer_rows=reducer_rows,
            resource_rows=resource_rows,
            terminal_class=terminal_class,
            research_conclusion=research_conclusion,
            return_code=return_code,
            taxonomy_result=None,
            empty_science=True,
        )

    def abort(self) -> None:
        if self._finished:
            return
        errors: list[BaseException] = []
        try:
            self.metadata.abort()
        except BaseException as exc:
            errors.append(exc)
        try:
            if not self.science._closed:
                self.science.abort()
        except BaseException as exc:
            errors.append(exc)
        try:
            self.atomic.__exit__(Exception, Exception("session abort"), None)
        except BaseException as exc:
            errors.append(exc)
        self._finished = True
        if errors:
            raise ArtifactError("artifact session abort failed") from errors[0]
