from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "research/archive_inventory/region_probe_r1"
CONTRACT = PROBE / "REGION_PROBE_CONTRACT.json"
APPROVAL = PROBE / "HUMAN_APPROVAL_TEMPLATE.md"
RELEASE = PROBE / "REGION_PROBE_EXECUTION_RELEASE.json"
EVIDENCE = PROBE / "evidence"


class ArchiveRegionProbeR1Tests(unittest.TestCase):
    def load(self) -> dict:
        return json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_contract_is_one_bucket_one_head_request_and_not_authorized(self) -> None:
        c = self.load()
        self.assertEqual(c["probe_id"], "HL-ARCHIVE-REGION-PROBE-R1-001")
        self.assertEqual(c["status"], "PREREGISTERED_NOT_AUTHORIZED")
        self.assertEqual(c["parent_r0_run_id"], 31260043109)
        self.assertEqual(c["parent_r0_attestation_merge_commit"], "105673b91d233ffcfd19a7bf3d881dbee6d85c6a")
        self.assertEqual(c["target_bucket"], "hl-mainnet-node-data")
        self.assertEqual(c["operation"], "HeadBucket")
        self.assertEqual(c["http_method"], "HEAD")
        self.assertEqual(c["request_path"], "/")
        self.assertEqual(c["maximum_s3_http_requests"], 1)
        self.assertEqual(c["maximum_runtime_seconds"], 30)
        self.assertEqual(c["maximum_retries"], 0)
        self.assertFalse(c["http_redirect_following_authorized"])
        self.assertFalse(c["implementation_authorized"])
        self.assertFalse(c["workflow_installation_authorized"])
        self.assertFalse(c["execution_authorized"])
        self.assertFalse(c["fresh_paid_attempt_authorized"])
        self.assertFalse(c["s3_request_executed"])
        self.assertIsNone(c["exact_bucket_region"])
        self.assertIsNone(c["empirical_result"])

    def test_no_list_object_or_market_capability_is_opened(self) -> None:
        c = self.load()
        for key in (
            "request_body_authorized", "response_body_authorized", "list_objects_v2_authorized",
            "get_object_authorized", "head_object_authorized", "get_object_attributes_authorized",
            "range_get_authorized", "object_body_download_authorized", "pagination_authorized",
            "decompression_authorized", "market_data_ingestion_authorized",
            "larger_300_request_inventory_authorized",
        ):
            self.assertFalse(c[key], key)
        self.assertTrue(all(value is False for value in c["trading_authorizations"].values()))

    def test_retention_is_strict_allowlist_and_region_is_not_predeclared(self) -> None:
        c = self.load()
        self.assertIn("x_amz_bucket_region", c["allowed_retained_fields"])
        self.assertIn("http_status", c["allowed_retained_fields"])
        self.assertIn("raw_header_set", c["forbidden_retained_data"])
        self.assertIn("response_body", c["forbidden_retained_data"])
        self.assertIn("authorization_header", c["forbidden_retained_data"])
        self.assertIn("oidc_token", c["forbidden_retained_data"])
        self.assertIsNone(c["exact_bucket_region"])
        self.assertEqual(c["region_value_validation"]["maximum_length"], 20)
        self.assertEqual(c["region_value_validation"]["allowed_characters_regex"], "^[a-z0-9-]+$")
        self.assertEqual(c["missing_region_header_behavior"], "TERMINAL_FAIL_NO_RETRY_NO_REDIRECT")

    def test_budget_is_only_proposed_in_immutable_preregistration_snapshot(self) -> None:
        c = self.load()
        self.assertEqual(c["proposed_maximum_one_time_budget_eur"], 0.10)
        self.assertIsNone(c["maximum_one_time_budget_eur"])
        self.assertEqual(c["maximum_monthly_budget_eur"], 0)
        self.assertTrue(c["human_approval_required"])
        self.assertEqual(c["human_approval_id"], "APPROVE_HL_ARCHIVE_REGION_PROBE_R1_001")
        text = APPROVAL.read_text(encoding="utf-8")
        self.assertIn("<CANONICAL_PREREGISTRATION_COMMIT>", text)
        self.assertIn("maximum_head_bucket_requests=1", text)
        self.assertIn("head_bucket_authorized=true", text)
        self.assertIn("list_objects_v2_authorized=false", text)
        self.assertIn("object_body_download_authorized=false", text)

    def test_preregistration_snapshot_remains_non_self_authorizing_after_attested_run(self) -> None:
        c = self.load()
        self.assertFalse(c["implementation_authorized"])
        self.assertFalse(c["workflow_installation_authorized"])
        self.assertFalse(c["execution_authorized"])
        self.assertFalse(c["fresh_paid_attempt_authorized"])
        self.assertTrue(RELEASE.is_file())
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        self.assertEqual(release["implementation_commit"], "91687b4c803e331d4b2ef8493df731c99e25a0e5")
        self.assertFalse(release["s3_request_executed"])
        self.assertIsNone(release["exact_bucket_region"])
        self.assertTrue((EVIDENCE / "HL-ARCHIVE-REGION-PROBE-R1-001-ATTESTATION.json").is_file())
        result = json.loads((EVIDENCE / "run-31273770895/region-probe-r1-result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["x_amz_bucket_region"], "ap-northeast-1")
        self.assertEqual(result["s3_http_request_count"], 1)
        self.assertFalse(result["list_objects_v2_requested"])
        self.assertFalse(result["response_body_read"])
        self.assertFalse((PROBE / "outputs").exists())


if __name__ == "__main__":
    unittest.main()
