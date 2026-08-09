from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r3"
CANDIDATE = BASE / "R3_EXECUTION_RELEASE.json"
ACTIVATION = BASE / "R3_EXECUTION_RELEASE_CANONICALIZATION.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-hourly-metadata-inventory-r3.yml"
VALIDATOR = ROOT / "governance/validate_r3_activation.py"
SPEC = importlib.util.spec_from_file_location("validate_r3_activation", VALIDATOR)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class ArchiveHourlyMetadataR3ActivationTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_candidate_is_byte_immutable_and_stays_inert(self) -> None:
        candidate = self.load(CANDIDATE)
        self.assertEqual(
            hashlib.sha256(CANDIDATE.read_bytes()).hexdigest(),
            "c64719a8e9b8a82a361dcc7e4b03c12fba8027cd8d1e72bfc05487a2ef6ad55b",
        )
        self.assertEqual(candidate["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertFalse(candidate["activation_record_present"])
        self.assertFalse(candidate["requester_pays_authorized"])
        self.assertFalse(candidate["list_objects_v2_authorized"])
        self.assertFalse(candidate["single_workflow_dispatch_authorized"])
        self.assertFalse(candidate["execution_ready"])

    def test_activation_binds_exact_release_review_merge_and_anchor(self) -> None:
        a = self.load(ACTIVATION)
        self.assertEqual(a["release_pr"], 43)
        self.assertEqual(a["release_exact_head"], "95dd5765728d2977cdf51b3ae13d6d76af93af2d")
        self.assertEqual(a["release_ci_run"], 31299183537)
        self.assertEqual(a["release_ci_job"], 93209089110)
        self.assertEqual(a["release_test_count"], 244)
        self.assertEqual(a["release_ci_result"], "SUCCESS")
        self.assertEqual(a["release_merge_commit"], "6cd8ed06f311b6cda0a6e06c4d63f1cf05a9aad5")
        self.assertTrue(a["release_merge_verified_against_main"])
        self.assertEqual(a["activation_anchor_commit"], "4bc99701f6a24a045c84b205963685a2fe8c3122")
        self.assertEqual(a["single_use_window_start_utc"], "2026-08-09T06:38:46Z")

    def test_activation_exactly_matches_approved_bounded_scope(self) -> None:
        a = self.load(ACTIVATION)
        self.assertEqual(a["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R3_RUN")
        self.assertEqual(a["implementation_commit"], "3b1dd0df4c5194875e22c1b790e0b41961313aa8")
        self.assertEqual(a["target_bucket"], "hl-mainnet-node-data")
        self.assertEqual(a["signing_region"], "ap-northeast-1")
        self.assertEqual(a["prefixes"], [
            "node_fills_by_block/hourly/",
            "node_fills/hourly/",
            "node_trades/hourly/",
        ])
        self.assertEqual(a["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(a["maximum_monthly_budget_eur"], 0)
        self.assertEqual(a["maximum_list_requests"], 48)
        self.assertEqual(a["maximum_pages_per_family"], 16)
        self.assertEqual(a["maximum_keys_per_request"], 1000)
        self.assertEqual(a["maximum_total_entries"], 48000)
        self.assertEqual(a["maximum_total_response_bytes"], 33554432)
        self.assertEqual(a["maximum_runtime_seconds"], 300)
        self.assertEqual(a["maximum_retries_per_request"], 0)
        self.assertTrue(a["pagination_authorized"])
        self.assertTrue(a["continuation_token_follow_authorized"])
        self.assertFalse(a["continuation_token_values_retained"])
        self.assertTrue(a["repeated_continuation_token_fails_closed"])
        self.assertTrue(a["duplicate_key_fails_closed"])
        self.assertFalse(a["http_redirect_following_authorized"])
        self.assertFalse(a["start_after_authorized"])
        self.assertFalse(a["delimiter_authorized"])

    def test_only_one_metadata_dispatch_is_open_and_broader_gates_stay_closed(self) -> None:
        a = self.load(ACTIVATION)
        self.assertTrue(a["requester_pays_authorized"])
        self.assertTrue(a["list_objects_v2_authorized"])
        self.assertTrue(a["single_workflow_dispatch_authorized"])
        self.assertTrue(a["execution_ready"])
        self.assertFalse(a["rerun_authorized"])
        for key in (
            "get_object_authorized", "head_object_authorized", "get_object_attributes_authorized",
            "range_get_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized",
            "object_body_download_authorized", "decompression_authorized",
            "explorer_blocks_inventory_authorized", "replica_cmds_inventory_authorized",
            "market_data_ingestion_authorized", "larger_300_request_inventory_authorized",
        ):
            self.assertFalse(a[key], key)
        self.assertTrue(all(value is False for value in a["trading_authorizations"].values()))
        self.assertEqual(a["s3_requests_executed"], 0)
        self.assertEqual(a["metadata_entries_observed"], 0)
        self.assertIsNone(a["empirical_result"])

    def test_workflow_uses_active_overlay_and_single_use_gate_before_oidc(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("EXPECTED_IMPLEMENTATION_COMMIT: 3b1dd0df4c5194875e22c1b790e0b41961313aa8", text)
        self.assertIn("EXECUTION_RELEASE_PATH: research/archive_inventory/r3/R3_EXECUTION_RELEASE_CANONICALIZATION.json", text)
        self.assertIn("RELEASE_CANDIDATE_PATH: research/archive_inventory/r3/R3_EXECUTION_RELEASE.json", text)
        self.assertIn("Run attempt must be 1; re-runs are forbidden", text)
        self.assertIn("a previous dispatch already consumed the R3 release", text)
        self.assertLess(
            text.index("Enforce R3 single-use release before AWS OIDC"),
            text.index("Assume exact AWS role with R3-only session permissions"),
        )

    def test_activation_validator_passes(self) -> None:
        self.assertEqual(validator.main(), 0)


if __name__ == "__main__":
    unittest.main()
