from __future__ import annotations

import dataclasses
import enum
import hashlib
from collections import Counter
from collections.abc import Iterator, Mapping
from typing import Protocol
from pathlib import Path

from .canonical import FrozenObject, NumberToken, canonical_json_bytes, strict_json_loads
from .identity import frame
from .join import DiskJoinLedger
from .materialize_r3 import MaterializedIndexes
from .storage import WorkspaceMeter, external_sort_partition, iter_equality_group_spools, iter_frames

_MAX_GROUP_KEYS = 100_000


class TaxonomyError(RuntimeError):
    pass


class Taxon(str, enum.Enum):
    TID_SCOPE_FALSE_POSITIVE = "TID_SCOPE_FALSE_POSITIVE"
    EXPECTED_COUNTERPARTY_PAIR = "EXPECTED_COUNTERPARTY_PAIR"
    EXACT_BLOCK_REPLAY_ACROSS_OBJECTS = "EXACT_BLOCK_REPLAY_ACROSS_OBJECTS"
    EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY = "EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY"
    CONFLICTING_BLOCK_REPLAY = "CONFLICTING_BLOCK_REPLAY"
    CONFLICTING_USER_FILL = "CONFLICTING_USER_FILL"
    INTRA_BLOCK_REPEAT = "INTRA_BLOCK_REPEAT"
    TID_SCHEMA_VIOLATION = "TID_SCHEMA_VIOLATION"
    UNCLASSIFIABLE = "UNCLASSIFIABLE"


class UnitUniverse(str, enum.Enum):
    BLOCK_NUMBER_REPEAT = "BLOCK_NUMBER_REPEAT"
    LEGACY_WEAK_KEY_REPEAT = "LEGACY_WEAK_KEY_REPEAT"
    WALLET_FILL_REPEAT = "WALLET_FILL_REPEAT"
    PROTOCOL_TRADE_GROUP = "PROTOCOL_TRADE_GROUP"


class EvidenceEmitter(Protocol):
    def emit(self, container: str, row: Mapping[str, object]) -> None: ...


@dataclasses.dataclass(frozen=True, slots=True)
class BlockProof:
    block_number: int
    proof_id: str
    exact_replay: bool
    conflicting: bool
    raw_locators: frozenset[tuple[str, int]]


@dataclasses.dataclass(slots=True)
class UniverseConservation:
    group_count: int = 0
    occurrence_count: int = 0
    taxon_group_counts: Counter[str] = dataclasses.field(default_factory=Counter)
    taxon_occurrence_counts: Counter[str] = dataclasses.field(default_factory=Counter)

    def add(self, taxon: Taxon, occurrences: int) -> None:
        if occurrences <= 0:
            raise TaxonomyError("taxonomy occurrence count must be positive")
        self.group_count += 1
        self.occurrence_count += occurrences
        self.taxon_group_counts[taxon.value] += 1
        self.taxon_occurrence_counts[taxon.value] += occurrences

    def mapping(self, universe: UnitUniverse) -> dict[str, object]:
        if sum(self.taxon_group_counts.values()) != self.group_count:
            raise TaxonomyError("taxonomy group conservation failed")
        if sum(self.taxon_occurrence_counts.values()) != self.occurrence_count:
            raise TaxonomyError("taxonomy occurrence conservation failed")
        return {
            "unit_universe": universe.value,
            "group_count": self.group_count,
            "occurrence_count": self.occurrence_count,
            "taxon_group_counts": dict(sorted(self.taxon_group_counts.items())),
            "taxon_occurrence_counts": dict(sorted(self.taxon_occurrence_counts.items())),
            "unclassifiable_group_count": self.taxon_group_counts[Taxon.UNCLASSIFIABLE.value],
            "unclassifiable_occurrence_count": self.taxon_occurrence_counts[Taxon.UNCLASSIFIABLE.value],
        }


