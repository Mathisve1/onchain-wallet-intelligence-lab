from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping, Sequence


class CanonicalError(ValueError):
    """Raised when a value cannot be represented under the frozen R11A grammar."""


_INTEGER_RE = re.compile(r"0|-?[1-9][0-9]*\Z")
_HEX_64_RE = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class JsonNumber:
    """Lossless finite JSON number token represented by Decimal and original token."""

    value: Decimal
    token: str


def _reject_constant(token: str) -> object:
    raise CanonicalError(f"non-finite JSON constant rejected: {token}")


def _pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CanonicalError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _parse_float(token: str) -> JsonNumber:
    value = Decimal(token)
    if not value.is_finite():
        raise CanonicalError("non-finite JSON number")
    return JsonNumber(value=value, token=token)


def strict_json_loads(raw: bytes) -> object:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise CanonicalError("invalid UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_pairs_hook,
            parse_float=_parse_float,
            parse_int=int,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, CanonicalError):
            raise
        raise CanonicalError("malformed strict JSON") from exc


def _minimal_integer(value: int) -> str:
    token = str(value)
    if not _INTEGER_RE.fullmatch(token):
        raise CanonicalError("non-canonical integer")
    return token


def decimal_scientific_token(value: Decimal) -> str:
    """Canonical decimal without quantize/context dependence."""

    if not value.is_finite():
        raise CanonicalError("non-finite decimal")
    if value.is_zero():
        return "0"
    sign, digits, exponent = value.as_tuple()
    coefficient_digits = list(digits)
    while coefficient_digits and coefficient_digits[-1] == 0:
        coefficient_digits.pop()
        exponent += 1
    if not coefficient_digits:
        return "0"
    coefficient = "".join(str(digit) for digit in coefficient_digits)
    if coefficient[0] == "0":
        coefficient = coefficient.lstrip("0")
    if not coefficient:
        return "0"
    if sign:
        coefficient = "-" + coefficient
    return f"{coefficient}e{_minimal_integer(exponent)}"


def decimal_fixed_token(value: Decimal) -> str:
    """Canonical fixed-point integral token without Decimal.quantize()."""

    if not value.is_finite():
        raise CanonicalError("non-finite decimal")
    if value.is_zero():
        return "0"
    if value != value.to_integral_value():
        raise CanonicalError("decimal is not mathematically integral")
    sign, digits, exponent = value.as_tuple()
    digit_text = "".join(str(digit) for digit in digits) or "0"
    if exponent >= 0:
        digit_text += "0" * exponent
    else:
        split = len(digit_text) + exponent
        if split <= 0:
            integer_part = "0"
            fractional = "0" * (-split) + digit_text
        else:
            integer_part = digit_text[:split]
            fractional = digit_text[split:]
        fractional = fractional.rstrip("0")
        if fractional:
            raise CanonicalError("integral decimal retained a fractional component")
        digit_text = integer_part or "0"
    digit_text = digit_text.lstrip("0") or "0"
    if sign and digit_text != "0":
        digit_text = "-" + digit_text
    if not _INTEGER_RE.fullmatch(digit_text):
        raise CanonicalError("invalid fixed-point integral token")
    return digit_text


def _escape_string(value: str) -> bytes:
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise CanonicalError("surrogate code point rejected") from exc
    out = bytearray(b'"')
    escapes = {
        0x08: b"\\b",
        0x09: b"\\t",
        0x0A: b"\\n",
        0x0C: b"\\f",
        0x0D: b"\\r",
        0x22: b'\\"',
        0x5C: b"\\\\",
    }
    for char in value:
        code = ord(char)
        if code in escapes:
            out.extend(escapes[code])
        elif code < 0x20:
            out.extend(f"\\u{code:04x}".encode("ascii"))
        else:
            out.extend(char.encode("utf-8"))
    out.append(0x22)
    return bytes(out)


def canonical_json_bytes(value: object) -> bytes:
    if value is None:
        return b"null"
    if value is True:
        return b"true"
    if value is False:
        return b"false"
    if isinstance(value, bool):
        raise CanonicalError("unexpected boolean subclass")
    if isinstance(value, int):
        return _minimal_integer(value).encode("ascii")
    if isinstance(value, JsonNumber):
        return decimal_scientific_token(value.value).encode("ascii")
    if isinstance(value, Decimal):
        return decimal_scientific_token(value).encode("ascii")
    if isinstance(value, float):
        raise CanonicalError("binary float rejected")
    if isinstance(value, str):
        return _escape_string(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise CanonicalError("binary value requires an explicit schema-level hex conversion")
    if isinstance(value, Mapping):
        keys = list(value.keys())
        if any(not isinstance(key, str) for key in keys):
            raise CanonicalError("mapping keys must be strings")
        keys.sort(key=lambda item: item.encode("utf-8", errors="strict"))
        pieces: list[bytes] = []
        for key in keys:
            pieces.append(_escape_string(key) + b":" + canonical_json_bytes(value[key]))
        return b"{" + b",".join(pieces) + b"}"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray, memoryview)):
        return b"[" + b",".join(canonical_json_bytes(item) for item in value) + b"]"
    raise CanonicalError(f"unsupported canonical JSON type: {type(value).__name__}")


def json_document_bytes(value: object) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def typed_bytes(value: object) -> bytes:
    """Typed canonical bytes used for identity hashes and complete equality keys."""

    def frame(payload: bytes) -> bytes:
        return str(len(payload)).encode("ascii") + b":" + payload

    if value is None:
        return b"N"
    if value is True:
        return b"B1"
    if value is False:
        return b"B0"
    if isinstance(value, bool):
        raise CanonicalError("unexpected boolean subclass")
    if isinstance(value, int):
        return b"I" + frame(_minimal_integer(value).encode("ascii"))
    if isinstance(value, JsonNumber):
        return b"D" + frame(decimal_scientific_token(value.value).encode("ascii"))
    if isinstance(value, Decimal):
        return b"D" + frame(decimal_scientific_token(value).encode("ascii"))
    if isinstance(value, float):
        raise CanonicalError("binary float rejected")
    if isinstance(value, str):
        return b"S" + frame(value.encode("utf-8", errors="strict"))
    if isinstance(value, Mapping):
        keys = list(value.keys())
        if any(not isinstance(key, str) for key in keys):
            raise CanonicalError("mapping keys must be strings")
        keys.sort(key=lambda item: item.encode("utf-8", errors="strict"))
        body = b"".join(frame(typed_bytes(key)) + frame(typed_bytes(value[key])) for key in keys)
        return b"O" + frame(body)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray, memoryview)):
        body = b"".join(frame(typed_bytes(item)) for item in value)
        return b"A" + frame(body)
    raise CanonicalError(f"unsupported typed value: {type(value).__name__}")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha256(value: object) -> str:
    return sha256_hex(typed_bytes(value))


def validate_sha256(value: str) -> str:
    if not _HEX_64_RE.fullmatch(value):
        raise CanonicalError("expected lowercase SHA-256 hex")
    return value


def ensure_unique_ids(rows: Iterable[Mapping[str, object]], field: str) -> None:
    seen: set[str] = set()
    for row in rows:
        value = row.get(field)
        if not isinstance(value, str):
            raise CanonicalError(f"{field} must be a string")
        if value in seen:
            raise CanonicalError(f"duplicate {field}: {value}")
        seen.add(value)
