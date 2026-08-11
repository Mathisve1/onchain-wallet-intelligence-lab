from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable, Mapping

from .canonical import typed_bytes
from .model import BlockObservation, Observation, RawBlockLocator, flatten_observations
from .taxonomy_types import (
    ScopeEvidence,
    Taxon,
    TaxonomyError,
    TaxonomyReport,
    TerminalClass,
    UNIT_TYPES,
    _protocol_group_id,
    _unit_id,
    _wallet_group_id,
    _weak_group_id,
)
from .taxonomy_logic import (
    _classify_blocks,
    _classify_protocol_groups,
    _classify_repeat_member,
    _schema_reason,
    _scope_false_positive_group_is_clean,
    _unit,
    _validate_foreign_keys,
    _wallet_fill_state,
)


def classify(blocks: Iterable[BlockObservation], scope: ScopeEvidence) -> TaxonomyReport:
    ordered_blocks = tuple(sorted(blocks, key=lambda row: row.locator))
    if len({row.locator for row in ordered_blocks}) != len(ordered_blocks):
        raise TaxonomyError("duplicate raw block locator")
    observations = flatten_observations(ordered_blocks)
    block_decisions, block_index = _classify_blocks(ordered_blocks)
    protocol_decisions, pair_proofs, protocol_member_rows_all = _classify_protocol_groups(observations)
    wallet_groups, wallet_conflicts, intra_groups, _ = _wallet_fill_state(observations)

    legacy: dict[tuple[str, tuple[str, str]], list[Observation]] = defaultdict(list)
    for row in observations:
        if row.legacy_weak_key is not None:
            legacy[row.legacy_weak_key].append(row)
    repeat_groups = {
        key: tuple(sorted(rows, key=lambda row: row.locator))
        for key, rows in legacy.items()
        if len(rows) > 1
    }

    units: list[Mapping[str, object]] = []
    duplicate_rows: list[Mapping[str, object]] = []
    schema_rows: list[Mapping[str, object]] = []
    group_sets: dict[str, set[object]] = {item.value: set() for item in Taxon}
    occurrence_counts: Counter[str] = Counter({item.value: 0 for item in Taxon})
    repeat_occurrence_count = 0
    valid_repeat_count = 0

    intersecting_protocol_keys: set[tuple[RawBlockLocator, tuple[str, str, int]]] = set()
    for key in sorted(repeat_groups, key=lambda item: typed_bytes([item[0], list(item[1])])):
        group = repeat_groups[key]
        clean_scope = _scope_false_positive_group_is_clean(
            group,
            wallet_conflicts=wallet_conflicts,
            block_index=block_index,
            protocol_decisions=protocol_decisions,
        )
        weak_group_id = _weak_group_id(key)
        for member in group:
            if member.protocol_trade_identity is not None:
                intersecting_protocol_keys.add((member.locator.block_locator, member.protocol_trade_identity))
        for index, row in enumerate(group):
            primary: Taxon | None = None
            supporting: tuple[Taxon, ...] = ()
            replay_id: str | None = None
            pair_id: str | None = None
            unit_id: str | None = None
            if index > 0:
                repeat_occurrence_count += 1
                primary, supporting, replay_id, pair_id = _classify_repeat_member(
                    row,
                    group,
                    wallet_groups=wallet_groups,
                    wallet_conflicts=wallet_conflicts,
                    intra_groups=intra_groups,
                    block_index=block_index,
                    protocol_decisions=protocol_decisions,
                    clean_scope_false_positive=clean_scope,
                )
                if row.tid_validation_status == "VALID_UINT50":
                    valid_repeat_count += 1
                    unit_id = _unit_id("LEGACY_REPEAT_OCCURRENCE", row.locator.as_mapping())
                    units.append(_unit(
                        "LEGACY_REPEAT_OCCURRENCE",
                        unit_id,
                        primary,
                        [row.locator],
                        [row.locator.block_locator],
                        supporting_taxa=[item.value for item in supporting],
                        weak_key_group_id=weak_group_id,
                        block_replay_group_id=block_index[row.locator.block_locator].group_id,
                        protocol_trade_group_id=(
                            _protocol_group_id(row.locator.block_locator, row.protocol_trade_identity)
                            if row.protocol_trade_identity is not None else None
                        ),
                        wallet_fill_group_id=(
                            _wallet_group_id(row.wallet_fill_identity)
                            if row.wallet_fill_identity is not None else None
                        ),
                        exact_block_replay_proof_id=replay_id,
                        expected_counterparty_pair_proof_ids=[pair_id] if pair_id else [],
                    ))
                    occurrence_counts[primary.value] += 1
                    if primary is Taxon.TID_SCOPE_FALSE_POSITIVE:
                        group_sets[primary.value].add(weak_group_id)
                    elif primary in {Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY, Taxon.CONFLICTING_USER_FILL}:
                        group_sets[primary.value].add(_wallet_group_id(row.wallet_fill_identity))  # type: ignore[arg-type]
                    elif primary is Taxon.INTRA_BLOCK_REPEAT:
                        group_sets[primary.value].add((_wallet_group_id(row.wallet_fill_identity), row.locator.block_locator))  # type: ignore[arg-type]
                    else:
                        group_sets[primary.value].add(unit_id)
            duplicate_rows.append({
                "record_type": "LEGACY_REPEAT_OBSERVATION",
                "raw_observation_locator": row.locator.as_mapping(),
                "raw_block_locator": row.locator.block_locator.as_mapping(),
                "source_object_key": row.source.object_key,
                "weak_key_group_id": weak_group_id,
                "legacy_weak_key": [key[0], list(key[1])],
                "group_first": index == 0,
                "primary_taxon": primary.value if primary is not None else None,
                "supporting_taxa": [item.value for item in supporting],
                "taxonomy_unit_id": unit_id,
                "exact_block_replay_proof_id": replay_id,
                "expected_counterparty_pair_proof_id": pair_id,
                "protocol_trade_identity": list(row.protocol_trade_identity) if row.protocol_trade_identity else None,
                "wallet_fill_identity": list(row.wallet_fill_identity) if row.wallet_fill_identity else None,
                "full_fill_sha256": row.full_fill_sha256,
                "full_event_sha256": row.full_event_sha256,
                "deduplication_authorized": False,
            })

    block_rows: list[Mapping[str, object]] = []
    replay_proofs: list[Mapping[str, object]] = []
    for decision in block_decisions:
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
            "primary_taxon": decision.primary_taxon.value if decision.primary_taxon else None,
            "conflicting_invariant_fields": list(decision.conflicting_fields),
            "exact_block_replay_proof_id": decision.proof_id,
        })
        if len(decision.members) > 1:
            if decision.primary_taxon is None:
                raise TaxonomyError("repeated block decision lacks a primary taxon")
            unit_id = _unit_id("ARCHIVE_BLOCK_NUMBER_GROUP", decision.group_id)
            units.append(_unit(
                "ARCHIVE_BLOCK_NUMBER_GROUP", unit_id, decision.primary_taxon, [],
                [row.locator for row in decision.members],
                supporting_taxa=[], block_replay_group_id=decision.group_id,
                exact_block_replay_proof_id=decision.proof_id,
                expected_counterparty_pair_proof_ids=[],
            ))
            group_sets[decision.primary_taxon.value].add(decision.group_id)
            occurrence_counts[decision.primary_taxon.value] += len(decision.members)
        if decision.proof_id:
            replay_proofs.append({
                "record_type": "EXACT_BLOCK_REPLAY_PROOF",
                "exact_block_replay_proof_id": decision.proof_id,
                "block_replay_group_id": decision.group_id,
                "block_number": decision.block_number,
                "member_raw_block_locators": [row.locator.as_mapping() for row in decision.members],
                "exact_raw_block_time": decision.members[0].block_time_exact,
                "ordered_event_count": decision.members[0].ordered_event_count,
                "ordered_event_fingerprint_sha256": decision.members[0].ordered_event_fingerprint_sha256,
            })

    retained_pair_proofs: list[Mapping[str, object]] = []
    retained_protocol_members: list[Mapping[str, object]] = []
    protocol_members_by_group: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in protocol_member_rows_all:
        protocol_members_by_group[str(row["protocol_trade_group_id"])].append(row)
    proofs_by_group = {str(row["protocol_trade_group_id"]): row for row in pair_proofs}
    for key in sorted(intersecting_protocol_keys, key=lambda item: (item[0], typed_bytes(list(item[1])))):
        decision = protocol_decisions[key]
        unit_id = _unit_id("PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE", decision.group_id)
        units.append(_unit(
            "PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE",
            unit_id,
            decision.primary_taxon,
            [row.locator for row in decision.members],
            [key[0]],
            supporting_taxa=[],
            protocol_trade_group_id=decision.group_id,
            block_replay_group_id=block_index[key[0]].group_id,
            exact_block_replay_proof_id=None,
            expected_counterparty_pair_proof_ids=[decision.proof_id] if decision.proof_id else [],
        ))
        group_sets[decision.primary_taxon.value].add(decision.group_id)
        occurrence_counts[decision.primary_taxon.value] += len(decision.members)
        retained_protocol_members.extend(protocol_members_by_group[decision.group_id])
        if decision.proof_id:
            retained_pair_proofs.append(proofs_by_group[decision.group_id])

    for row in observations:
        variants: list[tuple[str, Taxon, str]] = []
        if row.tid_validation_status != "VALID_UINT50":
            variants.append(("RAW_TID_SCHEMA_VIOLATION_OBSERVATION", Taxon.TID_SCHEMA_VIOLATION, _schema_reason(row, "RAW_TID_SCHEMA_VIOLATION_OBSERVATION")))
        if row.coin_validation_status != "VALID_EXACT_RAW_NONEMPTY_STRING":
            variants.append(("RAW_COIN_SCHEMA_VIOLATION_OBSERVATION", Taxon.UNCLASSIFIABLE, _schema_reason(row, "RAW_COIN_SCHEMA_VIOLATION_OBSERVATION")))
        if row.wallet_validation_status != "VALID_EXACT_LOWERCASE_0X40HEX":
            variants.append(("RAW_WALLET_SCHEMA_VIOLATION_OBSERVATION", Taxon.UNCLASSIFIABLE, _schema_reason(row, "RAW_WALLET_SCHEMA_VIOLATION_OBSERVATION")))
        for unit_type, primary, reason in variants:
            unit_id = _unit_id(unit_type, row.locator.as_mapping())
            units.append(_unit(unit_type, unit_id, primary, [row.locator], [row.locator.block_locator], supporting_taxa=[], exact_block_replay_proof_id=None, expected_counterparty_pair_proof_ids=[]))
            schema_rows.append({
                "record_type": "MINIMAL_SCHEMA_VIOLATION_EVIDENCE",
                "taxonomy_unit_type": unit_type,
                "taxonomy_unit_id": unit_id,
                "primary_taxon": primary.value,
                "raw_observation_locator": row.locator.as_mapping(),
                "raw_block_locator": row.locator.block_locator.as_mapping(),
                "reason": reason,
            })
            group_sets[primary.value].add((unit_type, row.locator))
            occurrence_counts[primary.value] += 1

    units.sort(key=lambda row: (UNIT_TYPES.index(str(row["taxonomy_unit_type"])), str(row["taxonomy_unit_id"])))
    duplicate_rows.sort(key=lambda row: typed_bytes(row["raw_observation_locator"]))
    block_rows.sort(key=lambda row: (int(row["block_number"]), str(row["block_replay_group_id"])))
    replay_proofs.sort(key=lambda row: str(row["exact_block_replay_proof_id"]))
    retained_pair_proofs.sort(key=lambda row: str(row["expected_counterparty_pair_proof_id"]))
    retained_protocol_members.sort(key=lambda row: (str(row["protocol_trade_group_id"]), typed_bytes(row["raw_observation_locator"])))
    schema_rows.sort(key=lambda row: (UNIT_TYPES.index(str(row["taxonomy_unit_type"])), typed_bytes(row["raw_observation_locator"])))

    all_fks = _validate_foreign_keys(
        units=units,
        duplicate_rows=duplicate_rows,
        block_rows=block_rows,
        replay_proofs=replay_proofs,
        pair_proofs=retained_pair_proofs,
        schema_rows=schema_rows,
        protocol_member_rows=retained_protocol_members,
    )

    repeated_decisions = [row for row in block_decisions if len(row.members) > 1]
    repeated_block_obs = sum(len(row.members) for row in repeated_decisions)
    unique_block_numbers = len(block_decisions)
    singleton_block_numbers = sum(len(row.members) == 1 for row in block_decisions)
    singleton_block_observations = sum(
        len(row.members) for row in block_decisions if len(row.members) == 1
    )
    valid_tid_obs = sum(row.tid_validation_status == "VALID_UINT50" for row in observations)
    tid_invalid_obs = len(observations) - valid_tid_obs
    valid_coin_obs = sum(row.coin_validation_status == "VALID_EXACT_RAW_NONEMPTY_STRING" for row in observations)
    coin_invalid_obs = len(observations) - valid_coin_obs
    valid_wallet_obs = sum(row.wallet_validation_status == "VALID_EXACT_LOWERCASE_0X40HEX" for row in observations)
    wallet_invalid_obs = len(observations) - valid_wallet_obs
    invalid_repeat = repeat_occurrence_count - valid_repeat_count

    universe_units: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for unit in units:
        universe_units[str(unit["taxonomy_unit_type"])].append(unit)
    unclassifiable_by_universe: dict[str, dict[str, int]] = {}
    for unit_type in UNIT_TYPES:
        rows = universe_units.get(unit_type, [])
        bad = [row for row in rows if row["primary_taxon"] == Taxon.UNCLASSIFIABLE.value]
        unclassifiable_by_universe[unit_type] = {
            "group_count": len(bad),
            "occurrence_count": sum(int(row["member_count"]) for row in bad),
        }

    valid_legacy_primary = sum(
        1 for unit in universe_units.get("LEGACY_REPEAT_OCCURRENCE", [])
        if unit["primary_taxon"] in {
            Taxon.TID_SCOPE_FALSE_POSITIVE.value,
            Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY.value,
            Taxon.CONFLICTING_USER_FILL.value,
            Taxon.INTRA_BLOCK_REPEAT.value,
            Taxon.UNCLASSIFIABLE.value,
        }
    )
    equations = {
        "repeat_valid_plus_invalid": repeat_occurrence_count == valid_repeat_count + invalid_repeat,
        "valid_repeat_primary_partition": valid_legacy_primary == valid_repeat_count,
        "block_group_primary_partition": len(repeated_decisions) == len(universe_units.get("ARCHIVE_BLOCK_NUMBER_GROUP", [])),
        "protocol_group_primary_partition": len(intersecting_protocol_keys) == len(universe_units.get("PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE", [])),
        "tid_schema_units": len(universe_units.get("RAW_TID_SCHEMA_VIOLATION_OBSERVATION", [])) == tid_invalid_obs,
        "coin_schema_units": len(universe_units.get("RAW_COIN_SCHEMA_VIOLATION_OBSERVATION", [])) == coin_invalid_obs,
        "wallet_schema_units": len(universe_units.get("RAW_WALLET_SCHEMA_VIOLATION_OBSERVATION", [])) == wallet_invalid_obs,
        "tid_observation_partition": len(observations) == valid_tid_obs + tid_invalid_obs,
        "coin_observation_partition": len(observations) == valid_coin_obs + coin_invalid_obs,
        "wallet_observation_partition": len(observations) == valid_wallet_obs + wallet_invalid_obs,
        "unique_block_partition": unique_block_numbers == singleton_block_numbers + len(repeated_decisions),
        "singleton_block_observation_count": singleton_block_observations == singleton_block_numbers,
        "raw_block_partition": len(ordered_blocks) == singleton_block_observations + repeated_block_obs,
        "duplicate_locator_uniqueness": len({typed_bytes(row["raw_observation_locator"]) for row in duplicate_rows}) == len(duplicate_rows),
        "schema_locator_type_uniqueness": len({(row["taxonomy_unit_type"], typed_bytes(row["raw_observation_locator"])) for row in schema_rows}) == len(schema_rows),
        "proof_foreign_keys": all_fks,
    }
    conservation = all(equations.values())
    no_unclassifiable = all(value["group_count"] == 0 and value["occurrence_count"] == 0 for value in unclassifiable_by_universe.values())
    if (
        scope.scientific_output_logical_status == "COMPLETE"
        and scope.exact_scope_complete
        and scope.all_resource_caps_respected
        and conservation
        and all_fks
        and no_unclassifiable
        and len(ordered_blocks) > 0
        and len(observations) > 0
        and repeat_occurrence_count > 0
    ):
        terminal = TerminalClass.COMPLETE
        claim = "PROVEN_COMPLETE_TAXONOMY_ONLY"
    else:
        terminal = TerminalClass.INCOMPLETE
        claim = "NOT_PROVEN"

    group_counts = {item.value: len(group_sets[item.value]) for item in Taxon}
    occurrence_complete = {item.value: int(occurrence_counts[item.value]) for item in Taxon}
    return TaxonomyReport(
        terminal_class=terminal,
        root_cause_claim_status=claim,
        raw_block_observation_count=len(ordered_blocks),
        raw_event_observation_count=len(observations),
        repeat_occurrence_count=repeat_occurrence_count,
        valid_tid_repeat_occurrence_count=valid_repeat_count,
        invalid_tid_repeat_occurrence_count=invalid_repeat,
        unique_block_number_count=unique_block_numbers,
        singleton_block_number_count=singleton_block_numbers,
        repeated_block_group_count=len(repeated_decisions),
        singleton_block_observation_count=singleton_block_observations,
        repeated_block_observation_count=repeated_block_obs,
        valid_tid_observation_count=valid_tid_obs,
        tid_schema_violation_observation_count=tid_invalid_obs,
        valid_coin_observation_count=valid_coin_obs,
        coin_schema_violation_observation_count=coin_invalid_obs,
        valid_wallet_observation_count=valid_wallet_obs,
        wallet_schema_violation_observation_count=wallet_invalid_obs,
        taxonomy_group_counts_by_class=group_counts,
        taxonomy_occurrence_counts_by_class=occurrence_complete,
        unclassifiable_by_unit_universe=unclassifiable_by_universe,
        conservation_equations=equations,
        all_proof_references_resolve=all_fks,
        taxonomy_conservation_passed=conservation,
        duplicate_rows=tuple(duplicate_rows),
        block_rows=tuple(block_rows),
        replay_proofs=tuple(replay_proofs),
        pair_proofs=tuple(retained_pair_proofs),
        taxonomy_units=tuple(units),
        schema_rows=tuple(schema_rows),
        protocol_member_rows=tuple(retained_protocol_members),
    )