@dataclasses.dataclass(frozen=True, slots=True)
class TaxonomyResult:
    conservation_rows: tuple[dict[str, object], ...]
    secondary_sort_rows: tuple[dict[str, object], ...]
    join_partition_rows: tuple[dict[str, object], ...]
    block_proof_count: int
    pair_proof_count: int
    proof_reference_count: int
    all_proof_references_resolve: bool
    all_unit_ids_unique: bool
    all_duplicate_rows_reference_one_unit: bool
    terminal_unclassifiable_group_count: int
    terminal_unclassifiable_occurrence_count: int


def _object(value: object, label: str) -> FrozenObject:
    if not isinstance(value, FrozenObject):
        raise TaxonomyError(f"{label} must be an object")
    return value


def _array(value: object, label: str) -> tuple[object, ...]:
    if not isinstance(value, tuple):
        raise TaxonomyError(f"{label} must be an array")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise TaxonomyError(f"{label} must be a string")
    return value


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _integer(value: object, label: str) -> int:
    if isinstance(value, NumberToken) and value.is_integer_token:
        return int(value.token, 10)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise TaxonomyError(f"{label} must be an exact integer")


def _row(payload: bytes) -> FrozenObject:
    return _object(strict_json_loads(payload), "materialized observation")


def _rows(path: Path, meter: WorkspaceMeter, phase: str) -> Iterator[FrozenObject]:
    for payload in iter_frames(path, runtime_guard=meter.runtime_guard, phase=phase):
        yield _row(payload)


def _locator(row: FrozenObject) -> tuple[str, int, int | None]:
    locator = _object(row["raw_locator"], "raw_locator")
    object_key = _text(locator["object_key"], "object_key")
    record_ordinal = _integer(locator["decompressed_record_ordinal_zero_based"], "record ordinal")
    event_ordinal = None
    if "event_ordinal_zero_based" in locator:
        event_ordinal = _integer(locator["event_ordinal_zero_based"], "event ordinal")
    return object_key, record_ordinal, event_ordinal


def _unit_id(universe: UnitUniverse, key: bytes) -> str:
    return hashlib.sha256(frame(universe.value.encode("ascii"), key)).hexdigest()


def _proof_id(proof_type: str, key: bytes) -> str:
    return hashlib.sha256(frame(proof_type.encode("ascii"), key)).hexdigest()


def _emit_unit(
    *,
    emitter: EvidenceEmitter,
    joins: DiskJoinLedger,
    conservation: UniverseConservation,
    universe: UnitUniverse,
    equality_key: bytes,
    taxon: Taxon,
    occurrence_count: int,
    proof_references: tuple[tuple[str, str], ...] = (),
) -> str:
    unit_id = _unit_id(universe, equality_key)
    joins.add_unit(unit_id)
    conservation.add(taxon, occurrence_count)
    emitter.emit(
        "r11a-taxonomy-units.ndjson",
        {
            "record_type": "TAXONOMY_UNIT",
            "taxonomy_unit_id": unit_id,
            "unit_universe": universe.value,
            "equality_key_sha256": hashlib.sha256(equality_key).hexdigest(),
            "primary_taxon": taxon.value,
            "occurrence_count": occurrence_count,
            "proof_references": [
                {"proof_type": proof_type, "proof_id": proof_id}
                for proof_type, proof_id in proof_references
            ],
        },
    )
    for proof_type, proof_id in proof_references:
        joins.add_reference(unit_id, proof_id, proof_type)
    return unit_id


def _duplicate_mapping(unit_id: str, taxon: Taxon, row: FrozenObject) -> dict[str, object]:
    return {
        "record_type": "DUPLICATE_OBSERVATION",
        "taxonomy_unit_id": unit_id,
        "primary_taxon": taxon.value,
        "raw_locator": row["raw_locator"],
        "block_number": row["block_number"],
        "exact_raw_local_time": row["exact_raw_local_time"],
        "exact_raw_block_time": row["exact_raw_block_time"],
        "canonical_wallet": row["canonical_wallet"],
        "exact_raw_coin_string": row["exact_raw_coin_string"],
        "validated_tid": row["validated_tid"],
        "exact_raw_side_string": row["exact_raw_side_string"],
        "full_event_sha256": row["full_event_sha256"],
        "fill_payload_sha256": row["fill_payload_sha256"],
        "schema_errors": row["schema_errors"],
        "selected_fill_payload": row["selected_fill_payload"],
    }


