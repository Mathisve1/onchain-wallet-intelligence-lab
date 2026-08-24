from __future__ import annotations

import dataclasses
import hashlib
import struct
from pathlib import Path
from typing import Final

from .identity import frame
from .index_r3 import SharedPartitionWriter
from .storage import (
    WorkspaceMeter,
    decode_keyed_record,
    external_sort_partition,
    iter_equality_group_spools,
    iter_frames,
)

_JOIN_DIRECTORY_MAX_BYTES: Final[int] = 700_000_000
_MAX_KEYS_PER_PARTITION: Final[int] = 250_000
_UINT32: Final[struct.Struct] = struct.Struct(">I")


class JoinError(RuntimeError):
    pass


def _unframe(value: bytes) -> tuple[bytes, ...]:
    offset = 0
    parts: list[bytes] = []
    while offset < len(value):
        if offset + _UINT32.size > len(value):
            raise JoinError("truncated join frame length")
        length = _UINT32.unpack_from(value, offset)[0]
        offset += _UINT32.size
        end = offset + length
        if end > len(value):
            raise JoinError("truncated join frame payload")
        parts.append(value[offset:end])
        offset = end
    return tuple(parts)


@dataclasses.dataclass(frozen=True, slots=True)
class JoinValidationResult:
    all_unit_ids_unique: bool
    all_proof_ids_unique: bool
    all_proof_references_resolve_exactly_once: bool
    all_duplicate_rows_reference_exactly_one_unit: bool
    unit_count: int
    proof_count: int
    proof_reference_count: int
    duplicate_row_reference_count: int
    partition_rows: tuple[dict[str, object], ...]


