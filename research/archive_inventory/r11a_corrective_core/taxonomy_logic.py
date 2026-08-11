from __future__ import annotations

from collections import Counter, defaultdict
from typing import Mapping, Sequence

from .canonical import ensure_unique_ids, typed_bytes
from .model import BlockObservation, Observation, RawBlockLocator, RawObservationLocator
from .taxonomy_types import (
    BlockDecision,
    PairDecision,
    Taxon,
    TaxonomyError,
    _block_group_id,
    _proof_id,
    _protocol_group_id,
)


def _classify_blocks(blocks: Sequence[BlockObservation]) -> tuple[tuple[BlockDecision, ...], dict[RawBlockLocator, BlockDecision]]:
    by_number: dict[int, list[BlockObservation]] = defaultdict(list)
    for block in blocks:
        by_number[block.block_number].append(block)
    decisions: list[BlockDecision] = []
    index: dict[RawBlockLocator, BlockDecision] = {}
    for number in sorted(by_number):
        members = tuple(sorted(by_number[number], key=lambda row: row.locator))
        group_id = _block_group_id(number)
        primary: Taxon | None = None
        proof: str | None = None
        conflicts: tuple[str, ...] = ()
        if len(members) > 1:
            invariant_sets = {
                "exact_raw_block_time": {row.block_time_exact for row in members},
                "ordered_event_count": {row.ordered_event_count for row in members},
                "ordered_event_fingerprint": {row.ordered_event_fingerprint_sha256 for row in members},
            }
            conflicts = tuple(name for name, values in invariant_sets.items() if len(values) > 1)
            if conflicts:
                primary = Taxon.CONFLICTING_BLOCK_REPLAY
            elif len({row.source.object_key for row in members}) >= 2:
                primary = Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS
                proof = _proof_id("EXACT_BLOCK_REPLAY", [group_id, [row.locator.as_mapping() for row in members]])
            else:
                primary = Taxon.UNCLASSIFIABLE
        decision = BlockDecision(group_id, number, members, primary, proof, conflicts)
        decisions.append(decision)
        for member in members:
            if member.locator in index:
                raise TaxonomyError("raw block locator resolved more than once")
            index[member.locator] = decision
    return tuple(decisions), index


def _pair_predicate(rows: Sequence[Observation]) -> bool:
    if len(rows) != 2:
        return False
    first, second = sorted(rows, key=lambda row: row.locator)
    if first.locator.block_locator != second.locator.block_locator:
        return False
    if first.protocol_trade_identity is None or first.protocol_trade_identity != second.protocol_trade_identity:
        return False
    if first.locator.event_ordinal_zero_based + 1 != second.locator.event_ordinal_zero_based:
        return False
    wallets = {first.canonical_lowercase_wallet_address, second.canonical_lowercase_wallet_address}
    if None in wallets or len(wallets) != 2:
        return False
    if {first.side_exact, second.side_exact} != {"A", "B"}:
        return False
    return True


def _classify_protocol_groups(observations: Sequence[Observation]) -> tuple[dict[tuple[RawBlockLocator, tuple[str, str, int]], PairDecision], tuple[Mapping[str, object], ...], tuple[Mapping[str, object], ...]]:
    groups: dict[tuple[RawBlockLocator, tuple[str, str, int]], list[Observation]] = defaultdict(list)
    for row in observations:
        if row.protocol_trade_identity is not None:
            groups[(row.locator.block_locator, row.protocol_trade_identity)].append(row)
    decisions: dict[tuple[RawBlockLocator, tuple[str, str, int]], PairDecision] = {}
    proofs: list[Mapping[str, object]] = []
    member_rows: list[Mapping[str, object]] = []
    for key in sorted(groups, key=lambda item: (item[0], typed_bytes(list(item[1])))):
        rows = tuple(sorted(groups[key], key=lambda row: row.locator))
        group_id = _protocol_group_id(*key)
        if _pair_predicate(rows):
            taxon = Taxon.EXPECTED_COUNTERPARTY_PAIR
            proof_id = _proof_id("EXPECTED_PAIR", [group_id, [row.locator.as_mapping() for row in rows]])
            proofs.append({
                "record_type": "EXPECTED_COUNTERPARTY_PAIR_PROOF",
                "expected_counterparty_pair_proof_id": proof_id,
                "protocol_trade_group_id": group_id,
                "raw_block_locator": key[0].as_mapping(),
                "protocol_trade_identity": list(key[1]),
                "member_count": 2,
                "member_raw_observation_locators": [row.locator.as_mapping() for row in rows],
            })
        else:
            taxon = Taxon.UNCLASSIFIABLE
            proof_id = None
        decisions[key] = PairDecision(group_id, rows, taxon, proof_id)
        for row in rows:
            member_rows.append({
                "record_type": "MINIMAL_PROTOCOL_TRADE_GROUP_MEMBER",
                "protocol_trade_group_id": group_id,
                "raw_observation_locator": row.locator.as_mapping(),
                "raw_block_locator": row.locator.block_locator.as_mapping(),
                "canonical_lowercase_wallet_address": row.canonical_lowercase_wallet_address,
                "protocol_trade_identity": list(key[1]),
                "side_exact": row.side_exact,
                "crossed_exact": row.crossed_exact,
                "full_event_sha256": row.full_event_sha256,
            })
    return decisions, tuple(proofs), tuple(member_rows)


