from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations
from typing import Iterable, Mapping, Sequence

from .identity import (
    BlockObservation,
    Observation,
    RawBlockLocator,
    RawObservationLocator,
    canonical_sha256,
    canonical_typed_bytes,
    first_diffmask,
    flatten_observations,
)
from .limits import DEFAULT_LIMITS, R11ALimits


class R11ADiagnosticError(ValueError):
    """Raised for incomplete provenance, conflicts, or conservation drift."""


class Taxon(StrEnum):
    TID_SCOPE_FALSE_POSITIVE = "TID_SCOPE_FALSE_POSITIVE"
    EXPECTED_COUNTERPARTY_PAIR = "EXPECTED_COUNTERPARTY_PAIR"
    EXACT_BLOCK_REPLAY_ACROSS_OBJECTS = "EXACT_BLOCK_REPLAY_ACROSS_OBJECTS"
    EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY = "EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY"
    CONFLICTING_BLOCK_REPLAY = "CONFLICTING_BLOCK_REPLAY"
    CONFLICTING_USER_FILL = "CONFLICTING_USER_FILL"
    INTRA_BLOCK_REPEAT = "INTRA_BLOCK_REPEAT"
    TID_SCHEMA_VIOLATION = "TID_SCHEMA_VIOLATION"
    UNCLASSIFIABLE = "UNCLASSIFIABLE"


class TerminalClass(StrEnum):
    ROOT_CAUSE_TAXONOMY_COMPLETE = "R11A_ROOT_CAUSE_TAXONOMY_COMPLETE"
    ARTIFACT_CAP_EXCEEDED = "R11A_DIAGNOSTIC_ARTIFACT_CAP_EXCEEDED"
    DIAGNOSTIC_INCOMPLETE = "R11A_DIAGNOSTIC_INCOMPLETE"


TAXON_ORDER = tuple(item.value for item in Taxon)
UNIT_TYPE_ORDER = (
    "LEGACY_REPEAT_OCCURRENCE",
    "ARCHIVE_BLOCK_NUMBER_GROUP",
    "PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE",
    "RAW_TID_SCHEMA_VIOLATION_OBSERVATION",
    "RAW_COIN_SCHEMA_VIOLATION_OBSERVATION",
    "RAW_WALLET_SCHEMA_VIOLATION_OBSERVATION",
)
UNIT_TYPE_INDEX = {name: index for index, name in enumerate(UNIT_TYPE_ORDER)}


@dataclass(frozen=True, slots=True)
class BlockDecision:
    group_id: str
    block_number: int
    members: tuple[BlockObservation, ...]
    primary_taxon: Taxon | None
    conflicting_fields: tuple[str, ...]
    proof_id: str | None


@dataclass(frozen=True, slots=True)
class PairProof:
    proof_id: str
    group_id: str
    block_locator: RawBlockLocator
    identity: tuple[str, str, int]
    members: tuple[Observation, Observation]


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    terminal_class: TerminalClass
    root_cause_claim_status: str
    raw_block_observation_count: int
    raw_event_observation_count: int
    repeat_occurrence_count_sum_n_minus_one: int
    valid_tid_repeat_occurrence_count_sum_n_minus_one: int
    invalid_tid_repeat_occurrence_count: int
    affected_weak_key_group_count: int
    affected_wallet_count: int
    affected_tid_count: int
    affected_canonical_key_count: int
    affected_block_count: int
    affected_object_count: int
    affected_path_hour_count: int
    affected_utc_day_count: int
    taxonomy_group_counts_by_class: Mapping[str, int]
    taxonomy_occurrence_counts_by_class: Mapping[str, int]
    repeat_relationship_counts: Mapping[str, int]
    unclassifiable_group_count: int
    taxonomy_conservation_passed: bool
    retention_caps_exceeded: bool
    duplicate_rows: tuple[Mapping[str, object], ...]
    block_rows: tuple[Mapping[str, object], ...]
    replay_proofs: tuple[Mapping[str, object], ...]
    pair_proofs: tuple[Mapping[str, object], ...]
    taxonomy_units: tuple[Mapping[str, object], ...]
    schema_rows: tuple[Mapping[str, object], ...]
    protocol_member_rows: tuple[Mapping[str, object], ...] = ()

    def summary(self) -> dict[str, object]:
        return {
            "terminal_class": self.terminal_class.value,
            "root_cause_claim_status": self.root_cause_claim_status,
            "raw_block_observation_count": self.raw_block_observation_count,
            "raw_event_observation_count": self.raw_event_observation_count,
            "repeat_occurrence_count_sum_n_minus_one": self.repeat_occurrence_count_sum_n_minus_one,
            "valid_tid_repeat_occurrence_count_sum_n_minus_one": self.valid_tid_repeat_occurrence_count_sum_n_minus_one,
            "invalid_tid_repeat_occurrence_count": self.invalid_tid_repeat_occurrence_count,
            "affected_weak_key_group_count": self.affected_weak_key_group_count,
            "affected_wallet_count": self.affected_wallet_count,
            "affected_tid_count": self.affected_tid_count,
            "affected_canonical_key_count": self.affected_canonical_key_count,
            "affected_block_count": self.affected_block_count,
            "affected_object_count": self.affected_object_count,
            "affected_path_hour_count": self.affected_path_hour_count,
            "affected_utc_day_count": self.affected_utc_day_count,
            "taxonomy_group_counts_by_class": dict(self.taxonomy_group_counts_by_class),
            "taxonomy_occurrence_counts_by_class": dict(self.taxonomy_occurrence_counts_by_class),
            "repeat_relationship_counts": dict(self.repeat_relationship_counts),
            "unclassifiable_group_count": self.unclassifiable_group_count,
            "taxonomy_conservation_passed": self.taxonomy_conservation_passed,
            "retention_caps_exceeded": self.retention_caps_exceeded,
        }


def _raw_block_sort(locator: RawBlockLocator) -> tuple[bytes, bytes, int]:
    return (
        locator.source_object_key.encode("utf-8", errors="strict"),
        bytes.fromhex(locator.compressed_object_sha256),
        locator.record_ordinal_zero_based,
    )


def _raw_observation_sort(locator: RawObservationLocator) -> tuple[bytes, bytes, int, int]:
    return (*_raw_block_sort(locator.block_locator), locator.event_ordinal_zero_based)


def _group_id(field_name: str, domain: str, fields: Sequence[tuple[str, object]]) -> str:
    return canonical_sha256(
        [
            "R11A_GROUP_ID_V1",
            field_name,
            domain,
            [[name, value] for name, value in fields],
        ]
    )


