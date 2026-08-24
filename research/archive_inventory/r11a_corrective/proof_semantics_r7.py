from __future__ import annotations

import dataclasses
import hashlib
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path

from .artifact_schema import DIAGNOSTIC_ID
from .canonical import (
    FrozenObject,
    NumberToken,
    canonical_json_bytes,
    historical_legacy_typed_tid,
    strict_json_loads,
)
from .identity import (
    BlockObservation,
    EventObservation,
    ProtocolTradeIdentity,
    RawBlockLocator,
    WalletFillIdentity,
    frame,
    parse_block_record,
)
from .locator_order import raw_locator_mapping_order_key
from .selection import DEFAULT_SELECTION

UNIT_FILE = "r11a-v2-taxonomy-units.ndjson"
BLOCK_PROOF_FILE = "r11a-v2-exact-block-replay-proofs.ndjson"
PAIR_PROOF_FILE = "r11a-v2-expected-counterparty-pair-proofs.ndjson"
BLOCK_ROWS_FILE = "r11a-v2-block-overlap-matrix.ndjson"
LEGACY_ROWS_FILE = "r11a-v2-duplicate-observations.ndjson"
PROTOCOL_ROWS_FILE = "r11a-v2-protocol-trade-group-members.ndjson"
SCHEMA_ROWS_FILE = "r11a-v2-repeat-intersecting-schema-evidence.ndjson"

BLOCK_PROOF_TYPE = "R11A_V2_EXACT_BLOCK_REPLAY_PROOF"
PAIR_PROOF_TYPE = "R11A_V2_EXPECTED_COUNTERPARTY_PAIR_PROOF"

_WALLET = re.compile(r"0x[0-9a-f]{40}\Z")
_TARGET_BY_KEY = {target.object_key: target for target in DEFAULT_SELECTION.targets}


class SemanticProofError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SemanticProofError(message)


def _obj(value: object, label: str) -> FrozenObject:
    require(isinstance(value, FrozenObject), f"{label} must be object")
    return value  # type: ignore[return-value]


def _int(value: object, label: str) -> int:
    if isinstance(value, NumberToken) and value.is_integer_token:
        return int(value.token, 10)
    if type(value) is int:
        return value
    raise SemanticProofError(f"{label} must be an exact integer")


def _text(value: object, label: str) -> str:
    require(isinstance(value, str) and bool(value), f"{label} must be exact text")
    return value  # type: ignore[return-value]


def _rows(path: Path) -> tuple[FrozenObject, ...]:
    rows: list[FrozenObject] = []
    with path.open("rb") as handle:
        for ordinal, raw in enumerate(handle):
            require(raw.endswith(b"\n"), f"{path.name}[{ordinal}] lacks newline")
            rows.append(_obj(strict_json_loads(raw), path.name))
    return tuple(rows)


def _canonical_equal(left: object, right: object) -> bool:
    return canonical_json_bytes(left, final_newline=False) == canonical_json_bytes(
        right, final_newline=False
    )


def _locator(
    value: object,
    *,
    event_required: bool,
) -> tuple[FrozenObject, RawBlockLocator, int | None]:
    locator = _obj(value, "raw locator")
    expected = {
        "object_key",
        "verified_compressed_sha256",
        "decompressed_record_ordinal_zero_based",
    }
    if event_required:
        expected.add("event_ordinal_zero_based")
    require(set(locator) == expected, "raw locator schema drift")
    object_key = locator["object_key"]
    compressed_sha = locator["verified_compressed_sha256"]
    require(isinstance(object_key, str), "raw locator object key is not text")
    require(isinstance(compressed_sha, str), "raw locator SHA is not text")
    target = _TARGET_BY_KEY.get(object_key)
    require(target is not None, "raw locator object key is outside frozen selection")
    require(
        compressed_sha == target.expected_compressed_sha256,
        "raw locator SHA differs from frozen selection",
    )
    record = _int(
        locator["decompressed_record_ordinal_zero_based"],
        "record ordinal",
    )
    event = (
        _int(locator["event_ordinal_zero_based"], "event ordinal")
        if event_required
        else None
    )
    block = RawBlockLocator(object_key, compressed_sha, record)
    raw_locator_mapping_order_key(
        {
            "object_key": object_key,
            "verified_compressed_sha256": compressed_sha,
            "decompressed_record_ordinal_zero_based": record,
            **({"event_ordinal_zero_based": event} if event is not None else {}),
        }
    )
    return locator, block, event


def _selected_fill(value: object) -> dict[str, object]:
    if not isinstance(value, FrozenObject):
        return {}
    return {
        field: value[field]
        for field in (
            "coin",
            "side",
            "time",
            "px",
            "sz",
            "closedPnl",
            "tid",
            "crossed",
            "liquidation",
        )
        if field in value
    }


