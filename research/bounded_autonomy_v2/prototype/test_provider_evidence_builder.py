import base64
import hashlib
import json
import unittest

from crypto_fixture_oracle import _mul, sign_digest
from provider_evidence_builder import ProviderEvidenceError, build_sanitized_evidence
from signature_backend_adapter import encode_der_ecdsa_for_fixture


def fixture_key() -> int:
    return int("0123456789" * 6 + "0123", 16)


def spki_for_key(private_key: int) -> bytes:
    x, y = _mul(private_key)
    point = b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big")
    algorithm = bytes.fromhex("301006072a8648ce3d020106052b8104000a")
    bit_string = b"\x03\x42\x00" + point
    body = algorithm + bit_string
    return b"\x30" + bytes([len(body)]) + body


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def capture_for_digest(digest: bytes, *, latency_count=100, revoke=True, public_format="SPKI_DER_BASE64"):
    key = fixture_key()
    signature = sign_digest(key, digest)
    der = encode_der_ecdsa_for_fixture(int(signature["r"], 16), int(signature["s"], 16))
    capture = {
        "schema_version": "0.3-local-ephemeral",
        "provider": "MOCK PROVIDER",
        "service": "MOCK KMS",
        "region_or_location": "test-region",
        "key_resource_version": "projects/example/keyVersions/7",
        "public_key_format": public_format,
        "curve": "secp256k1",
        "algorithm": "ECDSA_TEST",
        "request_mode": "fixture-prehashed-digest",
        "digest_mode": "EXACT_32_BYTE_PREHASHED",
        "signature_encoding": "DER",
        "fixture_id": "HL-OFFICIAL-DUMMY-MAINNET",
        "raw_signature_base64": base64.b64encode(der).decode(),
        "latency_samples_ms": [float(i + 1) for i in range(latency_count)],
        "key_disable_revoke_tested": revoke,
        "software_versions": {"fixture": "1"},
    }
    if public_format == "SPKI_DER_BASE64":
        capture["public_key_spki_base64"] = base64.b64encode(spki_for_key(key)).decode()
    else:
        x, y = _mul(key)
        capture["public_key_jwk_x"] = _b64url(x.to_bytes(32, "big"))
        capture["public_key_jwk_y"] = _b64url(y.to_bytes(32, "big"))
    return capture


class TestProviderEvidenceBuilder(unittest.TestCase):
    def exact_fixture_digest(self):
        return bytes.fromhex("e0aabfac88a47d3e7028b6ba6a94b30c8afcfffac26cbce788cf362b1312eafa")

    def test_complete_exact_digest_spki_capture_becomes_candidate_only(self):
        evidence = build_sanitized_evidence(capture_for_digest(self.exact_fixture_digest()))
        self.assertTrue(evidence["exact_digest_recovery_pass"])
        self.assertTrue(evidence["wrong_digest_rejected"])
        self.assertTrue(evidence["wrong_signer_rejected"])
        self.assertFalse(evidence["double_hash_signature_detected"])
        self.assertEqual(evidence["terminal_decision"], "COMPATIBLE_CANDIDATE")
        self.assertEqual(evidence["schema_version"], "0.4")
        self.assertFalse(evidence["testnet_action_authorized"])
        self.assertFalse(evidence["live_action_authorized"])

    def test_jwk_xy_capture_derives_same_signer(self):
        spki = build_sanitized_evidence(capture_for_digest(self.exact_fixture_digest(), public_format="SPKI_DER_BASE64"))
        jwk = build_sanitized_evidence(capture_for_digest(self.exact_fixture_digest(), public_format="JWK_XY_BASE64URL"))
        self.assertEqual(spki["expected_signer_address"], jwk["expected_signer_address"])
        self.assertEqual(spki["public_key_sha256"], jwk["public_key_sha256"])

    def test_incomplete_latency_or_revocation_never_promotes(self):
        evidence = build_sanitized_evidence(capture_for_digest(self.exact_fixture_digest(), latency_count=5, revoke=False))
        self.assertEqual(evidence["terminal_decision"], "INCOMPLETE_EVIDENCE")

    def test_double_hash_signature_is_detected_as_incompatible(self):
        digest = self.exact_fixture_digest()
        evidence = build_sanitized_evidence(capture_for_digest(hashlib.sha256(digest).digest()))
        self.assertFalse(evidence["exact_digest_recovery_pass"])
        self.assertTrue(evidence["double_hash_signature_detected"])
        self.assertEqual(evidence["terminal_decision"], "DIGEST_TRANSFORMATION_INCOMPATIBLE")

    def test_sanitized_evidence_does_not_copy_raw_capture_material(self):
        capture = capture_for_digest(self.exact_fixture_digest())
        output = json.dumps(build_sanitized_evidence(capture), sort_keys=True)
        self.assertNotIn(capture["key_resource_version"], output)
        self.assertNotIn(capture["raw_signature_base64"], output)
        self.assertNotIn(capture["public_key_spki_base64"], output)

    def test_mutable_key_reference_is_rejected(self):
        capture = capture_for_digest(self.exact_fixture_digest())
        capture["key_resource_version"] = "latest"
        with self.assertRaises(ProviderEvidenceError):
            build_sanitized_evidence(capture)

    def test_latency_percentiles_are_deterministic_nearest_rank(self):
        latency = build_sanitized_evidence(capture_for_digest(self.exact_fixture_digest(), latency_count=100))["latency_ms"]
        self.assertEqual(latency, {"sample_count": 100, "p50": 50.0, "p75": 75.0, "p90": 90.0, "p95": 95.0, "p99": 99.0})


if __name__ == "__main__":
    unittest.main()
