from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any

UINT50_MAX_EXCLUSIVE = 1 << 50
UINT64_MAX = (1 << 64) - 1
ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SELECTED_FILL_FIELD_ORDER = (
    "coin",
    "tid",
    "time",
    "side",
    "px",
    "sz",
    "closedPnl",
    "crossed",
    "liquidation",
)
CANONICAL_SERIALIZATION_VERSION = "R11A_V2_CANONICAL_TYPED_FIELDS_V1"
MAX_DEPTH = 128
MAX_LEGACY_TID_CHARS = 128


class R11AV2IdentityError(ValueError):
    """Raised when lossless parsing or identity construction fails closed."""


class _Missing:
    __slots__ = ()


MISSING = _Missing()


class FrozenDict(Mapping[str, object]):
    """Deeply immutable mapping with canonical UTF-8 key order."""

    __slots__ = ("_items", "_index")

    def __init__(self, items: Mapping[str, object] | Iterator[tuple[str, object]]) -> None:
        pairs = list(items.items()) if isinstance(items, Mapping) else list(items)
        if any(type(key) is not str for key, _ in pairs):
            raise R11AV2IdentityError("frozen mapping keys must be strings")
        keys = [key for key, _ in pairs]
        if len(keys) != len(set(keys)):
            raise R11AV2IdentityError("duplicate frozen mapping key")
        pairs.sort(key=lambda pair: pair[0].encode("utf-8", errors="strict"))
        self._items = tuple((key, deep_freeze(value)) for key, value in pairs)
        self._index = MappingProxyType({key: value for key, value in self._items})

    def __getitem__(self, key: str) -> object:
        return self._index[key]

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def items(self) -> tuple[tuple[str, object], ...]:  # type: ignore[override]
        return self._items

    def to_plain(self) -> dict[str, object]:
        return {key: thaw_json(value) for key, value in self._items}


def deep_freeze(value: object, *, _depth: int = 0, _seen: set[int] | None = None) -> object:
    if _depth > MAX_DEPTH:
        raise R11AV2IdentityError("JSON depth exceeds 128")
    if value is None or type(value) in {bool, int, str, bytes} or isinstance(value, Decimal):
        return value
    if type(value) is float:
        raise R11AV2IdentityError("binary float forbidden")
    seen = set() if _seen is None else _seen
    if isinstance(value, (dict, list, tuple, FrozenDict)):
        object_id = id(value)
        if object_id in seen:
            raise R11AV2IdentityError("cycle forbidden")
        seen.add(object_id)
        try:
            if isinstance(value, FrozenDict):
                return value
            if isinstance(value, dict):
                return FrozenDict((key, deep_freeze(item, _depth=_depth + 1, _seen=seen)) for key, item in value.items())
            return tuple(deep_freeze(item, _depth=_depth + 1, _seen=seen) for item in value)
        finally:
            seen.remove(object_id)
    raise R11AV2IdentityError(f"unsupported JSON value: {type(value).__name__}")


def thaw_json(value: object) -> object:
    if isinstance(value, FrozenDict):
        return value.to_plain()
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise R11AV2IdentityError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json_loads(raw: bytes | str) -> object:
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise R11AV2IdentityError("strict UTF-8 decode failed") from exc
    elif type(raw) is str:
        text = raw
    else:
        raise R11AV2IdentityError("strict_json_loads requires bytes or str")

    def reject_constant(token: str) -> object:
        raise R11AV2IdentityError(f"non-finite JSON constant: {token}")

    try:
        return json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_int=int,
            parse_float=Decimal,
            parse_constant=reject_constant,
        )
    except (json.JSONDecodeError, InvalidOperation) as exc:
        raise R11AV2IdentityError(f"strict JSON parse failure: {exc}") from exc


def _frame(value: bytes) -> bytes:
    return str(len(value)).encode("ascii") + b":" + value


def _decimal_token(value: Decimal) -> bytes:
    if not value.is_finite():
        raise R11AV2IdentityError("non-finite Decimal forbidden")
    if value.is_zero():
        return b"0"
    sign, digits, exponent = value.as_tuple()
    mutable = list(digits)
    while mutable and mutable[-1] == 0:
        mutable.pop()
        exponent += 1
    coefficient = "".join(str(digit) for digit in mutable)
    if sign:
        coefficient = "-" + coefficient
    return coefficient.encode("ascii") + b"e" + str(exponent).encode("ascii")