@dataclasses.dataclass(frozen=True, slots=True)
class EventSemantic:
    locator: FrozenObject
    locator_key: tuple[bytes, bytes, int, int]
    block_key: bytes
    block_number: int | None
    block_time: str | None
    weak_key: bytes
    protocol_key: bytes | None
    wallet_fill_key: bytes | None
    wallet: str | None
    coin: str | None
    tid: int | None
    side: str | None
    event_sha: str
    fill_sha: str | None
    raw_record_sha: str
    schema_errors: tuple[str, ...]
    selected_fill: dict[str, object]


def _event_semantic(
    row: FrozenObject,
    *,
    require_block_context: bool,
) -> EventSemantic:
    locator, block, event_ordinal = _locator(
        row["raw_locator"], event_required=True
    )
    require(event_ordinal is not None, "event locator lacks event ordinal")
    wallet_value = row["raw_wallet_value"]
    fill_value = row["raw_fill_value"]
    wallet: str | None = None
    errors: list[str] = []
    if isinstance(wallet_value, str) and _WALLET.fullmatch(wallet_value):
        wallet = wallet_value
    else:
        errors.append(
            "WALLET_NOT_STRING"
            if not isinstance(wallet_value, str)
            else "WALLET_NOT_CANONICAL_LOWERCASE_ADDRESS"
        )
    coin: str | None = None
    tid_value: object = None
    tid: int | None = None
    side: str | None = None
    if not isinstance(fill_value, FrozenObject):
        errors.append("FILL_NOT_OBJECT")
    else:
        raw_coin = fill_value["coin"] if "coin" in fill_value else None
        if (
            isinstance(raw_coin, str)
            and 0 < len(raw_coin.encode("utf-8", "strict")) <= 256
        ):
            coin = raw_coin
        else:
            errors.append("COIN_NOT_VALID_EXACT_STRING")
        tid_value = fill_value["tid"] if "tid" in fill_value else None
        if isinstance(tid_value, NumberToken) and tid_value.is_integer_token:
            parsed = int(tid_value.token, 10)
            if 0 <= parsed < (1 << 50):
                tid = parsed
            else:
                errors.append("TID_OUTSIDE_UINT50")
        elif isinstance(tid_value, NumberToken):
            errors.append("TID_NOT_LEXICAL_JSON_INTEGER")
        else:
            errors.append("TID_NOT_JSON_NUMBER_TOKEN")
        raw_side = fill_value["side"] if "side" in fill_value else None
        if (
            isinstance(raw_side, str)
            and 0 < len(raw_side.encode("utf-8", "strict")) <= 32
        ):
            side = raw_side
        elif raw_side is not None:
            errors.append("SIDE_NOT_VALID_EXACT_STRING")
    weak_wallet = (
        bytes.fromhex(wallet[2:])
        if wallet is not None
        else b"invalid-wallet\x00"
        + canonical_json_bytes(wallet_value, final_newline=False)
    )
    weak_key = frame(weak_wallet, historical_legacy_typed_tid(tid_value))
    block_time = (
        _text(row["exact_raw_block_time"], "exact raw block time")
        if "exact_raw_block_time" in row
        else None
    )
    if require_block_context:
        require(block_time is not None, "event block time is absent")
    protocol = (
        None
        if coin is None or tid is None or not require_block_context
        else ProtocolTradeIdentity(block_time, coin, tid)  # type: ignore[arg-type]
    )
    wallet_fill = (
        None
        if wallet is None or protocol is None
        else WalletFillIdentity(wallet, protocol)
    )
    event_sha = hashlib.sha256(
        canonical_json_bytes((wallet_value, fill_value), final_newline=False)
    ).hexdigest()
    fill_sha = (
        hashlib.sha256(
            canonical_json_bytes(fill_value, final_newline=False)
        ).hexdigest()
        if isinstance(fill_value, FrozenObject)
        else None
    )
    raw_record_sha = row["raw_record_fingerprint_sha256"]
    require(
        isinstance(raw_record_sha, str)
        and re.fullmatch(r"[0-9a-f]{64}", raw_record_sha) is not None,
        "raw record fingerprint claim is malformed",
    )
    if "canonical_wallet" in row:
        require(row["canonical_wallet"] == wallet, "canonical wallet claim is false")
    if "exact_raw_coin_string" in row:
        require(row["exact_raw_coin_string"] == coin, "coin claim is false")
    if "validated_tid" in row:
        observed_tid = None if row["validated_tid"] is None else _int(
            row["validated_tid"], "validated TID"
        )
        require(observed_tid == tid, "validated TID claim is false")
    if "exact_raw_side_string" in row:
        require(row["exact_raw_side_string"] == side, "side claim is false")
    if "full_event_sha256" in row:
        require(row["full_event_sha256"] == event_sha, "full event hash is false")
    if "fill_payload_sha256" in row:
        require(row["fill_payload_sha256"] == fill_sha, "fill hash is false")
    if "schema_errors" in row:
        require(
            tuple(row["schema_errors"]) == tuple(sorted(errors)),
            "schema error claim is false",
        )
    selected = _selected_fill(fill_value)
    if "selected_fill_payload" in row:
        require(
            _canonical_equal(row["selected_fill_payload"], selected),
            "selected fill projection is false",
        )
    block_number = (
        _int(row["block_number"], "block number")
        if "block_number" in row
        else None
    )
    if require_block_context:
        require(block_number is not None and block_time is not None, "event block context absent")
    block_key = block.key_bytes()
    if "raw_block_key_hex" in row:
        require(row["raw_block_key_hex"] == block_key.hex(), "raw block key claim is false")
    return EventSemantic(
        locator=locator,
        locator_key=raw_locator_mapping_order_key(
            {
                "object_key": locator["object_key"],
                "verified_compressed_sha256": locator[
                    "verified_compressed_sha256"
                ],
                "decompressed_record_ordinal_zero_based": _int(
                    locator["decompressed_record_ordinal_zero_based"],
                    "record ordinal",
                ),
                "event_ordinal_zero_based": event_ordinal,
            }
        ),
        block_key=block_key,
        block_number=block_number,
        block_time=block_time,
        weak_key=weak_key,
        protocol_key=None if protocol is None else protocol.key_bytes(),
        wallet_fill_key=None if wallet_fill is None else wallet_fill.key_bytes(),
        wallet=wallet,
        coin=coin,
        tid=tid,
        side=side,
        event_sha=event_sha,
        fill_sha=fill_sha,
        raw_record_sha=raw_record_sha,
        schema_errors=tuple(sorted(errors)),
        selected_fill=selected,
    )


