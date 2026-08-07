from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE_ROOT = ROOT / "research/wallet_copyability/probe_r1"
sys.path.insert(0, str(PROBE_ROOT))

import contract
import validate_attestation
import validate_attestation_strict
import validate_evidence


class ProbeR1AttestationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = contract.load_contract()
        self.record = validate_evidence.load_json(
            PROBE_ROOT / "ATTESTATION_TEMPLATE.json"
        )

    def test_pending_template_is_exact_and_empty(self) -> None:
        validate_attestation_strict.validate_field_set(self.record)
        validate_attestation.validate_pending(self.record, self.contract)
        self.assertEqual(
            self.record["status"],
            "PENDING_EXACT_WORKFLOW_EVIDENCE",
        )

    def test_pending_template_rejects_invented_evidence(self) -> None:
        mutations = []
        for key, value in (
            ("reviewed_commit", "0" * 40),
            ("workflow_run_id", 1),
            ("workflow_job_id", 2),
            ("artifact_digest", "sha256:" + "1" * 64),
            ("probe_output_sha256", "2" * 64),
            ("probe_terminal_status", "PUBLIC_PROBE_PASS"),
            ("archive_access_status", "LISTINGS_AVAILABLE"),
        ):
            mutation = copy.deepcopy(self.record)
            mutation[key] = value
            mutations.append(mutation)
        for mutation in mutations:
            with self.subTest(), self.assertRaises(validate_evidence.EvidenceError):
                validate_attestation.validate_pending(mutation, self.contract)

    def test_hidden_or_missing_fields_fail(self) -> None:
        hidden = copy.deepcopy(self.record)
        hidden["hidden_alpha_claim"] = True
        with self.assertRaises(validate_evidence.EvidenceError):
            validate_attestation_strict.validate_field_set(hidden)
        missing = copy.deepcopy(self.record)
        del missing["artifact_zip_sha256"]
        with self.assertRaises(validate_evidence.EvidenceError):
            validate_attestation_strict.validate_field_set(missing)
        nested = copy.deepcopy(self.record)
        nested["authorizations"]["automatic_execution_authorized"] = False
        with self.assertRaises(validate_evidence.EvidenceError):
            validate_attestation_strict.validate_field_set(nested)

    def test_pending_template_rejects_opened_gate_or_authorization(self) -> None:
        gate = copy.deepcopy(self.record)
        gate["next_gate"] = (
            "ARCHIVE_INVENTORY_PROPOSAL_ALLOWED_SEPARATE_REVIEW_REQUIRED"
        )
        with self.assertRaises(validate_evidence.EvidenceError):
            validate_attestation.validate_pending(gate, self.contract)
        authorized = copy.deepcopy(self.record)
        authorized["authorizations"]["shadow_authorized"] = True
        with self.assertRaises(validate_evidence.EvidenceError):
            validate_attestation.validate_pending(authorized, self.contract)
        market = copy.deepcopy(self.record)
        market["market_data_ingested"] = True
        with self.assertRaises(validate_evidence.EvidenceError):
            validate_attestation.validate_pending(market, self.contract)

    def test_identity_hash_and_digest_formats_are_closed(self) -> None:
        self.assertRegex("a" * 40, validate_attestation.SHA40)
        self.assertRegex("b" * 64, validate_attestation.SHA256)
        self.assertRegex(
            "sha256:" + "c" * 64,
            validate_attestation.DIGEST,
        )
        self.assertNotRegex(
            "sha256:" + "c" * 63,
            validate_attestation.DIGEST,
        )


if __name__ == "__main__":
    unittest.main()