def canonical_typed_bytes(
    value: object,
    *,
    _depth: int = 0,
    _seen: set[int] | None = None,
) -> bytes:
    if _depth > MAX_DEPTH:
        raise R11AV2IdentityError("canonical serialization depth exceeds 128")
    if value is MISSING:
        raise R11AV2IdentityError("MISSING requires an explicit presence flag")
    if value is None:
        return b"N"
    if type(value) is bool:
        return b"B1" if value else b"B0"
    if type(value) is int:
        return b"I" + _frame(str(value).encode("ascii"))
    if isinstance(value, Decimal):
        return b"D" + _frame(_decimal_token(value))
    if type(value) is float:
        raise R11AV2IdentityError("binary float forbidden")
    if type(value) is str:
        try:
            return b"S" + _frame(value.encode("utf-8", errors="strict"))
        except UnicodeEncodeError as exc:
            raise R11AV2IdentityError("invalid Unicode string") from exc
    if type(value) is bytes:
        return b"Y" + _frame(value)

    seen = set() if _seen is None else _seen
    if isinstance(value, (list, tuple, Mapping)):
        object_id = id(value)
        if object_id in seen:
            raise R11AV2IdentityError("cycle forbidden")
        seen.add(object_id)
        try:
            if isinstance(value, (list, tuple)):
                encoded = b"".join(
                    _frame(canonical_typed_bytes(item, _depth=_depth + 1, _seen=seen))
                    for item in value
                )
                prefix = b"L" if isinstance(value, list) else b"T"
                return prefix + _frame(str(len(value)).encode("ascii")) + encoded
            pairs: list[tuple[bytes, bytes]] = []
            for key, item in value.items():
                if type(key) is not str:
                    raise R11AV2IdentityError("mapping keys must be strings")
                key_bytes = canonical_typed_bytes(key, _depth=_depth + 1, _seen=seen)
                item_bytes = canonical_typed_bytes(item, _depth=_depth + 1, _seen=seen)
                pairs.append((key_bytes, item_bytes))
            pairs.sort(key=lambda pair: pair[0])
            encoded = b"".join(_frame(key) + _frame(item) for key, item in pairs)
            return b"M" + _frame(str(len(pairs)).encode("ascii")) + encoded
        finally:
            seen.remove(object_id)
    raise R11AV2IdentityError(f"unsupported canonical type: {type(value).__name__}")


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
    raise R11AV2IdentityError(f"unsupported parsed type: {type(value).__name__}")


def typed_token_hex(value: object) -> str | None:
    return None if value is MISSING else canonical_typed_bytes(value).hex()


def _integral_decimal_token(value: Decimal) -> str | None:
    """Return the historical integer spelling without context-dependent quantize()."""
    if not value.is_finite() or value != value.to_integral_value():
        return None
    if value.is_zero():
        return "0"
    sign, digits, exponent = value.as_tuple()
    raw = "".join(str(digit) for digit in digits)
    if exponent >= 0:
        length = len(raw) + exponent
        if length > MAX_LEGACY_TID_CHARS:
            return None
        token = raw + "0" * exponent
    else:
        split = len(raw) + exponent
        if split <= 0:
            return None
        if any(char != "0" for char in raw[split:]):
            return None
        token = raw[:split]
    token = token.lstrip("0") or "0"
    if token != "0" and sign:
        token = "-" + token
    return token if len(token) <= MAX_LEGACY_TID_CHARS else None


@dataclass(frozen=True, slots=True)
class Validation:
    raw_json_type: str
    raw_token: str | None
    status: str
    reason: str | None
    canonical_value: object | None


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
        token = str(value)
        return ("int", token) if len(token) <= MAX_LEGACY_TID_CHARS else None
    if isinstance(value, Decimal):
        token = _integral_decimal_token(value)
        return None if token is None else ("int", token)
    if type(value) is str and 0 < len(value) <= MAX_LEGACY_TID_CHARS:
        return ("str", value)
    return None