def _proof_id(record_type: str, fields: Sequence[tuple[str, object]]) -> str:
    return canonical_sha256(
        [
            "R11A_PROOF_ID_V1",
            record_type,
            [[name, value] for name, value in fields],
        ]
    )


def _unit_id(unit_type: str, fields: Sequence[tuple[str, object]]) -> str:
    return canonical_sha256(
        [
            "R11A_TAXONOMY_UNIT_ID_V1",
            unit_type,
            [[name, value] for name, value in fields],
        ]
    )


def _block_group_id(number: int) -> str:
    return _group_id(
        "block_replay_group_id",
        "BLOCK_NUMBER_GROUP",
        (("block_number", number),),
    )


def _weak_group_id(key: tuple[str, tuple[str, str]]) -> str:
    return _group_id(
        "weak_key_group_id",
        "WEAK_KEY_GROUP",
        (("legacy_weak_key", [key[0], list(key[1])]),),
    )


def _protocol_group_id(locator: RawBlockLocator, identity: tuple[str, str, int]) -> str:
    return _group_id(
        "protocol_trade_group_id",
        "PROTOCOL_TRADE_GROUP_PER_RAW_BLOCK",
        (
            ("raw_block_locator", locator.as_mapping()),
            ("protocol_trade_identity", list(identity)),
        ),
    )


def _wallet_group_id(identity: tuple[str, str, str, int]) -> str:
    return _group_id(
        "wallet_fill_group_id",
        "WALLET_FILL_GROUP",
        (("wallet_fill_identity", list(identity)),),
    )


def _block_fingerprints(block: BlockObservation) -> dict[str, object]:
    return {
        "canonical_serialization_version": "R11A_CANONICAL_JSON_TYPED_FIELDS_V1",
        "exact_raw_block_time": block.block_time_exact,
        "ordered_event_count": block.ordered_event_count,
        "ordered_event_fingerprint_sha256": block.ordered_event_fingerprint_sha256,
        "raw_record_sha256": block.raw_record_sha256,
    }


def _source_mapping(row: Observation) -> dict[str, object]:
    return {
        "object_key": row.source.object_key,
        "compressed_sha256": row.source.compressed_sha256,
        "path_hour_utc": row.source.path_hour_utc,
        "object_ordinal_zero_based": row.source.object_ordinal_zero_based,
        "record_ordinal_zero_based": row.locator.record_ordinal_zero_based,
    }


def _boundary_relation(first: Observation, row: Observation) -> dict[str, object]:
    same_object = (
        first.source.object_key,
        first.source.compressed_sha256,
    ) == (
        row.source.object_key,
        row.source.compressed_sha256,
    )
    same_path_hour = first.source.path_hour_utc == row.source.path_hour_utc
    hour_distance = abs(
        first.source.object_ordinal_zero_based - row.source.object_ordinal_zero_based
    )
    return {
        "same_object": same_object,
        "same_block_number": first.block_number == row.block_number,
        "same_raw_block_locator": first.locator.block_locator == row.locator.block_locator,
        "same_path_hour": same_path_hour,
        "same_utc_day": first.source.path_hour_utc[:10] == row.source.path_hour_utc[:10],
        "path_hour_distance": hour_distance,
        "adjacent_hour_boundary": not same_path_hour and hour_distance == 1,
    }


def _boundary_pair_counts(members: Sequence[BlockObservation]) -> dict[str, int]:
    counts = {
        "unordered_member_pair_count": 0,
        "same_source_object_pair_count": 0,
        "cross_source_object_pair_count": 0,
        "same_path_hour_pair_count": 0,
        "cross_path_hour_pair_count": 0,
        "same_utc_day_pair_count": 0,
        "cross_utc_day_pair_count": 0,
        "adjacent_path_hour_pair_count": 0,
        "non_adjacent_cross_path_hour_pair_count": 0,
    }
    for left, right in combinations(members, 2):
        counts["unordered_member_pair_count"] += 1
        same_object = (
            left.source.object_key,
            left.source.compressed_sha256,
        ) == (
            right.source.object_key,
            right.source.compressed_sha256,
        )
        counts["same_source_object_pair_count" if same_object else "cross_source_object_pair_count"] += 1
        same_hour = left.source.path_hour_utc == right.source.path_hour_utc
        counts["same_path_hour_pair_count" if same_hour else "cross_path_hour_pair_count"] += 1
        same_day = left.source.path_hour_utc[:10] == right.source.path_hour_utc[:10]
        counts["same_utc_day_pair_count" if same_day else "cross_utc_day_pair_count"] += 1
        if not same_hour:
            distance = abs(
                left.source.object_ordinal_zero_based
                - right.source.object_ordinal_zero_based
            )
            counts[
                "adjacent_path_hour_pair_count"
                if distance == 1
                else "non_adjacent_cross_path_hour_pair_count"
            ] += 1
    return counts


def classify_blocks(
    blocks: Sequence[BlockObservation],
) -> tuple[tuple[BlockDecision, ...], dict[RawBlockLocator, BlockDecision]]:
    grouped: dict[int, list[BlockObservation]] = defaultdict(list)
    for block in blocks:
        grouped[block.block_number].append(block)
    decisions: list[BlockDecision] = []
    locator_index: dict[RawBlockLocator, BlockDecision] = {}
    for number in sorted(grouped):
        members = tuple(sorted(grouped[number], key=lambda row: _raw_block_sort(row.locator)))
        conflicts: list[str] = []
        taxon: Taxon | None = None
        proof_id: str | None = None
        if len(members) > 1:
            if len({row.block_time_exact for row in members}) != 1:
                conflicts.append("exact_raw_block_time")
            if len({row.ordered_event_count for row in members}) != 1:
                conflicts.append("ordered_event_count")
            if len({row.ordered_event_fingerprint_sha256 for row in members}) != 1:
                conflicts.append("ordered_event_fingerprint_sha256")
            if conflicts:
                taxon = Taxon.CONFLICTING_BLOCK_REPLAY
            elif len({row.source.object_key for row in members}) >= 2:
                taxon = Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS
                member_evidence = [
                    {
                        "raw_block_locator": row.locator.as_mapping(),
                        "source_object_key": row.source.object_key,
                        "raw_record_sha256": row.raw_record_sha256,
                    }
                    for row in members
                ]
                proof_id = _proof_id(
                    "EXACT_BLOCK_REPLAY_PROOF",
                    (
                        ("record_type", "EXACT_BLOCK_REPLAY_PROOF"),
                        ("block_replay_group_id", _block_group_id(number)),
                        ("block_number", number),
                        ("member_count", len(members)),
                        ("member_evidence", member_evidence),
                        ("exact_raw_block_time", members[0].block_time_exact),
                        ("ordered_event_count", members[0].ordered_event_count),
                        (
                            "ordered_event_fingerprint_sha256",
                            members[0].ordered_event_fingerprint_sha256,
                        ),
                        ("classification", Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS.value),
                    ),
                )
            else:
                taxon = Taxon.UNCLASSIFIABLE
        decision = BlockDecision(
            _block_group_id(number),
            number,
            members,
            taxon,
            tuple(conflicts),
            proof_id,
        )
        decisions.append(decision)
        for member in members:
            if member.locator in locator_index:
                raise R11ADiagnosticError("block locator appears in multiple groups")
            locator_index[member.locator] = decision
    return tuple(decisions), locator_index


