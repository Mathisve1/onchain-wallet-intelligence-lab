from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Mapping, Sequence

from .identity import (
    BlockObservation,
    Observation,
    RawBlockLocator,
    canonical_sha256,
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


@dataclass(frozen=True, slots=True)
class BlockDecision:
    group_id: str
    block_number: int
    members: tuple[BlockObservation, ...]
    primary_taxon: Taxon
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


def _id(domain: str, value: object) -> str:
    return canonical_sha256(["R11A_GROUP_ID_V1", domain, value])


def _proof_id(domain: str, value: object) -> str:
    return canonical_sha256(["R11A_PROOF_ID_V1", domain, value])


def _block_group_id(number: int) -> str:
    return _id("BLOCK_NUMBER_GROUP", [number])


def _weak_group_id(key: tuple[str, tuple[str, str]]) -> str:
    return _id("WEAK_KEY_GROUP", [key[0], list(key[1])])


def _protocol_group_id(locator: RawBlockLocator, identity: tuple[str, str, int]) -> str:
    return _id("PROTOCOL_TRADE_GROUP_PER_RAW_BLOCK", [locator.as_mapping(), list(identity)])


def _wallet_group_id(identity: tuple[str, str, str, int]) -> str:
    return _id("WALLET_FILL_GROUP", list(identity))


def _unit_id(unit_type: str, value: object) -> str:
    return canonical_sha256(["R11A_TAXONOMY_UNIT_ID_V1", unit_type, value])


def classify_blocks(
    blocks: Sequence[BlockObservation],
) -> tuple[tuple[BlockDecision, ...], dict[RawBlockLocator, BlockDecision]]:
    grouped: dict[int, list[BlockObservation]] = defaultdict(list)
    for block in blocks:
        grouped[block.block_number].append(block)
    decisions: list[BlockDecision] = []
    locator_index: dict[RawBlockLocator, BlockDecision] = {}
    for number in sorted(grouped):
        members = tuple(sorted(grouped[number], key=lambda row: row.locator))
        if len(members) < 2:
            continue
        conflicts: list[str] = []
        if len({row.block_time_exact for row in members}) != 1:
            conflicts.append("exact_raw_block_time")
        if len({row.ordered_event_count for row in members}) != 1:
            conflicts.append("ordered_event_count")
        if len({row.ordered_event_fingerprint_sha256 for row in members}) != 1:
            conflicts.append("ordered_event_fingerprint_sha256")
        group_id = _block_group_id(number)
        proof_id: str | None = None
        if conflicts:
            taxon = Taxon.CONFLICTING_BLOCK_REPLAY
        elif len({row.source.object_key for row in members}) >= 2:
            taxon = Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS
            proof_id = _proof_id(
                "EXACT_BLOCK_REPLAY_PROOF",
                [group_id, number, [row.locator.as_mapping() for row in members], list(members[0].equality_invariants)],
            )
        else:
            taxon = Taxon.UNCLASSIFIABLE
        decision = BlockDecision(group_id, number, members, taxon, tuple(conflicts), proof_id)
        decisions.append(decision)
        for member in members:
            if member.locator in locator_index:
                raise R11ADiagnosticError("block locator appears in multiple groups")
            locator_index[member.locator] = decision
    return tuple(decisions), locator_index


def _pair_proof(rows: Sequence[Observation]) -> PairProof | None:
    ordered = tuple(sorted(rows, key=lambda row: row.locator))
    if len(ordered) != 2:
        return None
    first, second = ordered
    if first.protocol_trade_identity is None or first.protocol_trade_identity != second.protocol_trade_identity:
        return None
    if first.locator.block_locator != second.locator.block_locator:
        return None
    wallets = {first.canonical_lowercase_wallet_address, second.canonical_lowercase_wallet_address}
    if None in wallets or len(wallets) != 2 or {first.side_exact, second.side_exact} != {"A", "B"}:
        return None
    if abs(first.locator.event_ordinal_zero_based - second.locator.event_ordinal_zero_based) != 1:
        return None
    group_id = _protocol_group_id(first.locator.block_locator, first.protocol_trade_identity)
    return PairProof(
        _proof_id("EXPECTED_COUNTERPARTY_PAIR_PROOF", [group_id, [row.locator.as_mapping() for row in ordered]]),
        group_id,
        first.locator.block_locator,
        first.protocol_trade_identity,
        (first, second),
    )


def _classify_repeat(
    first: Observation,
    current: Observation,
    group: Sequence[Observation],
    block_index: Mapping[RawBlockLocator, BlockDecision],
) -> tuple[Taxon, tuple[Taxon, ...], str | None]:
    if current.tid_validation_status != "VALID_UINT50":
        return Taxon.TID_SCHEMA_VIOLATION, (), None
    if current.wallet_validation_status != "VALID_EXACT_LOWERCASE_0X40HEX" or current.coin_validation_status != "VALID_EXACT_RAW_NONEMPTY_STRING":
        return Taxon.UNCLASSIFIABLE, (), None
    protocol_rows = [
        row for row in group
        if row.protocol_trade_identity == current.protocol_trade_identity
        and row.locator.block_locator == current.locator.block_locator
    ]
    pair_support = _pair_proof(protocol_rows) is not None
    same_canonical = [row for row in group if row.wallet_fill_identity == current.wallet_fill_identity]
    if current.wallet_fill_identity is not None and any(
        row.full_event_sha256 != current.full_event_sha256 for row in same_canonical
    ):
        return Taxon.CONFLICTING_USER_FILL, ((Taxon.EXPECTED_COUNTERPARTY_PAIR,) if pair_support else ()), None
    if (
        first.wallet_fill_identity == current.wallet_fill_identity
        and first.locator.block_locator == current.locator.block_locator
        and first.locator.event_ordinal_zero_based != current.locator.event_ordinal_zero_based
        and first.full_event_sha256 == current.full_event_sha256
    ):
        return Taxon.INTRA_BLOCK_REPEAT, (), None
    if first.wallet_fill_identity == current.wallet_fill_identity and first.full_event_sha256 == current.full_event_sha256:
        decision = block_index.get(first.locator.block_locator)
        if (
            decision is not None
            and decision.primary_taxon is Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS
            and decision.proof_id is not None
            and current.locator.block_locator in {row.locator for row in decision.members}
        ):
            support = [Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS]
            if pair_support:
                support.insert(0, Taxon.EXPECTED_COUNTERPARTY_PAIR)
            return Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY, tuple(support), decision.proof_id
    protocol_keys = {row.protocol_trade_identity for row in group}
    if None not in protocol_keys and len(protocol_keys) >= 2:
        return Taxon.TID_SCOPE_FALSE_POSITIVE, ((Taxon.EXPECTED_COUNTERPARTY_PAIR,) if pair_support else ()), None
    return Taxon.UNCLASSIFIABLE, (), None


def _zero_taxa() -> dict[str, int]:
    return {item: 0 for item in TAXON_ORDER}


def _relationships() -> dict[str, int]:
    return {
        "intra_object": 0, "inter_object": 0,
        "intra_block": 0, "inter_block": 0,
        "same_path_hour": 0, "cross_path_hour": 0,
        "same_utc_day": 0, "cross_utc_day": 0,
        "adjacent_hour_boundary": 0, "non_adjacent_hour_boundary": 0,
        "exact_identical_payload": 0, "conflicting_payload": 0,
    }


def classify(
    blocks: Iterable[BlockObservation],
    *,
    limits: R11ALimits = DEFAULT_LIMITS,
) -> DiagnosticReport:
    limits.validate()
    ordered_blocks = tuple(sorted(blocks, key=lambda row: row.locator))
    if len({row.locator for row in ordered_blocks}) != len(ordered_blocks):
        raise R11ADiagnosticError("duplicate raw block locator")
    observations = flatten_observations(ordered_blocks)
    block_decisions, block_index = classify_blocks(ordered_blocks)
    legacy: dict[tuple[str, tuple[str, str]], list[Observation]] = defaultdict(list)
    for row in observations:
        if row.legacy_weak_key is not None:
            legacy[row.legacy_weak_key].append(row)
    repeat_groups = {
        key: tuple(sorted(rows, key=lambda row: row.locator))
        for key, rows in legacy.items() if len(rows) > 1
    }
    retention_caps_exceeded = (
        len(repeat_groups) > limits.maximum_repeated_legacy_key_groups_retained
        or sum(len(rows) for rows in repeat_groups.values()) > limits.maximum_repeated_observations_retained
        or len(block_decisions) > limits.maximum_repeated_block_groups_retained
    )
    group_counts = _zero_taxa()
    occurrence_counts = _zero_taxa()
    relationships = _relationships()
    duplicate_rows: list[Mapping[str, object]] = []
    units: list[Mapping[str, object]] = []
    pair_map: dict[str, PairProof] = {}
    repeat_occurrences = 0
    valid_repeat = 0
    affected: list[Observation] = []

    for key in sorted(repeat_groups, key=lambda item: canonical_sha256([item[0], list(item[1])])):
        group = repeat_groups[key]
        first = group[0]
        affected.extend(group)
        seen_taxa: set[Taxon] = set()
        for index, row in enumerate(group):
            taxon: Taxon | None = None
            supporting: tuple[Taxon, ...] = ()
            replay_id: str | None = None
            if index > 0:
                repeat_occurrences += 1
                taxon, supporting, replay_id = _classify_repeat(first, row, group, block_index)
                if row.tid_validation_status == "VALID_UINT50":
                    valid_repeat += 1
                occurrence_counts[taxon.value] += 1
                seen_taxa.add(taxon)
                unit_type = "RAW_TID_SCHEMA_VIOLATION_OBSERVATION" if taxon is Taxon.TID_SCHEMA_VIOLATION else "LEGACY_REPEAT_OCCURRENCE"
                units.append({
                    "record_type": "TAXONOMY_UNIT",
                    "taxonomy_unit_type": unit_type,
                    "taxonomy_unit_id": _unit_id(unit_type, row.locator.as_mapping()),
                    "primary_taxon": taxon.value,
                    "supporting_taxa": [item.value for item in supporting],
                    "member_count": 1,
                    "member_raw_observation_locators": [row.locator.as_mapping()],
                    "member_raw_block_locators": [row.locator.block_locator.as_mapping()],
                })
                same_object = (first.source.object_key, first.source.compressed_sha256) == (row.source.object_key, row.source.compressed_sha256)
                relationships["intra_object" if same_object else "inter_object"] += 1
                same_block = first.locator.block_locator == row.locator.block_locator
                relationships["intra_block" if same_block else "inter_block"] += 1
                same_hour = first.source.path_hour_utc == row.source.path_hour_utc
                relationships["same_path_hour" if same_hour else "cross_path_hour"] += 1
                same_day = first.source.path_hour_utc[:10] == row.source.path_hour_utc[:10]
                relationships["same_utc_day" if same_day else "cross_utc_day"] += 1
                if not same_hour:
                    hour_distance = abs(first.source.object_ordinal_zero_based - row.source.object_ordinal_zero_based)
                    relationships["adjacent_hour_boundary" if hour_distance == 1 else "non_adjacent_hour_boundary"] += 1
                relationships["exact_identical_payload" if first.full_event_sha256 == row.full_event_sha256 else "conflicting_payload"] += 1
            if row.protocol_trade_identity is not None:
                proof = _pair_proof([
                    item for item in observations
                    if item.locator.block_locator == row.locator.block_locator
                    and item.protocol_trade_identity == row.protocol_trade_identity
                ])
                if proof is not None:
                    pair_map[proof.proof_id] = proof
            duplicate_rows.append({
                "record_type": "LEGACY_REPEAT_OBSERVATION",
                "primary_taxon": taxon.value if taxon is not None else None,
                "supporting_taxa": [item.value for item in supporting],
                "weak_key_group_id": _weak_group_id(key),
                "legacy_weak_key": [key[0], list(key[1])],
                "raw_observation_locator": row.locator.as_mapping(),
                "raw_block_locator": row.locator.block_locator.as_mapping(),
                "source_object_key": row.source.object_key,
                "source_path_hour_utc": row.source.path_hour_utc,
                "block_number": row.block_number,
                "block_time_exact": row.block_time_exact,
                "local_time_exact": row.local_time_exact,
                "protocol_trade_identity": list(row.protocol_trade_identity) if row.protocol_trade_identity else None,
                "wallet_fill_identity": list(row.wallet_fill_identity) if row.wallet_fill_identity else None,
                "selected_fill_sha256": row.selected_fill_sha256,
                "full_fill_sha256": row.full_fill_sha256,
                "full_event_sha256": row.full_event_sha256,
                "first_versus_occurrence_field_diffmask": first_diffmask(first, row),
                "exact_block_replay_proof_id": replay_id,
                "deduplication_authorized": False,
            })
        for taxon in seen_taxa:
            group_counts[taxon.value] += 1

    block_rows: list[Mapping[str, object]] = []
    replay_rows: list[Mapping[str, object]] = []
    for decision in block_decisions:
        group_counts[decision.primary_taxon.value] += 1
        occurrence_counts[decision.primary_taxon.value] += len(decision.members)
        members = [{
            "raw_block_locator": row.locator.as_mapping(),
            "source_object_key": row.source.object_key,
            "exact_raw_block_time": row.block_time_exact,
            "ordered_event_count": row.ordered_event_count,
            "ordered_event_fingerprint_sha256": row.ordered_event_fingerprint_sha256,
            "raw_record_sha256": row.raw_record_sha256,
        } for row in decision.members]
        block_rows.append({
            "record_type": "BLOCK_NUMBER_GROUP",
            "block_replay_group_id": decision.group_id,
            "block_number": decision.block_number,
            "member_count": len(members),
            "members": members,
            "primary_taxon": decision.primary_taxon.value,
            "conflicting_invariant_fields": list(decision.conflicting_fields),
            "exact_block_replay_proof_id": decision.proof_id,
        })
        units.append({
            "record_type": "TAXONOMY_UNIT",
            "taxonomy_unit_type": "ARCHIVE_BLOCK_NUMBER_GROUP",
            "taxonomy_unit_id": _unit_id("ARCHIVE_BLOCK_NUMBER_GROUP", decision.group_id),
            "primary_taxon": decision.primary_taxon.value,
            "supporting_taxa": [],
            "member_count": len(members),
            "member_raw_block_locators": [row.locator.as_mapping() for row in decision.members],
        })
        if decision.proof_id is not None:
            replay_rows.append({
                "record_type": "EXACT_BLOCK_REPLAY_PROOF",
                "exact_block_replay_proof_id": decision.proof_id,
                "block_replay_group_id": decision.group_id,
                "block_number": decision.block_number,
                "member_count": len(members),
                "member_evidence": members,
                "classification": Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS.value,
            })

    pair_rows: list[Mapping[str, object]] = []
    for proof in sorted(pair_map.values(), key=lambda row: row.proof_id):
        group_counts[Taxon.EXPECTED_COUNTERPARTY_PAIR.value] += 1
        occurrence_counts[Taxon.EXPECTED_COUNTERPARTY_PAIR.value] += 2
        pair_rows.append({
            "record_type": "EXPECTED_COUNTERPARTY_PAIR_PROOF",
            "expected_counterparty_pair_proof_id": proof.proof_id,
            "protocol_trade_group_id": proof.group_id,
            "raw_block_locator": proof.block_locator.as_mapping(),
            "protocol_trade_identity": list(proof.identity),
            "member_count": 2,
            "members": [row.locator.as_mapping() for row in proof.members],
            "classification": Taxon.EXPECTED_COUNTERPARTY_PAIR.value,
        })

    schema_rows: list[Mapping[str, object]] = []
    for row in observations:
        variants = []
        if row.tid_validation_status != "VALID_UINT50":
            variants.append(("RAW_TID_SCHEMA_VIOLATION_OBSERVATION", Taxon.TID_SCHEMA_VIOLATION, row.tid_schema_violation_reason))
        if row.coin_validation_status != "VALID_EXACT_RAW_NONEMPTY_STRING":
            variants.append(("RAW_COIN_SCHEMA_VIOLATION_OBSERVATION", Taxon.UNCLASSIFIABLE, row.coin_schema_violation_reason))
        if row.wallet_validation_status != "VALID_EXACT_LOWERCASE_0X40HEX":
            variants.append(("RAW_WALLET_SCHEMA_VIOLATION_OBSERVATION", Taxon.UNCLASSIFIABLE, row.wallet_schema_violation_reason))
        for unit_type, taxon, reason in variants:
            unit_id = _unit_id(unit_type, row.locator.as_mapping())
            schema_rows.append({
                "record_type": "MINIMAL_SCHEMA_VIOLATION_EVIDENCE",
                "taxonomy_unit_type": unit_type,
                "taxonomy_unit_id": unit_id,
                "primary_taxon": taxon.value,
                "raw_observation_locator": row.locator.as_mapping(),
                "raw_block_locator": row.locator.block_locator.as_mapping(),
                "reason": reason,
                "full_lossless_payload_retained": False,
            })
            units.append({
                "record_type": "TAXONOMY_UNIT",
                "taxonomy_unit_type": unit_type,
                "taxonomy_unit_id": unit_id,
                "primary_taxon": taxon.value,
                "supporting_taxa": [],
                "member_count": 1,
                "member_raw_observation_locators": [row.locator.as_mapping()],
                "member_raw_block_locators": [row.locator.block_locator.as_mapping()],
            })
            group_counts[taxon.value] += 1
            occurrence_counts[taxon.value] += 1

    invalid_repeat = repeat_occurrences - valid_repeat
    conservation = (
        repeat_occurrences == valid_repeat + invalid_repeat
        and relationships["intra_object"] + relationships["inter_object"] == repeat_occurrences
        and relationships["intra_block"] + relationships["inter_block"] == repeat_occurrences
        and relationships["same_path_hour"] + relationships["cross_path_hour"] == repeat_occurrences
        and relationships["same_utc_day"] + relationships["cross_utc_day"] == repeat_occurrences
        and relationships["exact_identical_payload"] + relationships["conflicting_payload"] == repeat_occurrences
    )
    unclassifiable = sum(row.get("primary_taxon") == Taxon.UNCLASSIFIABLE.value for row in duplicate_rows)
    unclassifiable += sum(item.primary_taxon is Taxon.UNCLASSIFIABLE for item in block_decisions)
    unclassifiable += sum(row["primary_taxon"] == Taxon.UNCLASSIFIABLE.value for row in schema_rows)
    if retention_caps_exceeded:
        terminal = TerminalClass.ARTIFACT_CAP_EXCEEDED
        claim = "NOT_PROVEN"
        duplicate_rows = []
        block_rows = []
        replay_rows = []
        pair_rows = []
        units = []
        schema_rows = []
    elif conservation and unclassifiable == 0:
        terminal = TerminalClass.ROOT_CAUSE_TAXONOMY_COMPLETE
        claim = "PROVEN_COMPLETE_TAXONOMY_ONLY"
    else:
        terminal = TerminalClass.DIAGNOSTIC_INCOMPLETE
        claim = "NOT_PROVEN"
    return DiagnosticReport(
        terminal_class=terminal,
        root_cause_claim_status=claim,
        raw_block_observation_count=len(ordered_blocks),
        raw_event_observation_count=len(observations),
        repeat_occurrence_count_sum_n_minus_one=repeat_occurrences,
        valid_tid_repeat_occurrence_count_sum_n_minus_one=valid_repeat,
        invalid_tid_repeat_occurrence_count=invalid_repeat,
        affected_weak_key_group_count=len(repeat_groups),
        affected_wallet_count=len({row.canonical_lowercase_wallet_address for row in affected if row.canonical_lowercase_wallet_address}),
        affected_tid_count=len({row.legacy_weak_key[1] for row in affected if row.legacy_weak_key}),
        affected_canonical_key_count=len({row.wallet_fill_identity for row in affected if row.wallet_fill_identity}),
        affected_block_count=len({row.block_number for row in affected}),
        affected_object_count=len({(row.source.object_key, row.source.compressed_sha256) for row in affected}),
        affected_path_hour_count=len({row.source.path_hour_utc for row in affected}),
        affected_utc_day_count=len({row.source.path_hour_utc[:10] for row in affected}),
        taxonomy_group_counts_by_class=group_counts,
        taxonomy_occurrence_counts_by_class=occurrence_counts,
        repeat_relationship_counts=relationships,
        unclassifiable_group_count=unclassifiable,
        taxonomy_conservation_passed=conservation and not retention_caps_exceeded,
        retention_caps_exceeded=retention_caps_exceeded,
        duplicate_rows=tuple(sorted(duplicate_rows, key=lambda row: canonical_sha256(row["raw_observation_locator"]))),
        block_rows=tuple(sorted(block_rows, key=lambda row: (row["block_number"], row["block_replay_group_id"]))),
        replay_proofs=tuple(sorted(replay_rows, key=lambda row: row["exact_block_replay_proof_id"])),
        pair_proofs=tuple(sorted(pair_rows, key=lambda row: row["expected_counterparty_pair_proof_id"])),
        taxonomy_units=tuple(sorted(units, key=lambda row: (row["taxonomy_unit_type"], row["taxonomy_unit_id"]))),
        schema_rows=tuple(sorted(schema_rows, key=lambda row: (row["taxonomy_unit_type"], canonical_sha256(row["raw_observation_locator"])))),
    )