@dataclass(frozen=True, order=True, slots=True)
class SourceObject:
    object_ordinal_zero_based: int
    object_key: str
    compressed_sha256: str
    path_hour_utc: str

    def __post_init__(self) -> None:
        if type(self.object_ordinal_zero_based) is not int or self.object_ordinal_zero_based < 0:
            raise R11AV2IdentityError("object ordinal invalid")
        if type(self.object_key) is not str or not self.object_key:
            raise R11AV2IdentityError("object key invalid")
        if SHA256_RE.fullmatch(self.compressed_sha256) is None:
            raise R11AV2IdentityError("compressed SHA invalid")
        if type(self.path_hour_utc) is not str or len(self.path_hour_utc) != 20 or not self.path_hour_utc.endswith(":00:00Z"):
            raise R11AV2IdentityError("path hour invalid")


@dataclass(frozen=True, order=True, slots=True)
class RawBlockLocator:
    source_object_key: str
    compressed_object_sha256: str
    record_ordinal_zero_based: int

    def __post_init__(self) -> None:
        if not self.source_object_key:
            raise R11AV2IdentityError("raw block object key invalid")
        if SHA256_RE.fullmatch(self.compressed_object_sha256) is None:
            raise R11AV2IdentityError("raw block compressed SHA invalid")
        if type(self.record_ordinal_zero_based) is not int or self.record_ordinal_zero_based < 0:
            raise R11AV2IdentityError("record ordinal invalid")

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
        RawBlockLocator(self.source_object_key, self.compressed_object_sha256, self.record_ordinal_zero_based)
        if type(self.event_ordinal_zero_based) is not int or self.event_ordinal_zero_based < 0:
            raise R11AV2IdentityError("event ordinal invalid")

    @property
    def block_locator(self) -> RawBlockLocator:
        return RawBlockLocator(self.source_object_key, self.compressed_object_sha256, self.record_ordinal_zero_based)

    def as_mapping(self) -> dict[str, object]:
        return {
            "source_object_key": self.source_object_key,
            "compressed_object_sha256": self.compressed_object_sha256,
            "record_ordinal_zero_based": self.record_ordinal_zero_based,
            "event_ordinal_zero_based": self.event_ordinal_zero_based,
        }


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
    full_lossless_validated_fill_payload: FrozenDict


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
        return (self.block_time_exact, self.ordered_event_count, self.ordered_event_fingerprint_sha256)


def _require_uint64(value: object, label: str) -> int:
    if type(value) is not int or not 0 <= value <= UINT64_MAX:
        raise R11AV2IdentityError(f"{label} must be a uint64 JSON integer")
    return value


def _require_nonempty_string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise R11AV2IdentityError(f"{label} must be a nonempty string")
    return value