class DiskJoinLedger:
    """Multiplicity-preserving disk join for units, proofs and references.

    No correctness claim depends on an in-memory global set. Each join key is
    partitioned and externally sorted; per-partition key state has an explicit cap.
    """

    def __init__(self, meter: WorkspaceMeter) -> None:
        self.meter = meter
        self.root = meter.root / "taxonomy-join-ledger"
        self.root.mkdir(parents=True, exist_ok=False)
        per_writer = _JOIN_DIRECTORY_MAX_BYTES // 5
        self.units = SharedPartitionWriter(
            self.root / "units",
            meter,
            maximum_total_bytes=per_writer,
            label="taxonomy unit join ledger",
        )
        self.proofs = SharedPartitionWriter(
            self.root / "proofs",
            meter,
            maximum_total_bytes=per_writer,
            label="taxonomy proof join ledger",
        )
        self.references_by_unit = SharedPartitionWriter(
            self.root / "references-by-unit",
            meter,
            maximum_total_bytes=per_writer,
            label="proof references by unit",
        )
        self.references_by_proof = SharedPartitionWriter(
            self.root / "references-by-proof",
            meter,
            maximum_total_bytes=per_writer,
            label="proof references by proof",
        )
        self.duplicate_rows = SharedPartitionWriter(
            self.root / "duplicate-rows-by-unit",
            meter,
            maximum_total_bytes=per_writer,
            label="duplicate rows by taxonomy unit",
        )
        self._closed = False
        self._unit_count = 0
        self._proof_count = 0
        self._reference_count = 0
        self._duplicate_count = 0

    @staticmethod
    def _id_bytes(value: str, label: str) -> bytes:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise JoinError(f"{label} must be lowercase SHA-256 hex")
        return bytes.fromhex(value)

    def add_unit(self, unit_id: str) -> None:
        unit = self._id_bytes(unit_id, "unit ID")
        self.units.write(unit, b"U")
        self._unit_count += 1

    def add_proof(self, proof_id: str, proof_type: str) -> None:
        proof = self._id_bytes(proof_id, "proof ID")
        encoded_type = proof_type.encode("ascii")
        self.proofs.write(proof, encoded_type)
        self._proof_count += 1

    def add_reference(self, unit_id: str, proof_id: str, proof_type: str) -> None:
        unit = self._id_bytes(unit_id, "reference unit ID")
        proof = self._id_bytes(proof_id, "reference proof ID")
        encoded_type = proof_type.encode("ascii")
        self.references_by_unit.write(unit, frame(proof, encoded_type))
        self.references_by_proof.write(proof, frame(unit, encoded_type))
        self._reference_count += 1

    def add_duplicate_row(self, unit_id: str, row_identity_sha256: str) -> None:
        unit = self._id_bytes(unit_id, "duplicate-row unit ID")
        row = self._id_bytes(row_identity_sha256, "duplicate-row identity")
        self.duplicate_rows.write(unit, row)
        self._duplicate_count += 1

    def close(self) -> tuple[
        tuple[dict[str, object], ...],
        tuple[dict[str, object], ...],
        tuple[dict[str, object], ...],
        tuple[dict[str, object], ...],
        tuple[dict[str, object], ...],
    ]:
        if self._closed:
            raise JoinError("join ledger already closed")
        for writer in (
            self.units,
            self.proofs,
            self.references_by_unit,
            self.references_by_proof,
            self.duplicate_rows,
        ):
            writer.close()
        self._closed = True
        return (
            self.units.commitments(),
            self.proofs.commitments(),
            self.references_by_unit.commitments(),
            self.references_by_proof.commitments(),
            self.duplicate_rows.commitments(),
        )

    def abort(self) -> None:
        if self._closed:
            return
        errors: list[BaseException] = []
        for writer in (
            self.units,
            self.proofs,
            self.references_by_unit,
            self.references_by_proof,
            self.duplicate_rows,
        ):
            try:
                writer.abort()
            except BaseException as exc:
                errors.append(exc)
        self._closed = True
        if errors:
            raise JoinError("join-ledger cleanup failed") from errors[0]

    def _sort_directory(
        self,
        name: str,
        commitments: tuple[dict[str, object], ...],
    ) -> tuple[tuple[Path, ...], tuple[dict[str, object], ...]]:
        directory = self.root / name
        sorted_paths: list[Path] = []
        rows: list[dict[str, object]] = []
        for partition in range(256):
            source = directory / f"part-{partition:03d}.frames"
            destination = self.root / f"sorted-{name}-{partition:03d}.frames"
            temporary = self.root / f"sort-{name}-{partition:03d}"
            evidence = external_sort_partition(
                source,
                destination,
                temporary,
                self.meter,
                source_commitment=commitments[partition],
                maximum_source_bytes=source.stat().st_size,
            )
            sorted_paths.append(destination)
            rows.append(
                {
                    "join_ledger": name,
                    "partition_ordinal_zero_based": partition,
                    "source_multiset_commitment": evidence.source_commitment,
                    "destination_multiset_commitment": evidence.destination_commitment,
                    "sorted_stream_sha256": evidence.sorted_stream_sha256,
                    "sorted_file_bytes": evidence.output_bytes,
                }
            )
            self.meter.delete_file(source)
        if directory.exists():
            directory.rmdir()
        return tuple(sorted_paths), tuple(rows)

    @staticmethod
    def _group_payloads(path: Path, meter: WorkspaceMeter, phase: str) -> tuple[bytes, ...]:
        values: list[bytes] = []
        for payload in iter_frames(path, runtime_guard=meter.runtime_guard, phase=phase):
            if len(values) >= _MAX_KEYS_PER_PARTITION:
                raise JoinError("join group exceeds bounded per-partition state")
            values.append(payload)
        return tuple(values)

    def validate(self) -> JoinValidationResult:
        if not self._closed:
            commitments = self.close()
        else:
            commitments = (
                self.units.commitments(),
                self.proofs.commitments(),
                self.references_by_unit.commitments(),
                self.references_by_proof.commitments(),
                self.duplicate_rows.commitments(),
            )
        unit_paths, unit_rows = self._sort_directory("units", commitments[0])
        proof_paths, proof_rows = self._sort_directory("proofs", commitments[1])
        ref_unit_paths, ref_unit_rows = self._sort_directory(
            "references-by-unit", commitments[2]
        )
        ref_proof_paths, ref_proof_rows = self._sort_directory(
            "references-by-proof", commitments[3]
        )
        duplicate_paths, duplicate_rows = self._sort_directory(
            "duplicate-rows-by-unit", commitments[4]
        )
        all_units_unique = True
        all_proofs_unique = True
        all_refs_resolve = True
        all_duplicates_resolve = True

        for partition in range(256):
            unit_keys: set[bytes] = set()
            unit_spool = self.root / f"groups-units-{partition:03d}"
            for group in iter_equality_group_spools(
                unit_paths[partition],
                unit_spool,
                self.meter,
                maximum_group_spool_bytes=self.meter.limits.maximum_equality_group_spool_bytes,
            ):
                payloads = self._group_payloads(group.path, self.meter, "validate unit IDs")
                if payloads != (b"U",):
                    all_units_unique = False
                unit_keys.add(group.equality_key)
                if len(unit_keys) > _MAX_KEYS_PER_PARTITION:
                    raise JoinError("unit partition exceeds bounded key state")

            proof_map: dict[bytes, bytes] = {}
            proof_spool = self.root / f"groups-proofs-{partition:03d}"
            for group in iter_equality_group_spools(
                proof_paths[partition],
                proof_spool,
                self.meter,
                maximum_group_spool_bytes=self.meter.limits.maximum_equality_group_spool_bytes,
            ):
                payloads = self._group_payloads(group.path, self.meter, "validate proof IDs")
                if len(payloads) != 1:
                    all_proofs_unique = False
                    continue
                proof_map[group.equality_key] = payloads[0]
                if len(proof_map) > _MAX_KEYS_PER_PARTITION:
                    raise JoinError("proof partition exceeds bounded key state")

            ref_unit_spool = self.root / f"groups-ref-unit-{partition:03d}"
            for group in iter_equality_group_spools(
                ref_unit_paths[partition],
                ref_unit_spool,
                self.meter,
                maximum_group_spool_bytes=self.meter.limits.maximum_equality_group_spool_bytes,
            ):
                if group.equality_key not in unit_keys:
                    all_refs_resolve = False
                payloads = self._group_payloads(
                    group.path, self.meter, "validate references by unit"
                )
                if len(payloads) != len(set(payloads)):
                    all_refs_resolve = False

            ref_proof_spool = self.root / f"groups-ref-proof-{partition:03d}"
            for group in iter_equality_group_spools(
                ref_proof_paths[partition],
                ref_proof_spool,
                self.meter,
                maximum_group_spool_bytes=self.meter.limits.maximum_equality_group_spool_bytes,
            ):
                expected_type = proof_map.get(group.equality_key)
                if expected_type is None:
                    all_refs_resolve = False
                payloads = self._group_payloads(
                    group.path, self.meter, "validate references by proof"
                )
                if len(payloads) != len(set(payloads)):
                    all_refs_resolve = False
                for payload in payloads:
                    parts = _unframe(payload)
                    if len(parts) != 2 or expected_type is None or parts[1] != expected_type:
                        all_refs_resolve = False

            duplicate_spool = self.root / f"groups-duplicate-{partition:03d}"
            for group in iter_equality_group_spools(
                duplicate_paths[partition],
                duplicate_spool,
                self.meter,
                maximum_group_spool_bytes=self.meter.limits.maximum_equality_group_spool_bytes,
            ):
                if group.equality_key not in unit_keys:
                    all_duplicates_resolve = False
                payloads = self._group_payloads(
                    group.path, self.meter, "validate duplicate-row references"
                )
                if len(payloads) != len(set(payloads)):
                    all_duplicates_resolve = False

            for path in (
                unit_paths[partition],
                proof_paths[partition],
                ref_unit_paths[partition],
                ref_proof_paths[partition],
                duplicate_paths[partition],
            ):
                self.meter.delete_file(path)
        if self.root.exists():
            self.root.rmdir()
        return JoinValidationResult(
            all_unit_ids_unique=all_units_unique,
            all_proof_ids_unique=all_proofs_unique,
            all_proof_references_resolve_exactly_once=(
                all_units_unique and all_proofs_unique and all_refs_resolve
            ),
            all_duplicate_rows_reference_exactly_one_unit=(
                all_units_unique and all_duplicates_resolve
            ),
            unit_count=self._unit_count,
            proof_count=self._proof_count,
            proof_reference_count=self._reference_count,
            duplicate_row_reference_count=self._duplicate_count,
            partition_rows=unit_rows + proof_rows + ref_unit_rows + ref_proof_rows + duplicate_rows,
        )