def _add_raw_record_evidence(
    row: FrozenObject,
    evidence: dict[bytes, BlockObservation],
) -> None:
    raw_record = row["raw_record_value"]
    if raw_record is None:
        return
    _, block_locator, _ = _locator(
        row["raw_locator"],
        event_required="event_ordinal_zero_based" in _obj(
            row["raw_locator"], "raw locator"
        ),
    )
    observed = parse_block_record(
        raw_record,
        object_key=block_locator.object_key,
        verified_compressed_sha256=block_locator.verified_compressed_sha256,
        record_ordinal_zero_based=(
            block_locator.decompressed_record_ordinal_zero_based
        ),
    )
    key = block_locator.key_bytes()
    require(key not in evidence, "raw block record evidence is not unique")
    require(
        row["raw_record_fingerprint_sha256"]
        == observed.raw_record_fingerprint,
        "raw record fingerprint claim is false",
    )
    evidence[key] = observed


def _bind_event_to_raw_record(
    row: FrozenObject,
    semantic: EventSemantic,
    evidence: Mapping[bytes, BlockObservation],
) -> None:
    observed = evidence.get(semantic.block_key)
    require(observed is not None, "event raw block provenance is missing")
    event_ordinal = semantic.locator_key[3]
    events = observed.events
    require(0 <= event_ordinal < len(events), "event ordinal is absent from raw block")
    source_event = events[event_ordinal]
    require(
        semantic.block_number == observed.block_number,
        "event block number differs from retained raw record",
    )
    require(
        semantic.block_time == observed.exact_raw_block_time,
        "event block time differs from retained raw record",
    )
    if "exact_raw_local_time" in row:
        require(
            row["exact_raw_local_time"]
            == observed.exact_raw_local_time,
            "event local time differs from retained raw record",
        )
    require(
        _canonical_equal(row["raw_wallet_value"], source_event.raw_wallet_value)
        and _canonical_equal(row["raw_fill_value"], source_event.raw_fill_value),
        "event payload is not the claimed raw block member",
    )
    require(
        semantic.event_sha == source_event.full_event_sha256,
        "event fingerprint differs from retained raw record",
    )
    require(
        semantic.raw_record_sha
        == observed.raw_record_fingerprint,
        "event raw record commitment is false",
    )


def _event_locator_key(value: object) -> tuple[bytes, bytes, int, int]:
    return raw_locator_mapping_order_key(value)


def _proof_refs(unit: FrozenObject) -> dict[str, tuple[str, str]]:
    refs = unit["proof_references"]
    require(isinstance(refs, tuple), "proof references must be array")
    result: dict[str, tuple[str, str]] = {}
    for value in refs:
        ref = _obj(value, "proof reference")
        proof_id = _text(ref["proof_id"], "proof ID")
        require(proof_id not in result, "duplicate semantic proof reference")
        result[proof_id] = (
            _text(ref["proof_type"], "proof type"),
            _text(ref["proof_projection_sha256"], "proof projection SHA"),
        )
    return result


def _unit_maps(artifact: Path) -> tuple[dict[str, FrozenObject], dict[str, FrozenObject]]:
    units = {
        _text(row["taxonomy_unit_id"], "taxonomy unit ID"): row
        for row in _rows(artifact / UNIT_FILE)
    }
    require(len(units) == len(_rows(artifact / UNIT_FILE)), "duplicate semantic unit")
    proofs: dict[str, FrozenObject] = {}
    for name in (BLOCK_PROOF_FILE, PAIR_PROOF_FILE):
        for row in _rows(artifact / name):
            proof_id = _text(row["proof_id"], "proof ID")
            require(proof_id not in proofs, "duplicate semantic proof")
            proofs[proof_id] = row
    return units, proofs