def _emit_duplicate(
    emitter: EvidenceEmitter,
    joins: DiskJoinLedger,
    unit_id: str,
    taxon: Taxon,
    row: FrozenObject,
) -> None:
    mapping = _duplicate_mapping(unit_id, taxon, row)
    joins.add_duplicate_row(unit_id, hashlib.sha256(canonical_json_bytes(mapping)).hexdigest())
    emitter.emit("r11a-duplicate-observations.ndjson", mapping)


def _sorted_partitions(
    *,
    reducer_id: str,
    directory: Path,
    commitments: tuple[dict[str, object], ...],
    meter: WorkspaceMeter,
) -> Iterator[tuple[int, Path, Path, dict[str, object]]]:
    for partition in range(256):
        source = directory / f"part-{partition:03d}.frames"
        destination = meter.root / f"taxonomy-{reducer_id.lower()}-{partition:03d}.frames"
        temporary = meter.root / f"taxonomy-{reducer_id.lower()}-{partition:03d}-temp"
        evidence = external_sort_partition(
            source,
            destination,
            temporary,
            meter,
            source_commitment=commitments[partition],
            maximum_source_bytes=source.stat().st_size,
        )
        yield partition, destination, meter.root / f"taxonomy-{reducer_id.lower()}-{partition:03d}-groups", {
            "reducer_id": reducer_id,
            "partition_ordinal_zero_based": partition,
            "source_multiset_commitment": evidence.source_commitment,
            "destination_multiset_commitment": evidence.destination_commitment,
            "sorted_stream_sha256": evidence.sorted_stream_sha256,
            "sorted_file_bytes": evidence.output_bytes,
        }


def _locator_commitment_update(hasher: object, row: FrozenObject) -> None:
    object_key, record_ordinal, event_ordinal = _locator(row)
    encoded = frame(
        object_key.encode("utf-8"),
        record_ordinal.to_bytes(8, "big"),
        (0xFFFFFFFF if event_ordinal is None else event_ordinal).to_bytes(4, "big"),
    )
    hasher.update(len(encoded).to_bytes(8, "big"))  # type: ignore[attr-defined]
    hasher.update(encoded)  # type: ignore[attr-defined]


