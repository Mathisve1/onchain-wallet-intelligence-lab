from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPROVAL_DIR = ROOT / "research/archive_inventory/approvals"
APPROVAL_ID = "APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001"
APPROVED_COMMIT = "9af4b21863e47fb3bb2997ce77b9940eecf4597f"


class ArchiveR0ApprovalRecordTests(unittest.TestCase):
    def test_exact_text_is_hash_bound(self) -> None:
        raw = (APPROVAL_DIR / f"{APPROVAL_ID}.txt").read_bytes()
        record = json.loads((APPROVAL_DIR / f"{APPROVAL_ID}.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), record["exact_approval_text_sha256"])
        self.assertEqual(record["exact_approval_text_sha256"], "d70008eac7521b324f61161bcc0075e28cc3a116dd30f0c52b48d8cf5eb6ed46")

    def test_approval_is_exactly_scoped(self) -> None:
        record = json.loads((APPROVAL_DIR / f"{APPROVAL_ID}.json").read_text(encoding="utf-8"))
        self.assertEqual(record["approval_status"], "APPROVED_SCOPE_AND_BUDGET_AWAITING_IMPLEMENTATION")
        self.assertEqual(record["reviewed_commit"], APPROVED_COMMIT)
        self.assertEqual(record["maximum_one_time_budget_eur"], 1.0)
        self.assertEqual(record["maximum_monthly_budget_eur"], 0)
        self.assertEqual(record["maximum_list_requests"], 7)
        self.assertEqual(record["maximum_keys_per_request"], 25)
        self.assertEqual(record["maximum_total_entries"], 175)
        self.assertEqual(record["maximum_total_response_bytes"], 8388608)
        self.assertEqual(record["maximum_runtime_seconds"], 180)
        self.assertEqual(record["maximum_retries_per_request"], 0)
        self.assertFalse(record["pagination_authorized"])
        self.assertTrue(record["requester_pays_scope_approved"])
        self.assertTrue(record["list_objects_v2_scope_approved"])

    def test_approval_record_remains_immutable_snapshot_not_current_release_state(self) -> None:
        record = json.loads((APPROVAL_DIR / f"{APPROVAL_ID}.json").read_text(encoding="utf-8"))
        self.assertFalse(record["implementation_installed"])
        self.assertFalse(record["execution_workflow_installed"])
        self.assertFalse(record["execution_ready"])
        self.assertFalse(record["s3_request_executed"])
        self.assertFalse(record["market_data_ingested"])
        self.assertIsNone(record["empirical_result"])
        self.assertTrue(all(record["forbidden_capabilities"].values()))
        self.assertTrue(all(value is False for value in record["trading_authorizations"].values()))
        self.assertTrue((ROOT / ".github/workflows/hyperliquid-archive-metadata-canary-r0.yml").exists())
        implementation = json.loads(
            (ROOT / "research/archive_inventory/r0/R0_IMPLEMENTATION_CONTRACT.json").read_text(encoding="utf-8")
        )
        self.assertEqual(implementation["human_approval_text_sha256"], record["exact_approval_text_sha256"])
        self.assertEqual(implementation["human_approval_reviewed_commit"], record["reviewed_commit"])


if __name__ == "__main__":
    unittest.main()
