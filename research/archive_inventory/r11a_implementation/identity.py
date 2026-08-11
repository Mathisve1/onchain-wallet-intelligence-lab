from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping

UINT50_MAX_EXCLUSIVE = 1 << 50
UINT64_MAX = (1 << 64) - 1
ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CANONICAL_SERIALIZATION_VERSION = "R11A_CANONICAL_JSON_TYPED_FIELDS_V1"
SELECTED_FILL_FIELD_ORDER = (
    "coin", "tid", "time", "side", "px", "sz", "closedPnl", "crossed", "liquidation"
)


class R11AIdentityError(ValueError):
    """Raised when lossless parsing or canonical identity fails closed."""


class _Missing:
    __slots__ = ()


MISSING = _Missing()


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise R11AIdentityError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def strict_json_loads(raw: bytes | str) -> object:
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise R11AIdentityError("record is not strict UTF-8") from exc
    elif type(raw) is str:
        text = raw
    else:
        raise R11AIdentityError("strict_json_loads requires bytes or str")
    try:
        return json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_int=int,
            parse_float=Decimal,
            parse_constant=lambda token: (_ for _ in ()).throw(
                R11AIdentityError(f"non-finite JSON constant: {token}")
            ),
        )
    except (json.JSONDecodeError, InvalidOperation) as exc:
        raise R11AIdentityError(f"strict JSON parse failure: {exc}") from exc


def _frame(payload: bytes) -> bytes:
    return str(len(payload)).encode("ascii") + b":" + payload


def _decimal_token(value: Decimal) -> bytes:
    if not value.is_finite():
        raise R11AIdentityError("non-finite Decimal forbidden")
    if value.is_zero():
        return b"0"
    sign, raw_digits, exponent = value.as_tuple()
    digits = list(raw_digits)
    while digits and digits[-1] == 0:
        digits.pop()
        exponent += 1
    coefficient = "".join(str(digit) for digit in digits)
    if sign:
        coefficient = "-" + coefficient
    return coefficient.encode("ascii") + b"e" + str(exponent).encode("ascii")


def canonical_typed_bytes(
    value: object,
    *,
    _depth: int = 0,
    _seen: set[int] | None = None,
) -> bytes:
    if _depth > 128:
        raise R11AIdentityError("canonical serialization depth exceeds 128")
    if value is MISSING:
        raise R11AIdentityError("MISSING needs an explicit presence flag")
    if value is None:
        return b"N"
    if type(value) is bool:
        return b"B1" if value else b"B0"
    if type(value) is int:
        return b"I" + _frame(str(value).encode("ascii"))
    if isinstance(value, Decimal):
        return b"D" + _frame(_decimal_token(value))
    if type(value) is float:
        raise R11AIdentityError("binary float forbidden")
    if type(value) is str:
        try:
            return b"S" + _frame(value.encode("utf-8", errors="strict"))
        except UnicodeEncodeError as exc:
            raise R11AIdentityError("invalid Unicode string") from exc
    if type(value) is bytes:
        return b"Y" + _frame(value)
    seen = set() if _seen is None else _seen
    if isinstance(value, (list, tuple, Mapping)):
        object_id = id(value)
        if object_id in seen:
            raise R11AIdentityError("cycle forbidden")
        seen.add(object_id)
        try:
            if isinstance(value, list):
                encoded = b"".join(
                    _frame(canonical_typed_bytes(item, _depth=_depth + 1, _seen=seen))
                    for item in value
                )
                return b"L" + _frame(str(len(value)).encode("ascii")) + encoded
            if isinstance(value, tuple):
                encoded = b"".join(
                    _frame(canonical_typed_bytes(item, _depth=_depth + 1, _seen=seen))
                    for item in value
                )
                return b"T" + _frame(str(len(value)).encode("ascii")) + encoded
            pairs: list[tuple[bytes, bytes]] = []
            for key, item in value.items():
                if type(key) is not str:
                    raise R11AIdentityError("mapping keys must be strings")
                pairs.append(
                    (
                        canonical_typed_bytes(key, _depth=_depth + 1, _seen=seen),
                        canonical_typed_bytes(item, _depth=_depth + 1, _seen=seen),
                    )
                )
            pairs.sort(key=lambda pair: pair[0])
            encoded = b"".join(_frame(key) + _frame(item) for key, item in pairs)
            return b"M" + _frame(str(len(pairs)).encode("ascii")) + encoded
        finally:
            seen.remove(object_id)
    raise R11AIdentityError(f"unsupported canonical type: {type(value).__name__}")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_typed_bytes(value)).hexdigest()