def _classify_blocks(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    joins: DiskJoinLedger,
    conservation: UniverseConservation,
) -> tuple[dict[int, BlockProof], list[dict[str, object]]]:
    proofs: dict[int, BlockProof] = {}
    sort_rows: list[dict[str, object]] = []
    for partition, sorted_path, spool_directory, sort_row in _sorted_partitions(
        reducer_id="MATERIALIZED_BLOCK_NUMBER",
        directory=materialized.block_directory,
        commitments=materialized.block_commitments,
        meter=meter,
    ):
        sort_rows.append(sort_row)
        for group in iter_equality_group_spools(
            sorted_path,
            spool_directory,
            meter,
            maximum_group_spool_bytes=meter.limits.maximum_equality_group_spool_bytes,
        ):
            occurrence_count = 0
            block_number: int | None = None
            invariants: set[tuple[str, int, str]] = set()
            source_objects: set[str] = set()
            raw_locators: set[tuple[str, int]] = set()
            locator_commitment = hashlib.sha256()
            overflow = False
            for row in _rows(group.path, meter, "summarize block group"):
                occurrence_count += 1
                current = _integer(row["block_number"], "block number")
                if block_number is None:
                    block_number = current
                elif block_number != current:
                    raise TaxonomyError("block-number group contains different block numbers")
                invariants.add(
                    (
                        _text(row["exact_raw_block_time"], "block time"),
                        _integer(row["ordered_event_count"], "ordered event count"),
                        _text(row["ordered_event_fingerprint"], "event fingerprint"),
                    )
                )
                object_key, record_ordinal, _ = _locator(row)
                source_objects.add(object_key)
                raw_locators.add((object_key, record_ordinal))
                _locator_commitment_update(locator_commitment, row)
                if max(len(invariants), len(source_objects), len(raw_locators)) > _MAX_GROUP_KEYS:
                    overflow = True
            if occurrence_count <= 1:
                continue
            if block_number is None:
                raise TaxonomyError("empty repeated block group")
            if overflow:
                taxon = Taxon.UNCLASSIFIABLE
            elif len(invariants) > 1:
                taxon = Taxon.CONFLICTING_BLOCK_REPLAY
            elif len(source_objects) > 1:
                taxon = Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS
            else:
                taxon = Taxon.INTRA_BLOCK_REPEAT
            proof_id = ""
            references: tuple[tuple[str, str], ...] = ()
            invariant = sorted(invariants)[0] if invariants else ("", 0, "")
            if taxon is Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS:
                proof_id = _proof_id("EXACT_BLOCK_REPLAY_PROOF", group.equality_key)
                joins.add_proof(proof_id, "EXACT_BLOCK_REPLAY_PROOF")
                emitter.emit(
                    "r11a-exact-block-replay-proofs.ndjson",
                    {
                        "record_type": "EXACT_BLOCK_REPLAY_PROOF",
                        "proof_id": proof_id,
                        "block_number": block_number,
                        "occurrence_count": occurrence_count,
                        "distinct_source_object_count": len(source_objects),
                        "distinct_raw_locator_count": len(raw_locators),
                        "ordered_raw_locator_commitment_sha256": locator_commitment.hexdigest(),
                        "exact_raw_block_time": invariant[0],
                        "ordered_event_count": invariant[1],
                        "ordered_event_fingerprint": invariant[2],
                    },
                )
                references = (("EXACT_BLOCK_REPLAY_PROOF", proof_id),)
            unit_id = _emit_unit(
                emitter=emitter,
                joins=joins,
                conservation=conservation,
                universe=UnitUniverse.BLOCK_NUMBER_REPEAT,
                equality_key=group.equality_key,
                taxon=taxon,
                occurrence_count=occurrence_count,
                proof_references=references,
            )
            for row in _rows(group.path, meter, "emit block matrix"):
                mapping = {
                    "record_type": "BLOCK_OVERLAP_OBSERVATION",
                    "taxonomy_unit_id": unit_id,
                    "primary_taxon": taxon.value,
                    "block_number": row["block_number"],
                    "raw_locator": row["raw_locator"],
                    "exact_raw_block_time": row["exact_raw_block_time"],
                    "ordered_event_count": row["ordered_event_count"],
                    "ordered_event_fingerprint": row["ordered_event_fingerprint"],
                    "raw_record_fingerprint": row["raw_record_fingerprint"],
                }
                emitter.emit("r11a-block-overlap-matrix.ndjson", mapping)
                joins.add_duplicate_row(unit_id, hashlib.sha256(canonical_json_bytes(mapping)).hexdigest())
            if len(proofs) >= meter.limits.maximum_repeated_block_groups_retained:
                raise TaxonomyError("block proof map exceeds preregistered retained-group cap")
            proofs[block_number] = BlockProof(
                block_number,
                proof_id,
                taxon is Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS,
                taxon is Taxon.CONFLICTING_BLOCK_REPLAY,
                frozenset(raw_locators),
            )
        meter.delete_file(sorted_path)
        meter.delete_file(materialized.block_directory / f"part-{partition:03d}.frames")
    if materialized.block_directory.exists():
        materialized.block_directory.rmdir()
    return proofs, sort_rows


