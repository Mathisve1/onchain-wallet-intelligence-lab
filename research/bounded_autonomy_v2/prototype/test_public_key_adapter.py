import unittest

from crypto_fixture_oracle import _mul, public_address
from public_key_adapter import PublicKeyAdapterError, parse_secp256k1_spki


def fixture_key() -> int:
    return int("0123456789" * 6 + "0123", 16)


def spki_for_key(private_key: int) -> bytes:
    x, y = _mul(private_key)
    point = b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big")
    algorithm = bytes.fromhex("301006072a8648ce3d020106052b8104000a")
    bit_string = b"\x03\x42\x00" + point
    body = algorithm + bit_string
    return b"\x30" + bytes([len(body)]) + body


class TestPublicKeyAdapter(unittest.TestCase):
    def test_fixture_spki_derives_expected_ethereum_address(self):
        key = fixture_key()
        point, address = parse_secp256k1_spki(spki_for_key(key))
        self.assertEqual(len(point), 65)
        self.assertEqual(address, public_address(key))
        self.assertEqual(address, "0x14791697260e4c9a71f18484c9f997b308e59325")

    def test_wrong_curve_oid_rejected(self):
        raw = bytearray(spki_for_key(fixture_key()))
        raw[19] ^= 1
        with self.assertRaises(PublicKeyAdapterError):
            parse_secp256k1_spki(bytes(raw))

    def test_trailing_bytes_rejected(self):
        with self.assertRaises(PublicKeyAdapterError):
            parse_secp256k1_spki(spki_for_key(fixture_key()) + b"\x00")

    def test_compressed_or_malformed_point_rejected(self):
        raw = bytearray(spki_for_key(fixture_key()))
        raw[23] = 0x02
        with self.assertRaises(PublicKeyAdapterError):
            parse_secp256k1_spki(bytes(raw))


if __name__ == "__main__":
    unittest.main()
