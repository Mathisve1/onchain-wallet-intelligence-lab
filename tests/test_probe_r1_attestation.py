from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATTESTATION = ROOT / "research/wallet_copyability/probe_r1/ATTESTATION_TEMPLATE.json"


class ProbeR1AttestationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = json.loads(ATTESTATION.read_text(encoding="utf-8"))

    def test_pending_attestation_contains_no_invented_evidence(self) -> None:
        self.assertEqual(self.record["status"], "PENDING_EXACT_WORKFLOW_EVIDENCE")
        for key in (
            "reviewed_commit", "workflow_run_id", "workflow_run_attempt", "workflow_job_id",
            "workflow_conclusion", "artifact_id", "artifact_name", "artifact_digest",
            "artifact_zip_sha256", "probe_output_sha256", "probe_terminal_status",
            "archive_access_status", "probe_pass_count", "probe_fail_count",
            "contract_sha256", "collector_bundle_sha256", "independent_validation_status",
        ):
            self.assertIsNone(self.record[key], key)

    def test_attestation_cannot_claim_market_result_or_authorization(self) -> None:
        self.assertFalse(self.record["market_data_ingested"])
        self.assertIsNone(self.record["empirical_result"])
        self.assertFalse(self.record["independent_external_review"])
        self.assertTrue(all(value is False for value in self.record["authorizations"].values()))
        self.assertEqual(self.record["next_gate"], "DO_NOT_OPEN_ARCHIVE_INVENTORY_UNTIL_EXACT_EVIDENCE_AND_REVIEW_PASS")


if __name__ == "__main__":
    unittest.main()