def _classify_wallet_fills(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    joins: DiskJoinLedger,
    conservation: UniverseConservation,
    block_proofs: Mapping[int, BlockProof],
) -> list[dict[str, object]]:
    sort_rows: list[dict[str, object]] = []
    for partition, sorted_path, spool_directory, sort_row in _sorted_partitions(
        reducer_id="WALLET_FILL",
        directory=materialized.wallet_fill_directory,
        commitments=materialized.wallet_fill_commitments,
        meter=meter,
    ):
        sort_rows.append(sort_row)
        for group in iter_equality_group_spools(
            sorted_path,
            spool_directory,
            meter,
            maximum_group_spool_bytes=meter.limits.maximum_equality_group_spool_bytes,
        ):
            occurrences = 0
            event_hashes: set[str] = set()
            raw_blocks: set[tuple[str, int]] = set()
            proof_ids: set[str] = set()
            all_replay_proven = True
            overflow = False
            for row in _rows(group.path, meter, "summarize wallet-fill group"):
                occurrences += 1
                event_hashes.add(_text(row["full_event_sha256"], "event hash"))
                object_key, record_ordinal, _ = _locator(row)
                raw_block = (object_key, record_ordinal)
                raw_blocks.add(raw_block)
                proof = block_proofs.get(_integer(row["block_number"], "block number"))
                if proof is None or not proof.exact_replay or raw_block not in proof.raw_locators:
                    all_replay_proven = False
                else:
                    proof_ids.add(proof.proof_id)
                if max(len(event_hashes), len(raw_blocks), len(proof_ids)) > _MAX_GROUP_KEYS:
                    overflow = True
            if occurrences <= 1:
                continue
            if overflow:
                taxon = Taxon.UNCLASSIFIABLE
                references: tuple[tuple[str, str], ...] = ()
            elif len(event_hashes) > 1:
                taxon = Taxon.CONFLICTING_USER_FILL
                references = ()
            elif len(raw_blocks) < occurrences:
                taxon = Taxon.INTRA_BLOCK_REPEAT
                references = ()
            elif all_replay_proven and proof_ids:
                taxon = Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY
                references = tuple(
                    ("EXACT_BLOCK_REPLAY_PROOF", proof_id) for proof_id in sorted(proof_ids)
                )
            else:
                taxon = Taxon.UNCLASSIFIABLE
                references = ()
            unit_id = _emit_unit(
                emitter=emitter,
                joins=joins,
                conservation=conservation,
                universe=UnitUniverse.WALLET_FILL_REPEAT,
                equality_key=group.equality_key,
                taxon=taxon,
                occurrence_count=occurrences,
                proof_references=references,
            )
            for row in _rows(group.path, meter, "emit wallet-fill rows"):
                _emit_duplicate(emitter, joins, unit_id, taxon, row)
        meter.delete_file(sorted_path)
        meter.delete_file(materialized.wallet_fill_directory / f"part-{partition:03d}.frames")
    if materialized.wallet_fill_directory.exists():
        materialized.wallet_fill_directory.rmdir()
    return sort_rows


@dataclasses.dataclass(slots=True)
class _ProtocolBlockState:
    count: int = 0
    wallets: set[str] = dataclasses.field(default_factory=set)
    sides: set[str] = dataclasses.field(default_factory=set)
    minimum_ordinal: int | None = None
    maximum_ordinal: int | None = None
    distinct_ordinal_count: int = 0

    def add(self, wallet: str | None, side: str | None, ordinal: int | None) -> None:
        self.count += 1
        if wallet is not None and len(self.wallets) < 3:
            self.wallets.add(wallet)
        if side is not None and len(self.sides) < 3:
            self.sides.add(side)
        if ordinal is not None:
            if self.minimum_ordinal is None or ordinal < self.minimum_ordinal:
                self.minimum_ordinal = ordinal
            if self.maximum_ordinal is None or ordinal > self.maximum_ordinal:
                self.maximum_ordinal = ordinal
            self.distinct_ordinal_count += 1

    def is_expected_pair(self) -> bool:
        return (
            self.count == 2
            and len(self.wallets) == 2
            and self.sides == {"A", "B"}
            and self.minimum_ordinal is not None
            and self.maximum_ordinal == self.minimum_ordinal + 1
            and self.distinct_ordinal_count == 2
        )


