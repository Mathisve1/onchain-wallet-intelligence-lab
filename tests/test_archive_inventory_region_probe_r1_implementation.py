from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/region_probe_r1"
CONTRACT = BASE / "REGION_PROBE_IMPLEMENTATION_CONTRACT.json"


class ArchiveRegionProbeR1ImplementationTests(unittest.TestCase):
    def load(self) -> dict:
        return json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_candidate_is_exactly_bound_to_preregistration_and_approval(self) -> None:
        c = self.load()
        self.assertEqual(c["probe_id"], "HL-ARCHIVE-REGION-PROBE-R1-001")
        self.assertEqual(c["status"], "IMPLEMENTATION_CANDIDATE_REQUIRES_SEPARATE_EXECUTION_RELEASE")
        self.assertEqual(c["preregistration_commit"], "910997423f5e008f3c7bca65fd739d6aa14d25a7")
        self.assertEqual(c["approval_merge_commit"], "b86156d71ef438441e6d3903a8bbc2da564a2046")
        self.assertEqual(c["approval_id"], "APPROVE_HL_ARCHIVE_REGION_PROBE_R1_001")
        self.assertEqual(c["approval_text_sha256"], "56c8d01396b12d0dd783dbc1646ebbca947e51a024bb5c8f091cd0b7a889c541")
        self.assertEqual(c["target_bucket"], "hl-mainnet-node-data")
        self.assertEqual(c["operation"], "HeadBucket")
        self.assertEqual(c["http_method"], "HEAD")
        self.assertEqual(c["request_path"], "/")

    def test_candidate_is_one_request_no_body_no_retry_no_redirect(self) -> None:
        c = self.load()
        self.assertEqual(c["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(c["maximum_monthly_budget_eur"], 0)
        self.assertEqual(c["maximum_s3_http_requests"], 1)
        self.assertEqual(c["maximum_runtime_seconds"], 30)
        self.assertEqual(c["maximum_retries"], 0)
        self.assertFalse(c["http_redirect_following_authorized"])
        self.assertFalse(c["request_body_authorized"])
        self.assertFalse(c["response_body_authorized"])
        self.assertFalse(c["response_body_read_authorized"])
        self.assertEqual(c["transport"], "DIRECT_SIGV4_HTTPS_HEAD_NO_REDIRECT_NO_BODY")
        self.assertEqual(c["session_s3_policy"], "EXPLICIT_DENY_ALL_S3")
        self.assertFalse(c["persistent_role_permission_expansion_required"])

    def test_candidate_keeps_all_data_and_market_capabilities_closed(self) -> None:
        c = self.load()
        for key in (
            "list_objects_v2_authorized",
            "get_object_authorized",
            "head_object_authorized",
            "get_object_attributes_authorized",
            "range_get_authorized",
            "object_body_download_authorized",
            "pagination_authorized",
            "decompression_authorized",
            "market_data_ingestion_authorized",
            "larger_300_request_inventory_authorized",
            "execution_authorized",
            "fresh_paid_attempt_authorized",
            "s3_request_executed",
        ):
            self.assertFalse(c[key], key)
        self.assertIsNone(c["exact_bucket_region"])
        self.assertIsNone(c["empirical_result"])
        self.assertTrue(all(value is False for value in c["trading_authorizations"].values()))

    def test_candidate_requires_separate_release_and_has_no_release_file(self) -> None:
        c = self.load()
        self.assertTrue(c["separate_execution_release_required"])
        self.assertFalse(c["implementation_self_releases_execution"])
        self.assertEqual(c["execution_release_path"], "research/archive_inventory/region_probe_r1/REGION_PROBE_EXECUTION_RELEASE.json")
        self.assertFalse((BASE / "REGION_PROBE_EXECUTION_RELEASE.json").exists())
        self.assertFalse((BASE / "evidence").exists())
        self.assertFalse((BASE / "outputs").exists())


if __name__ == "__main__":
    unittest.main()
