from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence

from .canonical import (
    CanonicalError,
    JsonNumber,
    canonical_json_bytes,
    decimal_fixed_token,
    sha256_hex,
    strict_json_loads,
    typed_bytes,
    validate_sha256,
)

WALLET_RE = re.compile(r"0x[0-9a-f]{40}\Z")
UINT50_MAX = 1 << 50
UINT64_MAX = (1 << 64) - 1


class ModelError(ValueError):
    pass


_MISSING = object()


@dataclass(frozen=True, slots=True, order=True)
class SourceObject:
    object_ordinal_zero_based: int
    object_key: str
    compressed_sha256: str
    path_hour_utc: str

    def __post_init__(self) -> None:
        if self.object_ordinal_zero_based < 0:
            raise ModelError("negative object ordinal")
        if not self.object_key:
            raise ModelError("empty object key")
        validate_sha256(self.compressed_sha256)
        if len(self.path_hour_utc) < 13:
            raise ModelError("invalid path hour")


@dataclass(frozen=True, slots=True, order=True)
class RawBlockLocator:
    source_object_key: str
    compressed_object_sha256: str
    record_ordinal_zero_based: int

    def as_mapping(self) -> dict[str, object]:
        return {
            "source_object_key": self.source_object_key,
            "compressed_object_sha256": self.compressed_object_sha256,
            "record_ordinal_zero_based": self.record_ordinal_zero_based,
        }


@dataclass(frozen=True, slots=True, order=True)
class RawObservationLocator:
    source_object_key: str
    compressed_object_sha256: str
    record_ordinal_zero_based: int
    event_ordinal_zero_based: int

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
class Observation:
    locator: RawObservationLocator
    source: SourceObject
    block_number: int
    local_time_exact: str
    block_time_exact: str
    raw_wallet_json_type: str
    raw_wallet_token: str | None
    raw_wallet_address: str | None
    wallet_validation_status: str
    wallet_schema_violation_reason: str | None
    canonical_lowercase_wallet_address: str | None
    raw_tid_json_type: str
    raw_tid_token: str | None
    tid_validation_status: str
    tid_schema_violation_reason: str | None
    validated_integer_tid: int | None
    normalized_typed_tid: tuple[str, str] | None
    raw_coin_json_type: str
    raw_coin_token: str | None
    coin_validation_status: str
    coin_schema_violation_reason: str | None
    exact_raw_coin_string: str | None
    fill_time_exact: int
    side_exact: str
    crossed_exact: bool
    selected_fill_sha256: str
    full_fill_sha256: str
    full_event_sha256: str
    full_fill_canonical_bytes: bytes
    full_event_canonical_bytes: bytes

    @property
    def protocol_trade_identity(self) -> tuple[str, str, int] | None:
        if (
            self.tid_validation_status == "VALID_UINT50"
            and self.coin_validation_status == "VALID_EXACT_RAW_NONEMPTY_STRING"
            and self.validated_integer_tid is not None
            and self.exact_raw_coin_string is not None
        ):
            return (
                self.block_time_exact,
                self.exact_raw_coin_string,
                self.validated_integer_tid,
            )
        return None

    @property
    def wallet_fill_identity(self) -> tuple[str, str, str, int] | None:
        protocol = self.protocol_trade_identity
        if (
            protocol is not None
            and self.wallet_validation_status == "VALID_EXACT_LOWERCASE_0X40HEX"
            and self.canonical_lowercase_wallet_address is not None
        ):
            return (self.canonical_lowercase_wallet_address, *protocol)
        return None

    @property
    def legacy_weak_key(self) -> tuple[str, tuple[str, str]] | None:
        if (
            self.wallet_validation_status == "VALID_EXACT_LOWERCASE_0X40HEX"
            and self.canonical_lowercase_wallet_address is not None
            and self.normalized_typed_tid is not None
        ):
            return (self.canonical_lowercase_wallet_address, self.normalized_typed_tid)
        return None


@dataclass(frozen=True, slots=True)
class BlockObservation:
    locator: RawBlockLocator
    source: SourceObject
    block_number: int
    local_time_exact: str
    block_time_exact: str
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