def _classify_protocol_trades(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    joins: DiskJoinLedger,
    conservation: UniverseConservation,
) -> list[dict[str, object]]:
    sort_rows: list[dict[str, object]] = []
    for partition, sorted_path, spool_directory, sort_row in _sorted_partitions(
        reducer_id="PROTOCOL_TRADE",
        directory=materialized.protocol_trade_directory,
        commitments=materialized.protocol_trade_commitments,
        meter=meter,
    ):
        sort_rows.append(sort_row)
        for group in iter_equality_group_spools(
            sorted_path,
            spool_directory,
            meter,
            maximum_group_spool_bytes=meter.limits.maximum_equality_group_spool_bytes,
        ):
            occurrences = 0
            blocks: dict[tuple[str, int], _ProtocolBlockState] = {}
            commitment = hashlib.sha256()
            overflow = False
            for row in _rows(group.path, meter, "summarize protocol-trade group"):
                occurrences += 1
                object_key, record_ordinal, event_ordinal = _locator(row)
                state = blocks.setdefault((object_key, record_ordinal), _ProtocolBlockState())
                state.add(
                    _optional_text(row["canonical_wallet"], "wallet"),
                    _optional_text(row["exact_raw_side_string"], "side"),
                    event_ordinal,
                )
                _locator_commitment_update(commitment, row)
                if len(blocks) > _MAX_GROUP_KEYS:
                    overflow = True
            if occurrences <= 1:
                continue
            expected = not overflow and bool(blocks) and all(state.is_expected_pair() for state in blocks.values())
            if expected:
                taxon = Taxon.EXPECTED_COUNTERPARTY_PAIR
                proof_id = _proof_id("EXPECTED_COUNTERPARTY_PAIR_PROOF", group.equality_key)
                joins.add_proof(proof_id, "EXPECTED_COUNTERPARTY_PAIR_PROOF")
                emitter.emit(
                    "r11a-expected-counterparty-pair-proofs.ndjson",
                    {
                        "record_type": "EXPECTED_COUNTERPARTY_PAIR_PROOF",
                        "proof_id": proof_id,
                        "protocol_trade_key_sha256": hashlib.sha256(group.equality_key).hexdigest(),
                        "raw_block_occurrence_count": len(blocks),
                        "event_occurrence_count": occurrences,
                        "ordered_raw_locator_commitment_sha256": commitment.hexdigest(),
                    },
                )
                references = (("EXPECTED_COUNTERPARTY_PAIR_PROOF", proof_id),)
            else:
                taxon = Taxon.UNCLASSIFIABLE
                references = ()
            unit_id = _emit_unit(
                emitter=emitter,
                joins=joins,
                conservation=conservation,
                universe=UnitUniverse.PROTOCOL_TRADE_GROUP,
                equality_key=group.equality_key,
                taxon=taxon,
                occurrence_count=occurrences,
                proof_references=references,
            )
            for row in _rows(group.path, meter, "emit protocol members"):
                mapping = {
                    "record_type": "PROTOCOL_TRADE_GROUP_MEMBER",
                    "taxonomy_unit_id": unit_id,
                    "primary_taxon": taxon.value,
                    "raw_locator": row["raw_locator"],
                    "canonical_wallet": row["canonical_wallet"],
                    "exact_raw_side_string": row["exact_raw_side_string"],
                    "full_event_sha256": row["full_event_sha256"],
                }
                emitter.emit("r11a-protocol-trade-group-members.ndjson", mapping)
                joins.add_duplicate_row(unit_id, hashlib.sha256(canonical_json_bytes(mapping)).hexdigest())
        meter.delete_file(sorted_path)
        meter.delete_file(materialized.protocol_trade_directory / f"part-{partition:03d}.frames")
    if materialized.protocol_trade_directory.exists():
        materialized.protocol_trade_directory.rmdir()
    return sort_rows


