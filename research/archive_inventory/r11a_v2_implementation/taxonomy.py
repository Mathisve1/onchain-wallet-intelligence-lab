from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping, Sequence

from .identity import (
    BlockObservation,
    Observation,
    RawBlockLocator,
    block_locator_sort_key,
    canonical_sha256,
    canonical_typed_bytes,
    locator_sort_key,
)


class R11AV2TaxonomyError(ValueError):
    """Raised when a taxonomy or proof graph cannot be established exactly."""


class Taxon(str, Enum):
    TID_SCOPE_FALSE_POSITIVE = "TID_SCOPE_FALSE_POSITIVE"
    EXPECTED_COUNTERPARTY_PAIR = "EXPECTED_COUNTERPARTY_PAIR"
    EXACT_BLOCK_REPLAY_ACROSS_OBJECTS = "EXACT_BLOCK_REPLAY_ACROSS_OBJECTS"
    EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY = "EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY"
    CONFLICTING_BLOCK_REPLAY = "CONFLICTING_BLOCK_REPLAY"
    CONFLICTING_USER_FILL = "CONFLICTING_USER_FILL"
    INTRA_BLOCK_REPEAT = "INTRA_BLOCK_REPEAT"
    TID_SCHEMA_VIOLATION = "TID_SCHEMA_VIOLATION"
    UNCLASSIFIABLE = "UNCLASSIFIABLE"


UNIT_LEGACY = "LEGACY_REPEAT_OCCURRENCE"
UNIT_BLOCK = "ARCHIVE_BLOCK_NUMBER_GROUP"
UNIT_PROTOCOL = "PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE"
UNIT_TID_SCHEMA = "REPEAT_INTERSECTING_TID_SCHEMA_VIOLATION"
UNIT_COIN_SCHEMA = "REPEAT_INTERSECTING_COIN_SCHEMA_VIOLATION"
UNIT_WALLET_SCHEMA = "REPEAT_INTERSECTING_WALLET_SCHEMA_VIOLATION"
UNIT_UNIVERSES = (
    UNIT_LEGACY,
    UNIT_BLOCK,
    UNIT_PROTOCOL,
    UNIT_TID_SCHEMA,
    UNIT_COIN_SCHEMA,
    UNIT_WALLET_SCHEMA,
)


@dataclass(frozen=True, slots=True)
class BlockDecision:
    block_number: int
    group_id: str
    taxon: Taxon
    proof_id: str | None
    members: tuple[BlockObservation, ...]
    reason: str | None


@dataclass(frozen=True, slots=True)
class ProtocolDecision:
    raw_block_locator: RawBlockLocator
    protocol_identity: tuple[str, str, int]
    group_id: str
    taxon: Taxon
    proof_id: str | None
    members: tuple[Observation, ...]
    reason: str | None


@dataclass(frozen=True, slots=True)
class LegacyDecision:
    unit_id: str
    group_id: str
    primary_taxon: Taxon
    occurrence: Observation
    weak_group_members: tuple[Observation, ...]
    proof_ids: tuple[str, ...]
    reason: str | None


@dataclass(frozen=True, slots=True)
class TaxonomyReport:
    taxonomy_units: tuple[dict[str, object], ...]
    block_rows: tuple[dict[str, object], ...]
    duplicate_rows: tuple[dict[str, object], ...]
    replay_proofs: tuple[dict[str, object], ...]
    pair_proofs: tuple[dict[str, object], ...]
    protocol_member_rows: tuple[dict[str, object], ...]
    schema_rows: tuple[dict[str, object], ...]
    conservation: dict[str, object]
    all_proof_references_resolve: bool
    complete_taxonomy: bool


def _id(label: str, value: object) -> str:
    return hashlib.sha256(canonical_typed_bytes([label, value])).hexdigest()


def weak_key_bytes(observation: Observation) -> bytes | None:
    if observation.legacy_weak_key is None:
        return None
    wallet, typed_tid = observation.legacy_weak_key
    return canonical_typed_bytes(["LEGACY_WEAK_KEY_V2", wallet, typed_tid[0], typed_tid[1]])


