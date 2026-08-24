from __future__ import annotations

import dataclasses
import hashlib
import re
import struct
from collections.abc import Mapping
from typing import Final

from .canonical import (
    CanonicalJSONError,
    FrozenObject,
    FrozenValue,
    NumberToken,
    canonical_json_bytes,
    historical_legacy_typed_tid,
)

_WALLET_RE: Final[re.Pattern[str]] = re.compile(r"0x[0-9a-f]{40}\Z")
_MAX_COIN_BYTES: Final[int] = 256
_MAX_TIME_BYTES: Final[int] = 128
_MAX_SIDE_BYTES: Final[int] = 32
_MAX_TID_EXCLUSIVE: Final[int] = 1 << 50


class IdentityError(ValueError):
    pass


def sha256_bytes(value: bytes) -> bytes:
    return hashlib.sha256(value).digest()


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def frame(*parts: bytes) -> bytes:
    output = bytearray()
    for part in parts:
        if len(part) > 0xFFFFFFFF:
            raise IdentityError("identity component exceeds uint32 framing")
        output.extend(struct.pack(">I", len(part)))
        output.extend(part)
    return bytes(output)


def _require_text(value: FrozenValue | None, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise IdentityError(f"{label} must be a JSON string")
    encoded = value.encode("utf-8", "strict")
    if not encoded or len(encoded) > maximum:
        raise IdentityError(f"{label} length is outside the frozen bound")
    return value


def _require_uint_token(value: FrozenValue | None, label: str, bits: int) -> int:
    if not isinstance(value, NumberToken) or not value.is_integer_token:
        raise IdentityError(f"{label} must be a lexical JSON integer")
    parsed = int(value.token, 10)
    if parsed < 0 or parsed >= (1 << bits):
        raise IdentityError(f"{label} is outside uint{bits}")
    return parsed


def _optional_mapping_value(mapping: FrozenObject, key: str) -> FrozenValue | None:
    try:
        return mapping[key]
    except KeyError:
        return None


@dataclasses.dataclass(frozen=True, slots=True, order=True)
class RawBlockLocator:
    object_key: str
    verified_compressed_sha256: str
    decompressed_record_ordinal_zero_based: int

    def __post_init__(self) -> None:
        if not self.object_key or self.object_key.startswith("/") or ".." in self.object_key.split("/"):
            raise IdentityError("unsafe object key")
        if re.fullmatch(r"[0-9a-f]{64}", self.verified_compressed_sha256) is None:
            raise IdentityError("compressed SHA-256 must be lowercase hexadecimal")
        if self.decompressed_record_ordinal_zero_based < 0:
            raise IdentityError("record ordinal must be nonnegative")

    def key_bytes(self) -> bytes:
        return frame(
            self.object_key.encode("utf-8"),
            bytes.fromhex(self.verified_compressed_sha256),
            struct.pack(">Q", self.decompressed_record_ordinal_zero_based),
        )


@dataclasses.dataclass(frozen=True, slots=True, order=True)
class RawEventLocator:
    block: RawBlockLocator
    event_ordinal_zero_based: int

    def __post_init__(self) -> None:
        if self.event_ordinal_zero_based < 0:
            raise IdentityError("event ordinal must be nonnegative")

    def key_bytes(self) -> bytes:
        return frame(self.block.key_bytes(), struct.pack(">I", self.event_ordinal_zero_based))


@dataclasses.dataclass(frozen=True, slots=True, order=True)
class ProtocolTradeIdentity:
    exact_raw_block_time: str
    exact_raw_coin_string: str
    validated_json_integer_tid: int

    def key_bytes(self) -> bytes:
        return frame(
            self.exact_raw_block_time.encode("utf-8"),
            self.exact_raw_coin_string.encode("utf-8"),
            struct.pack(">Q", self.validated_json_integer_tid),
        )


@dataclasses.dataclass(frozen=True, slots=True, order=True)
class WalletFillIdentity:
    canonical_lowercase_wallet_address: str
    trade: ProtocolTradeIdentity

    def key_bytes(self) -> bytes:
        return frame(
            bytes.fromhex(self.canonical_lowercase_wallet_address[2:]),
            self.trade.key_bytes(),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class EventObservation:
    raw_locator: RawEventLocator
    block_number: int
    exact_raw_local_time: str
    exact_raw_block_time: str
    raw_wallet_value: FrozenValue
    raw_fill_value: FrozenValue
    immutable_fill_payload: FrozenObject | None
    canonical_wallet: str | None
    exact_raw_coin_string: str | None
    validated_tid: int | None
    exact_raw_side_string: str | None
    protocol_trade_identity: ProtocolTradeIdentity | None
    wallet_fill_identity: WalletFillIdentity | None
    legacy_weak_key_bytes: bytes
    full_event_canonical_bytes: bytes
    full_event_sha256: str
    fill_payload_sha256: str | None
    schema_errors: tuple[str, ...]

    @property
    def legacy_weak_key_sha256(self) -> bytes:
        return sha256_bytes(self.legacy_weak_key_bytes)

    @property
    def protocol_trade_sha256(self) -> bytes | None:
        return None if self.protocol_trade_identity is None else sha256_bytes(self.protocol_trade_identity.key_bytes())

    @property
    def wallet_fill_sha256(self) -> bytes | None:
        return None if self.wallet_fill_identity is None else sha256_bytes(self.wallet_fill_identity.key_bytes())

    def locator_mapping(self) -> dict[str, object]:
        return {
            "object_key": self.raw_locator.block.object_key,
            "verified_compressed_sha256": self.raw_locator.block.verified_compressed_sha256,
            "decompressed_record_ordinal_zero_based": self.raw_locator.block.decompressed_record_ordinal_zero_based,
            "event_ordinal_zero_based": self.raw_locator.event_ordinal_zero_based,
        }


@dataclasses.dataclass(frozen=True, slots=True)
class BlockObservation:
    raw_locator: RawBlockLocator
    block_number: int
    exact_raw_local_time: str
    exact_raw_block_time: str
    ordered_event_count: int
    ordered_event_fingerprint: str
    raw_record_fingerprint: str
    raw_record_value: FrozenObject
    events: tuple[EventObservation, ...]

    def equality_bytes(self) -> bytes:
        return frame(
            self.exact_raw_block_time.encode("utf-8"),
            struct.pack(">Q", self.ordered_event_count),
            bytes.fromhex(self.ordered_event_fingerprint),
        )

    def locator_mapping(self) -> dict[str, object]:
        return {
            "object_key": self.raw_locator.object_key,
            "verified_compressed_sha256": self.raw_locator.verified_compressed_sha256,
            "decompressed_record_ordinal_zero_based": self.raw_locator.decompressed_record_ordinal_zero_based,
        }


def _canonical_wallet(value: FrozenValue) -> tuple[str | None, str | None]:
    if not isinstance(value, str):
        return None, "WALLET_NOT_STRING"
    if _WALLET_RE.fullmatch(value) is None:
        return None, "WALLET_NOT_CANONICAL_LOWERCASE_ADDRESS"
    return value, None


def _strict_tid(value: FrozenValue | None) -> tuple[int | None, str | None]:
    if not isinstance(value, NumberToken):
        return None, "TID_NOT_JSON_NUMBER_TOKEN"
    if not value.is_integer_token:
        return None, "TID_NOT_LEXICAL_JSON_INTEGER"
    parsed = int(value.token, 10)
    if parsed < 0 or parsed >= _MAX_TID_EXCLUSIVE:
        return None, "TID_OUTSIDE_UINT50"
    return parsed, None


def parse_block_record(
    value: FrozenValue,
    *,
    object_key: str,
    verified_compressed_sha256: str,
    record_ordinal_zero_based: int,
) -> BlockObservation:
    if not isinstance(value, FrozenObject):
        raise IdentityError("archive record root must be an object")
    local_time = _require_text(_optional_mapping_value(value, "local_time"), "local_time", _MAX_TIME_BYTES)
    block_time = _require_text(_optional_mapping_value(value, "block_time"), "block_time", _MAX_TIME_BYTES)
    block_number = _require_uint_token(_optional_mapping_value(value, "block_number"), "block_number", 64)
    events_value = _optional_mapping_value(value, "events")
    if not isinstance(events_value, tuple):
        raise IdentityError("events must be an array")

    block_locator = RawBlockLocator(
        object_key=object_key,
        verified_compressed_sha256=verified_compressed_sha256,
        decompressed_record_ordinal_zero_based=record_ordinal_zero_based,
    )
    events: list[EventObservation] = []
    ordered_event_hasher = hashlib.sha256()

    for event_ordinal, event_value in enumerate(events_value):
        if not isinstance(event_value, tuple) or len(event_value) != 2:
            raise IdentityError("event must be an exact pair [wallet, fill]")
        wallet_value, fill_value = event_value
        immutable_fill = fill_value if isinstance(fill_value, FrozenObject) else None
        event_bytes = canonical_json_bytes(event_value, final_newline=False)
        ordered_event_hasher.update(struct.pack(">Q", len(event_bytes)))
        ordered_event_hasher.update(event_bytes)

        schema_errors: list[str] = []
        canonical_wallet, wallet_error = _canonical_wallet(wallet_value)
        if wallet_error is not None:
            schema_errors.append(wallet_error)

        coin: str | None = None
        tid_value: FrozenValue | None = None
        side: str | None = None
        if immutable_fill is None:
            schema_errors.append("FILL_NOT_OBJECT")
        else:
            raw_coin = _optional_mapping_value(immutable_fill, "coin")
            if isinstance(raw_coin, str) and 0 < len(raw_coin.encode("utf-8", "strict")) <= _MAX_COIN_BYTES:
                coin = raw_coin
            else:
                schema_errors.append("COIN_NOT_VALID_EXACT_STRING")
            tid_value = _optional_mapping_value(immutable_fill, "tid")
            raw_side = _optional_mapping_value(immutable_fill, "side")
            if isinstance(raw_side, str) and 0 < len(raw_side.encode("utf-8", "strict")) <= _MAX_SIDE_BYTES:
                side = raw_side
            elif raw_side is not None:
                schema_errors.append("SIDE_NOT_VALID_EXACT_STRING")

        tid, tid_error = _strict_tid(tid_value)
        if tid_error is not None:
            schema_errors.append(tid_error)

        protocol: ProtocolTradeIdentity | None = None
        wallet_fill: WalletFillIdentity | None = None
        if coin is not None and tid is not None:
            protocol = ProtocolTradeIdentity(block_time, coin, tid)
            if canonical_wallet is not None:
                wallet_fill = WalletFillIdentity(canonical_wallet, protocol)

        weak_wallet = (
            bytes.fromhex(canonical_wallet[2:])
            if canonical_wallet is not None
            else b"invalid-wallet\x00" + canonical_json_bytes(wallet_value, final_newline=False)
        )
        weak_tid = historical_legacy_typed_tid(tid_value)
        fill_bytes = None if immutable_fill is None else canonical_json_bytes(immutable_fill, final_newline=False)
        raw_locator = RawEventLocator(block_locator, event_ordinal)
        events.append(
            EventObservation(
                raw_locator=raw_locator,
                block_number=block_number,
                exact_raw_local_time=local_time,
                exact_raw_block_time=block_time,
                raw_wallet_value=wallet_value,
                raw_fill_value=fill_value,
                immutable_fill_payload=immutable_fill,
                canonical_wallet=canonical_wallet,
                exact_raw_coin_string=coin,
                validated_tid=tid,
                exact_raw_side_string=side,
                protocol_trade_identity=protocol,
                wallet_fill_identity=wallet_fill,
                legacy_weak_key_bytes=frame(weak_wallet, weak_tid),
                full_event_canonical_bytes=event_bytes,
                full_event_sha256=sha256_hex(event_bytes),
                fill_payload_sha256=None if fill_bytes is None else sha256_hex(fill_bytes),
                schema_errors=tuple(sorted(schema_errors)),
            )
        )

    raw_record_bytes = canonical_json_bytes(value, final_newline=False)
    return BlockObservation(
        raw_locator=block_locator,
        block_number=block_number,
        exact_raw_local_time=local_time,
        exact_raw_block_time=block_time,
        ordered_event_count=len(events),
        ordered_event_fingerprint=ordered_event_hasher.hexdigest(),
        raw_record_fingerprint=sha256_hex(raw_record_bytes),
        raw_record_value=value,
        events=tuple(events),
    )
