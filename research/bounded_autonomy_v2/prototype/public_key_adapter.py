from __future__ import annotations

import base64

from crypto_fixture_oracle import keccak256

EC_PUBLIC_KEY_OID = bytes.fromhex("06072a8648ce3d0201")
SECP256K1_OID = bytes.fromhex("06052b8104000a")
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F


class PublicKeyAdapterError(ValueError):
    pass


def _read_length(data: bytes, offset: int) -> tuple[int, int]:
    if offset >= len(data):
        raise PublicKeyAdapterError("spki:length_missing")
    first = data[offset]
    offset += 1
    if first < 0x80:
        return first, offset
    count = first & 0x7F
    if count == 0 or count > 4 or offset + count > len(data):
        raise PublicKeyAdapterError("spki:length_invalid")
    value = int.from_bytes(data[offset : offset + count], "big")
    if value < 0x80:
        raise PublicKeyAdapterError("spki:length_nonminimal")
    return value, offset + count


def _read_tlv(data: bytes, offset: int, expected_tag: int) -> tuple[bytes, int]:
    if offset >= len(data) or data[offset] != expected_tag:
        raise PublicKeyAdapterError(f"spki:tag:{expected_tag:02x}")
    length, content_offset = _read_length(data, offset + 1)
    end = content_offset + length
    if end > len(data):
        raise PublicKeyAdapterError("spki:truncated")
    return data[content_offset:end], end


def _normalize_point(point: bytes) -> tuple[bytes, str]:
    if len(point) != 65 or point[0] != 0x04:
        raise PublicKeyAdapterError("public_key:uncompressed_point_required")
    x = int.from_bytes(point[1:33], "big")
    y = int.from_bytes(point[33:65], "big")
    if not (0 < x < P and 0 < y < P and (y * y - (x * x * x + 7)) % P == 0):
        raise PublicKeyAdapterError("public_key:point_not_on_secp256k1")
    address = "0x" + keccak256(point[1:])[-20:].hex()
    return point, address


def parse_secp256k1_spki(spki_der: bytes) -> tuple[bytes, str]:
    """Return normalized uncompressed 65-byte point and derived Ethereum address."""
    if not isinstance(spki_der, (bytes, bytearray)):
        raise PublicKeyAdapterError("spki:type")
    data = bytes(spki_der)
    outer, end = _read_tlv(data, 0, 0x30)
    if end != len(data):
        raise PublicKeyAdapterError("spki:trailing")

    algorithm, offset = _read_tlv(outer, 0, 0x30)
    if algorithm != EC_PUBLIC_KEY_OID + SECP256K1_OID:
        raise PublicKeyAdapterError("spki:not_secp256k1_ec_public_key")

    bit_string, offset2 = _read_tlv(outer, offset, 0x03)
    if offset2 != len(outer):
        raise PublicKeyAdapterError("spki:outer_trailing")
    if len(bit_string) != 66 or bit_string[0] != 0:
        raise PublicKeyAdapterError("spki:bit_string")
    return _normalize_point(bit_string[1:])


def _b64url_coordinate(value: str, label: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise PublicKeyAdapterError(f"jwk:{label}:type")
    padded = value + "=" * ((4 - len(value) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception as exc:
        raise PublicKeyAdapterError(f"jwk:{label}:base64url") from exc
    if len(raw) != 32:
        raise PublicKeyAdapterError(f"jwk:{label}:length")
    return raw


def parse_secp256k1_jwk_xy(x_base64url: str, y_base64url: str) -> tuple[bytes, str]:
    """Normalize provider JWK x/y coordinates to the same uncompressed point/address form."""
    x = _b64url_coordinate(x_base64url, "x")
    y = _b64url_coordinate(y_base64url, "y")
    return _normalize_point(b"\x04" + x + y)