def json_type_label(value: object) -> str:
    if value is MISSING:
        return "MISSING"
    if value is None:
        return "NULL"
    if type(value) is bool:
        return "BOOLEAN"
    if type(value) is int:
        return "INTEGER"
    if isinstance(value, Decimal):
        return "NUMBER_FRACTION_OR_EXPONENT_TOKEN"
    if type(value) is str:
        return "STRING"
    if isinstance(value, list):
        return "ARRAY"
    if isinstance(value, dict):
        return "OBJECT"
    raise R11AIdentityError(f"unsupported parsed type: {type(value).__name__}")


def typed_token_hex(value: object) -> str | None:
    return None if value is MISSING else canonical_typed_bytes(value).hex()


@dataclass(frozen=True, order=True, slots=True)
class SourceObject:
    object_ordinal_zero_based: int
    object_key: str
    compressed_sha256: str
    path_hour_utc: str

    def __post_init__(self) -> None:
        if type(self.object_ordinal_zero_based) is not int or self.object_ordinal_zero_based < 0:
            raise R11AIdentityError("object ordinal invalid")
        if type(self.object_key) is not str or not self.object_key:
            raise R11AIdentityError("object key invalid")
        if SHA256_RE.fullmatch(self.compressed_sha256) is None:
            raise R11AIdentityError("compressed SHA invalid")
        if type(self.path_hour_utc) is not str or len(self.path_hour_utc) != 20 or not self.path_hour_utc.endswith(":00:00Z"):
            raise R11AIdentityError("path hour invalid")


@dataclass(frozen=True, order=True, slots=True)
class RawBlockLocator:
    source_object_key: str
    compressed_object_sha256: str
    record_ordinal_zero_based: int

    def __post_init__(self) -> None:
        if type(self.source_object_key) is not str or not self.source_object_key:
            raise R11AIdentityError("raw block object key invalid")
        if SHA256_RE.fullmatch(self.compressed_object_sha256) is None:
            raise R11AIdentityError("raw block SHA invalid")
        if type(self.record_ordinal_zero_based) is not int or self.record_ordinal_zero_based < 0:
            raise R11AIdentityError("record ordinal invalid")

    def as_mapping(self) -> dict[str, object]:
        return {
            "source_object_key": self.source_object_key,
            "compressed_object_sha256": self.compressed_object_sha256,
            "record_ordinal_zero_based": self.record_ordinal_zero_based,
        }


@dataclass(frozen=True, order=True, slots=True)
class RawObservationLocator:
    source_object_key: str
    compressed_object_sha256: str
    record_ordinal_zero_based: int
    event_ordinal_zero_based: int

    def __post_init__(self) -> None:
        RawBlockLocator(
            self.source_object_key,
            self.compressed_object_sha256,
            self.record_ordinal_zero_based,
        )
        if type(self.event_ordinal_zero_based) is not int or self.event_ordinal_zero_based < 0:
            raise R11AIdentityError("event ordinal invalid")

    @property
    def block_locator(self) -> RawBlockLocator:
        return RawBlockLocator(
            self.source_object_key,
            self.compressed_object_sha256,
            self.record_ordinal_zero_based,
        )

    def as_mapping(self) -> dict[str, object]:
        return {
            "source_object_key": self.source_object_key,
            "compressed_object_sha256": self.compressed_object_sha256,
            "record_ordinal_zero_based": self.record_ordinal_zero_based,
            "event_ordinal_zero_based": self.event_ordinal_zero_based,
        }


@dataclass(frozen=True, slots=True)
class Validation:
    raw_json_type: str
    raw_token: str | None
    status: str
    reason: str | None
    canonical_value: object | None