def _same_payload(rows: Sequence[Observation]) -> bool:
    return len({(row.full_fill_sha256, row.full_event_sha256) for row in rows}) == 1


def _wallet_fill_state(observations: Sequence[Observation]) -> tuple[dict[tuple[str, str, str, int], tuple[Observation, ...]], set[tuple[str, str, str, int]], set[tuple[tuple[str, str, str, int], RawBlockLocator]], dict[tuple[str, str, str, int], str]]:
    groups: dict[tuple[str, str, str, int], list[Observation]] = defaultdict(list)
    for row in observations:
        if row.wallet_fill_identity is not None:
            groups[row.wallet_fill_identity].append(row)
    frozen = {key: tuple(sorted(rows, key=lambda row: row.locator)) for key, rows in groups.items()}
    conflicting = {key for key, rows in frozen.items() if not _same_payload(rows)}
    intra: set[tuple[tuple[str, str, str, int], RawBlockLocator]] = set()
    replay_proof_by_wallet: dict[tuple[str, str, str, int], str] = {}
    for key, rows in frozen.items():
        by_block: dict[RawBlockLocator, list[Observation]] = defaultdict(list)
        for row in rows:
            by_block[row.locator.block_locator].append(row)
        for block_locator, members in by_block.items():
            if len(members) > 1 and _same_payload(members):
                intra.add((key, block_locator))
    return frozen, conflicting, intra, replay_proof_by_wallet


def _scope_false_positive_group_is_clean(
    group: Sequence[Observation],
    *,
    wallet_conflicts: set[tuple[str, str, str, int]],
    block_index: Mapping[RawBlockLocator, BlockDecision],
    protocol_decisions: Mapping[tuple[RawBlockLocator, tuple[str, str, int]], PairDecision],
) -> bool:
    if any(
        row.wallet_validation_status != "VALID_EXACT_LOWERCASE_0X40HEX"
        or row.coin_validation_status != "VALID_EXACT_RAW_NONEMPTY_STRING"
        or row.tid_validation_status != "VALID_UINT50"
        or row.protocol_trade_identity is None
        or row.wallet_fill_identity is None
        for row in group
    ):
        return False
    protocol_ids = {row.protocol_trade_identity for row in group}
    if len(protocol_ids) < 2:
        return False
    if any(row.wallet_fill_identity in wallet_conflicts for row in group):
        return False
    for row in group:
        decision = block_index[row.locator.block_locator]
        if decision.primary_taxon in {Taxon.CONFLICTING_BLOCK_REPLAY, Taxon.UNCLASSIFIABLE}:
            return False
        pair = protocol_decisions[(row.locator.block_locator, row.protocol_trade_identity)]
        if len(pair.members) > 1 and pair.primary_taxon is not Taxon.EXPECTED_COUNTERPARTY_PAIR:
            return False
    return True


def _classify_repeat_member(
    row: Observation,
    group: Sequence[Observation],
    *,
    wallet_groups: Mapping[tuple[str, str, str, int], Sequence[Observation]],
    wallet_conflicts: set[tuple[str, str, str, int]],
    intra_groups: set[tuple[tuple[str, str, str, int], RawBlockLocator]],
    block_index: Mapping[RawBlockLocator, BlockDecision],
    protocol_decisions: Mapping[tuple[RawBlockLocator, tuple[str, str, int]], PairDecision],
    clean_scope_false_positive: bool,
) -> tuple[Taxon, tuple[Taxon, ...], str | None, str | None]:
    if row.tid_validation_status != "VALID_UINT50":
        return Taxon.TID_SCHEMA_VIOLATION, (), None, None
    if (
        row.wallet_validation_status != "VALID_EXACT_LOWERCASE_0X40HEX"
        or row.coin_validation_status != "VALID_EXACT_RAW_NONEMPTY_STRING"
        or row.wallet_fill_identity is None
        or row.protocol_trade_identity is None
    ):
        return Taxon.UNCLASSIFIABLE, (), None, None
    pair = protocol_decisions[(row.locator.block_locator, row.protocol_trade_identity)]
    pair_id = pair.proof_id
    support_pair = (Taxon.EXPECTED_COUNTERPARTY_PAIR,) if pair_id else ()
    wallet_key = row.wallet_fill_identity
    wallet_members = tuple(wallet_groups[wallet_key])
    if wallet_key in wallet_conflicts:
        return Taxon.CONFLICTING_USER_FILL, support_pair, None, pair_id
    if (wallet_key, row.locator.block_locator) in intra_groups:
        return Taxon.INTRA_BLOCK_REPEAT, (), None, None
    distinct_blocks = {member.locator.block_locator for member in wallet_members}
    if len(distinct_blocks) >= 2 and _same_payload(wallet_members):
        decisions = {block_index[locator] for locator in distinct_blocks}
        if len(decisions) == 1:
            decision = next(iter(decisions))
            if decision.primary_taxon is Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS and decision.proof_id:
                support = support_pair + (Taxon.EXACT_BLOCK_REPLAY_ACROSS_OBJECTS,)
                return Taxon.EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY, support, decision.proof_id, pair_id
    if clean_scope_false_positive:
        return Taxon.TID_SCOPE_FALSE_POSITIVE, support_pair, None, pair_id
    return Taxon.UNCLASSIFIABLE, (), None, None


