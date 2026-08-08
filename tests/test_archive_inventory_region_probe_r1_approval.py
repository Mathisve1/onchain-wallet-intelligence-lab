from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/region_probe_r1"
TEXT = BASE / "approvals/APPROVE_HL_ARCHIVE_REGION_PROBE_R1_001.txt"
RECORD = BASE / "approvals/APPROVE_HL_ARCHIVE_REGION_PROBE_R1_001.json"
EXPECTED_SHA = "56c8d01396b12d0dd783dbc1646ebbca947e51a024bb5c8f091cd0b7a889c541"
EXPECTED_COMMIT = "910997423f5e008f3c7bca65fd739d6aa14d25a7"


class ArchiveRegionProbeR1ApprovalTests(unittest.TestCase):
    def load(self) -> dict:
        return json.loads(RECORD.read_text(encoding="utf-8"))

    def test_exact_approval_text_is_hash_bound(self) -> None:
        self.assertEqual(hashlib.sha256(TEXT.read_bytes()).hexdigest(), EXPECTED_SHA)
        record = self.load()
        self.assertEqual(record["exact_approval_text_sha256"], EXPECTED_SHA)
        self.assertEqual(record["reviewed_commit"], EXPECTED_COMMIT)
        self.assertEqual(record["approval_id"], "APPROVE_HL_ARCHIVE_REGION_PROBE_R1_001")

    def test_scope_and_budget_are_exact(self) -> None:
        r = self.load()
        self.assertEqual(r["approval_status"], "APPROVED_SCOPE_AND_BUDGET_AWAITING_IMPLEMENTATION")
        self.assertEqual(r["target_bucket"], "hl-mainnet-node-data")
        self.assertEqual(r["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(r["maximum_monthly_budget_eur"], 0)
        self.assertEqual(r["maximum_head_bucket_requests"], 1)
        self.assertEqual(r["maximum_runtime_seconds"], 30)
        self.assertEqual(r["maximum_retries"], 0)
        self.assertFalse(r["http_redirect_following_authorized"])
        self.assertTrue(r["head_bucket_scope_approved"])
        self.assertTrue(r["requester_pays_acknowledgement_scope_approved"])

    def test_approval_does_not_open_execution_or_data_access(self) -> None:
        r = self.load()
        for key in (
            "list_objects_v2_authorized",
            "get_object_authorized",
            "head_object_authorized",
            "object_body_download_authorized",
            "market_data_ingestion_authorized",
            "larger_300_request_inventory_authorized",
            "implementation_authorized",
            "workflow_installation_authorized",
            "execution_authorized",
            "fresh_paid_attempt_authorized",
        ):
            self.assertFalse(r[key], key)

    def test_project_state_separates_human_approval_from_runtime_release(self) -> None:
        state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
        self.assertIn("region_probe_r1_human_approved = true", state)
        self.assertIn("region_probe_r1_implementation_phase_authorized = true", state)
        self.assertIn("region_probe_r1_implementation_installed = false", state)
        self.assertIn("region_probe_r1_execution_release_present = false", state)
        self.assertIn("region_probe_r1_execution_authorized = false", state)
        self.assertIn("region_probe_r1_request_executed = false", state)
        self.assertIn("fresh_paid_attempt_authorized = false", state)


if __name__ == "__main__":
    unittest.main()