@dataclass(frozen=True, slots=True)
class Observation:
    locator: RawObservationLocator
    source: SourceObject
    block_number: int
    block_time_exact: str
    local_time_exact: str
    raw_wallet_address: str | None
    raw_wallet_json_type: str
    raw_wallet_token: str | None
    wallet_validation_status: str
    wallet_schema_violation_reason: str | None
    canonical_lowercase_wallet_address: str | None
    raw_tid_json_type: str
    raw_tid_token: str | None
    tid_validation_status: str
    tid_schema_violation_reason: str | None
    validated_integer_tid: int | None
    raw_coin_json_type: str
    raw_coin_token: str | None
    coin_validation_status: str
    coin_schema_violation_reason: str | None
    exact_raw_coin_string: str | None
    legacy_weak_key: tuple[str, tuple[str, str]] | None
    protocol_trade_identity: tuple[str, str, int] | None
    wallet_fill_identity: tuple[str, str, str, int] | None
    side_exact: str
    fill_time_exact: int
    crossed_exact: bool
    selected_fill_sha256: str
    full_fill_sha256: str
    full_event_sha256: str
    full_lossless_validated_fill_payload: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class BlockObservation:
    locator: RawBlockLocator
    source: SourceObject
    block_number: int
    block_time_exact: str
    local_time_exact: str
    ordered_event_count: int
    ordered_event_fingerprint_sha256: str
    raw_record_sha256: str
    observations: tuple[Observation, ...]

    @property
    def equality_invariants(self) -> tuple[str, int, str]:
        return (
            self.block_time_exact,
            self.ordered_event_count,
            self.ordered_event_fingerprint_sha256,
        )


def validate_wallet(value: object) -> Validation:
    label = json_type_label(value)
    token = typed_token_hex(value)
    if type(value) is not str:
        return Validation(label, token, "WALLET_SCHEMA_VIOLATION", "WALLET_WRONG_JSON_TYPE", None)
    if ADDRESS_RE.fullmatch(value) is None:
        return Validation(label, token, "WALLET_SCHEMA_VIOLATION", "WALLET_NOT_EXACT_LOWERCASE_0X40HEX", None)
    return Validation(label, token, "VALID_EXACT_LOWERCASE_0X40HEX", None, value)


def validate_tid(value: object) -> Validation:
    label = json_type_label(value)
    token = typed_token_hex(value)
    if value is MISSING:
        return Validation(label, token, "TID_SCHEMA_VIOLATION", "TID_MISSING", None)
    if isinstance(value, Decimal):
        return Validation(label, token, "TID_SCHEMA_VIOLATION", "TID_FRACTION_OR_EXPONENT_NUMBER_TOKEN_IS_NOT_A_JSON_INTEGER", None)
    if type(value) is not int:
        return Validation(label, token, "TID_SCHEMA_VIOLATION", "TID_WRONG_JSON_TYPE", None)
    if not 0 <= value < UINT50_MAX_EXCLUSIVE:
        return Validation(label, token, "TID_SCHEMA_VIOLATION", "TID_INTEGER_OUTSIDE_UINT50_RANGE", None)
    return Validation(label, token, "VALID_UINT50", None, value)


def validate_coin(value: object) -> Validation:
    label = json_type_label(value)
    token = typed_token_hex(value)
    if value is MISSING:
        return Validation(label, token, "COIN_SCHEMA_VIOLATION", "COIN_MISSING", None)
    if type(value) is not str:
        return Validation(label, token, "COIN_SCHEMA_VIOLATION", "COIN_WRONG_JSON_TYPE", None)
    if not value:
        return Validation(label, token, "COIN_SCHEMA_VIOLATION", "COIN_EMPTY_STRING", None)
    return Validation(label, token, "VALID_EXACT_RAW_NONEMPTY_STRING", None, value)


def historical_legacy_typed_tid(value: object) -> tuple[str, str] | None:
    if type(value) is int:
        return ("int", str(value))
    if isinstance(value, Decimal):
        if not value.is_finite() or value != value.to_integral_value():
            return None
        token = format(value.quantize(Decimal(1)), "f")
        return ("int", "0" if Decimal(token).is_zero() else token)
    if type(value) is str and 0 < len(value) <= 128:
        return ("str", value)
    return None


def _require_int(value: object, label: str) -> int:
    if type(value) is not int or not 0 <= value <= UINT64_MAX:
        raise R11AIdentityError(f"{label} must be uint64 JSON integer")
    return value


def _require_string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise R11AIdentityError(f"{label} must be nonempty exact string")
    return value