def _schema_reason(row: Observation, unit_type: str) -> str:
    if unit_type == "RAW_TID_SCHEMA_VIOLATION_OBSERVATION":
        return row.tid_schema_violation_reason or "TID_SCHEMA_VIOLATION"
    if unit_type == "RAW_COIN_SCHEMA_VIOLATION_OBSERVATION":
        return row.coin_schema_violation_reason or "COIN_SCHEMA_VIOLATION"
    if unit_type == "RAW_WALLET_SCHEMA_VIOLATION_OBSERVATION":
        return row.wallet_schema_violation_reason or "WALLET_SCHEMA_VIOLATION"
    raise TaxonomyError("unknown schema unit type")


def _unit(unit_type: str, unit_id: str, primary: Taxon, members: Sequence[RawObservationLocator], blocks: Sequence[RawBlockLocator], **extra: object) -> dict[str, object]:
    return {
        "record_type": "TAXONOMY_UNIT",
        "taxonomy_unit_type": unit_type,
        "taxonomy_unit_id": unit_id,
        "primary_taxon": primary.value,
        "supporting_taxa": extra.pop("supporting_taxa", []),
        "member_count": len(members) if members else len(blocks),
        "member_raw_observation_locators": [item.as_mapping() for item in members] if members else None,
        "member_raw_block_locators": [item.as_mapping() for item in blocks],
        **extra,
    }


def _validate_foreign_keys(
    *,
    units: Sequence[Mapping[str, object]],
    duplicate_rows: Sequence[Mapping[str, object]],
    block_rows: Sequence[Mapping[str, object]],
    replay_proofs: Sequence[Mapping[str, object]],
    pair_proofs: Sequence[Mapping[str, object]],
    schema_rows: Sequence[Mapping[str, object]],
    protocol_member_rows: Sequence[Mapping[str, object]],
) -> bool:
    ensure_unique_ids(units, "taxonomy_unit_id")
    ensure_unique_ids(replay_proofs, "exact_block_replay_proof_id")
    ensure_unique_ids(pair_proofs, "expected_counterparty_pair_proof_id")
    unit_ids = Counter(str(row["taxonomy_unit_id"]) for row in units)
    block_locators: Counter[bytes] = Counter()
    for group in block_rows:
        for member in group["members"]:  # type: ignore[index]
            block_locators[typed_bytes(member["raw_block_locator"])] += 1  # type: ignore[index]
    replay_ids = Counter(str(row["exact_block_replay_proof_id"]) for row in replay_proofs)
    pair_ids = Counter(str(row["expected_counterparty_pair_proof_id"]) for row in pair_proofs)
    protocol_ids = Counter(str(row["protocol_trade_group_id"]) for row in protocol_member_rows)
    try:
        for row in duplicate_rows:
            unit_id = row.get("taxonomy_unit_id")
            if unit_id is not None and unit_ids[str(unit_id)] != 1:
                return False
            if block_locators[typed_bytes(row["raw_block_locator"])] != 1:
                return False
            replay = row.get("exact_block_replay_proof_id")
            if replay is not None and replay_ids[str(replay)] != 1:
                return False
            pair = row.get("expected_counterparty_pair_proof_id")
            if pair is not None and pair_ids[str(pair)] != 1:
                return False
        for row in schema_rows:
            if unit_ids[str(row["taxonomy_unit_id"])] != 1:
                return False
            if block_locators[typed_bytes(row["raw_block_locator"])] != 1:
                return False
        for row in protocol_member_rows:
            if block_locators[typed_bytes(row["raw_block_locator"])] != 1:
                return False
            if protocol_ids[str(row["protocol_trade_group_id"])] < 1:
                return False
        for unit in units:
            replay = unit.get("exact_block_replay_proof_id")
            if replay is not None and replay_ids[str(replay)] != 1:
                return False
            for pair in unit.get("expected_counterparty_pair_proof_ids", []):  # type: ignore[union-attr]
                if pair_ids[str(pair)] != 1:
                    return False
    except (KeyError, TypeError):
        return False
    return True