@dataclasses.dataclass(slots=True)
class _WeakWalletState:
    occurrences: int = 0
    first_event_hash: str | None = None
    conflicting: bool = False
    raw_blocks: set[tuple[str, int]] = dataclasses.field(default_factory=set)
    all_replay_proven: bool = True
    proof_ids: set[str] = dataclasses.field(default_factory=set)


def _classify_weak_keys(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    joins: DiskJoinLedger,
    conservation: UniverseConservation,
    block_proofs: Mapping[int, BlockProof],
) -> list[dict[str, object]]:
    sort_rows: list[dict[str, object]] = []
    for partition, sorted_path, spool_directory, sort_row in _sorted_partitions(
        reducer_id="EXACT_LEGACY_WEAK_KEY",
        directory=materialized.weak_directory,
        commitments=materialized.weak_commitments,
        meter=meter,
    ):
        sort_rows.append(sort_row)
        for group in iter_equality_group_spools(
            sorted_path,
            spool_directory,
            meter,
            maximum_group_spool_bytes=meter.limits.maximum_equality_group_spool_bytes,
        ):
            occurrences = 0
            schema_invalid = False
            missing_identity = False
            conflicting_block = False
            protocol_keys: set[str] = set()
            wallets: dict[str, _WeakWalletState] = {}
            raw_block_key_count = 0
            overflow = False
            for row in _rows(group.path, meter, "summarize exact weak-key group"):
                occurrences += 1
                if _array(row["schema_errors"], "schema errors"):
                    schema_invalid = True
                protocol_key = _optional_text(row["protocol_trade_key_hex"], "protocol key")
                wallet_key = _optional_text(row["wallet_fill_key_hex"], "wallet fill key")
                if protocol_key is None or wallet_key is None:
                    missing_identity = True
                    continue
                if len(protocol_keys) < 3:
                    protocol_keys.add(protocol_key)
                state = wallets.setdefault(wallet_key, _WeakWalletState())
                state.occurrences += 1
                event_hash = _text(row["full_event_sha256"], "event hash")
                if state.first_event_hash is None:
                    state.first_event_hash = event_hash
                elif state.first_event_hash != event_hash:
                    state.conflicting = True
                object_key, record_ordinal, _ = _locator(row)
                raw_block = (object_key, record_ordinal)
                if raw_block not in state.raw_blocks:
                    state.raw_blocks.add(raw_block)
                    raw_block_key_count += 1
                proof = block_proofs.get(_integer(row["block_number"], "block number"))
                if proof is not None and proof.conflicting:
                    conflicting_block = True
                if proof is None or not proof.exact_replay or raw_block not in proof.raw_locators:
                    state.all_replay_proven = False
                else:
                    state.proof_ids.add(proof.proof_id)
                if len(wallets) > _MAX_GROUP_KEYS or raw_block_key_count > _MAX_GROUP_KEYS:
                    overflow = True
            conflicting_wallet = any(state.conflicting for state in wallets.values())
            intra_block = any(state.occurrences > len(state.raw_blocks) for state in wallets.values())
            replay_states = [
                state
                for state in wallets.values()
                if state.occurrences > 1 and state.all_replay_proven and state.proof_ids
            ]
            replay_proofs = {proof for state in replay_states for proof in state.proof_ids}
            if overflow:
                taxon = Taxon.UNCLASSIFIABLE
                references: tuple[tuple[str, str], ...] = ()
            elif schema_invalid:
                taxon = Taxon.TID_SCHEMA_VIOLATION
                references = ()
            elif conflicting_block:
                taxon = Taxon.UNCLASSIFIABLE
                references = ()
            elif conflicting_wallet:
                taxon = Taxon.CONFLICTING_USER_FILL
                references = ()
            elif intra_block:
                taxon = Taxon.INTRA_BLOCK_REPEAT
                references = ()
            elif replay_states:
                taxon = Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY
                references = tuple(
                    ("EXACT_BLOCK_REPLAY_PROOF", proof_id) for proof_id in sorted(replay_proofs)
                )
            elif not missing_identity and len(protocol_keys) >= 2:
                taxon = Taxon.TID_SCOPE_FALSE_POSITIVE
                references = ()
            else:
                taxon = Taxon.UNCLASSIFIABLE
                references = ()
            unit_id = _emit_unit(
                emitter=emitter,
                joins=joins,
                conservation=conservation,
                universe=UnitUniverse.LEGACY_WEAK_KEY_REPEAT,
                equality_key=group.equality_key,
                taxon=taxon,
                occurrence_count=occurrences,
                proof_references=references,
            )
            for row in _rows(group.path, meter, "emit exact weak-key rows"):
                _emit_duplicate(emitter, joins, unit_id, taxon, row)
                errors = _array(row["schema_errors"], "schema errors")
                if errors:
                    emitter.emit(
                        "r11a-schema-violation-evidence.ndjson",
                        {
                            "record_type": "SCHEMA_VIOLATION_OBSERVATION",
                            "taxonomy_unit_id": unit_id,
                            "raw_locator": row["raw_locator"],
                            "schema_errors": list(errors),
                            "legacy_weak_key_sha256": hashlib.sha256(group.equality_key).hexdigest(),
                        },
                    )
        meter.delete_file(sorted_path)
        meter.delete_file(materialized.weak_directory / f"part-{partition:03d}.frames")
    if materialized.weak_directory.exists():
        materialized.weak_directory.rmdir()
    return sort_rows


