from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4"
TEXT = BASE / "approvals/APPROVE_HL_ARCHIVE_HOURLY_BODY_SCHEMA_PILOT_R4_001.txt"
RECORD = BASE / "approvals/APPROVE_HL_ARCHIVE_HOURLY_BODY_SCHEMA_PILOT_R4_001.json"
STATUS = BASE / "APPROVAL_STATUS.md"
EXPECTED_COMMIT = "25a1f621d15cb708a485893025f03b991628aae1"
EXPECTED_SHA = "e52399feb7a0d36959089f556dd9f55062eb91d52feaa4c5af680d3c4e557264"


class ArchiveHourlyBodySchemaR4ApprovalTests(unittest.TestCase):
    def load(self) -> dict:
        return json.loads(RECORD.read_text(encoding="utf-8"))

    def test_exact_approval_text_is_hash_bound(self) -> None:
        self.assertEqual(hashlib.sha256(TEXT.read_bytes()).hexdigest(), EXPECTED_SHA)
        r = self.load()
        self.assertEqual(r["approval_id"], "APPROVE_HL_ARCHIVE_HOURLY_BODY_SCHEMA_PILOT_R4_001")
        self.assertEqual(r["reviewed_commit"], EXPECTED_COMMIT)
        self.assertEqual(r["exact_approval_text_sha256"], EXPECTED_SHA)

    def test_scope_budget_and_two_object_envelope_are_exact(self) -> None:
        r = self.load()
        self.assertEqual(r["target_bucket"], "hl-mainnet-node-data")
        self.assertEqual(r["signing_region"], "ap-northeast-1")
        self.assertEqual(r["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(r["maximum_monthly_budget_eur"], 0)
        self.assertEqual(r["maximum_get_object_requests"], 2)
        self.assertEqual(r["maximum_requests_per_object"], 1)
        self.assertEqual(r["maximum_total_compressed_bytes"], 14243987)
        self.assertEqual(r["maximum_total_decompressed_bytes"], 536870912)
        self.assertEqual(r["maximum_decompressed_bytes_per_object"], 268435456)
        self.assertEqual(r["maximum_runtime_seconds"], 180)
        self.assertEqual(r["maximum_retries_per_request"], 0)
        self.assertEqual(r["selected_objects"], [
            {
                "key": "node_fills/hourly/20250727/8.lz4",
                "size_bytes": 12726384,
                "etag": '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"',
            },
            {
                "key": "node_fills_by_block/hourly/20250727/8.lz4",
                "size_bytes": 1517603,
                "etag": '"60d4c1277f76651b5f04666bbe8d7594"',
            },
        ])
        self.assertTrue(r["if_match_etag_required"])
        self.assertTrue(r["exact_content_length_required"])
        self.assertTrue(r["lz4_frame_stream_only"])
        self.assertTrue(r["schema_parser_utf8_ndjson_object_stream_only"])

    def test_approval_opens_implementation_lane_but_not_runtime(self) -> None:
        r = self.load()
        self.assertEqual(r["approval_status"], "APPROVED_SCOPE_AND_BUDGET_AWAITING_IMPLEMENTATION")
        self.assertTrue(r["requester_pays_scope_approved"])
        self.assertTrue(r["get_object_scope_approved"])
        self.assertTrue(r["decompression_scope_approved"])
        self.assertTrue(r["implementation_phase_authorized"])
        self.assertFalse(r["implementation_installed"])
        self.assertFalse(r["execution_workflow_installed"])
        self.assertFalse(r["execution_release_present"])
        self.assertFalse(r["execution_ready"])
        self.assertFalse(r["paid_request_currently_authorized"])
        self.assertFalse(r["requester_pays_currently_authorized"])
        self.assertFalse(r["get_object_currently_authorized"])
        self.assertFalse(r["decompression_currently_authorized"])
        self.assertEqual(r["requests_executed"], 0)
        self.assertEqual(r["compressed_bytes_downloaded"], 0)
        self.assertEqual(r["decompressed_bytes_processed"], 0)
        self.assertIsNone(r["empirical_result"])

    def test_forbidden_capabilities_and_trading_remain_closed(self) -> None:
        r = self.load()
        self.assertTrue(all(value is True for value in r["forbidden_capabilities"].values()))
        self.assertTrue(all(value is False for value in r["trading_authorizations"].values()))
        status = STATUS.read_text(encoding="utf-8")
        self.assertIn("GetObject currently authorized: `false`", status)
        self.assertIn("execution ready: `false`", status)
        self.assertIn("wallet reconstruction", status)
        self.assertIn("P&L/alpha analysis", status)


if __name__ == "__main__":
    unittest.main()
