from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE_ROOT = ROOT / "research/wallet_copyability/probe_r1"
sys.path.insert(0, str(PROBE_ROOT))

import validate_attestation_strict
import validate_evidence


class ProbeR1StrictAttestationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = validate_evidence.load_json(PROBE_ROOT / "ATTESTATION_TEMPLATE.json")

    def test_exact_template_field_set_passes(self) -> None:
        validate_attestation_strict.validate_field_set(self.record)

    def test_hidden_top_level_field_fails(self) -> None:
        mutated = copy.deepcopy(self.record)
        mutated["hidden_alpha_claim"] = True
        with self.assertRaises(validate_evidence.EvidenceError):
            validate_attestation_strict.validate_field_set(mutated)

    def test_hidden_authorization_field_fails(self) -> None:
        mutated = copy.deepcopy(self.record)
        mutated["authorizations"]["automatic_execution_authorized"] = False
        with self.assertRaises(validate_evidence.EvidenceError):
            validate_attestation_strict.validate_field_set(mutated)

    def test_missing_field_fails(self) -> None:
        mutated = copy.deepcopy(self.record)
        del mutated["artifact_zip_sha256"]
        with self.assertRaises(validate_evidence.EvidenceError):
            validate_attestation_strict.validate_field_set(mutated)


if __name__ == "__main__":
    unittest.main()
