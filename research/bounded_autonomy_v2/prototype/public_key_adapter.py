from __future__ import annotations

from crypto_fixture_oracle import keccak256

EC_PUBLIC_KEY_OID = bytes.fromhex("06072a8648ce3d0201")
SECP256K1_OID = bytes.fromhex("06052b8104000a")


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


def parse_secp256k1_spki(spki_der: bytes) -> tuple[bytes, str]:
    """Return uncompressed 65-byte point and derived Ethereum address."""
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
    if len(bit_string) != 66 or bit_string[0] != 0 or bit_string[1] != 0x04:
        raise PublicKeyAdapterError("spki:uncompressed_point_required")
    point = bit_string[1:]
    x = int.from_bytes(point[1:33], "big")
    y = int.from_bytes(point[33:65], "big")
    p = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
    if not (0 < x < p and 0 < y < p and (y * y - (x * x * x + 7)) % p == 0):
        raise PublicKeyAdapterError("spki:point_not_on_secp256k1")
    address = "0x" + keccak256(point[1:])[-20:].hex()
    return point, address
