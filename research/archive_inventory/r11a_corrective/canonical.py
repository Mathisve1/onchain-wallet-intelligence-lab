from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import Iterator, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Final, TypeAlias

_JSON_INTEGER_RE: Final[re.Pattern[str]] = re.compile(r"-?(?:0|[1-9][0-9]*)\Z")
_JSON_NUMBER_RE: Final[re.Pattern[str]] = re.compile(
    r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z"
)
_MAX_NUMBER_TOKEN_BYTES: Final[int] = 4096
_MAX_NORMALIZED_INTEGER_DIGITS: Final[int] = 4096


class CanonicalJSONError(ValueError):
    """Raised when source JSON or a generated canonical document is invalid."""


@dataclasses.dataclass(frozen=True, slots=True)
class NumberToken:
    """A lossless JSON number token.

    `is_integer_token` describes the lexical JSON production, not whether a decimal
    or exponent token happens to be mathematically integral.
    """

    token: str
    is_integer_token: bool

    def __post_init__(self) -> None:
        encoded = self.token.encode("ascii", "strict")
        if not encoded or len(encoded) > _MAX_NUMBER_TOKEN_BYTES:
            raise CanonicalJSONError("JSON number token length is outside the frozen bound")
        pattern = _JSON_INTEGER_RE if self.is_integer_token else _JSON_NUMBER_RE
        if pattern.fullmatch(self.token) is None:
            raise CanonicalJSONError("invalid lossless JSON number token")
        if not self.is_integer_token and _JSON_INTEGER_RE.fullmatch(self.token) is not None:
            raise CanonicalJSONError("integer token was routed through the non-integer decoder")


FrozenScalar: TypeAlias = None | bool | str | int | NumberToken
FrozenValue: TypeAlias = "FrozenScalar | FrozenObject | tuple[FrozenValue, ...]"


@dataclasses.dataclass(frozen=True, slots=True)
class FrozenObject(Mapping[str, FrozenValue]):
    """Deep immutable JSON object with canonical UTF-8 key ordering."""

    items_tuple: tuple[tuple[str, FrozenValue], ...]
    _index: Mapping[str, FrozenValue] = dataclasses.field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        previous: bytes | None = None
        mutable: dict[str, FrozenValue] = {}
        for key, value in self.items_tuple:
            if not isinstance(key, str):
                raise CanonicalJSONError("object key must be a string")
            encoded = key.encode("utf-8", "strict")
            if previous is not None and encoded <= previous:
                raise CanonicalJSONError("FrozenObject keys must be unique and UTF-8 sorted")
            previous = encoded
            mutable[key] = value
        object.__setattr__(self, "_index", MappingProxyType(mutable))

    def __getitem__(self, key: str) -> FrozenValue:
        return self._index[key]

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self.items_tuple)

    def __len__(self) -> int:
        return len(self.items_tuple)


class _Pairs:
    __slots__ = ("pairs",)

    def __init__(self, pairs: list[tuple[str, object]]) -> None:
        self.pairs = pairs


def _reject_constant(token: str) -> object:
    raise CanonicalJSONError(f"non-finite JSON constant is forbidden: {token}")


def _pairs_hook(pairs: list[tuple[str, object]]) -> _Pairs:
    observed: set[str] = set()
    for key, _ in pairs:
        if key in observed:
            raise CanonicalJSONError(f"duplicate JSON object key: {key}")
        observed.add(key)
    return _Pairs(pairs)


def _freeze_decoded(value: object) -> FrozenValue:
    if isinstance(value, _Pairs):
        frozen = tuple(
            sorted(
                ((key, _freeze_decoded(child)) for key, child in value.pairs),
                key=lambda item: item[0].encode("utf-8", "strict"),
            )
        )
        return FrozenObject(frozen)
    if isinstance(value, list):
        return tuple(_freeze_decoded(child) for child in value)
    if value is None or isinstance(value, (bool, str, NumberToken)):
        return value
    raise CanonicalJSONError(f"unexpected decoded JSON value: {type(value).__name__}")


def strict_json_loads(raw: bytes) -> FrozenValue:
    """Decode one UTF-8 JSON value without lossy numeric coercion."""

    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise CanonicalJSONError("source bytes are not strict UTF-8") from exc
    try:
        decoded = json.loads(
            text,
            object_pairs_hook=_pairs_hook,
            parse_int=lambda token: NumberToken(token, True),
            parse_float=lambda token: NumberToken(token, False),
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, UnicodeError, CanonicalJSONError) as exc:
        if isinstance(exc, CanonicalJSONError):
            raise
        raise CanonicalJSONError("invalid strict JSON document") from exc
    return _freeze_decoded(decoded)


