from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r2"
TEXT = BASE / "approvals/APPROVE_HL_ARCHIVE_NODEDATA_CANARY_R2_001.txt"
RECORD = BASE / "approvals/APPROVE_HL_ARCHIVE_NODEDATA_CANARY_R2_001.json"
STATUS = BASE / "APPROVAL_STATUS.md"
EXPECTED_SHA = "728f4e21c045eb10e883bdf0f2e970686f0e6b6cc4dc67a4f214a882cf1831c6"
EXPECTED_COMMIT = "39b40cccc7e9a3fdbc439d06fb188e946d9da2aa"


class ArchiveNodeDataCanaryR2ApprovalTests(unittest.TestCase):
    def load(self) -> dict:
        return json.loads(RECORD.read_text(encoding="utf-8"))

    def test_exact_approval_text_is_hash_bound(self) -> None:
        self.assertEqual(hashlib.sha256(TEXT.read_bytes()).hexdigest(), EXPECTED_SHA)
        record = self.load()
        self.assertEqual(record["exact_approval_text_sha256"], EXPECTED_SHA)
        self.assertEqual(record["reviewed_commit"], EXPECTED_COMMIT)
        self.assertEqual(record["approval_id"], "APPROVE_HL_ARCHIVE_NODEDATA_CANARY_R2_001")

    def test_scope_budget_region_and_prefix_envelope_are_exact(self) -> None:
        r = self.load()
        self.assertEqual(r["approval_status"], "APPROVED_SCOPE_AND_BUDGET_AWAITING_IMPLEMENTATION")
        self.assertEqual(r["target_bucket"], "hl-mainnet-node-data")
        self.assertEqual(r["signing_region"], "ap-northeast-1")
        self.assertEqual(r["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(r["maximum_monthly_budget_eur"], 0)
        self.assertEqual(r["maximum_list_requests"], 5)
        self.assertEqual(r["maximum_keys_per_request"], 25)
        self.assertEqual(r["maximum_total_entries"], 125)
        self.assertEqual(r["maximum_total_response_bytes"], 8388608)
        self.assertEqual(r["maximum_runtime_seconds"], 120)
        self.assertEqual(r["maximum_retries_per_request"], 0)
        self.assertFalse(r["pagination_authorized"])
        self.assertFalse(r["http_redirect_following_authorized"])
        self.assertTrue(r["requester_pays_scope_approved"])
        self.assertTrue(r["list_objects_v2_scope_approved"])

    def test_immutable_approval_snapshot_does_not_self_open_runtime(self) -> None:
        r = self.load()
        self.assertTrue(r["implementation_phase_authorized"])
        for key in (
            "implementation_installed", "execution_workflow_installed", "execution_release_present",
            "execution_ready", "paid_request_currently_authorized", "requester_pays_currently_authorized",
            "list_objects_v2_currently_authorized", "market_data_ingested",
        ):
            self.assertFalse(r[key], key)
        self.assertEqual(r["s3_requests_executed"], 0)
        self.assertEqual(r["metadata_entries_observed"], 0)
        self.assertIsNone(r["empirical_result"])
        self.assertTrue(all(value is False for value in r["trading_authorizations"].values()))
        self.assertTrue(all(value is True for value in r["forbidden_capabilities"].values()))

    def test_later_release_does_not_mutate_approval_snapshot(self) -> None:
        self.assertTrue((BASE / "collector.py").is_file())
        self.assertTrue((BASE / "R2_IMPLEMENTATION_CONTRACT.json").is_file())
        self.assertTrue((BASE / "R2_EXECUTION_RELEASE.json").is_file())
        release = json.loads((BASE / "R2_EXECUTION_RELEASE.json").read_text(encoding="utf-8"))
        self.assertEqual(release["approval_text_sha256"], EXPECTED_SHA)
        self.assertEqual(release["approval_reviewed_commit"], EXPECTED_COMMIT)
        record = self.load()
        self.assertFalse(record["implementation_installed"])
        self.assertFalse(record["execution_workflow_installed"])
        self.assertFalse(record["execution_release_present"])
        self.assertFalse(record["execution_ready"])

    def test_project_state_keeps_pre_dispatch_runtime_zero(self) -> None:
        state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
        self.assertIn("r2_human_approved = true", state)
        self.assertIn(f"r2_approval_reviewed_commit = {EXPECTED_COMMIT}", state)
        self.assertIn(f"r2_approval_text_sha256 = {EXPECTED_SHA}", state)
        self.assertIn("r2_s3_requests_executed = 0", state)
        self.assertIn("region_probe_r1_execution_release_consumed = true", state)
        self.assertIn("region_probe_r1_exact_bucket_region = ap-northeast-1", state)


if __name__ == "__main__":
    unittest.main()
