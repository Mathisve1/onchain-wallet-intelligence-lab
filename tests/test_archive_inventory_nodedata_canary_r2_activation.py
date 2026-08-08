from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r2"
ATTESTATION = BASE / "R2_EXECUTION_RELEASE_002_CANONICALIZATION.json"
SUCCESSOR = BASE / "R2_EXECUTION_RELEASE_002.json"
CONSUMPTION = BASE / "R2_EXECUTION_RELEASE_001_CONSUMPTION.json"


class ArchiveNodeDataCanaryR2ActivationTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_canonicalization_binds_exact_review_and_merge(self) -> None:
        a = self.load(ATTESTATION)
        self.assertEqual(a["attestation_id"], "ATTEST_HL_ARCHIVE_NODEDATA_CANARY_R2_RELEASE_002_CANONICAL")
        self.assertEqual(a["release_id"], "RELEASE_HL_ARCHIVE_NODEDATA_CANARY_R2_002")
        self.assertEqual(a["release_pr"], 37)
        self.assertEqual(a["release_exact_head"], "d8e0a4102e26b12f64d7871b274e65891e81b431")
        self.assertEqual(a["release_ci_run"], 31279273339)
        self.assertEqual(a["release_ci_job"], 93157850604)
        self.assertEqual(a["release_test_count"], 185)
        self.assertEqual(a["release_ci_result"], "SUCCESS")
        self.assertEqual(a["repository_manifest_result"], "BYTE_EXACT_PASS")
        self.assertEqual(a["repository_governance_result"], "PASS")
        self.assertEqual(a["r2_implementation_validator_result"], "R2_IMPLEMENTATION_VALID")
        self.assertEqual(a["r2_successor_validator_result"], "R2_SUCCESSOR_RELEASE_VALID")
        self.assertEqual(a["release_merge_commit"], "6128e6a9974742113f74c6e17fba7159dc60bde5")
        self.assertTrue(a["release_merge_verified_against_main"])
        self.assertTrue(a["successor_release_canonical"])

    def test_predecessor_remains_zero_s3_and_consumed(self) -> None:
        a = self.load(ATTESTATION)
        c = self.load(CONSUMPTION)
        self.assertEqual(a["predecessor_release_id"], "RELEASE_HL_ARCHIVE_NODEDATA_CANARY_R2_001")
        self.assertEqual(a["predecessor_consumption_status"], c["status"])
        self.assertEqual(a["predecessor_s3_requests_executed"], 0)
        self.assertEqual(a["predecessor_metadata_entries_observed"], 0)
        self.assertFalse(c["rerun_authorized"])

    def test_canonical_successor_keeps_approved_envelope(self) -> None:
        a = self.load(ATTESTATION)
        r = self.load(SUCCESSOR)
        for key in (
            "target_bucket", "signing_region", "maximum_list_requests", "maximum_keys_per_request",
            "maximum_total_entries", "maximum_total_response_bytes", "maximum_runtime_seconds",
            "maximum_retries_per_request", "pagination_authorized", "http_redirect_following_authorized",
            "maximum_one_time_budget_eur", "maximum_monthly_budget_eur",
        ):
            self.assertEqual(a[key], r[key], key)
        self.assertEqual(a["target_bucket"], "hl-mainnet-node-data")
        self.assertEqual(a["signing_region"], "ap-northeast-1")
        self.assertEqual(a["maximum_list_requests"], 5)
        self.assertEqual(a["maximum_keys_per_request"], 25)
        self.assertEqual(a["maximum_total_entries"], 125)
        self.assertEqual(a["maximum_total_response_bytes"], 8388608)
        self.assertEqual(a["maximum_runtime_seconds"], 120)
        self.assertEqual(a["maximum_retries_per_request"], 0)
        self.assertFalse(a["pagination_authorized"])
        self.assertFalse(a["http_redirect_following_authorized"])
        self.assertEqual(a["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(a["maximum_monthly_budget_eur"], 0)

    def test_canonical_successor_is_single_use_and_no_broader_capability(self) -> None:
        a = self.load(ATTESTATION)
        self.assertTrue(a["successor_release_single_workflow_dispatch_authorized"])
        self.assertFalse(a["successor_release_rerun_authorized"])
        self.assertFalse(a["manual_reviewed_commit_input_required"])
        self.assertEqual(a["canonical_dispatch_identity_source"], "GITHUB_EVENT_REF_SHA_AND_CHECKED_OUT_HEAD")
        for key in (
            "get_object_authorized", "head_object_authorized", "get_object_attributes_authorized",
            "range_get_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized",
            "object_body_download_authorized", "decompression_authorized", "market_data_ingestion_authorized",
            "larger_300_request_inventory_authorized",
        ):
            self.assertFalse(a[key], key)
        self.assertTrue(all(value is False for value in a["trading_authorizations"].values()))
        self.assertFalse(a["execution_observed"])
        self.assertEqual(a["s3_requests_executed"], 0)
        self.assertEqual(a["metadata_entries_observed"], 0)
        self.assertIsNone(a["empirical_result"])

    def test_project_state_activates_only_release_scoped_r2_authority(self) -> None:
        state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
        self.assertIn("r2_successor_release_canonical = true", state)
        self.assertIn("r2_successor_release_commit = 6128e6a9974742113f74c6e17fba7159dc60bde5", state)
        self.assertIn("r2_execution_ready = true", state)
        self.assertIn("r2_execution_authorized = true", state)
        self.assertIn("r2_paid_request_authorized = true", state)
        self.assertIn("r2_requester_pays_authorized = true", state)
        self.assertIn("r2_list_objects_v2_authorized = true", state)
        self.assertIn("paid_request_authorized = false", state)
        self.assertIn("requester_pays_authorized = false", state)
        self.assertIn("list_objects_authorized = false", state)
        self.assertIn("larger_300_request_inventory_authorized = false", state)
        self.assertIn("object_body_download_authorized = false", state)
        self.assertIn("market_data_ingested = false", state)


if __name__ == "__main__":
    unittest.main()
