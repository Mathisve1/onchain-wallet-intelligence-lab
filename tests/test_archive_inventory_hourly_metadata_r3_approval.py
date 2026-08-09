from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r3"
TEXT = BASE / "approvals/APPROVE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001.txt"
RECORD = BASE / "approvals/APPROVE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001.json"
STATUS = BASE / "APPROVAL_STATUS.md"
EXPECTED_COMMIT = "ab4d42be02fe49d7f90f933317ef856f0322fd85"
EXPECTED_SHA = "3c3931133fb8b0dd322d7a296b7b70fca65dd341401a6eda2b6372938ed6cd10"


class ArchiveHourlyMetadataR3ApprovalTests(unittest.TestCase):
    def load(self) -> dict:
        return json.loads(RECORD.read_text(encoding="utf-8"))

    def test_exact_approval_text_is_hash_bound(self) -> None:
        self.assertEqual(hashlib.sha256(TEXT.read_bytes()).hexdigest(), EXPECTED_SHA)
        r = self.load()
        self.assertEqual(r["approval_id"], "APPROVE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001")
        self.assertEqual(r["reviewed_commit"], EXPECTED_COMMIT)
        self.assertEqual(r["exact_approval_text_sha256"], EXPECTED_SHA)

    def test_scope_budget_and_pagination_envelope_are_exact(self) -> None:
        r = self.load()
        self.assertEqual(r["target_bucket"], "hl-mainnet-node-data")
        self.assertEqual(r["signing_region"], "ap-northeast-1")
        self.assertEqual(r["prefixes"], [
            "node_fills_by_block/hourly/",
            "node_fills/hourly/",
            "node_trades/hourly/",
        ])
        self.assertEqual(r["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(r["maximum_monthly_budget_eur"], 0)
        self.assertEqual(r["maximum_list_requests"], 48)
        self.assertEqual(r["maximum_pages_per_family"], 16)
        self.assertEqual(r["maximum_keys_per_request"], 1000)
        self.assertEqual(r["maximum_total_entries"], 48000)
        self.assertEqual(r["maximum_total_response_bytes"], 33554432)
        self.assertEqual(r["maximum_runtime_seconds"], 300)
        self.assertEqual(r["maximum_retries_per_request"], 0)
        self.assertTrue(r["pagination_authorized"])
        self.assertTrue(r["continuation_token_follow_authorized"])
        self.assertFalse(r["continuation_token_values_retained"])
        self.assertTrue(r["repeated_continuation_token_fails_closed"])
        self.assertFalse(r["http_redirect_following_authorized"])
        self.assertFalse(r["start_after_authorized"])
        self.assertFalse(r["delimiter_authorized"])

    def test_approval_opens_implementation_lane_but_not_runtime(self) -> None:
        r = self.load()
        self.assertEqual(r["approval_status"], "APPROVED_SCOPE_AND_BUDGET_AWAITING_IMPLEMENTATION")
        self.assertTrue(r["requester_pays_scope_approved"])
        self.assertTrue(r["list_objects_v2_scope_approved"])
        self.assertTrue(r["implementation_phase_authorized"])
        self.assertFalse(r["implementation_installed"])
        self.assertFalse(r["execution_workflow_installed"])
        self.assertFalse(r["execution_release_present"])
        self.assertFalse(r["execution_ready"])
        self.assertFalse(r["paid_request_currently_authorized"])
        self.assertFalse(r["requester_pays_currently_authorized"])
        self.assertFalse(r["list_objects_v2_currently_authorized"])
        self.assertEqual(r["s3_requests_executed"], 0)
        self.assertEqual(r["metadata_entries_observed"], 0)
        self.assertIsNone(r["empirical_result"])

    def test_forbidden_capabilities_and_trading_remain_closed(self) -> None:
        r = self.load()
        self.assertTrue(all(value is True for value in r["forbidden_capabilities"].values()))
        self.assertTrue(all(value is False for value in r["trading_authorizations"].values()))
        status = STATUS.read_text(encoding="utf-8")
        self.assertIn("Runtime paid-request, Requester Pays and `ListObjectsV2` authority remain false", status)
        self.assertIn("larger 300-request inventory", status)


if __name__ == "__main__":
    unittest.main()