def classify_materialized_candidates(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
) -> TaxonomyResult:
    if materialized.cap_fallback_required:
        raise TaxonomyError("truncated materialization cannot enter taxonomy")
    joins = DiskJoinLedger(meter)
    conservation = {universe: UniverseConservation() for universe in UnitUniverse}
    try:
        block_proofs, sort_rows = _classify_blocks(
            materialized,
            meter,
            emitter,
            joins,
            conservation[UnitUniverse.BLOCK_NUMBER_REPEAT],
        )
        sort_rows += _classify_wallet_fills(
            materialized,
            meter,
            emitter,
            joins,
            conservation[UnitUniverse.WALLET_FILL_REPEAT],
            block_proofs,
        )
        sort_rows += _classify_protocol_trades(
            materialized,
            meter,
            emitter,
            joins,
            conservation[UnitUniverse.PROTOCOL_TRADE_GROUP],
        )
        sort_rows += _classify_weak_keys(
            materialized,
            meter,
            emitter,
            joins,
            conservation[UnitUniverse.LEGACY_WEAK_KEY_REPEAT],
            block_proofs,
        )
        join_result = joins.validate()
    except Exception:
        joins.abort()
        raise
    conservation_rows = tuple(conservation[universe].mapping(universe) for universe in UnitUniverse)
    return TaxonomyResult(
        conservation_rows=conservation_rows,
        secondary_sort_rows=tuple(sort_rows),
        join_partition_rows=join_result.partition_rows,
        block_proof_count=sum(1 for proof in block_proofs.values() if proof.exact_replay),
        pair_proof_count=sum(
            int(row["taxon_group_counts"].get(Taxon.EXPECTED_COUNTERPARTY_PAIR.value, 0))
            for row in conservation_rows
            if row["unit_universe"] == UnitUniverse.PROTOCOL_TRADE_GROUP.value
        ),
        proof_reference_count=join_result.proof_reference_count,
        all_proof_references_resolve=join_result.all_proof_references_resolve_exactly_once,
        all_unit_ids_unique=(join_result.all_unit_ids_unique and join_result.all_proof_ids_unique),
        all_duplicate_rows_reference_one_unit=join_result.all_duplicate_rows_reference_exactly_one_unit,
        terminal_unclassifiable_group_count=sum(int(row["unclassifiable_group_count"]) for row in conservation_rows),
        terminal_unclassifiable_occurrence_count=sum(int(row["unclassifiable_occurrence_count"]) for row in conservation_rows),
    )
