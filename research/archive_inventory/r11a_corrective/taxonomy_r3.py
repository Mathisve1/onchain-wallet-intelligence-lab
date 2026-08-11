from __future__ import annotations

import dataclasses
import enum
import hashlib
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping, Protocol
from pathlib import Path

from .canonical import FrozenObject, NumberToken, strict_json_loads
from .identity import frame
from .materialize_r3 import MaterializedIndexes
from .storage import WorkspaceMeter, external_sort_partition, iter_equality_group_spools, iter_frames

_MAX_COMPACT_KEYS_PER_GROUP = 100_000


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

    def add(self, taxon: Taxon, occurrence_count: int) -> None:
        if occurrence_count <= 0:
            raise TaxonomyError("taxonomy group must contain at least one occurrence")
        self.group_count += 1
        self.occurrence_count += occurrence_count
        self.taxon_group_counts[taxon.value] += 1
        self.taxon_occurrence_counts[taxon.value] += occurrence_count

    def row(self, universe: UnitUniverse) -> dict[str, object]:
        if sum(self.taxon_group_counts.values()) != self.group_count:
            raise TaxonomyError("group conservation failed")
        if sum(self.taxon_occurrence_counts.values()) != self.occurrence_count:
            raise TaxonomyError("occurrence conservation failed")
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
    block_proof_count: int
    pair_proof_count: int
    proof_reference_count: int
    all_proof_references_resolve: bool
    all_unit_ids_unique: bool
    all_duplicate_rows_reference_one_unit: bool
    terminal_unclassifiable_group_count: int
    terminal_unclassifiable_occurrence_count: int


class JoinLedger:
    def __init__(self, maximum_entries: int) -> None:
        if maximum_entries <= 0:
            raise TaxonomyError("join-ledger bound must be positive")
        self.maximum_entries = maximum_entries
        self.unit_ids: set[str] = set()
        self.proof_types: dict[str, str] = {}
        self.references: set[tuple[str, str, str]] = set()
        self.reference_count = 0
        self.duplicate_row_count = 0
        self.duplicate_row_resolved_count = 0

    def _check(self) -> None:
        if len(self.unit_ids) + len(self.proof_types) + len(self.references) > self.maximum_entries:
            raise TaxonomyError("bounded join ledger capacity exceeded")

    def add_unit(self, unit_id: str) -> None:
        if unit_id in self.unit_ids:
            raise TaxonomyError("duplicate taxonomy unit ID")
        self.unit_ids.add(unit_id)
        self._check()

    def add_proof(self, proof_id: str, proof_type: str) -> None:
        if proof_id in self.proof_types:
            raise TaxonomyError("duplicate proof ID")
        self.proof_types[proof_id] = proof_type
        self._check()

    def add_reference(self, unit_id: str, proof_id: str, proof_type: str) -> None:
        key = (unit_id, proof_id, proof_type)
        if key in self.references:
            raise TaxonomyError("duplicate proof foreign-key reference")
        self.references.add(key)
        self.reference_count += 1
        self._check()

    def add_duplicate_row(self, unit_id: str) -> None:
        self.duplicate_row_count += 1
        if unit_id in self.unit_ids:
            self.duplicate_row_resolved_count += 1

    def validate(self) -> tuple[bool, bool, bool]:
        all_references_resolve = all(
            unit_id in self.unit_ids and self.proof_types.get(proof_id) == proof_type
            for unit_id, proof_id, proof_type in self.references
        )
        return (
            all_references_resolve,
            True,
            self.duplicate_row_count == self.duplicate_row_resolved_count,
        )


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
    return _object(strict_json_loads(payload), "materialized row")


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


def _unit_id(universe: UnitUniverse, equality_key: bytes) -> str:
    return hashlib.sha256(frame(universe.value.encode("ascii"), equality_key)).hexdigest()


def _proof_id(proof_type: str, equality_key: bytes) -> str:
    return hashlib.sha256(frame(proof_type.encode("ascii"), equality_key)).hexdigest()