def parse_block_record(
    raw_record: bytes,
    *,
    source: SourceObject,
    record_ordinal_zero_based: int,
) -> BlockObservation:
    if type(raw_record) is not bytes or not raw_record or not raw_record.strip():
        raise R11AIdentityError("blank or non-byte NDJSON record")
    if raw_record.endswith(b"\n"):
        raise R11AIdentityError("record hash input must exclude LF delimiter")
    block = strict_json_loads(raw_record)
    if not isinstance(block, dict):
        raise R11AIdentityError("block wrapper must be object")
    for field in ("local_time", "block_time", "block_number", "events"):
        if field not in block:
            raise R11AIdentityError(f"block missing {field}")
    local_time = _require_string(block["local_time"], "local_time")
    block_time = _require_string(block["block_time"], "block_time")
    block_number = _require_int(block["block_number"], "block_number")
    events = block["events"]
    if not isinstance(events, list):
        raise R11AIdentityError("events must be array")
    observations: list[Observation] = []
    for event_ordinal, event in enumerate(events):
        if not isinstance(event, list) or len(event) != 2 or not isinstance(event[1], dict):
            raise R11AIdentityError("event must be [wallet, fill object]")
        wallet_raw, fill = event
        for field in ("time", "side", "px", "sz", "closedPnl", "crossed"):
            if field not in fill:
                raise R11AIdentityError(f"fill missing {field}")
        fill_time = _require_int(fill["time"], "fill.time")
        if type(fill["side"]) is not str or fill["side"] not in {"A", "B"}:
            raise R11AIdentityError("fill.side must be A or B")
        for field in ("px", "sz", "closedPnl"):
            _require_string(fill[field], f"fill.{field}")
        if type(fill["crossed"]) is not bool:
            raise R11AIdentityError("fill.crossed must be boolean")
        wallet = validate_wallet(wallet_raw)
        tid_raw = fill.get("tid", MISSING)
        coin_raw = fill.get("coin", MISSING)
        tid = validate_tid(tid_raw)
        coin = validate_coin(coin_raw)
        canonical_wallet = wallet.canonical_value if type(wallet.canonical_value) is str else None
        validated_tid = tid.canonical_value if type(tid.canonical_value) is int else None
        exact_coin = coin.canonical_value if type(coin.canonical_value) is str else None
        legacy_tid = historical_legacy_typed_tid(tid_raw)
        legacy_key = (canonical_wallet, legacy_tid) if canonical_wallet is not None and legacy_tid is not None else None
        trade_identity = (block_time, exact_coin, validated_tid) if exact_coin is not None and validated_tid is not None else None
        wallet_identity = (
            (canonical_wallet, block_time, exact_coin, validated_tid)
            if canonical_wallet is not None and exact_coin is not None and validated_tid is not None
            else None
        )
        selected = [
            "SELECTED_FILL_V1",
            [[field, field in fill, fill[field] if field in fill else None] for field in SELECTED_FILL_FIELD_ORDER],
        ]
        locator = RawObservationLocator(
            source.object_key,
            source.compressed_sha256,
            record_ordinal_zero_based,
            event_ordinal,
        )
        observations.append(
            Observation(
                locator=locator,
                source=source,
                block_number=block_number,
                block_time_exact=block_time,
                local_time_exact=local_time,
                raw_wallet_address=wallet_raw if type(wallet_raw) is str else None,
                raw_wallet_json_type=wallet.raw_json_type,
                raw_wallet_token=wallet.raw_token,
                wallet_validation_status=wallet.status,
                wallet_schema_violation_reason=wallet.reason,
                canonical_lowercase_wallet_address=canonical_wallet,
                raw_tid_json_type=tid.raw_json_type,
                raw_tid_token=tid.raw_token,
                tid_validation_status=tid.status,
                tid_schema_violation_reason=tid.reason,
                validated_integer_tid=validated_tid,
                raw_coin_json_type=coin.raw_json_type,
                raw_coin_token=coin.raw_token,
                coin_validation_status=coin.status,
                coin_schema_violation_reason=coin.reason,
                exact_raw_coin_string=exact_coin,
                legacy_weak_key=legacy_key,
                protocol_trade_identity=trade_identity,
                wallet_fill_identity=wallet_identity,
                side_exact=fill["side"],
                fill_time_exact=fill_time,
                crossed_exact=fill["crossed"],
                selected_fill_sha256=canonical_sha256(selected),
                full_fill_sha256=canonical_sha256(["FULL_FILL_V1", fill]),
                full_event_sha256=canonical_sha256(["FULL_EVENT_V1", True, wallet_raw, fill]),
                full_lossless_validated_fill_payload=dict(fill),
            )
        )
    locator = RawBlockLocator(source.object_key, source.compressed_sha256, record_ordinal_zero_based)
    return BlockObservation(
        locator=locator,
        source=source,
        block_number=block_number,
        block_time_exact=block_time,
        local_time_exact=local_time,
        ordered_event_count=len(events),
        ordered_event_fingerprint_sha256=canonical_sha256(["ORDERED_EVENT_VECTOR_V1", events]),
        raw_record_sha256=hashlib.sha256(raw_record).hexdigest(),
        observations=tuple(observations),
    )


