from __future__ import annotations

import dataclasses
import enum
import hashlib
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping, Protocol
from pathlib import Path

from .canonical import FrozenObject, NumberToken, strict_json_loads
from .identity import frame
from .limits import R11ALimits
from .materialize import MaterializedIndexes
from .storage import (
    WorkspaceMeter,
    external_sort_partition,
    iter_equality_group_spools,
    iter_frames,
)

_MAX_GROUP_DISTINCT_KEYS = 100_000


class TaxonomyError(RuntimeError):
    pass


class Taxon(str, enum.Enum):
    TID_SCOPE_FALSE_POSITIVE = "TID_SCOPE_FALSE_POSITIVE"
    EXPECTED_COUNTERPARTY_PAIR = "EXPECTED_COUNTERPARTY_PAIR"
    EXACT_BLOCK_REPLAY_ACROSS_OBJECTS = "EXACT_BLOCK_REPLAY_ACROSS_OBJECTS"
    EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY = (
        "EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY"
    )
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
    raw_locator_keys: frozenset[tuple[str, int]]
    source_object_keys: frozenset[str]


@dataclasses.dataclass(slots=True)
class UniverseConservation:
    group_count: int = 0
    occurrence_count: int = 0
    taxon_group_counts: Counter[str] = dataclasses.field(default_factory=Counter)
    taxon_occurrence_counts: Counter[str] = dataclasses.field(default_factory=Counter)

    def add(self, taxon: Taxon, occurrences: int) -> None:
        if occurrences <= 0:
            raise TaxonomyError("taxonomy unit must contain at least one occurrence")
        self.group_count += 1
        self.occurrence_count += occurrences
        self.taxon_group_counts[taxon.value] += 1
        self.taxon_occurrence_counts[taxon.value] += occurrences

    def validate(self) -> None:
        if sum(self.taxon_group_counts.values()) != self.group_count:
            raise TaxonomyError("taxonomy group conservation failed")
        if sum(self.taxon_occurrence_counts.values()) != self.occurrence_count:
            raise TaxonomyError("taxonomy occurrence conservation failed")

    def as_mapping(self, universe: UnitUniverse) -> dict[str, object]:
        self.validate()
        return {
            "unit_universe": universe.value,
            "group_count": self.group_count,
            "occurrence_count": self.occurrence_count,
            "taxon_group_counts": dict(sorted(self.taxon_group_counts.items())),
            "taxon_occurrence_counts": dict(sorted(self.taxon_occurrence_counts.items())),
            "unclassifiable_group_count": self.taxon_group_counts[Taxon.UNCLASSIFIABLE.value],
            "unclassifiable_occurrence_count": self.taxon_occurrence_counts[
                Taxon.UNCLASSIFIABLE.value
            ],
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


class _JoinLedger:
    def __init__(self) -> None:
        self.unit_ids: set[str] = set()
        self.proof_ids: dict[str, str] = {}
        self.references: list[tuple[str, str, str]] = []
        self.duplicate_unit_references: list[str] = []

    def unit(self, unit_id: str) -> None:
        if unit_id in self.unit_ids:
            raise TaxonomyError("duplicate taxonomy unit ID")
        self.unit_ids.add(unit_id)

    def proof(self, proof_id: str, proof_type: str) -> None:
        if proof_id in self.proof_ids:
            raise TaxonomyError("duplicate proof ID")
        self.proof_ids[proof_id] = proof_type

    def reference(self, unit_id: str, proof_id: str, proof_type: str) -> None:
        self.references.append((unit_id, proof_id, proof_type))

    def duplicate_reference(self, unit_id: str) -> None:
        self.duplicate_unit_references.append(unit_id)

    def validate(self) -> tuple[bool, bool, bool]:
        all_resolve = True
        observed_pairs: set[tuple[str, str, str]] = set()
        for unit_id, proof_id, proof_type in self.references:
            if unit_id not in self.unit_ids:
                all_resolve = False
            if self.proof_ids.get(proof_id) != proof_type:
                all_resolve = False
            key = (unit_id, proof_id, proof_type)
            if key in observed_pairs:
                all_resolve = False
            observed_pairs.add(key)
        duplicate_rows_resolve = all(
            unit_id in self.unit_ids for unit_id in self.duplicate_unit_references
        )
        return all_resolve, True, duplicate_rows_resolve


def _int(value: object, label: str) -> int:
    if isinstance(value, NumberToken) and value.is_integer_token:
        return int(value.token, 10)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise TaxonomyError(f"{label} must be an exact integer")


def _text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise TaxonomyError(f"{label} must be a string")
    return value


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _mapping(value: object, label: str) -> FrozenObject:
    if not isinstance(value, FrozenObject):
        raise TaxonomyError(f"{label} must be an object")
    return value


def _array(value: object, label: str) -> tuple[object, ...]:
    if not isinstance(value, tuple):
        raise TaxonomyError(f"{label} must be an array")
    return value


def _row(payload: bytes) -> FrozenObject:
    return _mapping(strict_json_loads(payload), "materialized row")


def _locator(row: FrozenObject) -> tuple[str, int, int | None]:
    locator = _mapping(row["raw_locator"], "raw_locator")
    object_key = _text(locator["object_key"], "object_key")
    record_ordinal = _int(
        locator["decompressed_record_ordinal_zero_based"], "record ordinal"
    )
    event_ordinal = None
    if "event_ordinal_zero_based" in locator:
        event_ordinal = _int(locator["event_ordinal_zero_based"], "event ordinal")
    return object_key, record_ordinal, event_ordinal


def _unit_id(universe: UnitUniverse, equality_key: bytes) -> str:
    return hashlib.sha256(frame(universe.value.encode("ascii"), equality_key)).hexdigest()


def _proof_id(proof_type: str, equality_key: bytes) -> str:
    return hashlib.sha256(frame(proof_type.encode("ascii"), equality_key)).hexdigest()


def _emit_unit(
    emitter: EvidenceEmitter,
    joins: _JoinLedger,
    conservation: UniverseConservation,
    *,
    universe: UnitUniverse,
    equality_key: bytes,
    taxon: Taxon,
    occurrence_count: int,
    proof_references: tuple[tuple[str, str], ...] = (),
) -> str:
    unit_id = _unit_id(universe, equality_key)
    joins.unit(unit_id)
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
        joins.reference(unit_id, proof_id, proof_type)
    return unit_id


def _sort_groups(
    *,
    reducer_id: str,
    directory: Path,
    commitments: tuple[dict[str, object], ...],
    meter: WorkspaceMeter,
) -> Iterator[tuple[int, bytes, Path, int]]:
    for partition in range(256):
        source = directory / f"part-{partition:03d}.frames"
        sorted_path = meter.root / f"taxonomy-sorted-{reducer_id.lower()}-{partition:03d}.frames"
        temp = meter.root / f"taxonomy-sort-temp-{reducer_id.lower()}-{partition:03d}"
        evidence = external_sort_partition(
            source,
            sorted_path,
            temp,
            meter,
            source_commitment=commitments[partition],
            maximum_source_bytes=source.stat().st_size,
        )
        yield partition, b"__SORT_EVIDENCE__", sorted_path, evidence.output_bytes


def _iter_group_payloads(path: Path, meter: WorkspaceMeter, phase: str) -> Iterator[FrozenObject]:
    for payload in iter_frames(path, runtime_guard=meter.runtime_guard, phase=phase):
        yield _row(payload)


def _classify_blocks(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    joins: _JoinLedger,
    conservation: UniverseConservation,
) -> tuple[dict[int, BlockProof], list[dict[str, object]]]:
    proofs: dict[int, BlockProof] = {}
    sort_rows: list[dict[str, object]] = []
    for partition, marker, sorted_path, output_bytes in _sort_groups(
        reducer_id="MATERIALIZED_BLOCK_NUMBER",
        directory=materialized.block_directory,
        commitments=materialized.block_commitments,
        meter=meter,
    ):
        sort_rows.append(
            {
                "reducer_id": "MATERIALIZED_BLOCK_NUMBER",
                "partition_ordinal_zero_based": partition,
                "sorted_file_bytes": output_bytes,
            }
        )
        spool_dir = meter.root / f"taxonomy-block-groups-{partition:03d}"
        for group in iter_equality_group_spools(
            sorted_path,
            spool_dir,
            meter,
            maximum_group_spool_bytes=meter.limits.maximum_equality_group_spool_bytes,
        ):
            rows = list(_iter_group_payloads(group.path, meter, "classify block group"))
            if len(rows) <= 1:
                continue
            if len(rows) > _MAX_GROUP_DISTINCT_KEYS:
                taxon = Taxon.UNCLASSIFIABLE
            else:
                invariants = {
                    (
                        _text(row["exact_raw_block_time"], "block time"),
                        _int(row["ordered_event_count"], "ordered event count"),
                        _text(row["ordered_event_fingerprint"], "event fingerprint"),
                    )
                    for row in rows
                }
                source_objects = {_locator(row)[0] for row in rows}
                if len(invariants) > 1:
                    taxon = Taxon.CONFLICTING_BLOCK_REPLAY
                elif len(source_objects) > 1:
                    taxon = Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS
                else:
                    taxon = Taxon.INTRA_BLOCK_REPEAT
            block_number = _int(rows[0]["block_number"], "block number")
            raw_locators = frozenset((_locator(row)[0], _locator(row)[1]) for row in rows)
            source_objects = frozenset(locator[0] for locator in raw_locators)
            proof_id: str | None = None
            if taxon is Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS:
                proof_id = _proof_id("EXACT_BLOCK_REPLAY_PROOF", group.equality_key)
                joins.proof(proof_id, "EXACT_BLOCK_REPLAY_PROOF")
                emitter.emit(
                    "r11a-exact-block-replay-proofs.ndjson",
                    {
                        "record_type": "EXACT_BLOCK_REPLAY_PROOF",
                        "proof_id": proof_id,
                        "block_number": block_number,
                        "occurrence_count": len(rows),
                        "distinct_source_object_count": len(source_objects),
                        "raw_locators": [
                            {
                                "object_key": object_key,
                                "decompressed_record_ordinal_zero_based": record_ordinal,
                            }
                            for object_key, record_ordinal in sorted(raw_locators)
                        ],
                        "equality_invariants": {
                            "exact_raw_block_time": _text(rows[0]["exact_raw_block_time"], "block time"),
                            "ordered_event_count": _int(rows[0]["ordered_event_count"], "event count"),
                            "ordered_event_fingerprint": _text(
                                rows[0]["ordered_event_fingerprint"], "event fingerprint"
                            ),
                        },
                    },
                )
            unit_references = (
                () if proof_id is None else (("EXACT_BLOCK_REPLAY_PROOF", proof_id),)
            )
            unit_id = _emit_unit(
                emitter,
                joins,
                conservation,
                universe=UnitUniverse.BLOCK_NUMBER_REPEAT,
                equality_key=group.equality_key,
                taxon=taxon,
                occurrence_count=len(rows),
                proof_references=unit_references,
            )
            for row in rows:
                emitter.emit(
                    "r11a-block-overlap-matrix.ndjson",
                    {
                        "record_type": "BLOCK_OVERLAP_OBSERVATION",
                        "taxonomy_unit_id": unit_id,
                        "block_number": block_number,
                        "primary_taxon": taxon.value,
                        "raw_locator": row["raw_locator"],
                        "exact_raw_block_time": row["exact_raw_block_time"],
                        "ordered_event_count": row["ordered_event_count"],
                        "ordered_event_fingerprint": row["ordered_event_fingerprint"],
                        "raw_record_fingerprint": row["raw_record_fingerprint"],
                    },
                )
                joins.duplicate_reference(unit_id)
            proofs[block_number] = BlockProof(
                block_number=block_number,
                proof_id="" if proof_id is None else proof_id,
                exact_replay=taxon is Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS,
                conflicting=taxon is Taxon.CONFLICTING_BLOCK_REPLAY,
                raw_locator_keys=raw_locators,
                source_object_keys=source_objects,
            )
        meter.delete_file(sorted_path)
        meter.delete_file(materialized.block_directory / f"part-{partition:03d}.frames")
    if materialized.block_directory.exists():
        materialized.block_directory.rmdir()
    return proofs, sort_rows


def _event_group_rows(path: Path, meter: WorkspaceMeter, phase: str) -> list[FrozenObject]:
    rows = list(_iter_group_payloads(path, meter, phase))
    if len(rows) > _MAX_GROUP_DISTINCT_KEYS:
        raise TaxonomyError("candidate equality group exceeds bounded classification key count")
    return rows


def _emit_duplicate_rows(
    emitter: EvidenceEmitter,
    joins: _JoinLedger,
    unit_id: str,
    taxon: Taxon,
    rows: Iterable[FrozenObject],
) -> None:
    for row in rows:
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
        joins.duplicate_reference(unit_id)


def _classify_wallet_fills(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    joins: _JoinLedger,
    conservation: UniverseConservation,
    block_proofs: Mapping[int, BlockProof],
) -> list[dict[str, object]]:
    sort_rows: list[dict[str, object]] = []
    for partition, marker, sorted_path, output_bytes in _sort_groups(
        reducer_id="WALLET_FILL",
        directory=materialized.wallet_fill_directory,
        commitments=materialized.wallet_fill_commitments,
        meter=meter,
    ):
        sort_rows.append(
            {
                "reducer_id": "WALLET_FILL",
                "partition_ordinal_zero_based": partition,
                "sorted_file_bytes": output_bytes,
            }
        )
        spool_dir = meter.root / f"taxonomy-wallet-groups-{partition:03d}"
        for group in iter_equality_group_spools(
            sorted_path,
            spool_dir,
            meter,
            maximum_group_spool_bytes=meter.limits.maximum_equality_group_spool_bytes,
        ):
            rows = _event_group_rows(group.path, meter, "classify wallet-fill group")
            if len(rows) <= 1:
                continue
            full_hashes = {_text(row["full_event_sha256"], "full event hash") for row in rows}
            raw_locators = [(_locator(row)[0], _locator(row)[1]) for row in rows]
            repeated_same_raw_block = len(set(raw_locators)) < len(raw_locators)
            block_numbers = {_int(row["block_number"], "block number") for row in rows}
            proof_ids: set[str] = set()
            all_exact_replay = True
            for block_number in block_numbers:
                proof = block_proofs.get(block_number)
                if proof is None or not proof.exact_replay:
                    all_exact_replay = False
                    break
                if not set(locator for locator in raw_locators if _int(
                    next(row for row in rows if (_locator(row)[0], _locator(row)[1]) == locator)["block_number"],
                    "block number",
                ) == block_number).issubset(proof.raw_locator_keys):
                    all_exact_replay = False
                    break
                proof_ids.add(proof.proof_id)
            if len(full_hashes) > 1:
                taxon = Taxon.CONFLICTING_USER_FILL
                references: tuple[tuple[str, str], ...] = ()
            elif repeated_same_raw_block:
                taxon = Taxon.INTRA_BLOCK_REPEAT
                references = ()
            elif all_exact_replay and proof_ids:
                taxon = Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY
                references = tuple(
                    ("EXACT_BLOCK_REPLAY_PROOF", proof_id) for proof_id in sorted(proof_ids)
                )
            else:
                taxon = Taxon.UNCLASSIFIABLE
                references = ()
            unit_id = _emit_unit(
                emitter,
                joins,
                conservation,
                universe=UnitUniverse.WALLET_FILL_REPEAT,
                equality_key=group.equality_key,
                taxon=taxon,
                occurrence_count=len(rows),
                proof_references=references,
            )
            _emit_duplicate_rows(emitter, joins, unit_id, taxon, rows)
        meter.delete_file(sorted_path)
        meter.delete_file(materialized.wallet_fill_directory / f"part-{partition:03d}.frames")
    if materialized.wallet_fill_directory.exists():
        materialized.wallet_fill_directory.rmdir()
    return sort_rows


def _classify_protocol_trades(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    joins: _JoinLedger,
    conservation: UniverseConservation,
) -> list[dict[str, object]]:
    sort_rows: list[dict[str, object]] = []
    for partition, marker, sorted_path, output_bytes in _sort_groups(
        reducer_id="PROTOCOL_TRADE",
        directory=materialized.protocol_trade_directory,
        commitments=materialized.protocol_trade_commitments,
        meter=meter,
    ):
        sort_rows.append(
            {
                "reducer_id": "PROTOCOL_TRADE",
                "partition_ordinal_zero_based": partition,
                "sorted_file_bytes": output_bytes,
            }
        )
        spool_dir = meter.root / f"taxonomy-protocol-groups-{partition:03d}"
        for group in iter_equality_group_spools(
            sorted_path,
            spool_dir,
            meter,
            maximum_group_spool_bytes=meter.limits.maximum_equality_group_spool_bytes,
        ):
            rows = _event_group_rows(group.path, meter, "classify protocol-trade group")
            by_block: dict[tuple[str, int], list[FrozenObject]] = defaultdict(list)
            for row in rows:
                object_key, record_ordinal, _ = _locator(row)
                by_block[(object_key, record_ordinal)].append(row)
            all_pairs = bool(by_block)
            for block_rows in by_block.values():
                if len(block_rows) != 2:
                    all_pairs = False
                    break
                wallets = {_optional_text(row["canonical_wallet"], "wallet") for row in block_rows}
                sides = {_optional_text(row["exact_raw_side_string"], "side") for row in block_rows}
                ordinals = sorted(_locator(row)[2] for row in block_rows)
                if None in wallets or len(wallets) != 2 or sides != {"A", "B"}:
                    all_pairs = False
                    break
                if ordinals[0] is None or ordinals[1] is None or ordinals[1] != ordinals[0] + 1:
                    all_pairs = False
                    break
            if all_pairs:
                taxon = Taxon.EXPECTED_COUNTERPARTY_PAIR
                proof_id = _proof_id("EXPECTED_COUNTERPARTY_PAIR_PROOF", group.equality_key)
                joins.proof(proof_id, "EXPECTED_COUNTERPARTY_PAIR_PROOF")
                emitter.emit(
                    "r11a-expected-counterparty-pair-proofs.ndjson",
                    {
                        "record_type": "EXPECTED_COUNTERPARTY_PAIR_PROOF",
                        "proof_id": proof_id,
                        "protocol_trade_key_sha256": hashlib.sha256(group.equality_key).hexdigest(),
                        "raw_block_occurrence_count": len(by_block),
                        "event_occurrence_count": len(rows),
                        "raw_block_locators": [
                            {
                                "object_key": object_key,
                                "decompressed_record_ordinal_zero_based": record_ordinal,
                            }
                            for object_key, record_ordinal in sorted(by_block)
                        ],
                    },
                )
                references = (("EXPECTED_COUNTERPARTY_PAIR_PROOF", proof_id),)
            else:
                taxon = Taxon.UNCLASSIFIABLE
                references = ()
            unit_id = _emit_unit(
                emitter,
                joins,
                conservation,
                universe=UnitUniverse.PROTOCOL_TRADE_GROUP,
                equality_key=group.equality_key,
                taxon=taxon,
                occurrence_count=len(rows),
                proof_references=references,
            )
            for row in rows:
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
                joins.duplicate_reference(unit_id)
        meter.delete_file(sorted_path)
        meter.delete_file(materialized.protocol_trade_directory / f"part-{partition:03d}.frames")
    if materialized.protocol_trade_directory.exists():
        materialized.protocol_trade_directory.rmdir()
    return sort_rows


def _classify_weak_groups(
    materialized: MaterializedIndexes,
    meter: WorkspaceMeter,
    emitter: EvidenceEmitter,
    joins: _JoinLedger,
    conservation: UniverseConservation,
    block_proofs: Mapping[int, BlockProof],
) -> list[dict[str, object]]:
    sort_rows: list[dict[str, object]] = []
    for partition, marker, sorted_path, output_bytes in _sort_groups(
        reducer_id="EXACT_LEGACY_WEAK_KEY",
        directory=materialized.weak_directory,
        commitments=materialized.weak_commitments,
        meter=meter,
    ):
        sort_rows.append(
            {
                "reducer_id": "EXACT_LEGACY_WEAK_KEY",
                "partition_ordinal_zero_based": partition,
                "sorted_file_bytes": output_bytes,
            }
        )
        spool_dir = meter.root / f"taxonomy-weak-groups-{partition:03d}"
        for group in iter_equality_group_spools(
            sorted_path,
            spool_dir,
            meter,
            maximum_group_spool_bytes=meter.limits.maximum_equality_group_spool_bytes,
        ):
            rows = _event_group_rows(group.path, meter, "classify exact weak-key group")
            if len(rows) <= 1:
                continue
            schema_invalid = any(len(_array(row["schema_errors"], "schema_errors")) > 0 for row in rows)
            protocol_keys = {_optional_text(row["protocol_trade_key_hex"], "protocol key") for row in rows}
            wallet_keys = {_optional_text(row["wallet_fill_key_hex"], "wallet fill key") for row in rows}
            full_hashes_by_wallet: dict[str, set[str]] = defaultdict(set)
            locators_by_wallet: dict[str, list[tuple[str, int, int | None, int]]] = defaultdict(list)
            for row in rows:
                wallet_key = _optional_text(row["wallet_fill_key_hex"], "wallet fill key")
                if wallet_key is None:
                    continue
                full_hashes_by_wallet[wallet_key].add(_text(row["full_event_sha256"], "event hash"))
                object_key, record_ordinal, event_ordinal = _locator(row)
                locators_by_wallet[wallet_key].append(
                    (object_key, record_ordinal, event_ordinal, _int(row["block_number"], "block number"))
                )
            conflicting_wallet = any(len(hashes) > 1 for hashes in full_hashes_by_wallet.values())
            intra_block_repeat = any(
                len({(object_key, record_ordinal, event_ordinal) for object_key, record_ordinal, event_ordinal, _ in locators})
                < len(locators)
                or len({(object_key, record_ordinal) for object_key, record_ordinal, _, _ in locators})
                < len(locators)
                for locators in locators_by_wallet.values()
            )
            replay_proof_ids: set[str] = set()
            replay_reobservation = False
            for locators in locators_by_wallet.values():
                if len(locators) <= 1:
                    continue
                candidate = True
                local_proofs: set[str] = set()
                for object_key, record_ordinal, _, block_number in locators:
                    proof = block_proofs.get(block_number)
                    if (
                        proof is None
                        or not proof.exact_replay
                        or (object_key, record_ordinal) not in proof.raw_locator_keys
                    ):
                        candidate = False
                        break
                    local_proofs.add(proof.proof_id)
                if candidate and local_proofs:
                    replay_reobservation = True
                    replay_proof_ids.update(local_proofs)
            no_missing_identity = None not in protocol_keys and None not in wallet_keys
            if schema_invalid:
                taxon = Taxon.TID_SCHEMA_VIOLATION
                references: tuple[tuple[str, str], ...] = ()
            elif conflicting_wallet:
                taxon = Taxon.CONFLICTING_USER_FILL
                references = ()
            elif intra_block_repeat:
                taxon = Taxon.INTRA_BLOCK_REPEAT
                references = ()
            elif replay_reobservation:
                taxon = Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY
                references = tuple(
                    ("EXACT_BLOCK_REPLAY_PROOF", proof_id)
                    for proof_id in sorted(replay_proof_ids)
                )
            elif no_missing_identity and len(protocol_keys) >= 2:
                taxon = Taxon.TID_SCOPE_FALSE_POSITIVE
                references = ()
            else:
                taxon = Taxon.UNCLASSIFIABLE
                references = ()
            unit_id = _emit_unit(
                emitter,
                joins,
                conservation,
                universe=UnitUniverse.LEGACY_WEAK_KEY_REPEAT,
                equality_key=group.equality_key,
                taxon=taxon,
                occurrence_count=len(rows),
                proof_references=references,
            )
            _emit_duplicate_rows(emitter, joins, unit_id, taxon, rows)
            if schema_invalid:
                for row in rows:
                    errors = _array(row["schema_errors"], "schema errors")
                    if not errors:
                        continue
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
        raise TaxonomyError("truncated materialization cannot enter scientific classification")
    joins = _JoinLedger()
    conservation = {universe: UniverseConservation() for universe in UnitUniverse}
    block_proofs, secondary_sort_rows = _classify_blocks(
        materialized,
        meter,
        emitter,
        joins,
        conservation[UnitUniverse.BLOCK_NUMBER_REPEAT],
    )
    secondary_sort_rows += _classify_wallet_fills(
        materialized,
        meter,
        emitter,
        joins,
        conservation[UnitUniverse.WALLET_FILL_REPEAT],
        block_proofs,
    )
    secondary_sort_rows += _classify_protocol_trades(
        materialized,
        meter,
        emitter,
        joins,
        conservation[UnitUniverse.PROTOCOL_TRADE_GROUP],
    )
    secondary_sort_rows += _classify_weak_groups(
        materialized,
        meter,
        emitter,
        joins,
        conservation[UnitUniverse.LEGACY_WEAK_KEY_REPEAT],
        block_proofs,
    )
    conservation_rows = tuple(
        conservation[universe].as_mapping(universe) for universe in UnitUniverse
    )
    all_resolve, all_unit_ids_unique, duplicate_rows_resolve = joins.validate()
    unclassifiable_groups = sum(
        row["unclassifiable_group_count"] for row in conservation_rows
    )
    unclassifiable_occurrences = sum(
        row["unclassifiable_occurrence_count"] for row in conservation_rows
    )
    return TaxonomyResult(
        conservation_rows=conservation_rows,
        secondary_sort_rows=tuple(secondary_sort_rows),
        block_proof_count=sum(
            proof_type == "EXACT_BLOCK_REPLAY_PROOF" for proof_type in joins.proof_ids.values()
        ),
        pair_proof_count=sum(
            proof_type == "EXPECTED_COUNTERPARTY_PAIR_PROOF"
            for proof_type in joins.proof_ids.values()
        ),
        proof_reference_count=len(joins.references),
        all_proof_references_resolve=all_resolve,
        all_unit_ids_unique=all_unit_ids_unique,
        all_duplicate_rows_reference_one_unit=duplicate_rows_resolve,
        terminal_unclassifiable_group_count=int(unclassifiable_groups),
        terminal_unclassifiable_occurrence_count=int(unclassifiable_occurrences),
    )
