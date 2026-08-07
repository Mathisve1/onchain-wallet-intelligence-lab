from __future__ import annotations

from crypto_fixture_oracle import N, recover_address


class SignatureAdapterError(ValueError):
    pass


def _read_length(data: bytes, offset: int) -> tuple[int, int]:
    if offset >= len(data):
        raise SignatureAdapterError("der:length_missing")
    first = data[offset]
    offset += 1
    if first < 0x80:
        return first, offset
    count = first & 0x7F
    if count == 0 or count > 4 or offset + count > len(data):
        raise SignatureAdapterError("der:length_invalid")
    value = int.from_bytes(data[offset : offset + count], "big")
    if value < 0x80:
        raise SignatureAdapterError("der:length_nonminimal")
    return value, offset + count


def _read_integer(data: bytes, offset: int) -> tuple[int, int]:
    if offset >= len(data) or data[offset] != 0x02:
        raise SignatureAdapterError("der:int_tag")
    length, offset = _read_length(data, offset + 1)
    end = offset + length
    if length == 0 or end > len(data):
        raise SignatureAdapterError("der:int_length")
    raw = data[offset:end]
    if raw[0] & 0x80:
        raise SignatureAdapterError("der:int_negative")
    if len(raw) > 1 and raw[0] == 0 and not (raw[1] & 0x80):
        raise SignatureAdapterError("der:int_nonminimal")
    return int.from_bytes(raw, "big"), end


def parse_der_ecdsa(signature: bytes) -> tuple[int, int]:
    """Strict test-stage DER parser for candidate backend signatures."""
    if not isinstance(signature, (bytes, bytearray)):
        raise SignatureAdapterError("der:type")
    data = bytes(signature)
    if not data or data[0] != 0x30:
        raise SignatureAdapterError("der:sequence")
    length, offset = _read_length(data, 1)
    if offset + length != len(data):
        raise SignatureAdapterError("der:sequence_length")
    r, offset = _read_integer(data, offset)
    s, offset = _read_integer(data, offset)
    if offset != len(data):
        raise SignatureAdapterError("der:trailing")
    if not (1 <= r < N and 1 <= s < N):
        raise SignatureAdapterError("der:scalar_range")
    return r, s


def _encode_der_integer(value: int) -> bytes:
    raw = value.to_bytes((value.bit_length() + 7) // 8 or 1, "big")
    if raw[0] & 0x80:
        raw = b"\x00" + raw
    return b"\x02" + bytes([len(raw)]) + raw


def encode_der_ecdsa_for_fixture(r: int, s: int) -> bytes:
    """Fixture helper only; production backends provide their own signature bytes."""
    if not (1 <= r < N and 1 <= s < N):
        raise SignatureAdapterError("der:scalar_range")
    body = _encode_der_integer(r) + _encode_der_integer(s)
    if len(body) >= 0x80:
        raise SignatureAdapterError("der:test_encoder_long_body")
    return b"\x30" + bytes([len(body)]) + body


def adapt_der_signature(signature_der: bytes, digest: bytes, expected_signer_address: str) -> dict:
    """
    Convert backend DER ECDSA into Hyperliquid-style recoverable r/s/v only when
    the signature uniquely recovers the pre-registered API-wallet address.
    """
    r, s = parse_der_ecdsa(signature_der)
    if s > N // 2:
        s = N - s

    expected = expected_signer_address.lower()
    candidates: list[int] = []
    for v in (27, 28):
        try:
            recovered = recover_address(digest, r, s, v).lower()
        except Exception:
            continue
        if recovered == expected:
            candidates.append(v)

    if len(candidates) != 1:
        raise SignatureAdapterError("signature:recovery_not_unique")

    return {
        "r": "0x" + format(r, "x"),
        "s": "0x" + format(s, "x"),
        "v": candidates[0],
    }