def flatten_observations(blocks: Iterable[BlockObservation]) -> tuple[Observation, ...]:
    rows = sorted((row for block in blocks for row in block.observations), key=lambda row: row.locator)
    if len({row.locator for row in rows}) != len(rows):
        raise R11AIdentityError("duplicate raw observation locator")
    return tuple(rows)


def first_diffmask(first: Observation, current: Observation) -> dict[str, bool]:
    additional_first = set(first.full_lossless_validated_fill_payload) - set(SELECTED_FILL_FIELD_ORDER)
    additional_current = set(current.full_lossless_validated_fill_payload) - set(SELECTED_FILL_FIELD_ORDER)
    return {
        "raw_wallet_typed_value_differs": (first.raw_wallet_json_type, first.raw_wallet_token) != (current.raw_wallet_json_type, current.raw_wallet_token),
        "coin_typed_value_or_presence_differs": (first.raw_coin_json_type, first.raw_coin_token) != (current.raw_coin_json_type, current.raw_coin_token),
        "tid_typed_value_or_presence_differs": (first.raw_tid_json_type, first.raw_tid_token) != (current.raw_tid_json_type, current.raw_tid_token),
        "time_differs": first.fill_time_exact != current.fill_time_exact,
        "side_differs": first.side_exact != current.side_exact,
        "px_differs": first.full_lossless_validated_fill_payload["px"] != current.full_lossless_validated_fill_payload["px"],
        "sz_differs": first.full_lossless_validated_fill_payload["sz"] != current.full_lossless_validated_fill_payload["sz"],
        "closedPnl_differs": first.full_lossless_validated_fill_payload["closedPnl"] != current.full_lossless_validated_fill_payload["closedPnl"],
        "crossed_differs": first.crossed_exact != current.crossed_exact,
        "liquidation_differs": first.full_lossless_validated_fill_payload.get("liquidation", MISSING) != current.full_lossless_validated_fill_payload.get("liquidation", MISSING),
        "additional_fill_field_set_or_value_differs": additional_first != additional_current or any(
            first.full_lossless_validated_fill_payload[key] != current.full_lossless_validated_fill_payload[key]
            for key in additional_first & additional_current
        ),
        "full_fill_sha256_differs": first.full_fill_sha256 != current.full_fill_sha256,
        "full_event_sha256_differs": first.full_event_sha256 != current.full_event_sha256,
        "raw_block_locator_differs": first.locator.block_locator != current.locator.block_locator,
        "block_number_differs": first.block_number != current.block_number,
        "wrapper_block_time_exact_differs": first.block_time_exact != current.block_time_exact,
        "local_time_exact_differs": first.local_time_exact != current.local_time_exact,
    }


def validate_golden_vectors() -> None:
    vectors = (
        (None, "4e", "8ce86a6ae65d3692e7305e2c58ac62eebd97d3d943e093f577da25c36988246b"),
        (True, "4231", "5b950e77941d01cdf246d00b1ece546bc95234b77d98b44c9187e2733afa696a"),
        (-12, "49333a2d3132", "2eedfdf36c487caa7457f94b188ac00bc3b1d196a5514ae372f770c67ea8b9ce"),
        (Decimal("1.2300"), "44363a313233652d32", "99aa0166b53ea1512ad81c91e5e261960cbb2d65ea8fd33fc01555883525e558"),
        ("é", "53323ac3a9", "52669a268b3de8bd030d5dca3e0171b22b253b2ac8ccc8a7a238985fe419e171"),
        ([1, "x"], "4c313a32343a49313a31343a53313a78", "5f7bb65918827caad1305f9ec7283105338fcc89daa21b36d43629a79331b086"),
        ({"b": 2, "a": 1}, "4d313a32343a53313a61343a49313a31343a53313a62343a49313a32", "eabf326e40ac5de0e41e7c9fd6d87081399c11b576619c71e797b9cb46e35916"),
    )
    for value, expected_hex, expected_sha in vectors:
        encoded = canonical_typed_bytes(value)
        if encoded.hex() != expected_hex or hashlib.sha256(encoded).hexdigest() != expected_sha:
            raise R11AIdentityError(f"canonical golden vector mismatch: {value!r}")


validate_golden_vectors()
