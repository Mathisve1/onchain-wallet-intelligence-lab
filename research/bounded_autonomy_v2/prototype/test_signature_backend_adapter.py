import unittest

from crypto_fixture_oracle import N, action_hash, agent_digest, public_address, sign_l1
from signature_backend_adapter import (
    SignatureAdapterError,
    adapt_der_signature,
    encode_der_ecdsa_for_fixture,
    parse_der_ecdsa,
)


def official_public_fixture_private_key() -> int:
    return int("0123456789" * 6 + "0123", 16)


class TestSignatureBackendAdapter(unittest.TestCase):
    def fixture(self):
        key = official_public_fixture_private_key()
        action = {"type": "dummy", "num": 100000000000}
        digest = agent_digest(action_hash(action, None, 0, None), True)
        signature = sign_l1(key, action, None, 0, None, True)
        return digest, signature, public_address(key)

    def test_der_roundtrip_and_unique_address_recovery(self):
        digest, signature, address = self.fixture()
        der = encode_der_ecdsa_for_fixture(int(signature["r"], 16), int(signature["s"], 16))
        self.assertEqual(adapt_der_signature(der, digest, address), signature)

    def test_high_s_is_normalized_and_recovers_same_signer(self):
        digest, signature, address = self.fixture()
        low_s = int(signature["s"], 16)
        high_s = N - low_s
        der = encode_der_ecdsa_for_fixture(int(signature["r"], 16), high_s)
        self.assertEqual(adapt_der_signature(der, digest, address), signature)

    def test_wrong_expected_signer_address_is_rejected(self):
        digest, signature, _ = self.fixture()
        der = encode_der_ecdsa_for_fixture(int(signature["r"], 16), int(signature["s"], 16))
        with self.assertRaises(SignatureAdapterError):
            adapt_der_signature(der, digest, "0x" + "11" * 20)

    def test_mutated_digest_is_rejected(self):
        digest, signature, address = self.fixture()
        mutated = bytes([digest[0] ^ 1]) + digest[1:]
        der = encode_der_ecdsa_for_fixture(int(signature["r"], 16), int(signature["s"], 16))
        with self.assertRaises(SignatureAdapterError):
            adapt_der_signature(der, mutated, address)

    def test_trailing_der_bytes_are_rejected(self):
        _, signature, _ = self.fixture()
        der = encode_der_ecdsa_for_fixture(int(signature["r"], 16), int(signature["s"], 16)) + b"\x00"
        with self.assertRaises(SignatureAdapterError):
            parse_der_ecdsa(der)

    def test_negative_der_integer_is_rejected(self):
        with self.assertRaises(SignatureAdapterError):
            parse_der_ecdsa(b"\x30\x06\x02\x01\x80\x02\x01\x01")


if __name__ == "__main__":
    unittest.main()
