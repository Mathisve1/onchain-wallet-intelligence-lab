import hashlib
import unittest

from crypto_fixture_oracle import action_hash, agent_digest, public_address, sign_digest, sign_l1
from provider_fixture_harness import BackendConfig, adapt_candidate_signature
from signature_backend_adapter import (
    SignatureAdapterError,
    encode_der_ecdsa_for_fixture,
    encode_p1363_ecdsa_for_fixture,
)


def official_public_fixture_private_key() -> int:
    return int("0123456789" * 6 + "0123", 16)


class TestProviderFixtureHarness(unittest.TestCase):
    def fixture(self):
        key = official_public_fixture_private_key()
        action = {"type": "dummy", "num": 100000000000}
        digest = agent_digest(action_hash(action, None, 0, None), True)
        signature = sign_l1(key, action, None, 0, None, True)
        config = BackendConfig(
            provider="MOCK",
            key_version="version-1",
            algorithm="ECDSA",
            encoding="DER",
            expected_signer_address=public_address(key),
            digest_mode="EXACT_32_BYTE_PREHASHED",
        )
        return action, digest, signature, config

    def test_exact_der_digest_signature_passes(self):
        _, digest, signature, config = self.fixture()
        der = encode_der_ecdsa_for_fixture(int(signature["r"], 16), int(signature["s"], 16))
        self.assertEqual(adapt_candidate_signature(config, digest, der), signature)

    def test_double_hashed_digest_signature_is_rejected(self):
        _, digest, _, config = self.fixture()
        key = official_public_fixture_private_key()
        wrong_digest = hashlib.sha256(digest).digest()
        wrong_signature = sign_digest(key, wrong_digest)
        der = encode_der_ecdsa_for_fixture(int(wrong_signature["r"], 16), int(wrong_signature["s"], 16))
        with self.assertRaises(SignatureAdapterError):
            adapt_candidate_signature(config, digest, der)

    def test_wrong_network_digest_signature_is_rejected(self):
        action, digest, _, config = self.fixture()
        key = official_public_fixture_private_key()
        testnet_digest = agent_digest(action_hash(action, None, 0, None), False)
        testnet_signature = sign_digest(key, testnet_digest)
        der = encode_der_ecdsa_for_fixture(int(testnet_signature["r"], 16), int(testnet_signature["s"], 16))
        with self.assertRaises(SignatureAdapterError):
            adapt_candidate_signature(config, digest, der)

    def test_mutable_latest_key_reference_is_rejected(self):
        _, digest, signature, config = self.fixture()
        bad = BackendConfig(
            provider="MOCK",
            key_version="latest",
            algorithm=config.algorithm,
            encoding="DER",
            expected_signer_address=config.expected_signer_address,
            digest_mode=config.digest_mode,
        )
        der = encode_der_ecdsa_for_fixture(int(signature["r"], 16), int(signature["s"], 16))
        with self.assertRaises(ValueError):
            adapt_candidate_signature(bad, digest, der)

    def test_fixed_width_p1363_candidate_can_be_verified(self):
        _, digest, signature, config = self.fixture()
        p1363_config = BackendConfig(
            provider="MOCK",
            key_version="version-1",
            algorithm=config.algorithm,
            encoding="P1363",
            expected_signer_address=config.expected_signer_address,
            digest_mode=config.digest_mode,
        )
        raw = encode_p1363_ecdsa_for_fixture(int(signature["r"], 16), int(signature["s"], 16))
        self.assertEqual(adapt_candidate_signature(p1363_config, digest, raw), signature)

    def test_non_32_byte_digest_is_rejected(self):
        _, digest, signature, config = self.fixture()
        der = encode_der_ecdsa_for_fixture(int(signature["r"], 16), int(signature["s"], 16))
        with self.assertRaises(ValueError):
            adapt_candidate_signature(config, digest[:-1], der)


if __name__ == "__main__":
    unittest.main()
