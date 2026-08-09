from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r3"
RELEASE = BASE / "R3_EXECUTION_RELEASE.json"
ACTIVATION = BASE / "R3_EXECUTION_RELEASE_CANONICALIZATION.json"
IMPLEMENTATION = BASE / "R3_IMPLEMENTATION_CONTRACT.json"
VALIDATOR = ROOT / "governance/validate_r3_release.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-hourly-metadata-inventory-r3.yml"
SPEC = importlib.util.spec_from_file_location("validate_r3_release", VALIDATOR)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class ArchiveHourlyMetadataR3ReleaseTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_release_binds_exact_canonical_implementation_evidence(self) -> None:
        r = self.load(RELEASE)
        self.assertEqual(r["release_id"], "RELEASE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001")
        self.assertEqual(r["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertEqual(r["preregistration_commit"], "ab4d42be02fe49d7f90f933317ef856f0322fd85")
        self.assertEqual(r["approval_merge_commit"], "e562f3fbd8f1dac1b4d7e93eed2f5ee6b77c5da6")
        self.assertEqual(r["approval_text_sha256"], "3c3931133fb8b0dd322d7a296b7b70fca65dd341401a6eda2b6372938ed6cd10")
        self.assertEqual(r["implementation_pr"], 42)
        self.assertEqual(r["implementation_commit"], "3b1dd0df4c5194875e22c1b790e0b41961313aa8")
        self.assertEqual(r["implementation_exact_head_ci_commit"], "02681dbf13415f953fd3c79f66ee5de4919a169c")
        self.assertEqual(r["implementation_ci_run"], 31297902934)
        self.assertEqual(r["implementation_ci_job"], 93205871178)
        self.assertEqual(r["implementation_test_count"], 236)
        self.assertEqual(r["implementation_ci_result"], "SUCCESS")
        self.assertEqual(r["implementation_validator_result"], "R3_IMPLEMENTATION_VALID")

    def test_release_candidate_envelope_exactly_matches_human_approval(self) -> None:
        r = self.load(RELEASE)
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
        self.assertTrue(r["pagination_authorized_after_activation"])
        self.assertTrue(r["continuation_token_follow_authorized_after_activation"])
        self.assertFalse(r["continuation_token_values_retained"])
        self.assertTrue(r["repeated_continuation_token_fails_closed"])
        self.assertTrue(r["duplicate_key_fails_closed"])
        self.assertFalse(r["http_redirect_following_authorized"])
        self.assertFalse(r["start_after_authorized"])
        self.assertFalse(r["delimiter_authorized"])

    def test_release_candidate_is_inert_until_separate_activation(self) -> None:
        r = self.load(RELEASE)
        self.assertTrue(r["activation_required"])
        self.assertFalse(r["activation_record_present"])
        self.assertIsNone(r["canonical_release_merge_commit"])
        self.assertIsNone(r["single_use_window_start_utc"])
        self.assertFalse(ACTIVATION.exists())
        self.assertTrue(r["requester_pays_scope_authorized_after_activation"])
        self.assertTrue(r["list_objects_v2_scope_authorized_after_activation"])
        self.assertTrue(r["single_workflow_dispatch_authorized_after_activation"])
        self.assertFalse(r["requester_pays_authorized"])
        self.assertFalse(r["list_objects_v2_authorized"])
        self.assertFalse(r["single_workflow_dispatch_authorized"])
        self.assertFalse(r["execution_ready"])
        self.assertFalse(r["rerun_authorized"])
        self.assertEqual(r["s3_requests_executed"], 0)
        self.assertEqual(r["metadata_entries_observed"], 0)
        self.assertIsNone(r["empirical_result"])

    def test_forbidden_capabilities_and_trading_remain_closed(self) -> None:
        r = self.load(RELEASE)
        for key in (
            "get_object_authorized", "head_object_authorized", "get_object_attributes_authorized",
            "range_get_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized",
            "object_body_download_authorized", "decompression_authorized",
            "explorer_blocks_inventory_authorized", "replica_cmds_inventory_authorized",
            "market_data_ingestion_authorized", "larger_300_request_inventory_authorized",
        ):
            self.assertFalse(r[key], key)
        self.assertTrue(all(value is False for value in r["trading_authorizations"].values()))

    def test_immutable_implementation_snapshot_remains_non_release(self) -> None:
        impl = self.load(IMPLEMENTATION)
        self.assertEqual(impl["expected_canonical_implementation_commit"], "PENDING_CANONICAL_IMPLEMENTATION_MERGE")
        self.assertFalse(impl["execution_release_present"])
        self.assertFalse(impl["execution_authorized"])
        self.assertFalse(impl["paid_request_authorized"])
        self.assertFalse(impl["requester_pays_authorized"])
        self.assertFalse(impl["list_objects_v2_authorized"])
        self.assertEqual(impl["s3_requests_executed"], 0)
        self.assertEqual(impl["metadata_entries_observed"], 0)

    def test_workflow_still_fails_closed_after_release_candidate_merge(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE", text)
        self.assertIn("Implementation is not yet canonical; no AWS authentication is allowed", text)
        self.assertLess(
            text.index("Prove canonical implementation and release before AWS OIDC"),
            text.index("Assume exact AWS role with R3-only session permissions"),
        )

    def test_status_records_canonical_impl_but_inert_release_candidate(self) -> None:
        status = (ROOT / "research/archive_inventory/STATUS.md").read_text(encoding="utf-8")
        self.assertIn("R3_RELEASE_CANDIDATE_UNDER_REVIEW_NO_EXECUTION", status)
        self.assertIn("canonical implementation merge: `3b1dd0df4c5194875e22c1b790e0b41961313aa8`", status)
        self.assertIn("activation record present: `false`", status)
        self.assertIn("workflow therefore execution-capable after release-candidate merge alone: `false`", status)
        self.assertIn("R3 S3 requests executed / entries observed: `0 / 0`", status)

    def test_release_validator_passes(self) -> None:
        self.assertEqual(validator.main(), 0)


if __name__ == "__main__":
    unittest.main()