def _json_type_and_token(value: object) -> tuple[str, str | None]:
    if value is _MISSING:
        return "MISSING", None
    if value is None:
        return "NULL", typed_bytes(None).hex()
    if isinstance(value, bool):
        return "BOOLEAN", typed_bytes(value).hex()
    if isinstance(value, int):
        return "INTEGER", typed_bytes(value).hex()
    if isinstance(value, JsonNumber):
        return "NUMBER_FRACTION_OR_EXPONENT_TOKEN", typed_bytes(value).hex()
    if isinstance(value, str):
        return "STRING", typed_bytes(value).hex()
    if isinstance(value, list):
        return "ARRAY", typed_bytes(value).hex()
    if isinstance(value, dict):
        return "OBJECT", typed_bytes(value).hex()
    raise ModelError(f"unsupported parsed JSON type: {type(value).__name__}")


def _validate_wallet(value: object) -> tuple[str, str | None, str | None, str, str | None]:
    json_type, token = _json_type_and_token(value)
    raw = value if isinstance(value, str) else None
    if not isinstance(value, str):
        return json_type, token, raw, "WALLET_SCHEMA_VIOLATION", "WALLET_WRONG_JSON_TYPE"
    if not WALLET_RE.fullmatch(value):
        return json_type, token, raw, "WALLET_SCHEMA_VIOLATION", "WALLET_NOT_EXACT_LOWERCASE_0X40HEX"
    return json_type, token, raw, "VALID_EXACT_LOWERCASE_0X40HEX", None


def _validate_coin(value: object) -> tuple[str, str | None, str | None, str, str | None]:
    json_type, token = _json_type_and_token(value)
    if value is _MISSING:
        return json_type, token, None, "COIN_SCHEMA_VIOLATION", "COIN_MISSING"
    if not isinstance(value, str):
        return json_type, token, None, "COIN_SCHEMA_VIOLATION", "COIN_WRONG_JSON_TYPE"
    if value == "":
        return json_type, token, value, "COIN_SCHEMA_VIOLATION", "COIN_EMPTY_STRING"
    return json_type, token, value, "VALID_EXACT_RAW_NONEMPTY_STRING", None


def _historical_typed_tid(value: object) -> tuple[str, str] | None:
    if isinstance(value, bool) or value is None or value is _MISSING:
        return None
    if isinstance(value, int):
        return ("int", str(value))
    if isinstance(value, JsonNumber):
        try:
            return ("int", decimal_fixed_token(value.value))
        except CanonicalError:
            return None
    if isinstance(value, str) and 0 < len(value) <= 128:
        return ("str", value)
    return None


def _validate_tid(value: object) -> tuple[str, str | None, str, str | None, int | None, tuple[str, str] | None]:
    json_type, token = _json_type_and_token(value)
    legacy = _historical_typed_tid(value)
    if value is _MISSING:
        return json_type, token, "TID_SCHEMA_VIOLATION", "TID_MISSING", None, legacy
    if not isinstance(value, int) or isinstance(value, bool):
        reason = (
            "TID_FRACTION_OR_EXPONENT_NUMBER_TOKEN_IS_NOT_A_JSON_INTEGER"
            if isinstance(value, JsonNumber)
            else "TID_WRONG_JSON_TYPE"
        )
        return json_type, token, "TID_SCHEMA_VIOLATION", reason, None, legacy
    if value < 0 or value >= UINT50_MAX:
        return json_type, token, "TID_SCHEMA_VIOLATION", "TID_INTEGER_OUTSIDE_UINT50_RANGE", None, legacy
    return json_type, token, "VALID_UINT50", None, value, legacy


def _require_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ModelError(f"{label} must be a JSON object")
    return value


def _require_int(value: object, label: str, maximum: int = UINT64_MAX) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not (0 <= value <= maximum):
        raise ModelError(f"{label} must be an unsigned JSON integer")
    return value


def _require_nonempty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ModelError(f"{label} must be a non-empty string")
    return value