def parse_block_record(
    raw_record: bytes,
    *,
    source: SourceObject,
    record_ordinal_zero_based: int,
) -> BlockObservation:
    if type(raw_record) is not bytes or not raw_record or not raw_record.strip():
        raise R11AV2IdentityError("blank or non-byte NDJSON record")
    if raw_record.endswith(b"\n"):
        raise R11AV2IdentityError("record bytes must exclude LF delimiter")
    block = strict_json_loads(raw_record)
    if not isinstance(block, dict):
        raise R11AV2IdentityError("block wrapper must be object")
    required_block_fields = ("local_time", "block_time", "block_number", "events")
    if any(field not in block for field in required_block_fields):
        raise R11AV2IdentityError("block wrapper missing required field")
    local_time = _require_nonempty_string(block["local_time"], "local_time")
    block_time = _require_nonempty_string(block["block_time"], "block_time")
    block_number = _require_uint64(block["block_number"], "block_number")
    events = block["events"]
    if not isinstance(events, list):
        raise R11AV2IdentityError("events must be an array")

    observations: list[Observation] = []
    for event_ordinal, event in enumerate(events):
        if not isinstance(event, list) or len(event) != 2 or not isinstance(event[1], dict):
            raise R11AV2IdentityError("event must be [wallet, fill object]")
        wallet_raw, fill = event
        for field in ("time", "side", "px", "sz", "closedPnl", "crossed"):
            if field not in fill:
                raise R11AV2IdentityError(f"fill missing required field: {field}")
        fill_time = _require_uint64(fill["time"], "fill.time")
        side = fill["side"]
        if type(side) is not str or side not in {"A", "B"}:
            raise R11AV2IdentityError("fill.side must be A or B")
        for field in ("px", "sz", "closedPnl"):
            _require_nonempty_string(fill[field], f"fill.{field}")
        crossed = fill["crossed"]
        if type(crossed) is not bool:
            raise R11AV2IdentityError("fill.crossed must be boolean")

        wallet = validate_wallet(wallet_raw)
        tid_raw = fill.get("tid", MISSING)
        coin_raw = fill.get("coin", MISSING)
        tid = validate_tid(tid_raw)
        coin = validate_coin(coin_raw)
        canonical_wallet = wallet.canonical_value if type(wallet.canonical_value) is str else None
        validated_tid = tid.canonical_value if type(tid.canonical_value) is int else None
        exact_coin = coin.canonical_value if type(coin.canonical_value) is str else None
        historical_tid = historical_legacy_typed_tid(tid_raw)
        legacy_key = (
            (canonical_wallet, historical_tid)
            if canonical_wallet is not None and historical_tid is not None
            else None
        )
        protocol_identity = (
            (block_time, exact_coin, validated_tid)
            if exact_coin is not None and validated_tid is not None
            else None
        )
        wallet_identity = (
            (canonical_wallet, block_time, exact_coin, validated_tid)
            if canonical_wallet is not None and exact_coin is not None and validated_tid is not None
            else None
        )
        selected = [
            "SELECTED_FILL_V2",
            [[field, field in fill, fill[field] if field in fill else None] for field in SELECTED_FILL_FIELD_ORDER],
        ]
        frozen_fill = deep_freeze(fill)
        if not isinstance(frozen_fill, FrozenDict):
            raise R11AV2IdentityError("frozen fill payload is not a mapping")
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
                protocol_trade_identity=protocol_identity,
                wallet_fill_identity=wallet_identity,
                side_exact=side,
                fill_time_exact=fill_time,
                crossed_exact=crossed,
                selected_fill_sha256=canonical_sha256(selected),
                full_fill_sha256=canonical_sha256(["FULL_FILL_V2", frozen_fill]),
                full_event_sha256=canonical_sha256(["FULL_EVENT_V2", wallet_raw, frozen_fill]),
                full_lossless_validated_fill_payload=frozen_fill,
            )
        )

    locator = RawBlockLocator(source.object_key, source.compressed_sha256, record_ordinal_zero_based)
    frozen_events = deep_freeze(events)
    return BlockObservation(
        locator=locator,
        source=source,
        block_number=block_number,
        block_time_exact=block_time,
        local_time_exact=local_time,
        ordered_event_count=len(events),
        ordered_event_fingerprint_sha256=canonical_sha256(["ORDERED_EVENT_VECTOR_V2", frozen_events]),
        raw_record_sha256=hashlib.sha256(raw_record).hexdigest(),
        observations=tuple(observations),
    )


def locator_sort_key(locator: RawObservationLocator) -> tuple[bytes, bytes, int, int]:
    return (
        locator.source_object_key.encode("utf-8", errors="strict"),
        bytes.fromhex(locator.compressed_object_sha256),
        locator.record_ordinal_zero_based,
        locator.event_ordinal_zero_based,
    )


def block_locator_sort_key(locator: RawBlockLocator) -> tuple[bytes, bytes, int]:
    return (
        locator.source_object_key.encode("utf-8", errors="strict"),
        bytes.fromhex(locator.compressed_object_sha256),
        locator.record_ordinal_zero_based,
    )


def validate_golden_vectors() -> None:
    vectors = (
        (None, "4e"),
        (True, "4231"),
        (-12, "49333a2d3132"),
        (Decimal("1.2300"), "44363a313233652d32"),
        ("é", "53323ac3a9"),
        ([1, "x"], "4c313a32343a49313a31343a53313a78"),
        ({"b": 2, "a": 1}, "4d313a32343a53313a61343a49313a31343a53313a62343a49313a32"),
    )
    for value, expected_hex in vectors:
        if canonical_typed_bytes(value).hex() != expected_hex:
            raise R11AV2IdentityError(f"canonical golden vector mismatch: {value!r}")
    if historical_legacy_typed_tid(Decimal("1E+1000")) is not None:
        raise R11AV2IdentityError("oversize historical Decimal token was not rejected")
    if historical_legacy_typed_tid(Decimal("1000.000")) != ("int", "1000"):
        raise R11AV2IdentityError("integral Decimal historical normalization drift")


validate_golden_vectors()
