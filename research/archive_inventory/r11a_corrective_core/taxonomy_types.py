from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from .canonical import canonical_sha256
from .model import BlockObservation, Observation, RawBlockLocator


class TaxonomyError(ValueError):
    pass


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
    COMPLETE = "R11A_ROOT_CAUSE_TAXONOMY_COMPLETE"
    CAP = "R11A_DIAGNOSTIC_ARTIFACT_CAP_EXCEEDED"
    INCOMPLETE = "R11A_DIAGNOSTIC_INCOMPLETE"


UNIT_TYPES = (
    "LEGACY_REPEAT_OCCURRENCE",
    "ARCHIVE_BLOCK_NUMBER_GROUP",
    "PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE",
    "RAW_TID_SCHEMA_VIOLATION_OBSERVATION",
    "RAW_COIN_SCHEMA_VIOLATION_OBSERVATION",
    "RAW_WALLET_SCHEMA_VIOLATION_OBSERVATION",
)


@dataclass(frozen=True, slots=True)
class BlockDecision:
    group_id: str
    block_number: int
    members: tuple[BlockObservation, ...]
    primary_taxon: Taxon | None
    proof_id: str | None
    conflicting_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PairDecision:
    group_id: str
    members: tuple[Observation, ...]
    primary_taxon: Taxon
    proof_id: str | None


@dataclass(frozen=True, slots=True)
class ScopeEvidence:
    selected_object_count: int
    complete_object_count: int
    complete_utc_day_count: int
    expected_utc_day_count: int
    all_object_two_pass_commitments_match: bool
    all_512_reducer_rows_complete: bool
    all_resource_caps_respected: bool
    scientific_output_logical_status: str

    @property
    def exact_scope_complete(self) -> bool:
        return (
            self.selected_object_count == 72
            and self.complete_object_count == 72
            and self.complete_utc_day_count == self.expected_utc_day_count == 3
            and self.all_object_two_pass_commitments_match
            and self.all_512_reducer_rows_complete
        )


@dataclass(frozen=True, slots=True)
class TaxonomyReport:
    terminal_class: TerminalClass
    root_cause_claim_status: str
    raw_block_observation_count: int
    raw_event_observation_count: int
    repeat_occurrence_count: int
    valid_tid_repeat_occurrence_count: int
    invalid_tid_repeat_occurrence_count: int
    unique_block_number_count: int
    singleton_block_number_count: int
    repeated_block_group_count: int
    singleton_block_observation_count: int
    repeated_block_observation_count: int
    valid_tid_observation_count: int
    tid_schema_violation_observation_count: int
    valid_coin_observation_count: int
    coin_schema_violation_observation_count: int
    valid_wallet_observation_count: int
    wallet_schema_violation_observation_count: int
    taxonomy_group_counts_by_class: Mapping[str, int]
    taxonomy_occurrence_counts_by_class: Mapping[str, int]
    unclassifiable_by_unit_universe: Mapping[str, Mapping[str, int]]
    conservation_equations: Mapping[str, bool]
    all_proof_references_resolve: bool
    taxonomy_conservation_passed: bool
    duplicate_rows: tuple[Mapping[str, object], ...]
    block_rows: tuple[Mapping[str, object], ...]
    replay_proofs: tuple[Mapping[str, object], ...]
    pair_proofs: tuple[Mapping[str, object], ...]
    taxonomy_units: tuple[Mapping[str, object], ...]
    schema_rows: tuple[Mapping[str, object], ...]
    protocol_member_rows: tuple[Mapping[str, object], ...]


def _id(domain: str, value: object) -> str:
    return canonical_sha256(["R11A_CORRECTIVE_V2", domain, value])


def _block_group_id(number: int) -> str:
    return _id("BLOCK_GROUP", number)


def _protocol_group_id(locator: RawBlockLocator, identity: tuple[str, str, int]) -> str:
    return _id("PROTOCOL_GROUP", [locator.as_mapping(), list(identity)])


def _wallet_group_id(identity: tuple[str, str, str, int]) -> str:
    return _id("WALLET_GROUP", list(identity))


def _weak_group_id(key: tuple[str, tuple[str, str]]) -> str:
    return _id("WEAK_GROUP", [key[0], list(key[1])])


def _unit_id(unit_type: str, value: object) -> str:
    return _id("TAXONOMY_UNIT", [unit_type, value])


def _proof_id(kind: str, value: object) -> str:
    return _id("PROOF", [kind, value])
