from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "research/archive_inventory"
R0 = ARCHIVE / "r0"
RELEASE = R0 / "R0_EXECUTION_RELEASE.json"
APPROVAL = ARCHIVE / "approvals/APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001.json"


class ArchiveR0ExecutionReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.release = json.loads(RELEASE.read_text(encoding="utf-8"))
        self.approval = json.loads(APPROVAL.read_text(encoding="utf-8"))

    def test_release_is_exactly_bound_to_canonical_implementation_and_approval(self) -> None:
        self.assertEqual(self.release["release_id"], "RELEASE_HL_ARCHIVE_METADATA_CANARY_R0_001")
        self.assertEqual(self.release["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R0_RUN")
        self.assertEqual(self.release["implementation_pr"], 22)
        self.assertEqual(self.release["implementation_commit"], "cd5c46b25502b671693dd5ebb091e7273399bccf")
        self.assertEqual(self.release["implementation_exact_head_ci_commit"], "41dcd5c2788af60ce9337b0c7eff4395264c4682")
        self.assertEqual(self.release["implementation_ci_run"], 31257261899)
        self.assertEqual(self.release["implementation_ci_job"], 93102453441)
        self.assertEqual(self.release["implementation_test_count"], 108)
        self.assertEqual(self.release["human_approval_id"], self.approval["approval_id"])
        self.assertEqual(self.release["human_approval_reviewed_commit"], self.approval["reviewed_commit"])
        self.assertEqual(self.release["human_approval_text_sha256"], self.approval["exact_approval_text_sha256"])

    def test_single_use_window_is_immutable_approval_timestamp(self) -> None:
        self.assertEqual(self.approval["recorded_at_utc"], "2026-08-08T10:10:00Z")
        self.assertEqual(self.release["single_use_window_start_utc"], self.approval["recorded_at_utc"])
        self.assertEqual(self.release["single_use_window_source"], "CANONICAL_HUMAN_APPROVAL_RECORDED_AT_UTC")
        self.assertTrue(self.release["single_workflow_dispatch_authorized"])
        self.assertFalse(self.release["rerun_authorized"])

    def test_release_cannot_expand_approved_cost_or_request_envelope(self) -> None:
        for key in (
            "maximum_one_time_budget_eur", "maximum_monthly_budget_eur", "maximum_list_requests",
            "maximum_keys_per_request", "maximum_total_entries", "maximum_total_response_bytes",
            "maximum_runtime_seconds", "maximum_retries_per_request", "pagination_authorized",
        ):
            self.assertEqual(self.release[key], self.approval[key])
        self.assertTrue(self.release["requester_pays_authorized"])
        self.assertTrue(self.release["list_objects_v2_authorized"])
        self.assertFalse(self.release["http_redirect_following_authorized"])
        self.assertFalse(self.release["continuation_token_follow_authorized"])

    def test_release_forbidden_capabilities_and_market_trading_gates_remain_closed(self) -> None:
        for key in (
            "get_object_authorized", "head_object_authorized", "get_object_attributes_authorized",
            "range_get_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized",
            "object_body_download_authorized", "decompression_authorized", "market_data_ingestion_authorized",
            "larger_300_request_inventory_authorized",
        ):
            self.assertFalse(self.release[key])
        self.assertEqual(self.release["s3_requests_executed"], 0)
        self.assertIsNone(self.release["empirical_result"])
        self.assertTrue(all(value is False for value in self.release["trading_authorizations"].values()))

    def test_immutable_approval_snapshot_is_not_rewritten_as_current_release_state(self) -> None:
        self.assertFalse(self.approval["implementation_installed"])
        self.assertFalse(self.approval["execution_workflow_installed"])
        self.assertFalse(self.approval["execution_ready"])
        self.assertFalse(self.approval["s3_request_executed"])
        self.assertIsNone(self.approval["empirical_result"])


if __name__ == "__main__":
    unittest.main()