def deep_freeze(value: object) -> FrozenValue:
    """Create a deep immutable canonical snapshot of a generated JSON value."""

    if isinstance(value, FrozenObject):
        return value
    if isinstance(value, Mapping):
        rows: list[tuple[str, FrozenValue]] = []
        for key, child in value.items():
            if not isinstance(key, str):
                raise CanonicalJSONError("generated mapping key must be a string")
            rows.append((key, deep_freeze(child)))
        rows.sort(key=lambda item: item[0].encode("utf-8", "strict"))
        for left, right in zip(rows, rows[1:]):
            if left[0] == right[0]:
                raise CanonicalJSONError("duplicate generated mapping key")
        return FrozenObject(tuple(rows))
    if isinstance(value, tuple):
        return tuple(deep_freeze(child) for child in value)
    if isinstance(value, list):
        return tuple(deep_freeze(child) for child in value)
    if value is None or isinstance(value, (bool, str, NumberToken)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise CanonicalJSONError(f"unsupported generated JSON value: {type(value).__name__}")


def _encode_string(value: str) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _encode(value: FrozenValue, output: bytearray) -> None:
    if value is None:
        output.extend(b"null")
        return
    if value is True:
        output.extend(b"true")
        return
    if value is False:
        output.extend(b"false")
        return
    if isinstance(value, str):
        output.extend(_encode_string(value))
        return
    if isinstance(value, int):
        output.extend(str(value).encode("ascii"))
        return
    if isinstance(value, NumberToken):
        output.extend(value.token.encode("ascii"))
        return
    if isinstance(value, FrozenObject):
        output.append(ord("{"))
        for index, (key, child) in enumerate(value.items_tuple):
            if index:
                output.append(ord(","))
            output.extend(_encode_string(key))
            output.append(ord(":"))
            _encode(child, output)
        output.append(ord("}"))
        return
    if isinstance(value, tuple):
        output.append(ord("["))
        for index, child in enumerate(value):
            if index:
                output.append(ord(","))
            _encode(child, output)
        output.append(ord("]"))
        return
    raise CanonicalJSONError(f"cannot encode canonical value: {type(value).__name__}")


def canonical_json_bytes(value: object, *, final_newline: bool = True) -> bytes:
    frozen = deep_freeze(value)
    output = bytearray()
    _encode(frozen, output)
    if final_newline:
        output.append(0x0A)
    return bytes(output)


def mathematically_integral_number(token: NumberToken) -> str | None:
    """Return an exact context-independent base-10 integer string when integral.

    The implementation never calls ``quantize()`` and therefore does not depend on
    the active Decimal precision. Very large exponent expansions remain bounded.
    """

    if token.is_integer_token:
        return str(int(token.token, 10))
    try:
        decimal_value = Decimal(token.token)
    except InvalidOperation:
        return None
    if not decimal_value.is_finite():
        return None
    sign, digits_tuple, exponent = decimal_value.as_tuple()
    digits = "".join(str(digit) for digit in digits_tuple) or "0"
    if exponent >= 0:
        expanded = digits + ("0" * exponent)
    else:
        fractional_digits = -exponent
        if fractional_digits > len(digits):
            return None
        split = len(digits) - fractional_digits
        fractional = digits[split:]
        if any(character != "0" for character in fractional):
            return None
        expanded = digits[:split] or "0"
    expanded = expanded.lstrip("0") or "0"
    if len(expanded) > _MAX_NORMALIZED_INTEGER_DIGITS:
        raise CanonicalJSONError("integral JSON number expansion exceeds the frozen bound")
    if sign and expanded != "0":
        return "-" + expanded
    return expanded




def historical_legacy_typed_tid(value: FrozenValue) -> bytes:
    """Reproduce the historical weak-key projection without defining identity.

    This output is diagnostic only. It is deliberately type-tagged and may never be
    used as protocol-trade or wallet-fill identity.
    """

    if isinstance(value, NumberToken):
        integral = mathematically_integral_number(value)
        if integral is not None:
            return b"number-integral\x00" + integral.encode("ascii")
        return b"number-token\x00" + value.token.encode("ascii")
    if isinstance(value, str):
        return b"string\x00" + value.encode("utf-8", "strict")
    if value is None:
        return b"null\x00"
    if value is True:
        return b"boolean\x00true"
    if value is False:
        return b"boolean\x00false"
    if isinstance(value, int):
        return b"generated-integer\x00" + str(value).encode("ascii")
    return b"compound\x00" + canonical_json_bytes(value, final_newline=False)