def _emit_unit(
    *,
    emitter: EvidenceEmitter,
    joins: JoinLedger,
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


def _emit_duplicate_row(
    emitter: EvidenceEmitter,
    joins: JoinLedger,
    unit_id: str,
    taxon: Taxon,
    row: FrozenObject,
) -> None:
    emitter.emit(
        "r11a-duplicate-observations.ndjson",
        {
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
        },
    )
    joins.add_duplicate_row(unit_id)


def _sorted_groups(
    *,
    reducer_id: str,
    directory: Path,
    commitments: tuple[dict[str, object], ...],
    meter: WorkspaceMeter,
) -> Iterator[tuple[int, Path, Path, dict[str, object]]]:
    for partition in range(256):
        source = directory / f"part-{partition:03d}.frames"
        sorted_path = meter.root / f"taxonomy-{reducer_id.lower()}-{partition:03d}.frames"
        temp = meter.root / f"taxonomy-{reducer_id.lower()}-{partition:03d}-temp"
        evidence = external_sort_partition(
            source,
            sorted_path,
            temp,
            meter,
            source_commitment=commitments[partition],
            maximum_source_bytes=source.stat().st_size,
        )
        spool_directory = meter.root / f"taxonomy-{reducer_id.lower()}-{partition:03d}-groups"
        yield partition, sorted_path, spool_directory, {
            "reducer_id": reducer_id,
            "partition_ordinal_zero_based": partition,
            "source_multiset_commitment": evidence.source_commitment,
            "destination_multiset_commitment": evidence.destination_commitment,
            "sorted_stream_sha256": evidence.sorted_stream_sha256,
            "sorted_file_bytes": evidence.output_bytes,
        }


def _locator_commitment_update(hasher: hashlib._Hash, row: FrozenObject) -> None:
    object_key, record_ordinal, event_ordinal = _locator(row)
    encoded = frame(
        object_key.encode("utf-8"),
        record_ordinal.to_bytes(8, "big"),
        (0xFFFFFFFF if event_ordinal is None else event_ordinal).to_bytes(4, "big"),
    )
    hasher.update(len(encoded).to_bytes(8, "big"))
    hasher.update(encoded)


def _classify_block_groups(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    joins: JoinLedger,
    conservation: UniverseConservation,
) -> tuple[dict[int, BlockProof], list[dict[str, object]]]:
    proofs: dict[int, BlockProof] = {}
    sort_rows: list[dict[str, object]] = []
    for partition, sorted_path, spool_directory, sort_row in _sorted_groups(
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
            for row in _rows(group.path, meter, "summarize block repeat group"):
                occurrence_count += 1
                current_block = _integer(row["block_number"], "block number")
                if block_number is None:
                    block_number = current_block
                elif block_number != current_block:
                    raise TaxonomyError("block-number equality group contains different block numbers")
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
                if max(len(invariants), len(source_objects), len(raw_locators)) > _MAX_COMPACT_KEYS_PER_GROUP:
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
                        "exact_raw_block_time": next(iter(invariants))[0],
                        "ordered_event_count": next(iter(invariants))[1],
                        "ordered_event_fingerprint": next(iter(invariants))[2],
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
            for row in _rows(group.path, meter, "emit block overlap rows"):
                emitter.emit(
                    "r11a-block-overlap-matrix.ndjson",
                    {
                        "record_type": "BLOCK_OVERLAP_OBSERVATION",
                        "taxonomy_unit_id": unit_id,
                        "primary_taxon": taxon.value,
                        "block_number": row["block_number"],
                        "raw_locator": row["raw_locator"],
                        "exact_raw_block_time": row["exact_raw_block_time"],
                        "ordered_event_count": row["ordered_event_count"],
                        "ordered_event_fingerprint": row["ordered_event_fingerprint"],
                        "raw_record_fingerprint": row["raw_record_fingerprint"],
                    },
                )
                joins.add_duplicate_row(unit_id)
            proofs[block_number] = BlockProof(
                block_number=block_number,
                proof_id=proof_id,
                exact_replay=taxon is Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS,
                conflicting=taxon is Taxon.CONFLICTING_BLOCK_REPLAY,
                raw_locators=frozenset(raw_locators),
            )
        meter.delete_file(sorted_path)
        meter.delete_file(materialized.block_directory / f"part-{partition:03d}.frames")
    if materialized.block_directory.exists():
        materialized.block_directory.rmdir()
    return proofs, sort_rows


def _classify_wallet_groups(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    joins: JoinLedger,
    conservation: UniverseConservation,
    block_proofs: Mapping[int, BlockProof],
) -> list[dict[str, object]]:
    sort_rows: list[dict[str, object]] = []
    for partition, sorted_path, spool_directory, sort_row in _sorted_groups(
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
            occurrence_count = 0
            full_hashes: set[str] = set()
            raw_blocks: set[tuple[str, int]] = set()
            proof_ids: set[str] = set()
            all_rows_replay_proven = True
            overflow = False
            for row in _rows(group.path, meter, "summarize wallet-fill group"):
                occurrence_count += 1
                full_hashes.add(_text(row["full_event_sha256"], "full event hash"))
                object_key, record_ordinal, _ = _locator(row)
                raw_block = (object_key, record_ordinal)
                if raw_block in raw_blocks:
                    pass
                raw_blocks.add(raw_block)
                block_number = _integer(row["block_number"], "block number")
                proof = block_proofs.get(block_number)
                if proof is None or not proof.exact_replay or raw_block not in proof.raw_locators:
                    all_rows_replay_proven = False
                else:
                    proof_ids.add(proof.proof_id)
                if max(len(full_hashes), len(raw_blocks), len(proof_ids)) > _MAX_COMPACT_KEYS_PER_GROUP:
                    overflow = True
            if occurrence_count <= 1:
                continue
            duplicate_within_raw_block = len(raw_blocks) < occurrence_count
            if overflow:
                taxon = Taxon.UNCLASSIFIABLE
                references: tuple[tuple[str, str], ...] = ()
            elif len(full_hashes) > 1:
                taxon = Taxon.CONFLICTING_USER_FILL
                references = ()
            elif duplicate_within_raw_block:
                taxon = Taxon.INTRA_BLOCK_REPEAT
                references = ()
            elif all_rows_replay_proven and proof_ids:
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
                occurrence_count=occurrence_count,
                proof_references=references,
            )
            for row in _rows(group.path, meter, "emit wallet-fill duplicate rows"):
                _emit_duplicate_row(emitter, joins, unit_id, taxon, row)
        meter.delete_file(sorted_path)
        meter.delete_file(materialized.wallet_fill_directory / f"part-{partition:03d}.frames")
    if materialized.wallet_fill_directory.exists():
        materialized.wallet_fill_directory.rmdir()
    return sort_rows


def _classify_protocol_groups(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    joins: JoinLedger,
    conservation: UniverseConservation,
) -> list[dict[str, object]]:
    sort_rows: list[dict[str, object]] = []
    for partition, sorted_path, spool_directory, sort_row in _sorted_groups(
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
            occurrence_count = 0
            per_block: dict[tuple[str, int], dict[str, object]] = {}
            overflow = False
            locator_commitment = hashlib.sha256()
            for row in _rows(group.path, meter, "summarize protocol-trade group"):
                occurrence_count += 1
                object_key, record_ordinal, event_ordinal = _locator(row)
                raw_block = (object_key, record_ordinal)
                state = per_block.setdefault(
                    raw_block,
                    {"count": 0, "wallets": set(), "sides": set(), "ordinals": []},
                )
                state["count"] = int(state["count"]) + 1
                wallet = _optional_text(row["canonical_wallet"], "wallet")
                side = _optional_text(row["exact_raw_side_string"], "side")
                if wallet is not None:
                    cast_wallets = state["wallets"]
                    assert isinstance(cast_wallets, set)
                    cast_wallets.add(wallet)
                if side is not None:
                    cast_sides = state["sides"]
                    assert isinstance(cast_sides, set)
                    cast_sides.add(side)
                cast_ordinals = state["ordinals"]
                assert isinstance(cast_ordinals, list)
                cast_ordinals.append(event_ordinal)
                _locator_commitment_update(locator_commitment, row)
                if len(per_block) > _MAX_COMPACT_KEYS_PER_GROUP:
                    overflow = True
            all_pairs = not overflow and bool(per_block)
            if all_pairs:
                for state in per_block.values():
                    wallets = state["wallets"]
                    sides = state["sides"]
                    ordinals = sorted(state["ordinals"])
                    if (
                        state["count"] != 2
                        or len(wallets) != 2
                        or sides != {"A", "B"}
                        or len(ordinals) != 2
                        or ordinals[0] is None
                        or ordinals[1] is None
                        or ordinals[1] != ordinals[0] + 1
                    ):
                        all_pairs = False
                        break
            if all_pairs:
                taxon = Taxon.EXPECTED_COUNTERPARTY_PAIR
                proof_id = _proof_id("EXPECTED_COUNTERPARTY_PAIR_PROOF", group.equality_key)
                joins.add_proof(proof_id, "EXPECTED_COUNTERPARTY_PAIR_PROOF")
                emitter.emit(
                    "r11a-expected-counterparty-pair-proofs.ndjson",
                    {
                        "record_type": "EXPECTED_COUNTERPARTY_PAIR_PROOF",
                        "proof_id": proof_id,
                        "protocol_trade_key_sha256": hashlib.sha256(group.equality_key).hexdigest(),
                        "raw_block_occurrence_count": len(per_block),
                        "event_occurrence_count": occurrence_count,
                        "ordered_raw_locator_commitment_sha256": locator_commitment.hexdigest(),
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
                occurrence_count=occurrence_count,
                proof_references=references,
            )
            for row in _rows(group.path, meter, "emit protocol-trade members"):
                emitter.emit(
                    "r11a-protocol-trade-group-members.ndjson",
                    {
                        "record_type": "PROTOCOL_TRADE_GROUP_MEMBER",
                        "taxonomy_unit_id": unit_id,
                        "primary_taxon": taxon.value,
                        "raw_locator": row["raw_locator"],
                        "canonical_wallet": row["canonical_wallet"],
                        "exact_raw_side_string": row["exact_raw_side_string"],
                        "full_event_sha256": row["full_event_sha256"],
                    },
                )
                joins.add_duplicate_row(unit_id)
        meter.delete_file(sorted_path)
        meter.delete_file(materialized.protocol_trade_directory / f"part-{partition:03d}.frames")
    if materialized.protocol_trade_directory.exists():
        materialized.protocol_trade_directory.rmdir()
    return sort_rows


@dataclasses.dataclass(slots=True)
class _WeakWalletState:
    occurrence_count: int = 0
    first_event_hash: str | None = None
    conflicting: bool = False
    raw_blocks: set[tuple[str, int]] = dataclasses.field(default_factory=set)
    all_replay_proven: bool = True
    proof_ids: set[str] = dataclasses.field(default_factory=set)


def _classify_weak_groups(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    joins: JoinLedger,
    conservation: UniverseConservation,
    block_proofs: Mapping[int, BlockProof],
) -> list[dict[str, object]]:
    sort_rows: list[dict[str, object]] = []
    for partition, sorted_path, spool_directory, sort_row in _sorted_groups(
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
            occurrence_count = 0
            schema_invalid = False
            missing_identity = False
            conflicting_block = False
            protocol_keys: set[str] = set()
            wallet_states: dict[str, _WeakWalletState] = {}
            overflow = False
            for row in _rows(group.path, meter, "summarize exact weak-key group"):
                occurrence_count += 1
                if _array(row["schema_errors"], "schema errors"):
                    schema_invalid = True
                protocol_key = _optional_text(row["protocol_trade_key_hex"], "protocol key")
                wallet_key = _optional_text(row["wallet_fill_key_hex"], "wallet fill key")
                if protocol_key is None or wallet_key is None:
                    missing_identity = True
                else:
                    if len(protocol_keys) < 3:
                        protocol_keys.add(protocol_key)
                    state = wallet_states.setdefault(wallet_key, _WeakWalletState())
                    state.occurrence_count += 1
                    full_hash = _text(row["full_event_sha256"], "full event hash")
                    if state.first_event_hash is None:
                        state.first_event_hash = full_hash
                    elif state.first_event_hash != full_hash:
                        state.conflicting = True
                    object_key, record_ordinal, _ = _locator(row)
                    raw_block = (object_key, record_ordinal)
                    state.raw_blocks.add(raw_block)
                    block_number = _integer(row["block_number"], "block number")
                    proof = block_proofs.get(block_number)
                    if proof is not None and proof.conflicting:
                        conflicting_block = True
                    if proof is None or not proof.exact_replay or raw_block not in proof.raw_locators:
                        state.all_replay_proven = False
                    else:
                        state.proof_ids.add(proof.proof_id)
                if len(wallet_states) > _MAX_COMPACT_KEYS_PER_GROUP:
                    overflow = True
            conflicting_wallet = any(state.conflicting for state in wallet_states.values())
            intra_block_repeat = any(
                state.occurrence_count > len(state.raw_blocks) for state in wallet_states.values()
            )
            replay_reobservation_states = [
                state
                for state in wallet_states.values()
                if state.occurrence_count > 1 and state.all_replay_proven and state.proof_ids
            ]
            replay_proof_ids = {
                proof_id for state in replay_reobservation_states for proof_id in state.proof_ids
            }
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
            elif intra_block_repeat:
                taxon = Taxon.INTRA_BLOCK_REPEAT
                references = ()
            elif replay_reobservation_states:
                taxon = Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY
                references = tuple(
                    ("EXACT_BLOCK_REPLAY_PROOF", proof_id)
                    for proof_id in sorted(replay_proof_ids)
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
                occurrence_count=occurrence_count,
                proof_references=references,
            )
            for row in _rows(group.path, meter, "emit exact weak-key duplicate rows"):
                _emit_duplicate_row(emitter, joins, unit_id, taxon, row)
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
    joins = JoinLedger(maximum_entries=max(1000, meter.limits.maximum_repeated_observations_retained * 4))
    conservation = {universe: UniverseConservation() for universe in UnitUniverse}
    block_proofs, sort_rows = _classify_block_groups(
        materialized,
        meter,
        emitter,
        joins,
        conservation[UnitUniverse.BLOCK_NUMBER_REPEAT],
    )
    sort_rows += _classify_wallet_groups(
        materialized,
        meter,
        emitter,
        joins,
        conservation[UnitUniverse.WALLET_FILL_REPEAT],
        block_proofs,
    )
    sort_rows += _classify_protocol_groups(
        materialized,
        meter,
        emitter,
        joins,
        conservation[UnitUniverse.PROTOCOL_TRADE_GROUP],
    )
    sort_rows += _classify_weak_groups(
        materialized,
        meter,
        emitter,
        joins,
        conservation[UnitUniverse.LEGACY_WEAK_KEY_REPEAT],
        block_proofs,
    )
    conservation_rows = tuple(conservation[universe].row(universe) for universe in UnitUniverse)
    all_proofs, all_units, all_duplicates = joins.validate()
    return TaxonomyResult(
        conservation_rows=conservation_rows,
        secondary_sort_rows=tuple(sort_rows),
        block_proof_count=sum(value == "EXACT_BLOCK_REPLAY_PROOF" for value in joins.proof_types.values()),
        pair_proof_count=sum(value == "EXPECTED_COUNTERPARTY_PAIR_PROOF" for value in joins.proof_types.values()),
        proof_reference_count=joins.reference_count,
        all_proof_references_resolve=all_proofs,
        all_unit_ids_unique=all_units,
        all_duplicate_rows_reference_one_unit=all_duplicates,
        terminal_unclassifiable_group_count=sum(int(row["unclassifiable_group_count"]) for row in conservation_rows),
        terminal_unclassifiable_occurrence_count=sum(int(row["unclassifiable_occurrence_count"]) for row in conservation_rows),
    )
