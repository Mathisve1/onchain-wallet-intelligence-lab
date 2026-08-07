from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE_ROOT = ROOT / "research/wallet_copyability/probe_r1"
sys.path.insert(0, str(PROBE_ROOT))

import contract
import validate_attestation
import validate_evidence


class ProbeR1AttestationValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = contract.load_contract()
        self.pending = validate_evidence.load_json(PROBE_ROOT / "ATTESTATION_TEMPLATE.json")

    def test_pending_template_validates(self) -> None:
        validate_attestation.validate_pending(self.pending, self.contract)

    def test_pending_template_rejects_invented_identity(self) -> None:
        mutations = []
        commit = copy.deepcopy(self.pending)
        commit["reviewed_commit"] = "0" * 40
        mutations.append(commit)
        run = copy.deepcopy(self.pending)
        run["workflow_run_id"] = 1
        mutations.append(run)
        artifact = copy.deepcopy(self.pending)
        artifact["artifact_digest"] = "sha256:" + "1" * 64
        mutations.append(artifact)
        output = copy.deepcopy(self.pending)
        output["probe_output_sha256"] = "2" * 64
        mutations.append(output)
        terminal = copy.deepcopy(self.pending)
        terminal["probe_terminal_status"] = "PUBLIC_PROBE_PASS"
        mutations.append(terminal)
        for mutation in mutations:
            with self.subTest(), self.assertRaises(validate_evidence.EvidenceError):
                validate_attestation.validate_pending(mutation, self.contract)

    def test_pending_template_rejects_opened_gate_or_authorization(self) -> None:
        opened = copy.deepcopy(self.pending)
        opened["next_gate"] = "ARCHIVE_INVENTORY_PROPOSAL_ALLOWED_SEPARATE_REVIEW_REQUIRED"
        with self.assertRaises(validate_evidence.EvidenceError):
            validate_attestation.validate_pending(opened, self.contract)
        authorized = copy.deepcopy(self.pending)
        authorized["authorizations"]["shadow_authorized"] = True
        with self.assertRaises(validate_evidence.EvidenceError):
            validate_attestation.validate_pending(authorized, self.contract)
        market = copy.deepcopy(self.pending)
        market["market_data_ingested"] = True
        with self.assertRaises(validate_evidence.EvidenceError):
            validate_attestation.validate_pending(market, self.contract)

    def test_hash_and_digest_formats_are_closed(self) -> None:
        self.assertRegex("a" * 40, validate_attestation.SHA40)
        self.assertRegex("b" * 64, validate_attestation.SHA256)
        self.assertRegex("sha256:" + "c" * 64, validate_attestation.DIGEST)
        self.assertNotRegex("sha256:" + "c" * 63, validate_attestation.DIGEST)


if __name__ == "__main__":
    unittest.main()