def _pair_proof(rows: Sequence[Observation]) -> PairProof | None:
    ordered = tuple(sorted(rows, key=lambda row: _raw_observation_sort(row.locator)))
    if len(ordered) != 2:
        return None
    first, second = ordered
    if (
        first.protocol_trade_identity is None
        or first.protocol_trade_identity != second.protocol_trade_identity
    ):
        return None
    if first.locator.block_locator != second.locator.block_locator:
        return None
    wallets = {
        first.canonical_lowercase_wallet_address,
        second.canonical_lowercase_wallet_address,
    }
    if None in wallets or len(wallets) != 2:
        return None
    if {first.side_exact, second.side_exact} != {"A", "B"}:
        return None
    if abs(
        first.locator.event_ordinal_zero_based
        - second.locator.event_ordinal_zero_based
    ) != 1:
        return None
    group_id = _protocol_group_id(
        first.locator.block_locator,
        first.protocol_trade_identity,
    )
    members = [
        {
            "raw_observation_locator": row.locator.as_mapping(),
            "canonical_lowercase_wallet_address": row.canonical_lowercase_wallet_address,
            "side_exact": row.side_exact,
            "crossed_exact": row.crossed_exact,
            "full_event_sha256": row.full_event_sha256,
        }
        for row in ordered
    ]
    proof_id = _proof_id(
        "EXPECTED_COUNTERPARTY_PAIR_PROOF",
        (
            ("record_type", "EXPECTED_COUNTERPARTY_PAIR_PROOF"),
            ("protocol_trade_group_id", group_id),
            ("raw_block_locator", first.locator.block_locator.as_mapping()),
            ("protocol_trade_identity", list(first.protocol_trade_identity)),
            ("member_count", 2),
            ("members", members),
            ("classification", Taxon.EXPECTED_COUNTERPARTY_PAIR.value),
        ),
    )
    return PairProof(
        proof_id,
        group_id,
        first.locator.block_locator,
        first.protocol_trade_identity,
        (first, second),
    )


def _zero_taxa() -> dict[str, int]:
    return {item: 0 for item in TAXON_ORDER}


def _relationships() -> dict[str, int]:
    return {
        "intra_object": 0,
        "inter_object": 0,
        "intra_block": 0,
        "inter_block": 0,
        "same_path_hour": 0,
        "cross_path_hour": 0,
        "same_utc_day": 0,
        "cross_utc_day": 0,
        "adjacent_hour_boundary": 0,
        "non_adjacent_hour_boundary": 0,
        "exact_identical_payload": 0,
        "conflicting_payload": 0,
    }


def _classify_repeat(
    first: Observation,
    current: Observation,
    group: Sequence[Observation],
    block_index: Mapping[RawBlockLocator, BlockDecision],
    pair_by_protocol_group: Mapping[
        tuple[RawBlockLocator, tuple[str, str, int]], PairProof
    ],
) -> tuple[Taxon, tuple[Taxon, ...], str | None, str | None]:
    if current.tid_validation_status != "VALID_UINT50":
        return Taxon.TID_SCHEMA_VIOLATION, (), None, None
    if (
        current.wallet_validation_status != "VALID_EXACT_LOWERCASE_0X40HEX"
        or current.coin_validation_status != "VALID_EXACT_RAW_NONEMPTY_STRING"
    ):
        return Taxon.UNCLASSIFIABLE, (), None, None
    pair_key = (
        current.locator.block_locator,
        current.protocol_trade_identity,
    )
    pair = (
        pair_by_protocol_group.get(pair_key)
        if current.protocol_trade_identity is not None
        else None
    )
    pair_support = pair is not None
    same_canonical = [
        row
        for row in group
        if row.wallet_fill_identity == current.wallet_fill_identity
    ]
    if current.wallet_fill_identity is not None and any(
        row.full_event_sha256 != current.full_event_sha256
        for row in same_canonical
    ):
        support = (Taxon.EXPECTED_COUNTERPARTY_PAIR,) if pair_support else ()
        return (
            Taxon.CONFLICTING_USER_FILL,
            support,
            None,
            pair.proof_id if pair is not None else None,
        )
    if (
        first.wallet_fill_identity == current.wallet_fill_identity
        and first.locator.block_locator == current.locator.block_locator
        and first.locator.event_ordinal_zero_based
        != current.locator.event_ordinal_zero_based
        and first.full_event_sha256 == current.full_event_sha256
    ):
        return Taxon.INTRA_BLOCK_REPEAT, (), None, None
    if (
        first.wallet_fill_identity == current.wallet_fill_identity
        and first.full_event_sha256 == current.full_event_sha256
    ):
        first_decision = block_index.get(first.locator.block_locator)
        current_decision = block_index.get(current.locator.block_locator)
        if (
            first_decision is not None
            and first_decision is current_decision
            and first_decision.primary_taxon
            is Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS
            and first_decision.proof_id is not None
        ):
            support = [Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS]
            if pair_support:
                support.insert(0, Taxon.EXPECTED_COUNTERPARTY_PAIR)
            return (
                Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY,
                tuple(support),
                first_decision.proof_id,
                pair.proof_id if pair is not None else None,
            )
    protocol_keys = {row.protocol_trade_identity for row in group}
    if None not in protocol_keys and len(protocol_keys) >= 2:
        support = (Taxon.EXPECTED_COUNTERPARTY_PAIR,) if pair_support else ()
        return (
            Taxon.TID_SCOPE_FALSE_POSITIVE,
            support,
            None,
            pair.proof_id if pair is not None else None,
        )
    return Taxon.UNCLASSIFIABLE, (), None, None


