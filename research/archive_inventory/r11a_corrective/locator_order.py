from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Final

from .canonical import NumberToken

_SHA256: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{64}\Z")


class LocatorOrderError(ValueError):
    pass


def raw_locator_order_key(
    *,
    object_key: str,
    verified_compressed_sha256: str,
    record_ordinal_zero_based: int,
    event_ordinal_zero_based: int | None,
) -> tuple[bytes, bytes, int, int]:
    """The single frozen scientific order for retained raw locators.

    Object ordinals are intentionally absent.  The key and digest are byte
    ordered and both ordinals are numeric, so `/10.lz4` sorts before `/2.lz4`
    while event ordinal 10 sorts after 2.
    """
    if not isinstance(object_key, str) or not object_key:
        raise LocatorOrderError("raw locator object key is absent")
    try:
        object_key_bytes = object_key.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise LocatorOrderError("raw locator object key is not UTF-8") from exc
    if (
        not isinstance(verified_compressed_sha256, str)
        or _SHA256.fullmatch(verified_compressed_sha256) is None
    ):
        raise LocatorOrderError("raw locator compressed SHA-256 is malformed")
    if type(record_ordinal_zero_based) is not int or record_ordinal_zero_based < 0:
        raise LocatorOrderError("raw locator record ordinal is invalid")
    event = -1 if event_ordinal_zero_based is None else event_ordinal_zero_based
    if type(event) is not int or event < -1:
        raise LocatorOrderError("raw locator event ordinal is invalid")
    return (
        object_key_bytes,
        bytes.fromhex(verified_compressed_sha256),
        record_ordinal_zero_based,
        event,
    )


def raw_locator_mapping_order_key(locator: Mapping[str, object]) -> tuple[bytes, bytes, int, int]:
    expected = {
        "object_key",
        "verified_compressed_sha256",
        "decompressed_record_ordinal_zero_based",
    }
    if not expected.issubset(locator):
        raise LocatorOrderError("raw locator field set is incomplete")
    object_key = locator["object_key"]
    compressed_sha = locator["verified_compressed_sha256"]
    record = locator["decompressed_record_ordinal_zero_based"]
    event = locator.get("event_ordinal_zero_based")
    if not isinstance(object_key, str) or not isinstance(compressed_sha, str):
        raise LocatorOrderError("raw locator text field type drift")
    if isinstance(record, NumberToken) and record.is_integer_token:
        record = int(record.token, 10)
    if isinstance(event, NumberToken) and event.is_integer_token:
        event = int(event.token, 10)
    if type(record) is not int or (event is not None and type(event) is not int):
        raise LocatorOrderError("raw locator ordinal type drift")
    return raw_locator_order_key(
        object_key=object_key,
        verified_compressed_sha256=compressed_sha,
        record_ordinal_zero_based=record,
        event_ordinal_zero_based=event,
    )


def canonical_object_locator_ranks(
    locators: Sequence[tuple[str, str]],
) -> dict[tuple[str, str], int]:
    """Return compact ranks equivalent to the frozen object/SHA byte order.

    Primary reducer payloads use this rank only as a bounded serialization of
    the first two raw-locator comparator components.  It is deliberately not
    the target's selection/object ordinal.
    """
    if len(locators) > 256:
        raise LocatorOrderError("compact object locator rank exceeds uint8")
    if len(set(locators)) != len(locators):
        raise LocatorOrderError("object locator rank input is ambiguous")
    ordered = sorted(
        locators,
        key=lambda value: raw_locator_order_key(
            object_key=value[0],
            verified_compressed_sha256=value[1],
            record_ordinal_zero_based=0,
            event_ordinal_zero_based=None,
        )[:2],
    )
    return {value: rank for rank, value in enumerate(ordered)}


__all__ = [
    "canonical_object_locator_ranks",
    "LocatorOrderError",
    "raw_locator_mapping_order_key",
    "raw_locator_order_key",
]
