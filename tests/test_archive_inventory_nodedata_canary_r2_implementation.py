from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r2"
CONTRACT = BASE / "R2_IMPLEMENTATION_CONTRACT.json"
RELEASE = BASE / "R2_EXECUTION_RELEASE.json"


class ArchiveNodeDataCanaryR2ImplementationTests(unittest.TestCase):
    def load(self) -> dict:
        return json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exact_approval_region_endpoint_and_prefix_binding(self) -> None:
        c = self.load()
        self.assertEqual(c["canary_id"], "HL-ARCHIVE-NODEDATA-METADATA-CANARY-R2-001")
        self.assertEqual(c["status"], "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION")
        self.assertEqual(c["preregistration_commit"], "39b40cccc7e9a3fdbc439d06fb188e946d9da2aa")
        self.assertEqual(c["approval_merge_commit"], "151e08f54037ca7d3a0a9c17d3bdfb84d707a66e")
        self.assertEqual(c["human_approval_text_sha256"], "728f4e21c045eb10e883bdf0f2e970686f0e6b6cc4dc67a4f214a882cf1831c6")
        self.assertEqual(c["target_bucket"], "hl-mainnet-node-data")
        self.assertEqual(c["signing_region"], "ap-northeast-1")
        self.assertEqual(c["regional_virtual_hosted_endpoint"], "hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com")
        self.assertEqual(
            [row["prefix"] for row in c["dataset_families"]],
            ["node_fills_by_block/", "node_fills/", "node_trades/", "explorer_blocks/", "replica_cmds/"],
        )

    def test_caps_and_transport_are_exact(self) -> None:
        c = self.load()
        self.assertTrue(c["exactly_one_request_per_family"])
        self.assertEqual(c["maximum_list_requests"], 5)
        self.assertEqual(c["maximum_keys_per_request"], 25)
        self.assertEqual(c["maximum_total_entries"], 125)
        self.assertEqual(c["maximum_total_response_bytes"], 8388608)
        self.assertEqual(c["maximum_runtime_seconds"], 120)
        self.assertEqual(c["maximum_retries_per_request"], 0)
        self.assertFalse(c["pagination_authorized"])
        self.assertFalse(c["continuation_token_follow_authorized"])
        self.assertFalse(c["http_redirect_following_authorized"])
        self.assertEqual(c["s3_transport"], "DIRECT_SIGV4_HTTPS_REGIONAL_ENDPOINT_NO_REDIRECT_FOLLOW")
        self.assertTrue(c["request_counter_incremented_before_transport"])
        self.assertFalse(c["raw_list_response_retained"])
        self.assertFalse(c["continuation_token_value_retained"])
        self.assertEqual(c["allowed_response_header_fields"], ["x-amz-request-charged"])

    def test_immutable_implementation_snapshot_never_self_releases(self) -> None:
        c = self.load()
        self.assertEqual(c["expected_canonical_implementation_commit"], "PENDING_CANONICAL_IMPLEMENTATION_MERGE")
        self.assertTrue(c["execution_release_required"])
        for key in (
            "execution_release_present",
            "execution_authorized",
            "paid_request_authorized",
            "requester_pays_authorized",
            "list_objects_v2_authorized",
            "get_object_authorized",
            "head_object_authorized",
            "get_object_attributes_authorized",
            "range_get_authorized",
            "list_object_versions_authorized",
            "list_all_my_buckets_authorized",
            "object_body_download_authorized",
            "decompression_authorized",
            "market_data_ingestion_authorized",
            "larger_300_request_inventory_authorized",
        ):
            self.assertFalse(c[key], key)
        self.assertEqual(c["s3_requests_executed"], 0)
        self.assertEqual(c["metadata_entries_observed"], 0)
        self.assertIsNone(c["empirical_result"])
        self.assertTrue(all(value is False for value in c["trading_authorizations"].values()))

    def test_separate_release_exists_without_rewriting_implementation_snapshot(self) -> None:
        self.assertTrue(RELEASE.is_file())
        release = json.loads(RELEASE.read_text(encoding="utf-8"))
        self.assertEqual(release["implementation_commit"], "142ce50be20507761c4cce37b325ac69d57f8b25")
        self.assertTrue(release["single_workflow_dispatch_authorized"])
        self.assertFalse(release["rerun_authorized"])
        c = self.load()
        self.assertFalse(c["execution_release_present"])
        self.assertFalse(c["execution_authorized"])
        self.assertFalse(c["list_objects_v2_authorized"])

    def test_session_scope_is_narrower_than_persistent_role(self) -> None:
        c = self.load()
        self.assertEqual(c["session_s3_policy"], "ALLOW_LISTBUCKET_EXACT_FIVE_PREFIXES_MAX25_ONLY")
        self.assertFalse(c["persistent_iam_expansion_required"])
        self.assertEqual(c["workflow_trigger"], "workflow_dispatch_only")


if __name__ == "__main__":
    unittest.main()