def _taxonomy_unit(
    *,
    unit_type: str,
    unit_id: str,
    primary_taxon: Taxon,
    supporting: Sequence[Taxon],
    member_observations: Sequence[RawObservationLocator] | None,
    member_blocks: Sequence[RawBlockLocator],
    weak_key_group_id: str | None = None,
    block_replay_group_id: str | None = None,
    protocol_trade_group_id: str | None = None,
    wallet_fill_group_id: str | None = None,
    classification_predicate_priority: int = 1,
    replay_proof_id: str | None = None,
    pair_proof_ids: Sequence[str] = (),
) -> dict[str, object]:
    return {
        "record_type": "TAXONOMY_UNIT",
        "taxonomy_unit_type": unit_type,
        "taxonomy_unit_id": unit_id,
        "primary_taxon": primary_taxon.value,
        "supporting_taxa": [item.value for item in supporting],
        "member_count": (
            len(member_observations)
            if member_observations is not None
            else len(member_blocks)
        ),
        "member_raw_observation_locators": (
            [row.as_mapping() for row in member_observations]
            if member_observations is not None
            else None
        ),
        "member_raw_block_locators": [row.as_mapping() for row in member_blocks],
        "weak_key_group_id": weak_key_group_id,
        "block_replay_group_id": block_replay_group_id,
        "protocol_trade_group_id": protocol_trade_group_id,
        "wallet_fill_group_id": wallet_fill_group_id,
        "classification_predicate_priority": classification_predicate_priority,
        "exact_block_replay_proof_id": replay_proof_id,
        "expected_counterparty_pair_proof_ids": list(pair_proof_ids),
    }


def _schema_unit(
    row: Observation,
    *,
    unit_type: str,
    taxon: Taxon,
    reason: str,
) -> tuple[dict[str, object], dict[str, object]]:
    unit_id = _unit_id(
        unit_type,
        (("raw_observation_locator", row.locator.as_mapping()),),
    )
    evidence = {
        "record_type": "MINIMAL_SCHEMA_VIOLATION_EVIDENCE",
        "taxonomy_unit_type": unit_type,
        "taxonomy_unit_id": unit_id,
        "primary_taxon": taxon.value,
        "raw_observation_locator": row.locator.as_mapping(),
        "raw_block_locator": row.locator.block_locator.as_mapping(),
        "raw_tid_json_type": (
            row.raw_tid_json_type
            if unit_type == "RAW_TID_SCHEMA_VIOLATION_OBSERVATION"
            else None
        ),
        "raw_tid_token": (
            row.raw_tid_token
            if unit_type == "RAW_TID_SCHEMA_VIOLATION_OBSERVATION"
            else None
        ),
        "tid_schema_violation_reason": (
            reason
            if unit_type == "RAW_TID_SCHEMA_VIOLATION_OBSERVATION"
            else None
        ),
        "raw_coin_json_type": (
            row.raw_coin_json_type
            if unit_type == "RAW_COIN_SCHEMA_VIOLATION_OBSERVATION"
            else None
        ),
        "raw_coin_token": (
            row.raw_coin_token
            if unit_type == "RAW_COIN_SCHEMA_VIOLATION_OBSERVATION"
            else None
        ),
        "coin_schema_violation_reason": (
            reason
            if unit_type == "RAW_COIN_SCHEMA_VIOLATION_OBSERVATION"
            else None
        ),
        "raw_wallet_json_type": (
            row.raw_wallet_json_type
            if unit_type == "RAW_WALLET_SCHEMA_VIOLATION_OBSERVATION"
            else None
        ),
        "raw_wallet_token": (
            row.raw_wallet_token
            if unit_type == "RAW_WALLET_SCHEMA_VIOLATION_OBSERVATION"
            else None
        ),
        "wallet_schema_violation_reason": (
            reason
            if unit_type == "RAW_WALLET_SCHEMA_VIOLATION_OBSERVATION"
            else None
        ),
        "full_lossless_payload_retained": False,
    }
    unit = _taxonomy_unit(
        unit_type=unit_type,
        unit_id=unit_id,
        primary_taxon=taxon,
        supporting=(),
        member_observations=(row.locator,),
        member_blocks=(row.locator.block_locator,),
    )
    return evidence, unit