def _block_decisions(
    blocks: Sequence[BlockObservation],
    repeated_block_numbers: set[int],
) -> tuple[dict[int, BlockDecision], tuple[dict[str, object], ...], tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    by_number: dict[int, list[BlockObservation]] = defaultdict(list)
    for block in blocks:
        if block.block_number in repeated_block_numbers:
            by_number[block.block_number].append(block)
    if set(by_number) != repeated_block_numbers:
        missing = sorted(repeated_block_numbers - set(by_number))
        raise R11AV2TaxonomyError(f"repeated block groups were not fully materialized: {missing[:10]}")
    decisions: dict[int, BlockDecision] = {}
    matrix_rows: list[dict[str, object]] = []
    proofs: list[dict[str, object]] = []
    units: list[dict[str, object]] = []
    for block_number in sorted(by_number):
        members = tuple(sorted(by_number[block_number], key=lambda item: block_locator_sort_key(item.locator)))
        if len(members) < 2:
            raise R11AV2TaxonomyError("repeated block group has fewer than two members")
        locators = [member.locator.as_mapping() for member in members]
        group_id = _id("BLOCK_GROUP_V2", [block_number, locators])
        invariant_set = {member.equality_invariants for member in members}
        distinct_objects = {member.source.object_key for member in members}
        if len(invariant_set) > 1:
            taxon = Taxon.CONFLICTING_BLOCK_REPLAY
            proof_id = None
            reason = "BLOCK_EQUALITY_INVARIANTS_CONFLICT"
        elif len(distinct_objects) >= 2:
            taxon = Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS
            proof_id = _id("EXACT_BLOCK_REPLAY_PROOF_V2", [group_id, next(iter(invariant_set))])
            reason = None
            proofs.append({
                "record_type": "EXACT_BLOCK_REPLAY_PROOF",
                "proof_id": proof_id,
                "block_group_id": group_id,
                "block_number": block_number,
                "member_count": len(members),
                "distinct_source_object_count": len(distinct_objects),
                "exact_raw_block_time": members[0].block_time_exact,
                "ordered_event_count": members[0].ordered_event_count,
                "ordered_event_fingerprint_sha256": members[0].ordered_event_fingerprint_sha256,
                "member_raw_block_locators": locators,
            })
        else:
            taxon = Taxon.UNCLASSIFIABLE
            proof_id = None
            reason = "REPEATED_BLOCK_NUMBER_WITHOUT_CROSS_OBJECT_EXACT_REPLAY_OR_CONFLICT"
        decisions[block_number] = BlockDecision(block_number, group_id, taxon, proof_id, members, reason)
        units.append({
            "record_type": "TAXONOMY_UNIT",
            "unit_universe": UNIT_BLOCK,
            "unit_id": _id("BLOCK_TAXONOMY_UNIT_V2", group_id),
            "group_id": group_id,
            "primary_taxon": taxon.value,
            "member_count": len(members),
            "occurrence_count": len(members),
            "primary_locator": None,
            "proof_ids": [proof_id] if proof_id is not None else [],
            "unclassifiable_reason": reason,
        })
        for member_ordinal, member in enumerate(members):
            matrix_rows.append({
                "record_type": "BLOCK_OVERLAP_MEMBER",
                "block_group_id": group_id,
                "block_group_primary_taxon": taxon.value,
                "block_group_proof_id": proof_id,
                "member_ordinal_zero_based": member_ordinal,
                "block_number": block_number,
                "raw_block_locator": member.locator.as_mapping(),
                "source_object_key": member.source.object_key,
                "path_hour_utc": member.source.path_hour_utc,
                "exact_raw_block_time": member.block_time_exact,
                "ordered_event_count": member.ordered_event_count,
                "ordered_event_fingerprint_sha256": member.ordered_event_fingerprint_sha256,
                "raw_record_sha256": member.raw_record_sha256,
            })
    return decisions, tuple(matrix_rows), tuple(proofs), tuple(units)


def _protocol_decisions(
    blocks: Sequence[BlockObservation],
    repeated_weak_keys: set[bytes],
) -> tuple[dict[tuple[RawBlockLocator, tuple[str, str, int]], ProtocolDecision], tuple[dict[str, object], ...], tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    decisions: dict[tuple[RawBlockLocator, tuple[str, str, int]], ProtocolDecision] = {}
    proof_rows: list[dict[str, object]] = []
    member_rows: list[dict[str, object]] = []
    unit_rows: list[dict[str, object]] = []
    for block in sorted(blocks, key=lambda item: block_locator_sort_key(item.locator)):
        intersecting_protocols = {
            obs.protocol_trade_identity
            for obs in block.observations
            if weak_key_bytes(obs) in repeated_weak_keys and obs.protocol_trade_identity is not None
        }
        grouped: dict[tuple[str, str, int], list[Observation]] = defaultdict(list)
        for obs in block.observations:
            if obs.protocol_trade_identity in intersecting_protocols:
                assert obs.protocol_trade_identity is not None
                grouped[obs.protocol_trade_identity].append(obs)
        for protocol_identity in sorted(grouped):
            members = tuple(sorted(grouped[protocol_identity], key=lambda item: locator_sort_key(item.locator)))
            group_id = _id("PROTOCOL_GROUP_V2", [block.locator.as_mapping(), protocol_identity])
            wallets = [member.canonical_lowercase_wallet_address for member in members]
            sides = {member.side_exact for member in members}
            ordinals = sorted(member.locator.event_ordinal_zero_based for member in members)
            wallet_fill_counts = Counter(member.wallet_fill_identity for member in members)
            exact_pair = (
                len(members) == 2
                and all(wallet is not None for wallet in wallets)
                and len(set(wallets)) == 2
                and sides == {"A", "B"}
                and ordinals[1] == ordinals[0] + 1
                and all(identity is not None and count == 1 for identity, count in wallet_fill_counts.items())
            )
            if exact_pair:
                taxon = Taxon.EXPECTED_COUNTERPARTY_PAIR
                proof_id = _id("COUNTERPARTY_PAIR_PROOF_V2", [group_id, [m.locator.as_mapping() for m in members]])
                reason = None
                proof_rows.append({
                    "record_type": "EXPECTED_COUNTERPARTY_PAIR_PROOF",
                    "proof_id": proof_id,
                    "protocol_group_id": group_id,
                    "raw_block_locator": block.locator.as_mapping(),
                    "protocol_trade_identity": list(protocol_identity),
                    "member_count": 2,
                    "member_raw_observation_locators": [member.locator.as_mapping() for member in members],
                    "wallets": wallets,
                    "side_set": sorted(sides),
                    "event_ordinals": ordinals,
                })
            else:
                taxon = Taxon.UNCLASSIFIABLE
                proof_id = None
                reason = "PROTOCOL_GROUP_INTERSECTING_REPEAT_IS_NOT_EXACT_EXPECTED_COUNTERPARTY_PAIR"
            decision = ProtocolDecision(block.locator, protocol_identity, group_id, taxon, proof_id, members, reason)
            decisions[(block.locator, protocol_identity)] = decision
            unit_rows.append({
                "record_type": "TAXONOMY_UNIT",
                "unit_universe": UNIT_PROTOCOL,
                "unit_id": _id("PROTOCOL_TAXONOMY_UNIT_V2", group_id),
                "group_id": group_id,
                "primary_taxon": taxon.value,
                "member_count": len(members),
                "occurrence_count": len(members),
                "primary_locator": block.locator.as_mapping(),
                "proof_ids": [proof_id] if proof_id is not None else [],
                "unclassifiable_reason": reason,
            })
            for member_ordinal, member in enumerate(members):
                member_rows.append({
                    "record_type": "PROTOCOL_TRADE_GROUP_MEMBER",
                    "protocol_group_id": group_id,
                    "protocol_group_primary_taxon": taxon.value,
                    "pair_proof_id": proof_id,
                    "member_ordinal_zero_based": member_ordinal,
                    "raw_observation_locator": member.locator.as_mapping(),
                    "raw_block_locator": member.locator.block_locator.as_mapping(),
                    "protocol_trade_identity": list(protocol_identity),
                    "wallet_user_fill_identity": list(member.wallet_fill_identity) if member.wallet_fill_identity is not None else None,
                    "side_exact": member.side_exact,
                    "full_event_sha256": member.full_event_sha256,
                })
    return decisions, tuple(proof_rows), tuple(member_rows), tuple(unit_rows)


def _replay_proof_for_fill_subgroup(subgroup: Sequence[Observation], block_decisions: Mapping[int, BlockDecision]) -> str | None:
    if len(subgroup) < 2 or len({member.full_event_sha256 for member in subgroup}) != 1:
        return None
    locators = {member.locator.block_locator for member in subgroup}
    if len(locators) < 2:
        return None
    proof_ids: set[str] = set()
    for member in subgroup:
        decision = block_decisions.get(member.block_number)
        if decision is None or decision.taxon is not Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS or decision.proof_id is None:
            return None
        if member.locator.block_locator not in {block.locator for block in decision.members}:
            return None
        proof_ids.add(decision.proof_id)
    return next(iter(proof_ids)) if len(proof_ids) == 1 else None


def _legacy_decisions(
    observations: Sequence[Observation],
    repeated_weak_keys: set[bytes],
    block_decisions: Mapping[int, BlockDecision],
    protocol_decisions: Mapping[tuple[RawBlockLocator, tuple[str, str, int]], ProtocolDecision],
) -> tuple[tuple[LegacyDecision, ...], tuple[dict[str, object], ...], tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    grouped: dict[bytes, list[Observation]] = defaultdict(list)
    for observation in observations:
        key = weak_key_bytes(observation)
        if key in repeated_weak_keys:
            assert key is not None
            grouped[key].append(observation)
    if set(grouped) != repeated_weak_keys:
        raise R11AV2TaxonomyError("repeated weak-key groups were not fully materialized")
    decisions: list[LegacyDecision] = []
    duplicate_rows: list[dict[str, object]] = []
    schema_rows: list[dict[str, object]] = []
    schema_units: list[dict[str, object]] = []
    for key in sorted(grouped):
        members = tuple(sorted(grouped[key], key=lambda item: locator_sort_key(item.locator)))
        if len(members) < 2:
            raise R11AV2TaxonomyError("repeated weak-key group has fewer than two members")
        group_id = _id("LEGACY_WEAK_GROUP_V2", [key.hex(), [m.locator.as_mapping() for m in members]])
        fill_groups: dict[tuple[str, str, str, int] | None, list[Observation]] = defaultdict(list)
        for member in members:
            fill_groups[member.wallet_fill_identity].append(member)
        protocol_keys = {member.protocol_trade_identity for member in members}
        clean_identity = all(
            member.canonical_lowercase_wallet_address is not None
            and member.validated_integer_tid is not None
            and member.exact_raw_coin_string is not None
            and member.protocol_trade_identity is not None
            and member.wallet_fill_identity is not None
            for member in members
        )
        clean_protocol_proofs = clean_identity and all(
            (decision := protocol_decisions.get((member.locator.block_locator, member.protocol_trade_identity))) is not None
            and decision.taxon is Taxon.EXPECTED_COUNTERPARTY_PAIR
            and decision.proof_id is not None
            for member in members
        )
        any_fill_conflict = any(
            identity is not None and len({member.full_event_sha256 for member in subgroup}) > 1
            for identity, subgroup in fill_groups.items()
        )
        for group_ordinal, member in enumerate(members):
            duplicate_rows.append({
                "record_type": "LEGACY_WEAK_KEY_GROUP_MEMBER",
                "legacy_group_id": group_id,
                "legacy_group_member_ordinal_zero_based": group_ordinal,
                "legacy_group_member_count": len(members),
                "raw_observation_locator": member.locator.as_mapping(),
                "raw_block_locator": member.locator.block_locator.as_mapping(),
                "source_object_key": member.source.object_key,
                "path_hour_utc": member.source.path_hour_utc,
                "block_number": member.block_number,
                "exact_raw_block_time": member.block_time_exact,
                "canonical_wallet_address": member.canonical_lowercase_wallet_address,
                "tid_validation_status": member.tid_validation_status,
                "coin_validation_status": member.coin_validation_status,
                "wallet_validation_status": member.wallet_validation_status,
                "validated_integer_tid": member.validated_integer_tid,
                "exact_raw_coin_string": member.exact_raw_coin_string,
                "protocol_trade_identity": list(member.protocol_trade_identity) if member.protocol_trade_identity is not None else None,
                "wallet_user_fill_identity": list(member.wallet_fill_identity) if member.wallet_fill_identity is not None else None,
                "selected_fill_sha256": member.selected_fill_sha256,
                "full_fill_sha256": member.full_fill_sha256,
                "full_event_sha256": member.full_event_sha256,
            })
            for universe, status, reason in (
                (UNIT_TID_SCHEMA, member.tid_validation_status, member.tid_schema_violation_reason),
                (UNIT_COIN_SCHEMA, member.coin_validation_status, member.coin_schema_violation_reason),
                (UNIT_WALLET_SCHEMA, member.wallet_validation_status, member.wallet_schema_violation_reason),
            ):
                if reason is None:
                    continue
                schema_id = _id("REPEAT_SCHEMA_UNIT_V2", [universe, member.locator.as_mapping(), reason])
                schema_rows.append({
                    "record_type": "REPEAT_INTERSECTING_SCHEMA_EVIDENCE",
                    "schema_unit_id": schema_id,
                    "unit_universe": universe,
                    "legacy_group_id": group_id,
                    "raw_observation_locator": member.locator.as_mapping(),
                    "validation_status": status,
                    "violation_reason": reason,
                    "raw_tid_json_type": member.raw_tid_json_type,
                    "raw_tid_token": member.raw_tid_token,
                    "raw_coin_json_type": member.raw_coin_json_type,
                    "raw_coin_token": member.raw_coin_token,
                    "raw_wallet_json_type": member.raw_wallet_json_type,
                    "raw_wallet_token": member.raw_wallet_token,
                })
                schema_units.append({
                    "record_type": "TAXONOMY_UNIT",
                    "unit_universe": universe,
                    "unit_id": schema_id,
                    "group_id": group_id,
                    "primary_taxon": Taxon.TID_SCHEMA_VIOLATION.value if universe == UNIT_TID_SCHEMA else Taxon.UNCLASSIFIABLE.value,
                    "member_count": 1,
                    "occurrence_count": 1,
                    "primary_locator": member.locator.as_mapping(),
                    "proof_ids": [],
                    "unclassifiable_reason": None if universe == UNIT_TID_SCHEMA else reason,
                })
        for occurrence in members[1:]:
            subgroup = tuple(fill_groups[occurrence.wallet_fill_identity])
            proof_ids: set[str] = set()
            protocol_decision = protocol_decisions.get((occurrence.locator.block_locator, occurrence.protocol_trade_identity)) if occurrence.protocol_trade_identity is not None else None
            if protocol_decision is not None and protocol_decision.proof_id is not None:
                proof_ids.add(protocol_decision.proof_id)
            replay_proof = _replay_proof_for_fill_subgroup(subgroup, block_decisions)
            if replay_proof is not None:
                proof_ids.add(replay_proof)
            if occurrence.tid_schema_violation_reason is not None:
                taxon = Taxon.TID_SCHEMA_VIOLATION
                reason = occurrence.tid_schema_violation_reason
            elif occurrence.wallet_schema_violation_reason is not None or occurrence.coin_schema_violation_reason is not None or occurrence.protocol_trade_identity is None or occurrence.wallet_fill_identity is None:
                taxon = Taxon.UNCLASSIFIABLE
                reason = "REQUIRED_IDENTITY_FIELD_MISSING_OR_INVALID"
            elif len({member.full_event_sha256 for member in subgroup}) > 1:
                taxon = Taxon.CONFLICTING_USER_FILL
                reason = "COMPLETE_CANONICAL_WALLET_FILL_GROUP_CONFLICTS"
            elif any(other.locator.block_locator == occurrence.locator.block_locator and other.locator != occurrence.locator and other.full_event_sha256 == occurrence.full_event_sha256 for other in subgroup):
                taxon = Taxon.INTRA_BLOCK_REPEAT
                reason = None
            elif replay_proof is not None:
                taxon = Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY
                reason = None
            elif clean_identity and clean_protocol_proofs and not any_fill_conflict and None not in protocol_keys and len(protocol_keys) >= 2:
                taxon = Taxon.TID_SCOPE_FALSE_POSITIVE
                reason = None
            else:
                taxon = Taxon.UNCLASSIFIABLE
                reason = "NO_COMPLETE_GROUP_WIDE_PRIMARY_PREDICATE_MATCHED"
            decisions.append(LegacyDecision(
                unit_id=_id("LEGACY_REPEAT_OCCURRENCE_UNIT_V2", [group_id, occurrence.locator.as_mapping()]),
                group_id=group_id,
                primary_taxon=taxon,
                occurrence=occurrence,
                weak_group_members=members,
                proof_ids=tuple(sorted(proof_ids)),
                reason=reason,
            ))
    return tuple(decisions), tuple(duplicate_rows), tuple(schema_rows), tuple(schema_units)


def _locator_key(mapping: Mapping[str, object]) -> tuple[object, ...]:
    base: tuple[object, ...] = (
        str(mapping["source_object_key"]),
        str(mapping["compressed_object_sha256"]),
        int(mapping["record_ordinal_zero_based"]),
    )
    return base + ((int(mapping["event_ordinal_zero_based"]),) if "event_ordinal_zero_based" in mapping else ())


def _validate_graph(
    *,
    taxonomy_units: Sequence[Mapping[str, object]],
    duplicate_rows: Sequence[Mapping[str, object]],
    block_rows: Sequence[Mapping[str, object]],
    replay_proofs: Sequence[Mapping[str, object]],
    pair_proofs: Sequence[Mapping[str, object]],
    protocol_member_rows: Sequence[Mapping[str, object]],
    schema_rows: Sequence[Mapping[str, object]],
    selected_object_keys: set[str],
) -> dict[str, object]:
    unit_ids = [str(row["unit_id"]) for row in taxonomy_units]
    if len(unit_ids) != len(set(unit_ids)):
        raise R11AV2TaxonomyError("taxonomy unit IDs are not unique")
    proof_rows = list(replay_proofs) + list(pair_proofs)
    proof_ids = [str(row["proof_id"]) for row in proof_rows]
    if len(proof_ids) != len(set(proof_ids)):
        raise R11AV2TaxonomyError("proof IDs are not unique")
    proof_index = Counter(proof_ids)
    all_refs: list[str] = []
    for row in taxonomy_units:
        refs = row.get("proof_ids", [])
        if not isinstance(refs, list):
            raise R11AV2TaxonomyError("taxonomy proof_ids must be a list")
        all_refs.extend(str(item) for item in refs)
    all_proof_references_resolve = all(proof_index[reference] == 1 for reference in all_refs)
    if not all_proof_references_resolve:
        raise R11AV2TaxonomyError("taxonomy proof foreign key failed exact-once resolution")
    duplicate_locator_index: Counter[tuple[object, ...]] = Counter()
    duplicate_group_index: Counter[str] = Counter()
    for row in duplicate_rows:
        locator = row["raw_observation_locator"]
        if not isinstance(locator, Mapping):
            raise R11AV2TaxonomyError("duplicate row locator missing")
        duplicate_locator_index[_locator_key(locator)] += 1
        duplicate_group_index[str(row["legacy_group_id"])] += 1
        if str(row["source_object_key"]) not in selected_object_keys:
            raise R11AV2TaxonomyError("duplicate row references object outside canonical selection")
    if any(count != 1 for count in duplicate_locator_index.values()):
        raise R11AV2TaxonomyError("duplicate observation locator is not unique")
    block_locator_index: Counter[tuple[object, ...]] = Counter()
    block_group_index: Counter[str] = Counter()
    for row in block_rows:
        locator = row["raw_block_locator"]
        if not isinstance(locator, Mapping):
            raise R11AV2TaxonomyError("block matrix locator missing")
        block_locator_index[_locator_key(locator)] += 1
        block_group_index[str(row["block_group_id"])] += 1
        if str(row["source_object_key"]) not in selected_object_keys:
            raise R11AV2TaxonomyError("block row references object outside canonical selection")
    if any(count != 1 for count in block_locator_index.values()):
        raise R11AV2TaxonomyError("block locator is not unique")
    pair_proof_index = {str(row["proof_id"]): row for row in pair_proofs}
    for row in protocol_member_rows:
        proof = row.get("pair_proof_id")
        if proof is not None and str(proof) not in pair_proof_index:
            raise R11AV2TaxonomyError("protocol member references absent pair proof")
        block_locator = row["raw_block_locator"]
        if not isinstance(block_locator, Mapping) or str(block_locator["source_object_key"]) not in selected_object_keys:
            raise R11AV2TaxonomyError("protocol member block locator invalid")
    for row in replay_proofs:
        if block_group_index[str(row["block_group_id"])] != int(row["member_count"]):
            raise R11AV2TaxonomyError("replay proof member count does not match block matrix")
    for row in pair_proofs:
        proof_id = str(row["proof_id"])
        member_count = sum(str(member.get("pair_proof_id")) == proof_id for member in protocol_member_rows)
        if member_count != int(row["member_count"]):
            raise R11AV2TaxonomyError("pair proof member count does not match protocol ledger")
    for row in schema_rows:
        locator = row["raw_observation_locator"]
        if not isinstance(locator, Mapping) or duplicate_locator_index[_locator_key(locator)] != 1:
            raise R11AV2TaxonomyError("schema evidence does not resolve to one retained repeat observation")
        if duplicate_group_index[str(row["legacy_group_id"])] < 2:
            raise R11AV2TaxonomyError("schema evidence legacy group is not repeated")
    primary_counts = Counter(str(row["primary_taxon"]) for row in taxonomy_units)
    universe_unit_counts = Counter(str(row["unit_universe"]) for row in taxonomy_units)
    universe_occurrence_counts: Counter[str] = Counter()
    universe_unclassifiable_groups: Counter[str] = Counter()
    universe_unclassifiable_occurrences: Counter[str] = Counter()
    for row in taxonomy_units:
        universe = str(row["unit_universe"])
        occurrences = int(row["occurrence_count"])
        universe_occurrence_counts[universe] += occurrences
        if row["primary_taxon"] == Taxon.UNCLASSIFIABLE.value:
            universe_unclassifiable_groups[universe] += 1
            universe_unclassifiable_occurrences[universe] += occurrences
    for universe in UNIT_UNIVERSES:
        universe_unit_counts.setdefault(universe, 0)
        universe_occurrence_counts.setdefault(universe, 0)
        universe_unclassifiable_groups.setdefault(universe, 0)
        universe_unclassifiable_occurrences.setdefault(universe, 0)
    return {
        "all_proof_references_resolve": all_proof_references_resolve,
        "proof_reference_count": len(all_refs),
        "proof_row_count": len(proof_rows),
        "taxonomy_unit_count": len(taxonomy_units),
        "primary_taxon_counts": dict(sorted(primary_counts.items())),
        "unit_universe_counts": dict(sorted(universe_unit_counts.items())),
        "unit_universe_occurrence_counts": dict(sorted(universe_occurrence_counts.items())),
        "unit_universe_unclassifiable_group_counts": dict(sorted(universe_unclassifiable_groups.items())),
        "unit_universe_unclassifiable_occurrence_counts": dict(sorted(universe_unclassifiable_occurrences.items())),
        "duplicate_observation_row_count": len(duplicate_rows),
        "block_matrix_row_count": len(block_rows),
        "replay_proof_row_count": len(replay_proofs),
        "pair_proof_row_count": len(pair_proofs),
        "protocol_member_row_count": len(protocol_member_rows),
        "schema_evidence_row_count": len(schema_rows),
    }


def classify(
    blocks: Iterable[BlockObservation],
    *,
    repeated_weak_keys: set[bytes],
    repeated_block_numbers: set[int],
    selected_object_keys: set[str],
) -> TaxonomyReport:
    materialized = tuple(blocks)
    raw_block_locators = [block.locator for block in materialized]
    if len(raw_block_locators) != len(set(raw_block_locators)):
        raise R11AV2TaxonomyError("materialized raw block locator is not unique")
    observations = tuple(observation for block in materialized for observation in block.observations)
    raw_observation_locators = [observation.locator for observation in observations]
    if len(raw_observation_locators) != len(set(raw_observation_locators)):
        raise R11AV2TaxonomyError("materialized raw observation locator is not unique")
    block_decisions, block_rows, replay_proofs, block_units = _block_decisions(materialized, repeated_block_numbers)
    protocol_decisions, pair_proofs, protocol_members, protocol_units = _protocol_decisions(materialized, repeated_weak_keys)
    legacy_decisions, duplicate_rows, schema_rows, schema_units = _legacy_decisions(observations, repeated_weak_keys, block_decisions, protocol_decisions)
    legacy_units = tuple({
        "record_type": "TAXONOMY_UNIT",
        "unit_universe": UNIT_LEGACY,
        "unit_id": decision.unit_id,
        "group_id": decision.group_id,
        "primary_taxon": decision.primary_taxon.value,
        "member_count": len(decision.weak_group_members),
        "occurrence_count": 1,
        "primary_locator": decision.occurrence.locator.as_mapping(),
        "proof_ids": list(decision.proof_ids),
        "unclassifiable_reason": decision.reason,
    } for decision in legacy_decisions)
    taxonomy_units = tuple(sorted(block_units + protocol_units + schema_units + legacy_units, key=lambda row: (str(row["unit_universe"]), str(row["unit_id"]))))
    block_rows = tuple(sorted(block_rows, key=lambda row: (str(row["block_group_id"]), int(row["member_ordinal_zero_based"]))))
    duplicate_rows = tuple(sorted(duplicate_rows, key=lambda row: (str(row["legacy_group_id"]), int(row["legacy_group_member_ordinal_zero_based"]))))
    replay_proofs = tuple(sorted(replay_proofs, key=lambda row: str(row["proof_id"])))
    pair_proofs = tuple(sorted(pair_proofs, key=lambda row: str(row["proof_id"])))
    protocol_members = tuple(sorted(protocol_members, key=lambda row: (str(row["protocol_group_id"]), int(row["member_ordinal_zero_based"]))))
    schema_rows = tuple(sorted(schema_rows, key=lambda row: (str(row["unit_universe"]), str(row["schema_unit_id"]))))
    conservation = _validate_graph(
        taxonomy_units=taxonomy_units,
        duplicate_rows=duplicate_rows,
        block_rows=block_rows,
        replay_proofs=replay_proofs,
        pair_proofs=pair_proofs,
        protocol_member_rows=protocol_members,
        schema_rows=schema_rows,
        selected_object_keys=selected_object_keys,
    )
    complete_taxonomy = conservation["all_proof_references_resolve"] is True and all(value == 0 for value in conservation["unit_universe_unclassifiable_group_counts"].values()) and all(value == 0 for value in conservation["unit_universe_unclassifiable_occurrence_counts"].values())
    conservation["complete_taxonomy_from_retained_science"] = complete_taxonomy
    conservation["taxonomy_units_sha256"] = canonical_sha256(taxonomy_units)
    conservation["duplicate_rows_sha256"] = canonical_sha256(duplicate_rows)
    conservation["block_rows_sha256"] = canonical_sha256(block_rows)
    conservation["replay_proofs_sha256"] = canonical_sha256(replay_proofs)
    conservation["pair_proofs_sha256"] = canonical_sha256(pair_proofs)
    conservation["protocol_member_rows_sha256"] = canonical_sha256(protocol_members)
    conservation["schema_rows_sha256"] = canonical_sha256(schema_rows)
    return TaxonomyReport(
        taxonomy_units=taxonomy_units,
        block_rows=block_rows,
        duplicate_rows=duplicate_rows,
        replay_proofs=replay_proofs,
        pair_proofs=pair_proofs,
        protocol_member_rows=protocol_members,
        schema_rows=schema_rows,
        conservation=conservation,
        all_proof_references_resolve=bool(conservation["all_proof_references_resolve"]),
        complete_taxonomy=complete_taxonomy,
    )