def parse_block_record(raw_record: bytes, source: SourceObject, record_ordinal_zero_based: int) -> BlockObservation:
    root = _require_mapping(strict_json_loads(raw_record), "block wrapper")
    for field in ("local_time", "block_time", "block_number", "events"):
        if field not in root:
            raise ModelError(f"missing wrapper field: {field}")
    local_time = _require_nonempty_string(root["local_time"], "local_time")
    block_time = _require_nonempty_string(root["block_time"], "block_time")
    block_number = _require_int(root["block_number"], "block_number")
    events = root["events"]
    if not isinstance(events, list):
        raise ModelError("events must be an ordered array")
    block_locator = RawBlockLocator(
        source.object_key,
        source.compressed_sha256,
        record_ordinal_zero_based,
    )
    observations: list[Observation] = []
    ordered_event_hashes: list[str] = []
    for event_ordinal, event in enumerate(events):
        if not isinstance(event, list) or len(event) != 2:
            raise ModelError("event must be exact two-element array")
        wallet_value, fill_value = event
        fill = _require_mapping(fill_value, "fill")
        for field in ("time", "side", "px", "sz", "closedPnl", "crossed"):
            if field not in fill:
                raise ModelError(f"missing required fill field: {field}")
        fill_time = _require_int(fill["time"], "fill.time")
        side = fill["side"]
        if side not in ("A", "B"):
            raise ModelError("fill.side must be exact A or B")
        for field in ("px", "sz", "closedPnl"):
            _require_nonempty_string(fill[field], f"fill.{field}")
        crossed = fill["crossed"]
        if not isinstance(crossed, bool):
            raise ModelError("fill.crossed must be a JSON boolean")

        wallet_json_type, wallet_token, raw_wallet, wallet_status, wallet_reason = _validate_wallet(wallet_value)
        tid_value = fill.get("tid", _MISSING)
        tid_json_type, tid_token, tid_status, tid_reason, tid_int, legacy_tid = _validate_tid(tid_value)
        coin_value = fill.get("coin", _MISSING)
        coin_json_type, coin_token, coin_string, coin_status, coin_reason = _validate_coin(coin_value)

        fill_bytes = canonical_json_bytes(fill)
        event_bytes = canonical_json_bytes(event)
        selected = {
            "coin": coin_value if coin_value is not _MISSING else None,
            "side": side,
            "time": fill_time,
            "px": fill["px"],
            "sz": fill["sz"],
            "closedPnl": fill["closedPnl"],
            "tid": tid_value if tid_value is not _MISSING else None,
            "crossed": crossed,
            "liquidation_present": "liquidation" in fill,
            "liquidation": fill.get("liquidation"),
        }
        locator = RawObservationLocator(
            source.object_key,
            source.compressed_sha256,
            record_ordinal_zero_based,
            event_ordinal,
        )
        full_event_hash = sha256_hex(event_bytes)
        ordered_event_hashes.append(full_event_hash)
        observations.append(
            Observation(
                locator=locator,
                source=source,
                block_number=block_number,
                local_time_exact=local_time,
                block_time_exact=block_time,
                raw_wallet_json_type=wallet_json_type,
                raw_wallet_token=wallet_token,
                raw_wallet_address=raw_wallet,
                wallet_validation_status=wallet_status,
                wallet_schema_violation_reason=wallet_reason,
                canonical_lowercase_wallet_address=(raw_wallet if wallet_reason is None else None),
                raw_tid_json_type=tid_json_type,
                raw_tid_token=tid_token,
                tid_validation_status=tid_status,
                tid_schema_violation_reason=tid_reason,
                validated_integer_tid=tid_int,
                normalized_typed_tid=legacy_tid,
                raw_coin_json_type=coin_json_type,
                raw_coin_token=coin_token,
                coin_validation_status=coin_status,
                coin_schema_violation_reason=coin_reason,
                exact_raw_coin_string=coin_string,
                fill_time_exact=fill_time,
                side_exact=side,
                crossed_exact=crossed,
                selected_fill_sha256=sha256_hex(canonical_json_bytes(selected)),
                full_fill_sha256=sha256_hex(fill_bytes),
                full_event_sha256=full_event_hash,
                full_fill_canonical_bytes=fill_bytes,
                full_event_canonical_bytes=event_bytes,
            )
        )
    ordered_fingerprint = sha256_hex(
        b"R11A_ORDERED_EVENT_VECTOR_V2\x00"
        + b"".join(bytes.fromhex(item) for item in ordered_event_hashes)
    )
    return BlockObservation(
        locator=block_locator,
        source=source,
        block_number=block_number,
        local_time_exact=local_time,
        block_time_exact=block_time,
        ordered_event_count=len(observations),
        ordered_event_fingerprint_sha256=ordered_fingerprint,
        raw_record_sha256=hashlib.sha256(raw_record).hexdigest(),
        observations=tuple(observations),
    )


def flatten_observations(blocks: Sequence[BlockObservation]) -> tuple[Observation, ...]:
    rows = [row for block in blocks for row in block.observations]
    rows.sort(key=lambda row: row.locator)
    if len({row.locator for row in rows}) != len(rows):
        raise ModelError("duplicate raw observation locator")
    return tuple(rows)