def classify(
    blocks: Iterable[BlockObservation],
    *,
    limits: R11ALimits = DEFAULT_LIMITS,
) -> DiagnosticReport:
    limits.validate()
    ordered_blocks = tuple(
        sorted(blocks, key=lambda row: _raw_block_sort(row.locator))
    )
    if len({row.locator for row in ordered_blocks}) != len(ordered_blocks):
        raise R11ADiagnosticError("duplicate raw block locator")
    observations = flatten_observations(ordered_blocks)
    block_decisions, block_index = classify_blocks(ordered_blocks)
    block_by_locator = {row.locator: row for row in ordered_blocks}

    protocol_groups: dict[
        tuple[RawBlockLocator, tuple[str, str, int]], list[Observation]
    ] = defaultdict(list)
    for row in observations:
        if row.protocol_trade_identity is not None:
            protocol_groups[
                (row.locator.block_locator, row.protocol_trade_identity)
            ].append(row)
    pair_by_protocol_group: dict[
        tuple[RawBlockLocator, tuple[str, str, int]], PairProof
    ] = {}
    for key, rows in protocol_groups.items():
        proof = _pair_proof(rows)
        if proof is not None:
            pair_by_protocol_group[key] = proof

    legacy: dict[tuple[str, tuple[str, str]], list[Observation]] = defaultdict(list)
    for row in observations:
        if row.legacy_weak_key is not None:
            legacy[row.legacy_weak_key].append(row)
    repeat_groups = {
        key: tuple(
            sorted(rows, key=lambda row: _raw_observation_sort(row.locator))
        )
        for key, rows in legacy.items()
        if len(rows) > 1
    }
    repeated_block_decisions = [
        row for row in block_decisions if len(row.members) > 1
    ]
    retention_caps_exceeded = (
        len(repeat_groups)
        > limits.maximum_repeated_legacy_key_groups_retained
        or sum(len(rows) for rows in repeat_groups.values())
        > limits.maximum_repeated_observations_retained
        or len(repeated_block_decisions)
        > limits.maximum_repeated_block_groups_retained
    )
    if retention_caps_exceeded:
        zero = _zero_taxa()
        return DiagnosticReport(
            terminal_class=TerminalClass.ARTIFACT_CAP_EXCEEDED,
            root_cause_claim_status="NOT_PROVEN",
            raw_block_observation_count=len(ordered_blocks),
            raw_event_observation_count=len(observations),
            repeat_occurrence_count_sum_n_minus_one=0,
            valid_tid_repeat_occurrence_count_sum_n_minus_one=0,
            invalid_tid_repeat_occurrence_count=0,
            affected_weak_key_group_count=0,
            affected_wallet_count=0,
            affected_tid_count=0,
            affected_canonical_key_count=0,
            affected_block_count=0,
            affected_object_count=0,
            affected_path_hour_count=0,
            affected_utc_day_count=0,
            taxonomy_group_counts_by_class=zero,
            taxonomy_occurrence_counts_by_class=dict(zero),
            repeat_relationship_counts=_relationships(),
            unclassifiable_group_count=0,
            taxonomy_conservation_passed=False,
            retention_caps_exceeded=True,
            duplicate_rows=(),
            block_rows=(),
            replay_proofs=(),
            pair_proofs=(),
            taxonomy_units=(),
            schema_rows=(),
            protocol_member_rows=(),
        )

    group_sets: dict[str, set[object]] = {
        name: set() for name in TAXON_ORDER
    }
    occurrence_counts = _zero_taxa()
    relationships = _relationships()
    duplicate_rows: list[Mapping[str, object]] = []
    units: list[Mapping[str, object]] = []
    schema_rows: list[Mapping[str, object]] = []
    repeat_occurrences = 0
    valid_repeat = 0
    affected: list[Observation] = []
    intersecting_protocol_keys: set[
        tuple[RawBlockLocator, tuple[str, str, int]]
    ] = set()

    for key in sorted(
        repeat_groups,
        key=lambda item: canonical_typed_bytes([item[0], list(item[1])]),
    ):
        group = repeat_groups[key]
        first = group[0]
        weak_group_id = _weak_group_id(key)
        affected.extend(group)
        wallet_group_counts: dict[tuple[str, str, str, int], int] = defaultdict(int)
        protocol_group_counts: dict[
            tuple[RawBlockLocator, tuple[str, str, int]], int
        ] = defaultdict(int)
        for member in group:
            if member.wallet_fill_identity is not None:
                wallet_group_counts[member.wallet_fill_identity] += 1
            if member.protocol_trade_identity is not None:
                protocol_key = (
                    member.locator.block_locator,
                    member.protocol_trade_identity,
                )
                protocol_group_counts[protocol_key] += 1
                intersecting_protocol_keys.add(protocol_key)

        for index, row in enumerate(group):
            taxon: Taxon | None = None
            supporting: tuple[Taxon, ...] = ()
            replay_id: str | None = None
            pair_id: str | None = None
            taxonomy_unit_type: str | None = None
            taxonomy_unit_id: str | None = None
            classification_priority: int | None = None
            if index > 0:
                repeat_occurrences += 1
                taxon, supporting, replay_id, pair_id = _classify_repeat(
                    first,
                    row,
                    group,
                    block_index,
                    pair_by_protocol_group,
                )
                if row.tid_validation_status == "VALID_UINT50":
                    valid_repeat += 1
                    taxonomy_unit_type = "LEGACY_REPEAT_OCCURRENCE"
                    taxonomy_unit_id = _unit_id(
                        taxonomy_unit_type,
                        (("raw_observation_locator", row.locator.as_mapping()),),
                    )
                    priority_by_taxon = {
                        Taxon.CONFLICTING_USER_FILL: 2,
                        Taxon.INTRA_BLOCK_REPEAT: 3,
                        Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY: 4,
                        Taxon.TID_SCOPE_FALSE_POSITIVE: 5,
                        Taxon.UNCLASSIFIABLE: 6,
                    }
                    classification_priority = priority_by_taxon.get(taxon, 1)
                    units.append(
                        _taxonomy_unit(
                            unit_type=taxonomy_unit_type,
                            unit_id=taxonomy_unit_id,
                            primary_taxon=taxon,
                            supporting=supporting,
                            member_observations=(row.locator,),
                            member_blocks=(row.locator.block_locator,),
                            weak_key_group_id=weak_group_id,
                            block_replay_group_id=block_index[
                                row.locator.block_locator
                            ].group_id,
                            protocol_trade_group_id=(
                                _protocol_group_id(
                                    row.locator.block_locator,
                                    row.protocol_trade_identity,
                                )
                                if row.protocol_trade_identity is not None
                                else None
                            ),
                            wallet_fill_group_id=(
                                _wallet_group_id(row.wallet_fill_identity)
                                if row.wallet_fill_identity is not None
                                else None
                            ),
                            classification_predicate_priority=classification_priority,
                            replay_proof_id=replay_id,
                            pair_proof_ids=((pair_id,) if pair_id else ()),
                        )
                    )
                    group_key: object
                    if taxon is Taxon.TID_SCOPE_FALSE_POSITIVE:
                        group_key = weak_group_id
                    elif taxon in {
                        Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY,
                        Taxon.CONFLICTING_USER_FILL,
                    }:
                        group_key = (
                            _wallet_group_id(row.wallet_fill_identity)
                            if row.wallet_fill_identity is not None
                            else taxonomy_unit_id
                        )
                    elif taxon is Taxon.INTRA_BLOCK_REPEAT:
                        group_key = (
                            _wallet_group_id(row.wallet_fill_identity)
                            if row.wallet_fill_identity is not None
                            else taxonomy_unit_id,
                            row.locator.block_locator,
                        )
                    else:
                        group_key = taxonomy_unit_id
                    group_sets[taxon.value].add(group_key)
                else:
                    taxonomy_unit_type = "RAW_TID_SCHEMA_VIOLATION_OBSERVATION"
                    taxonomy_unit_id = _unit_id(
                        taxonomy_unit_type,
                        (("raw_observation_locator", row.locator.as_mapping()),),
                    )
                occurrence_counts[taxon.value] += 1
                relation = _boundary_relation(first, row)
                relationships[
                    "intra_object" if relation["same_object"] else "inter_object"
                ] += 1
                relationships[
                    "intra_block"
                    if relation["same_raw_block_locator"]
                    else "inter_block"
                ] += 1
                relationships[
                    "same_path_hour"
                    if relation["same_path_hour"]
                    else "cross_path_hour"
                ] += 1
                relationships[
                    "same_utc_day"
                    if relation["same_utc_day"]
                    else "cross_utc_day"
                ] += 1
                if not relation["same_path_hour"]:
                    relationships[
                        "adjacent_hour_boundary"
                        if relation["adjacent_hour_boundary"]
                        else "non_adjacent_hour_boundary"
                    ] += 1
                relationships[
                    "exact_identical_payload"
                    if first.full_event_sha256 == row.full_event_sha256
                    else "conflicting_payload"
                ] += 1
            elif row.tid_validation_status != "VALID_UINT50":
                taxon = Taxon.TID_SCHEMA_VIOLATION
                taxonomy_unit_type = "RAW_TID_SCHEMA_VIOLATION_OBSERVATION"
                taxonomy_unit_id = _unit_id(
                    taxonomy_unit_type,
                    (("raw_observation_locator", row.locator.as_mapping()),),
                )
            elif row.coin_validation_status != "VALID_EXACT_RAW_NONEMPTY_STRING":
                taxon = Taxon.UNCLASSIFIABLE

            block_decision = block_index[row.locator.block_locator]
            protocol_group_id = (
                _protocol_group_id(
                    row.locator.block_locator,
                    row.protocol_trade_identity,
                )
                if row.protocol_trade_identity is not None
                else None
            )
            wallet_group_id = (
                _wallet_group_id(row.wallet_fill_identity)
                if row.wallet_fill_identity is not None
                else None
            )
            duplicate_rows.append(
                {
                    "record_type": "LEGACY_REPEAT_OBSERVATION",
                    "primary_taxon": taxon.value if taxon is not None else None,
                    "supporting_taxa": [item.value for item in supporting],
                    "taxonomy_unit_type": taxonomy_unit_type,
                    "taxonomy_unit_id": taxonomy_unit_id,
                    "weak_key_group_id": weak_group_id,
                    "block_replay_group_id": block_decision.group_id,
                    "protocol_trade_group_id": protocol_group_id,
                    "wallet_fill_group_id": wallet_group_id,
                    "legacy_weak_key": [key[0], list(key[1])],
                    "raw_wallet_address": row.raw_wallet_address,
                    "raw_wallet_json_type": row.raw_wallet_json_type,
                    "raw_wallet_token": row.raw_wallet_token,
                    "wallet_validation_status": row.wallet_validation_status,
                    "wallet_schema_violation_reason": row.wallet_schema_violation_reason,
                    "canonical_lowercase_wallet_address": row.canonical_lowercase_wallet_address,
                    "raw_tid_json_type": row.raw_tid_json_type,
                    "raw_tid_token": row.raw_tid_token,
                    "tid_validation_status": row.tid_validation_status,
                    "tid_schema_violation_reason": row.tid_schema_violation_reason,
                    "validated_integer_tid": row.validated_integer_tid,
                    "raw_coin_json_type": row.raw_coin_json_type,
                    "raw_coin_token": row.raw_coin_token,
                    "coin_validation_status": row.coin_validation_status,
                    "coin_schema_violation_reason": row.coin_schema_violation_reason,
                    "exact_raw_coin_string": row.exact_raw_coin_string,
                    "weak_key_group_multiplicity": len(group),
                    "block_replay_group_multiplicity": len(block_decision.members),
                    "protocol_trade_group_multiplicity": (
                        protocol_group_counts.get(
                            (row.locator.block_locator, row.protocol_trade_identity)
                        )
                        if row.protocol_trade_identity is not None
                        else None
                    ),
                    "wallet_fill_group_multiplicity": (
                        wallet_group_counts.get(row.wallet_fill_identity)
                        if row.wallet_fill_identity is not None
                        else None
                    ),
                    "protocol_trade_identity": (
                        list(row.protocol_trade_identity)
                        if row.protocol_trade_identity is not None
                        else None
                    ),
                    "wallet_fill_identity": (
                        list(row.wallet_fill_identity)
                        if row.wallet_fill_identity is not None
                        else None
                    ),
                    "raw_observation_locator": row.locator.as_mapping(),
                    "raw_block_locator": row.locator.block_locator.as_mapping(),
                    "source": _source_mapping(row),
                    "block_number": row.block_number,
                    "block_time_exact": row.block_time_exact,
                    "local_time_exact": row.local_time_exact,
                    "side_exact": row.side_exact,
                    "fill_time_exact": row.fill_time_exact,
                    "selected_fill_sha256": row.selected_fill_sha256,
                    "full_fill_sha256": row.full_fill_sha256,
                    "full_event_sha256": row.full_event_sha256,
                    "block_fingerprints": _block_fingerprints(
                        block_by_locator[row.locator.block_locator]
                    ),
                    "full_lossless_validated_fill_payload": dict(
                        row.full_lossless_validated_fill_payload
                    ),
                    "first_versus_occurrence_field_diffmask": first_diffmask(
                        first, row
                    ),
                    "boundary_relationship_to_group_first": _boundary_relation(
                        first, row
                    ),
                    "exact_block_replay_proof": (
                        {"exact_block_replay_proof_id": replay_id}
                        if replay_id is not None
                        else None
                    ),
                    "expected_counterparty_pair_proof": (
                        {"expected_counterparty_pair_proof_id": pair_id}
                        if pair_id is not None
                        else None
                    ),
                    "deduplication_authorized": False,
                }
            )

    block_rows: list[Mapping[str, object]] = []
    replay_rows: list[Mapping[str, object]] = []
    for decision in block_decisions:
        members = [
            {
                "raw_block_locator": row.locator.as_mapping(),
                "source_object_key": row.source.object_key,
                "block_fingerprints": _block_fingerprints(row),
            }
            for row in decision.members
        ]
        block_rows.append(
            {
                "record_type": "BLOCK_NUMBER_GROUP",
                "block_replay_group_id": decision.group_id,
                "block_number": decision.block_number,
                "member_count": len(members),
                "members": members,
                "member_raw_block_locators": [
                    row.locator.as_mapping() for row in decision.members
                ],
                "member_source_object_keys": sorted(
                    {row.source.object_key for row in decision.members},
                    key=lambda value: value.encode("utf-8", errors="strict"),
                ),
                "primary_taxon": (
                    decision.primary_taxon.value
                    if decision.primary_taxon is not None
                    else None
                ),
                "conflicting_invariant_fields": list(
                    decision.conflicting_fields
                ),
                "exact_block_replay_proof_id": decision.proof_id,
                "boundary_relationship_counts": _boundary_pair_counts(
                    decision.members
                ),
            }
        )
        if len(decision.members) > 1:
            if decision.primary_taxon is None:
                raise R11ADiagnosticError("repeated block group lacks taxon")
            occurrence_counts[decision.primary_taxon.value] += len(
                decision.members
            )
            group_sets[decision.primary_taxon.value].add(decision.group_id)
            unit_id = _unit_id(
                "ARCHIVE_BLOCK_NUMBER_GROUP",
                (("block_replay_group_id", decision.group_id),),
            )
            units.append(
                _taxonomy_unit(
                    unit_type="ARCHIVE_BLOCK_NUMBER_GROUP",
                    unit_id=unit_id,
                    primary_taxon=decision.primary_taxon,
                    supporting=(),
                    member_observations=None,
                    member_blocks=tuple(
                        row.locator for row in decision.members
                    ),
                    block_replay_group_id=decision.group_id,
                    classification_predicate_priority=(
                        1
                        if decision.primary_taxon
                        is Taxon.CONFLICTING_BLOCK_REPLAY
                        else 2
                        if decision.primary_taxon
                        is Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS
                        else 3
                    ),
                    replay_proof_id=decision.proof_id,
                )
            )
        if decision.proof_id is not None:
            member_evidence = [
                {
                    "raw_block_locator": row.locator.as_mapping(),
                    "source_object_key": row.source.object_key,
                    "raw_record_sha256": row.raw_record_sha256,
                }
                for row in decision.members
            ]
            replay_rows.append(
                {
                    "record_type": "EXACT_BLOCK_REPLAY_PROOF",
                    "exact_block_replay_proof_id": decision.proof_id,
                    "block_replay_group_id": decision.group_id,
                    "block_number": decision.block_number,
                    "member_count": len(member_evidence),
                    "member_evidence": member_evidence,
                    "exact_raw_block_time": decision.members[0].block_time_exact,
                    "ordered_event_count": decision.members[0].ordered_event_count,
                    "ordered_event_fingerprint_sha256": decision.members[
                        0
                    ].ordered_event_fingerprint_sha256,
                    "classification": Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS.value,
                }
            )

    pair_rows: list[Mapping[str, object]] = []
    protocol_member_rows: list[Mapping[str, object]] = []
    for protocol_key in sorted(
        intersecting_protocol_keys,
        key=lambda item: (
            _raw_block_sort(item[0]),
            canonical_typed_bytes(list(item[1])),
        ),
    ):
        rows = tuple(
            sorted(
                protocol_groups[protocol_key],
                key=lambda row: _raw_observation_sort(row.locator),
            )
        )
        proof = pair_by_protocol_group.get(protocol_key)
        taxon = (
            Taxon.EXPECTED_COUNTERPARTY_PAIR
            if proof is not None
            else Taxon.UNCLASSIFIABLE
        )
        group_id = _protocol_group_id(protocol_key[0], protocol_key[1])
        unit_id = _unit_id(
            "PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE",
            (("protocol_trade_group_id", group_id),),
        )
        group_sets[taxon.value].add(group_id)
        occurrence_counts[taxon.value] += len(rows)
        units.append(
            _taxonomy_unit(
                unit_type="PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE",
                unit_id=unit_id,
                primary_taxon=taxon,
                supporting=(),
                member_observations=tuple(row.locator for row in rows),
                member_blocks=(protocol_key[0],),
                block_replay_group_id=block_index[
                    protocol_key[0]
                ].group_id,
                protocol_trade_group_id=group_id,
                classification_predicate_priority=1 if proof else 2,
                pair_proof_ids=((proof.proof_id,) if proof else ()),
            )
        )
        for row in rows:
            protocol_member_rows.append(
                {
                    "record_type": "MINIMAL_PROTOCOL_TRADE_GROUP_MEMBER",
                    "raw_observation_locator": row.locator.as_mapping(),
                    "raw_block_locator": row.locator.block_locator.as_mapping(),
                    "protocol_trade_group_id": group_id,
                    "canonical_lowercase_wallet_address": row.canonical_lowercase_wallet_address,
                    "protocol_trade_identity": list(protocol_key[1]),
                    "side_exact": row.side_exact,
                    "crossed_exact": row.crossed_exact,
                    "full_event_sha256": row.full_event_sha256,
                    "retention_reason": (
                        "EXPECTED_COUNTERPARTY_PAIR_PROOF_INTERSECTING_RETAINED_LEGACY_REPEAT_EVIDENCE"
                        if proof
                        else "UNCLASSIFIABLE_PROTOCOL_TRADE_GROUP_INTERSECTING_RETAINED_LEGACY_REPEAT_EVIDENCE"
                    ),
                    "full_lossless_payload_retained": False,
                }
            )
        if proof is not None:
            members = [
                {
                    "raw_observation_locator": row.locator.as_mapping(),
                    "canonical_lowercase_wallet_address": row.canonical_lowercase_wallet_address,
                    "side_exact": row.side_exact,
                    "crossed_exact": row.crossed_exact,
                    "full_event_sha256": row.full_event_sha256,
                }
                for row in proof.members
            ]
            pair_rows.append(
                {
                    "record_type": "EXPECTED_COUNTERPARTY_PAIR_PROOF",
                    "expected_counterparty_pair_proof_id": proof.proof_id,
                    "protocol_trade_group_id": proof.group_id,
                    "raw_block_locator": proof.block_locator.as_mapping(),
                    "protocol_trade_identity": list(proof.identity),
                    "member_count": 2,
                    "members": members,
                    "classification": Taxon.EXPECTED_COUNTERPARTY_PAIR.value,
                }
            )

    for row in observations:
        variants: list[tuple[str, Taxon, str | None]] = []
        if row.tid_validation_status != "VALID_UINT50":
            variants.append(
                (
                    "RAW_TID_SCHEMA_VIOLATION_OBSERVATION",
                    Taxon.TID_SCHEMA_VIOLATION,
                    row.tid_schema_violation_reason,
                )
            )
        if row.coin_validation_status != "VALID_EXACT_RAW_NONEMPTY_STRING":
            variants.append(
                (
                    "RAW_COIN_SCHEMA_VIOLATION_OBSERVATION",
                    Taxon.UNCLASSIFIABLE,
                    row.coin_schema_violation_reason,
                )
            )
        if row.wallet_validation_status != "VALID_EXACT_LOWERCASE_0X40HEX":
            variants.append(
                (
                    "RAW_WALLET_SCHEMA_VIOLATION_OBSERVATION",
                    Taxon.UNCLASSIFIABLE,
                    row.wallet_schema_violation_reason,
                )
            )
        for unit_type, taxon, reason in variants:
            if reason is None:
                raise R11ADiagnosticError("schema violation lacks reason")
            evidence, unit = _schema_unit(
                row,
                unit_type=unit_type,
                taxon=taxon,
                reason=reason,
            )
            schema_rows.append(evidence)
            units.append(unit)
            group_sets[taxon.value].add(
                (unit_type, row.locator)
            )
            occurrence_counts[taxon.value] += 1

    invalid_repeat = repeat_occurrences - valid_repeat
    group_counts = {
        name: len(group_sets[name]) for name in TAXON_ORDER
    }
    valid_primary_total = sum(
        occurrence_counts[name]
        for name in (
            Taxon.TID_SCOPE_FALSE_POSITIVE.value,
            Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY.value,
            Taxon.CONFLICTING_USER_FILL.value,
            Taxon.INTRA_BLOCK_REPEAT.value,
            Taxon.UNCLASSIFIABLE.value,
        )
    )
    # UNCLASSIFIABLE also includes non-repeat protocol/schema/block units. Remove
    # those when checking the valid legacy repeat partition.
    valid_legacy_unclassifiable = sum(
        1
        for unit in units
        if unit["taxonomy_unit_type"] == "LEGACY_REPEAT_OCCURRENCE"
        and unit["primary_taxon"] == Taxon.UNCLASSIFIABLE.value
    )
    valid_primary_total = (
        occurrence_counts[Taxon.TID_SCOPE_FALSE_POSITIVE.value]
        + occurrence_counts[
            Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY.value
        ]
        + occurrence_counts[Taxon.CONFLICTING_USER_FILL.value]
        + occurrence_counts[Taxon.INTRA_BLOCK_REPEAT.value]
        + valid_legacy_unclassifiable
    )
    repeated_block_unit_count = sum(
        unit["taxonomy_unit_type"] == "ARCHIVE_BLOCK_NUMBER_GROUP"
        for unit in units
    )
    protocol_unit_count = sum(
        unit["taxonomy_unit_type"]
        == "PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE"
        for unit in units
    )
    tid_schema_unit_count = sum(
        unit["taxonomy_unit_type"]
        == "RAW_TID_SCHEMA_VIOLATION_OBSERVATION"
        for unit in units
    )
    unclassifiable_units = [
        unit
        for unit in units
        if unit["primary_taxon"] == Taxon.UNCLASSIFIABLE.value
    ]
    conservation = (
        repeat_occurrences == valid_repeat + invalid_repeat
        and valid_primary_total == valid_repeat
        and invalid_repeat
        == sum(
            1
            for row in duplicate_rows[1:]
            if row["primary_taxon"] == Taxon.TID_SCHEMA_VIOLATION.value
        )
        if False
        else True
    )
    # Explicitly evaluate without conditional-expression precedence ambiguity.
    invalid_repeat_rows = sum(
        1
        for row in duplicate_rows
        if row["primary_taxon"] == Taxon.TID_SCHEMA_VIOLATION.value
        and row["first_versus_occurrence_field_diffmask"]
        != {key: False for key in row["first_versus_occurrence_field_diffmask"]}
    )
    conservation = (
        repeat_occurrences == valid_repeat + invalid_repeat
        and valid_primary_total == valid_repeat
        and invalid_repeat_rows == invalid_repeat
        and relationships["intra_object"] + relationships["inter_object"]
        == repeat_occurrences
        and relationships["intra_block"] + relationships["inter_block"]
        == repeat_occurrences
        and relationships["same_path_hour"]
        + relationships["cross_path_hour"]
        == repeat_occurrences
        and relationships["same_utc_day"]
        + relationships["cross_utc_day"]
        == repeat_occurrences
        and relationships["exact_identical_payload"]
        + relationships["conflicting_payload"]
        == repeat_occurrences
        and relationships["adjacent_hour_boundary"]
        + relationships["non_adjacent_hour_boundary"]
        == relationships["cross_path_hour"]
        and repeated_block_unit_count == len(repeated_block_decisions)
        and protocol_unit_count == len(intersecting_protocol_keys)
        and tid_schema_unit_count
        == sum(
            row.tid_validation_status != "VALID_UINT50"
            for row in observations
        )
        and len({row["taxonomy_unit_id"] for row in units}) == len(units)
        and len(
            {
                canonical_sha256(row["raw_observation_locator"])
                for row in duplicate_rows
            }
        )
        == len(duplicate_rows)
    )
    unclassifiable = len(unclassifiable_units)
    if conservation and unclassifiable == 0:
        terminal = TerminalClass.ROOT_CAUSE_TAXONOMY_COMPLETE
        claim = "PROVEN_COMPLETE_TAXONOMY_ONLY"
    else:
        terminal = TerminalClass.DIAGNOSTIC_INCOMPLETE
        claim = "NOT_PROVEN"

    unit_sort = lambda row: (
        UNIT_TYPE_INDEX[str(row["taxonomy_unit_type"])],
        bytes.fromhex(str(row["taxonomy_unit_id"])),
    )
    return DiagnosticReport(
        terminal_class=terminal,
        root_cause_claim_status=claim,
        raw_block_observation_count=len(ordered_blocks),
        raw_event_observation_count=len(observations),
        repeat_occurrence_count_sum_n_minus_one=repeat_occurrences,
        valid_tid_repeat_occurrence_count_sum_n_minus_one=valid_repeat,
        invalid_tid_repeat_occurrence_count=invalid_repeat,
        affected_weak_key_group_count=len(repeat_groups),
        affected_wallet_count=len(
            {
                row.canonical_lowercase_wallet_address
                for row in affected
                if row.canonical_lowercase_wallet_address is not None
            }
        ),
        affected_tid_count=len(
            {
                row.legacy_weak_key[1]
                for row in affected
                if row.legacy_weak_key is not None
            }
        ),
        affected_canonical_key_count=len(
            {
                row.wallet_fill_identity
                for row in affected
                if row.wallet_fill_identity is not None
            }
        ),
        affected_block_count=len({row.block_number for row in affected}),
        affected_object_count=len(
            {
                (row.source.object_key, row.source.compressed_sha256)
                for row in affected
            }
        ),
        affected_path_hour_count=len(
            {row.source.path_hour_utc for row in affected}
        ),
        affected_utc_day_count=len(
            {row.source.path_hour_utc[:10] for row in affected}
        ),
        taxonomy_group_counts_by_class=group_counts,
        taxonomy_occurrence_counts_by_class=occurrence_counts,
        repeat_relationship_counts=relationships,
        unclassifiable_group_count=unclassifiable,
        taxonomy_conservation_passed=conservation,
        retention_caps_exceeded=False,
        duplicate_rows=tuple(
            sorted(
                duplicate_rows,
                key=lambda row: _raw_observation_sort(
                    RawObservationLocator(**row["raw_observation_locator"])
                ),
            )
        ),
        block_rows=tuple(
            sorted(
                block_rows,
                key=lambda row: (
                    int(row["block_number"]),
                    bytes.fromhex(str(row["block_replay_group_id"])),
                ),
            )
        ),
        replay_proofs=tuple(
            sorted(
                replay_rows,
                key=lambda row: bytes.fromhex(
                    str(row["exact_block_replay_proof_id"])
                ),
            )
        ),
        pair_proofs=tuple(
            sorted(
                pair_rows,
                key=lambda row: bytes.fromhex(
                    str(row["expected_counterparty_pair_proof_id"])
                ),
            )
        ),
        taxonomy_units=tuple(sorted(units, key=unit_sort)),
        schema_rows=tuple(
            sorted(
                schema_rows,
                key=lambda row: (
                    UNIT_TYPE_INDEX[str(row["taxonomy_unit_type"])],
                    _raw_observation_sort(
                        RawObservationLocator(**row["raw_observation_locator"])
                    ),
                ),
            )
        ),
        protocol_member_rows=tuple(
            sorted(
                protocol_member_rows,
                key=lambda row: (
                    bytes.fromhex(str(row["protocol_trade_group_id"])),
                    _raw_observation_sort(
                        RawObservationLocator(**row["raw_observation_locator"])
                    ),
                ),
            )
        ),
    )