def _rows_by_unit(rows: Iterable[FrozenObject]) -> dict[str, list[FrozenObject]]:
    result: dict[str, list[FrozenObject]] = defaultdict(list)
    for row in rows:
        result[_text(row["taxonomy_unit_id"], "taxonomy unit ID")].append(row)
    return result


def _check_unit_common(
    unit: FrozenObject,
    rows: list[FrozenObject],
    universe: str,
) -> None:
    require(unit["diagnostic_id"] == DIAGNOSTIC_ID, "unit diagnostic drift")
    require(unit["unit_universe"] == universe, "unit authoritative universe drift")
    require(
        _int(unit["occurrence_count"], "unit occurrence count") == len(rows),
        "unit occurrence multiplicity is false",
    )
    require(
        all(row["primary_taxon"] == unit["primary_taxon"] for row in rows),
        "retained primary taxon differs from authoritative unit",
    )


def validate_semantic_proofs(artifact: Path) -> None:
    units, proofs = _unit_maps(artifact)
    block_rows = _rows(artifact / BLOCK_ROWS_FILE)
    protocol_rows = _rows(artifact / PROTOCOL_ROWS_FILE)
    legacy_rows = _rows(artifact / LEGACY_ROWS_FILE)
    schema_rows = _rows(artifact / SCHEMA_ROWS_FILE)
    expected_proofs: set[str] = set()
    block_lookup: dict[bytes, tuple[str, str | None]] = {}
    raw_record_evidence: dict[bytes, BlockObservation] = {}
    authoritative_block_groups: dict[int, set[bytes]] = {}

    for unit_id, rows in _rows_by_unit(block_rows).items():
        require(unit_id in units, "block row has dangling authoritative unit")
        unit = units[unit_id]
        _check_unit_common(unit, rows, "ARCHIVE_BLOCK_NUMBER_GROUP")
        require(len(rows) >= 2, "repeated block unit is not a repeated group")
        parsed: list[tuple[FrozenObject, object]] = []
        locators: set[tuple[bytes, bytes, int, int]] = set()
        for row in rows:
            locator, block_locator, event = _locator(row["raw_locator"], event_required=False)
            require(event is None, "block locator unexpectedly has event ordinal")
            observed = parse_block_record(
                row["raw_record_value"],
                object_key=block_locator.object_key,
                verified_compressed_sha256=block_locator.verified_compressed_sha256,
                record_ordinal_zero_based=block_locator.decompressed_record_ordinal_zero_based,
            )
            require(row["raw_block_key_hex"] == observed.raw_locator.key_bytes().hex(), "block raw key is false")
            require(_int(row["block_number"], "block number") == observed.block_number, "block number is false")
            require(row["exact_raw_block_time"] == observed.exact_raw_block_time, "block time is false")
            require(_int(row["ordered_event_count"], "event count") == observed.ordered_event_count, "block event count is false")
            require(row["ordered_event_fingerprint_sha256"] == observed.ordered_event_fingerprint, "block event commitment is false")
            require(row["raw_record_fingerprint_sha256"] == observed.raw_record_fingerprint, "block record commitment is false")
            raw_key = observed.raw_locator.key_bytes()
            require(
                raw_key not in raw_record_evidence,
                "raw block record evidence is not unique",
            )
            raw_record_evidence[raw_key] = observed
            key = raw_locator_mapping_order_key(
                {
                    "object_key": locator["object_key"],
                    "verified_compressed_sha256": locator["verified_compressed_sha256"],
                    "decompressed_record_ordinal_zero_based": _int(locator["decompressed_record_ordinal_zero_based"], "record ordinal"),
                }
            )
            require(key not in locators, "duplicate block source locator")
            locators.add(key)
            parsed.append((row, observed))
        parsed.sort(key=lambda pair: raw_locator_mapping_order_key(pair[0]["raw_locator"]))
        locator_hasher = hashlib.sha256()
        for row, observed in parsed:
            object_key = str(_obj(row["raw_locator"], "raw locator")["object_key"])
            projection = {
                "object_ordinal_zero_based": _TARGET_BY_KEY[object_key].object_ordinal_zero_based,
                "object_key": object_key,
                "record_ordinal_zero_based": observed.raw_locator.decompressed_record_ordinal_zero_based,
                "raw_block_key_sha256": hashlib.sha256(observed.raw_locator.key_bytes()).hexdigest(),
            }
            locator_hasher.update(frame(canonical_json_bytes(projection, final_newline=False)))
        block_numbers = {observed.block_number for _, observed in parsed}
        invariants = {
            (
                observed.exact_raw_block_time,
                observed.ordered_event_count,
                observed.ordered_event_fingerprint,
            )
            for _, observed in parsed
        }
        distinct_objects = {observed.raw_locator.object_key for _, observed in parsed}
        require(len(block_numbers) == 1, "block equality group membership is false")
        block_number = next(iter(block_numbers))
        require(
            block_number not in authoritative_block_groups,
            "block-number equality group is split across authoritative units",
        )
        authoritative_block_groups[block_number] = {
            observed.raw_locator.key_bytes() for _, observed in parsed
        }
        expected_taxon = (
            "CONFLICTING_BLOCK_REPLAY"
            if len(invariants) > 1
            else "EXACT_BLOCK_REPLAY_ACROSS_OBJECTS"
            if len(distinct_objects) >= 2
            else "UNCLASSIFIABLE"
        )
        require(unit["primary_taxon"] == expected_taxon, "block primary taxon is semantically false")
        commitment = locator_hasher.hexdigest()
        require(
            _canonical_equal(
                unit["key_projection"],
                {
                    "block_number": block_number,
                    "raw_block_locator_count": len(parsed),
                    "ordered_raw_locator_projection_sha256": commitment,
                },
            ),
            "block unit key projection is false",
        )
        refs = _proof_refs(unit)
        proof_id: str | None = None
        if expected_taxon == "EXACT_BLOCK_REPLAY_ACROSS_OBJECTS":
            require(len(refs) == 1, "exact block unit lacks its sole proof")
            proof_id = next(iter(refs))
            require(proof_id in proofs, "exact block proof is dangling")
            proof = proofs[proof_id]
            invariant = next(iter(invariants))
            expected_projection = {
                "block_number": block_number,
                "raw_block_locator_count": len(parsed),
                "distinct_source_object_count": len(distinct_objects),
                "ordered_raw_locator_projection_sha256": commitment,
                "exact_raw_block_time": invariant[0],
                "ordered_event_count": invariant[1],
                "ordered_event_fingerprint_sha256": invariant[2],
            }
            require(proof["record_type"] == BLOCK_PROOF_TYPE, "wrong block proof type")
            require(_canonical_equal(proof["projection"], expected_projection), "self-consistent block proof claim is false")
            expected_proofs.add(proof_id)
        else:
            require(not refs, "non-exact block unit claims replay proof")
        for _, observed in parsed:
            raw_key = observed.raw_locator.key_bytes()
            require(raw_key not in block_lookup, "raw block locator is ambiguously authoritative")
            block_lookup[raw_key] = (expected_taxon, proof_id)

    for row in (*protocol_rows, *schema_rows):
        _add_raw_record_evidence(row, raw_record_evidence)

    evidence_groups: defaultdict[int, set[bytes]] = defaultdict(set)
    for raw_key, observed in raw_record_evidence.items():
        evidence_groups[observed.block_number].add(raw_key)
    expected_block_groups = {
        block_number: raw_keys
        for block_number, raw_keys in evidence_groups.items()
        if len(raw_keys) >= 2
    }
    require(
        authoritative_block_groups == expected_block_groups,
        "authoritative repeated-block equality-group membership is incomplete",
    )

    protocol_semantics: dict[tuple[bytes, bytes], tuple[str, str | None]] = {}
    protocol_events: list[EventSemantic] = []
    for unit_id, rows in _rows_by_unit(protocol_rows).items():
        require(unit_id in units, "protocol row has dangling authoritative unit")
        unit = units[unit_id]
        _check_unit_common(
            unit,
            rows,
            "PROTOCOL_MATCHED_TRADE_GROUP_PER_RAW_BLOCK_OCCURRENCE",
        )
        members = [_event_semantic(row, require_block_context=True) for row in rows]
        for row, member in zip(rows, members, strict=True):
            _bind_event_to_raw_record(row, member, raw_record_evidence)
        members.sort(key=lambda value: value.locator_key)
        require(len({member.locator_key for member in members}) == len(members), "duplicate protocol member locator")
        require(all(member.protocol_key is not None for member in members), "protocol group contains invalid identity")
        group_keys = {(member.block_key, member.protocol_key) for member in members}
        require(len(group_keys) == 1, "protocol equality group membership is false")
        raw_block_key, protocol_key_optional = next(iter(group_keys))
        require(protocol_key_optional is not None, "protocol key absent")
        protocol_key = protocol_key_optional
        expected_pair = (
            len(members) == 2
            and len({member.wallet for member in members}) == 2
            and {member.side for member in members} == {"A", "B"}
            and members[1].locator_key[3] == members[0].locator_key[3] + 1
            and len({member.wallet_fill_key for member in members}) == 2
            and all(member.wallet_fill_key is not None for member in members)
        )
        expected_taxon = "EXPECTED_COUNTERPARTY_PAIR" if expected_pair else "UNCLASSIFIABLE"
        require(unit["primary_taxon"] == expected_taxon, "counterparty primary taxon is semantically false")
        require(
            _canonical_equal(
                unit["key_projection"],
                {
                    "raw_block_key_sha256": hashlib.sha256(raw_block_key).hexdigest(),
                    "protocol_trade_key_sha256": hashlib.sha256(protocol_key).hexdigest(),
                },
            ),
            "protocol unit key projection is false",
        )
        refs = _proof_refs(unit)
        proof_id = None
        if expected_pair:
            require(len(refs) == 1, "counterparty unit lacks its sole proof")
            proof_id = next(iter(refs))
            proof = proofs.get(proof_id)
            require(proof is not None and proof["record_type"] == PAIR_PROOF_TYPE, "counterparty proof type is false")
            hasher = hashlib.sha256()
            for row in sorted(rows, key=lambda value: raw_locator_mapping_order_key(value["raw_locator"])):
                hasher.update(
                    canonical_json_bytes(
                        {
                            "raw_locator": row["raw_locator"],
                            "raw_block_key_hex": row["raw_block_key_hex"],
                            "block_number": row["block_number"],
                            "exact_raw_block_time": row["exact_raw_block_time"],
                            "raw_wallet_value": row["raw_wallet_value"],
                            "raw_fill_value": row["raw_fill_value"],
                            "raw_record_fingerprint_sha256": row[
                                "raw_record_fingerprint_sha256"
                            ],
                            "canonical_wallet": row["canonical_wallet"],
                            "exact_raw_coin_string": row["exact_raw_coin_string"],
                            "validated_tid": row["validated_tid"],
                            "exact_raw_side_string": row["exact_raw_side_string"],
                            "full_event_sha256": row["full_event_sha256"],
                        },
                        final_newline=False,
                    )
                )
            expected_projection = {
                "raw_block_key_sha256": hashlib.sha256(raw_block_key).hexdigest(),
                "protocol_trade_key_sha256": hashlib.sha256(protocol_key).hexdigest(),
                "member_count": len(members),
                "ordered_member_projection_sha256": hasher.hexdigest(),
            }
            require(_canonical_equal(proof["projection"], expected_projection), "self-consistent counterparty proof claim is false")
            expected_proofs.add(proof_id)
        else:
            require(not refs, "non-pair protocol unit claims pair proof")
        semantic_key = (raw_block_key, protocol_key)
        require(semantic_key not in protocol_semantics, "protocol equality group is ambiguous")
        protocol_semantics[semantic_key] = (expected_taxon, proof_id)
        protocol_events.extend(members)

    schema_events: list[EventSemantic] = []
    schema_members: set[tuple[tuple[bytes, bytes, int, int], str]] = set()
    schema_by_unit = _rows_by_unit(schema_rows)
    for unit_id, rows in schema_by_unit.items():
        require(unit_id in units, "schema row has dangling authoritative unit")
        unit = units[unit_id]
        universe = _text(unit["unit_universe"], "unit universe")
        _check_unit_common(unit, rows, universe)
        require(len(rows) == 1, "schema unit must contain one occurrence")
        row = rows[0]
        semantic = _event_semantic(row, require_block_context=True)
        _bind_event_to_raw_record(row, semantic, raw_record_evidence)
        dimension = {
            "REPEAT_INTERSECTING_TID_SCHEMA_VIOLATION": any(error.startswith("TID_") for error in semantic.schema_errors),
            "REPEAT_INTERSECTING_COIN_SCHEMA_VIOLATION": "COIN_NOT_VALID_EXACT_STRING" in semantic.schema_errors,
            "REPEAT_INTERSECTING_WALLET_SCHEMA_VIOLATION": any(error.startswith("WALLET_") for error in semantic.schema_errors),
        }.get(universe)
        require(dimension is True, "schema unit does not exhibit its authoritative violation")
        expected_taxon = "TID_SCHEMA_VIOLATION" if universe.endswith("TID_SCHEMA_VIOLATION") else "UNCLASSIFIABLE"
        require(unit["primary_taxon"] == expected_taxon, "schema unit taxon is false")
        require(
            _canonical_equal(
                unit["key_projection"],
                {
                    "raw_locator": row["raw_locator"],
                    "legacy_weak_key_sha256": hashlib.sha256(semantic.weak_key).hexdigest(),
                },
            ),
            "schema unit key projection is false",
        )
        require(not _proof_refs(unit), "schema unit must not claim proof")
        schema_member = (semantic.locator_key, universe)
        require(schema_member not in schema_members, "duplicate schema membership")
        schema_members.add(schema_member)
        schema_events.append(semantic)

    evidence_weak_groups: defaultdict[bytes, list[EventObservation]] = defaultdict(
        list
    )
    evidence_events_by_block: dict[bytes, tuple[EventObservation, ...]] = {}
    for raw_block_key, block in raw_record_evidence.items():
        evidence_events_by_block[raw_block_key] = block.events
        for event in block.events:
            evidence_weak_groups[event.legacy_weak_key_bytes].append(event)
    repeated_weak_keys = {
        key for key, members in evidence_weak_groups.items() if len(members) > 1
    }

    expected_legacy_locators: set[tuple[bytes, bytes, int, int]] = set()
    for key in repeated_weak_keys:
        members = sorted(
            evidence_weak_groups[key],
            key=lambda event: _event_locator_key(event.locator_mapping()),
        )
        expected_legacy_locators.update(
            _event_locator_key(event.locator_mapping()) for event in members[1:]
        )

    expected_protocol_locators: set[tuple[bytes, bytes, int, int]] = set()
    expected_schema_members: set[
        tuple[tuple[bytes, bytes, int, int], str]
    ] = set()
    relevant_nonrepeated_blocks: set[bytes] = set()
    for raw_block_key, events in evidence_events_by_block.items():
        weak_members = [
            event
            for event in events
            if event.legacy_weak_key_bytes in repeated_weak_keys
        ]
        if weak_members:
            relevant_nonrepeated_blocks.add(raw_block_key)
        protocol_keys = {
            event.protocol_trade_identity.key_bytes()
            for event in weak_members
            if event.protocol_trade_identity is not None
        }
        for event in events:
            if (
                event.protocol_trade_identity is not None
                and event.protocol_trade_identity.key_bytes() in protocol_keys
            ):
                expected_protocol_locators.add(
                    _event_locator_key(event.locator_mapping())
                )
        for event in weak_members:
            locator_key = _event_locator_key(event.locator_mapping())
            errors = set(event.schema_errors)
            if any(value.startswith("TID_") for value in errors):
                expected_schema_members.add(
                    (
                        locator_key,
                        "REPEAT_INTERSECTING_TID_SCHEMA_VIOLATION",
                    )
                )
            if "COIN_NOT_VALID_EXACT_STRING" in errors:
                expected_schema_members.add(
                    (
                        locator_key,
                        "REPEAT_INTERSECTING_COIN_SCHEMA_VIOLATION",
                    )
                )
            if any(value.startswith("WALLET_") for value in errors):
                expected_schema_members.add(
                    (
                        locator_key,
                        "REPEAT_INTERSECTING_WALLET_SCHEMA_VIOLATION",
                    )
                )

    actual_protocol_locators = {member.locator_key for member in protocol_events}
    require(
        len(actual_protocol_locators) == len(protocol_events),
        "protocol retained locator is ambiguous",
    )
    require(
        actual_protocol_locators == expected_protocol_locators,
        "protocol equality-group membership is incomplete",
    )
    require(
        schema_members == expected_schema_members,
        "repeat-intersecting schema membership is incomplete",
    )
    repeated_block_locators = {
        raw_key for raw_keys in authoritative_block_groups.values() for raw_key in raw_keys
    }
    require(
        set(raw_record_evidence)
        == repeated_block_locators | relevant_nonrepeated_blocks,
        "raw block provenance contains a missing or extraneous locator",
    )

    context_by_locator: dict[tuple[bytes, bytes, int, int], EventSemantic] = {}
    for semantic in (*protocol_events, *schema_events):
        previous = context_by_locator.get(semantic.locator_key)
        if previous is not None:
            require(previous == semantic, "ambiguous canonical event context")
        context_by_locator[semantic.locator_key] = semantic
    legacy_semantics: dict[str, EventSemantic] = {}
    for unit_id, rows in _rows_by_unit(legacy_rows).items():
        require(unit_id in units, "legacy row has dangling authoritative unit")
        unit = units[unit_id]
        _check_unit_common(unit, rows, "LEGACY_REPEAT_OCCURRENCE")
        require(len(rows) == 1, "legacy repeat unit multiplicity must be one")
        semantic = _event_semantic(rows[0], require_block_context=True)
        _bind_event_to_raw_record(rows[0], semantic, raw_record_evidence)
        previous = context_by_locator.get(semantic.locator_key)
        if previous is not None:
            require(previous == semantic, "legacy evidence conflicts with canonical context")
        context_by_locator[semantic.locator_key] = semantic
        legacy_semantics[unit_id] = semantic

    require(
        {semantic.locator_key for semantic in legacy_semantics.values()}
        == expected_legacy_locators,
        "legacy first-occurrence exclusion or complete equality-group membership is false",
    )

    weak_groups: defaultdict[bytes, list[EventSemantic]] = defaultdict(list)
    for semantic in context_by_locator.values():
        weak_groups[semantic.weak_key].append(semantic)
    for members in weak_groups.values():
        members.sort(key=lambda value: value.locator_key)

    for unit_id, semantic in legacy_semantics.items():
        unit = units[unit_id]
        row = _rows_by_unit(legacy_rows)[unit_id][0]
        group = sorted(weak_groups[semantic.weak_key], key=lambda value: value.locator_key)
        wallet_group = [
            value
            for value in group
            if semantic.wallet_fill_key is not None
            and value.wallet_fill_key == semantic.wallet_fill_key
        ]
        block_states = [block_lookup.get(value.block_key) for value in wallet_group]
        explicit_block_conflict = any(
            state is not None and state[0] in {"CONFLICTING_BLOCK_REPLAY", "UNCLASSIFIABLE"}
            for state in block_states
        )
        raw_blocks = {value.block_key for value in wallet_group}
        replay_proofs = {
            state[1]
            for state in block_states
            if state is not None and state[0] == "EXACT_BLOCK_REPLAY_ACROSS_OBJECTS" and state[1] is not None
        }
        unresolved_multi = len(raw_blocks) > 1 and (
            any(
                state is None
                or state[0] != "EXACT_BLOCK_REPLAY_ACROSS_OBJECTS"
                or state[1] is None
                for state in block_states
            )
            or len(replay_proofs) != 1
        )
        conflicting_wallet = len({value.event_sha for value in wallet_group}) > 1
        intra_block = any(
            len({value.locator_key[3] for value in wallet_group if value.block_key == block_key and value.event_sha == event_sha}) > 1
            for block_key, event_sha in {(value.block_key, value.event_sha) for value in wallet_group}
        )
        scope_complete = (
            len({value.protocol_key for value in group if value.protocol_key is not None}) >= 2
            and all(value.protocol_key is not None and value.wallet_fill_key is not None for value in group)
            and not any(
                state is not None and state[0] in {"CONFLICTING_BLOCK_REPLAY", "UNCLASSIFIABLE"}
                for value in group
                for state in (block_lookup.get(value.block_key),)
            )
            and not any(
                len({item.event_sha for item in group if item.wallet_fill_key == key}) > 1
                for key in {item.wallet_fill_key for item in group if item.wallet_fill_key is not None}
            )
            and not any(
                len({item.block_key for item in group if item.wallet_fill_key == key}) > 1
                and (
                    any(
                        block_lookup.get(item.block_key) is None
                        or block_lookup[item.block_key][0] != "EXACT_BLOCK_REPLAY_ACROSS_OBJECTS"
                        or block_lookup[item.block_key][1] is None
                        for item in group
                        if item.wallet_fill_key == key
                    )
                    or len(
                        {
                            block_lookup[item.block_key][1]
                            for item in group
                            if item.wallet_fill_key == key
                        }
                    )
                    != 1
                )
                for key in {item.wallet_fill_key for item in group if item.wallet_fill_key is not None}
            )
        )
        if any(error.startswith("TID_") for error in semantic.schema_errors):
            expected_taxon = "TID_SCHEMA_VIOLATION"
        elif semantic.protocol_key is None or semantic.wallet_fill_key is None:
            expected_taxon = "UNCLASSIFIABLE"
        elif explicit_block_conflict:
            expected_taxon = "UNCLASSIFIABLE"
        elif unresolved_multi:
            expected_taxon = "UNCLASSIFIABLE"
        elif conflicting_wallet:
            expected_taxon = "CONFLICTING_USER_FILL"
        elif intra_block:
            expected_taxon = "INTRA_BLOCK_REPEAT"
        elif (
            len(wallet_group) > 1
            and len({value.event_sha for value in wallet_group}) == 1
            and len(raw_blocks) > 1
            and len(replay_proofs) == 1
        ):
            expected_taxon = "EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY"
        elif scope_complete:
            expected_taxon = "TID_SCOPE_FALSE_POSITIVE"
        else:
            expected_taxon = "UNCLASSIFIABLE"
        require(unit["primary_taxon"] == expected_taxon, "legacy primary taxon is semantically false")
        require(
            _canonical_equal(
                unit["key_projection"],
                {
                    "legacy_weak_key_sha256": hashlib.sha256(semantic.weak_key).hexdigest(),
                    "raw_locator": row["raw_locator"],
                    "complete_group_observation_count": len(group),
                    "complete_wallet_fill_group_key_sha256": (
                        None
                        if semantic.wallet_fill_key is None
                        else hashlib.sha256(semantic.wallet_fill_key).hexdigest()
                    ),
                },
            ),
            "legacy unit key projection or multiplicity is false",
        )
        expected_refs: set[str] = set()
        expected_supporting: list[str] = []
        if semantic.protocol_key is not None:
            protocol = protocol_semantics.get((semantic.block_key, semantic.protocol_key))
            if protocol is not None and protocol[0] == "EXPECTED_COUNTERPARTY_PAIR":
                expected_supporting.append("EXPECTED_COUNTERPARTY_PAIR")
                require(protocol[1] is not None, "counterparty support lacks proof")
                expected_refs.add(str(protocol[1]))
        if expected_taxon == "EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY":
            require(len(replay_proofs) == 1, "wallet replay lacks unique block proof")
            expected_refs.update(str(value) for value in replay_proofs)
        require(set(_proof_refs(unit)) == expected_refs, "legacy unit-to-proof membership is false")
        require(tuple(unit["supporting_taxa"]) == tuple(expected_supporting), "legacy supporting relationship is false")
        expected_proofs.update(expected_refs)

    retained_units = {
        _text(row["taxonomy_unit_id"], "taxonomy unit ID")
        for row in (*block_rows, *protocol_rows, *legacy_rows, *schema_rows)
    }
    require(retained_units == set(units), "authoritative unit universe has missing or extra retained membership")
    require(expected_proofs == set(proofs), "proof universe has missing, extra, or semantically false proof")


__all__ = ["SemanticProofError", "validate_semantic_proofs"]
