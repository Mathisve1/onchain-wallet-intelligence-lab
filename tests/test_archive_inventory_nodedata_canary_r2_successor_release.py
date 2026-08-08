from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r2"
PREDECESSOR = BASE / "R2_EXECUTION_RELEASE.json"
CONSUMPTION = BASE / "R2_EXECUTION_RELEASE_001_CONSUMPTION.json"
SUCCESSOR = BASE / "R2_EXECUTION_RELEASE_002.json"
VALIDATOR = ROOT / "governance/validate_r2_successor_release.py"
SPEC = importlib.util.spec_from_file_location("validate_r2_successor_release", VALIDATOR)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class ArchiveNodeDataCanaryR2SuccessorReleaseTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_predecessor_release_remains_immutable_snapshot(self) -> None:
        r = self.load(PREDECESSOR)
        self.assertEqual(r["release_id"], "RELEASE_HL_ARCHIVE_NODEDATA_CANARY_R2_001")
        self.assertEqual(r["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R2_RUN")
        self.assertEqual(r["s3_requests_executed"], 0)
        self.assertEqual(r["metadata_entries_observed"], 0)
        self.assertIsNone(r["empirical_result"])
        self.assertFalse(r["rerun_authorized"])

    def test_predecessor_consumption_is_pre_oidc_and_zero_s3(self) -> None:
        a = self.load(CONSUMPTION)
        self.assertEqual(
            a["attestation_id"],
            "ATTEST_HL_ARCHIVE_NODEDATA_CANARY_R2_RELEASE_001_CONSUMED_PRE_OIDC",
        )
        self.assertEqual(a["status"], "CONSUMED_BY_FIRST_DISPATCH_PRE_OIDC_NO_S3_EXECUTION")
        self.assertEqual(a["predecessor_release_merge_commit"], "0dd6f32ab3a202b0c58f37821d1038ac917d84ce")
        self.assertEqual(a["visible_exact_reviewed_commit"], "0dd6f32ab3a202b0c58f37821d1038ac917d84ce")
        self.assertEqual(a["visible_dispatch_ref"], "refs/heads/main")
        self.assertEqual(a["visible_dispatch_sha"], "0dd6f32ab3a202b0c58f37821d1038ac917d84ce")
        self.assertFalse(a["aws_oidc_role_assumption_step_executed"])
        self.assertFalse(a["collector_step_executed"])
        self.assertEqual(a["s3_http_requests_executed"], 0)
        self.assertEqual(a["list_objects_v2_requests_executed"], 0)
        self.assertEqual(a["metadata_entries_observed"], 0)
        self.assertEqual(a["requester_pays_s3_requests_executed"], 0)
        self.assertFalse(a["rerun_authorized"])
        self.assertTrue(a["successor_release_required_for_any_new_dispatch"])

    def test_successor_identity_and_lineage(self) -> None:
        r = self.load(SUCCESSOR)
        self.assertEqual(r["release_id"], "RELEASE_HL_ARCHIVE_NODEDATA_CANARY_R2_002")
        self.assertEqual(r["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R2_SUCCESSOR_RUN_AFTER_MERGE")
        self.assertEqual(r["predecessor_release_id"], "RELEASE_HL_ARCHIVE_NODEDATA_CANARY_R2_001")
        self.assertTrue(r["predecessor_release_consumed"])
        self.assertEqual(r["predecessor_s3_requests_executed"], 0)
        self.assertEqual(r["preregistration_commit"], "39b40cccc7e9a3fdbc439d06fb188e946d9da2aa")
        self.assertEqual(r["approval_merge_commit"], "151e08f54037ca7d3a0a9c17d3bdfb84d707a66e")
        self.assertEqual(r["approval_text_sha256"], "728f4e21c045eb10e883bdf0f2e970686f0e6b6cc4dc67a4f214a882cf1831c6")
        self.assertEqual(r["implementation_commit"], "142ce50be20507761c4cce37b325ac69d57f8b25")

    def test_successor_removes_manual_sha_input(self) -> None:
        r = self.load(SUCCESSOR)
        self.assertEqual(r["github_event_required"], "workflow_dispatch")
        self.assertEqual(r["canonical_dispatch_ref_required"], "refs/heads/main")
        self.assertEqual(r["canonical_dispatch_sha_source"], "github.sha")
        self.assertFalse(r["manual_reviewed_commit_input_required"])

    def test_successor_envelope_is_unchanged(self) -> None:
        r = self.load(SUCCESSOR)
        self.assertEqual(r["target_bucket"], "hl-mainnet-node-data")
        self.assertEqual(r["signing_region"], "ap-northeast-1")
        self.assertEqual(r["regional_virtual_hosted_endpoint"], "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com")
        self.assertEqual(r["operation"], "ListObjectsV2")
        self.assertEqual(r["request_payer"], "requester")
        self.assertEqual(r["dataset_family_count"], 5)
        self.assertEqual(r["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(r["maximum_monthly_budget_eur"], 0)
        self.assertEqual(r["maximum_list_requests"], 5)
        self.assertEqual(r["maximum_keys_per_request"], 25)
        self.assertEqual(r["maximum_total_entries"], 125)
        self.assertEqual(r["maximum_total_response_bytes"], 8388608)
        self.assertEqual(r["maximum_runtime_seconds"], 120)
        self.assertEqual(r["maximum_retries_per_request"], 0)
        self.assertFalse(r["pagination_authorized"])
        self.assertFalse(r["continuation_token_follow_authorized"])
        self.assertFalse(r["http_redirect_following_authorized"])

    def test_only_approved_network_scope_is_open_for_one_dispatch(self) -> None:
        r = self.load(SUCCESSOR)
        self.assertTrue(r["requester_pays_authorized"])
        self.assertTrue(r["list_objects_v2_authorized"])
        self.assertTrue(r["single_workflow_dispatch_authorized"])
        self.assertFalse(r["rerun_authorized"])
        self.assertEqual(r["session_s3_policy"], "ALLOW_LISTBUCKET_EXACT_FIVE_PREFIXES_MAX25_ONLY")
        self.assertFalse(r["persistent_role_permission_expansion_required"])
        for key in (
            "get_object_authorized", "head_object_authorized", "get_object_attributes_authorized",
            "range_get_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized",
            "object_body_download_authorized", "decompression_authorized", "market_data_ingestion_authorized",
            "larger_300_request_inventory_authorized",
        ):
            self.assertFalse(r[key], key)
        self.assertEqual(r["s3_requests_executed"], 0)
        self.assertEqual(r["metadata_entries_observed"], 0)
        self.assertIsNone(r["empirical_result"])
        self.assertTrue(all(value is False for value in r["trading_authorizations"].values()))

    def test_successor_validator_passes(self) -> None:
        self.assertEqual(validator.main(), 0)


if __name__ == "__main__":
    unittest.main()
