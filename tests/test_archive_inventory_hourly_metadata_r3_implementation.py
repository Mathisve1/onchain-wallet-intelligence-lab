from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r3"
IMPLEMENTATION = BASE / "R3_IMPLEMENTATION_CONTRACT.json"
RELEASE = BASE / "R3_EXECUTION_RELEASE.json"
ACTIVATION = BASE / "R3_EXECUTION_RELEASE_CANONICALIZATION.json"
CONSUMPTION = BASE / "R3_EXECUTION_RELEASE_CONSUMPTION.json"
VALIDATOR = ROOT / "governance/validate_r3_implementation.py"
SPEC = importlib.util.spec_from_file_location("validate_r3_implementation", VALIDATOR)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class ArchiveHourlyMetadataR3ImplementationTests(unittest.TestCase):
    def load(self) -> dict:
        return json.loads(IMPLEMENTATION.read_text(encoding="utf-8"))

    def test_exact_lineage_and_three_prefix_scope(self) -> None:
        r = self.load()
        self.assertEqual(r["inventory_id"], "HL-ARCHIVE-HOURLY-METADATA-INVENTORY-R3-001")
        self.assertEqual(r["preregistration_commit"], "ab4d42be02fe49d7f90f933317ef856f0322fd85")
        self.assertEqual(r["approval_merge_commit"], "e562f3fbd8f1dac1b4d7e93eed2f5ee6b77c5da6")
        self.assertEqual(r["approval_text_sha256"], "3c3931133fb8b0dd322d7a296b7b70fca65dd341401a6eda2b6372938ed6cd10")
        self.assertEqual(
            [(row["dataset_family_id"], row["prefix"]) for row in r["dataset_families"]],
            [
                ("node_fills_by_block", "node_fills_by_block/hourly/"),
                ("node_fills", "node_fills/hourly/"),
                ("node_trades", "node_trades/hourly/"),
            ],
        )

    def test_exact_caps_and_pagination_semantics(self) -> None:
        r = self.load()
        self.assertEqual(r["maximum_keys_per_request"], 1000)
        self.assertEqual(r["maximum_pages_per_family"], 16)
        self.assertEqual(r["maximum_list_requests"], 48)
        self.assertEqual(r["maximum_total_entries"], 48000)
        self.assertEqual(r["maximum_total_response_bytes"], 33554432)
        self.assertEqual(r["maximum_runtime_seconds"], 300)
        self.assertEqual(r["maximum_retries_per_request"], 0)
        self.assertTrue(r["pagination_authorized"])
        self.assertTrue(r["continuation_token_follow_authorized"])
        self.assertFalse(r["continuation_token_values_retained"])
        self.assertTrue(r["repeated_continuation_token_fails_closed"])
        self.assertTrue(r["duplicate_key_fails_closed"])
        self.assertFalse(r["http_redirect_following_authorized"])
        self.assertFalse(r["start_after_authorized"])
        self.assertFalse(r["delimiter_authorized"])
        self.assertFalse(r["fetch_owner"])

    def test_complete_or_censored_is_not_complete_by_assumption(self) -> None:
        r = self.load()
        self.assertTrue(r["family_complete_only_if_final_page_is_truncated_false"])
        self.assertEqual(r["family_page_cap_status"], "CENSORED_BY_LIMIT")
        self.assertEqual(r["request_or_response_failure_status"], "INCOMPLETE_DUE_TO_FAILURE")
        self.assertEqual(r["invalid_key_grammar_status"], "UNRESOLVED_LAYOUT")
        self.assertTrue(r["gap_claim_requires_complete_family_enumeration"])
        self.assertTrue(r["boundary_dates_are_not_automatically_gap_tested"])
        self.assertEqual(r["internal_full_date_expected_hours"], 24)
        self.assertEqual(
            r["pass_results"],
            ["THREE_HOURLY_FAMILIES_COMPLETE", "THREE_HOURLY_FAMILIES_COMPLETE_OR_CENSORED"],
        )

    def test_immutable_implementation_snapshot_remains_non_release(self) -> None:
        r = self.load()
        self.assertEqual(r["status"], "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION")
        self.assertTrue(r["execution_release_required"])
        self.assertEqual(r["expected_canonical_implementation_commit"], "PENDING_CANONICAL_IMPLEMENTATION_MERGE")
        self.assertFalse(r["execution_release_present"])
        self.assertFalse(r["execution_authorized"])
        self.assertFalse(r["paid_request_authorized"])
        self.assertFalse(r["requester_pays_authorized"])
        self.assertFalse(r["list_objects_v2_authorized"])
        self.assertEqual(r["s3_requests_executed"], 0)
        self.assertEqual(r["metadata_entries_observed"], 0)
        self.assertIsNone(r["empirical_result"])
        if RELEASE.exists():
            release = json.loads(RELEASE.read_text(encoding="utf-8"))
            self.assertEqual(release["implementation_commit"], "3b1dd0df4c5194875e22c1b790e0b41961313aa8")
            self.assertFalse(release["execution_ready"])
            self.assertFalse(release["requester_pays_authorized"])
            self.assertFalse(release["list_objects_v2_authorized"])

    def test_forbidden_capabilities_and_trading_stay_closed(self) -> None:
        r = self.load()
        for key in (
            "get_object_authorized", "head_object_authorized", "get_object_attributes_authorized",
            "range_get_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized",
            "object_body_download_authorized", "decompression_authorized",
            "explorer_blocks_inventory_authorized", "replica_cmds_inventory_authorized",
            "market_data_ingestion_authorized", "larger_300_request_inventory_authorized",
        ):
            self.assertFalse(r[key], key)
        self.assertTrue(all(value is False for value in r["trading_authorizations"].values()))

    def test_current_state_records_consumed_run_without_mutating_implementation(self) -> None:
        status = (ROOT / "research/archive_inventory/STATUS.md").read_text(encoding="utf-8")
        self.assertIn("canonical implementation merge: `3b1dd0df4c5194875e22c1b790e0b41961313aa8`", status)
        self.assertIn("canonical human approval merge: `e562f3fbd8f1dac1b4d7e93eed2f5ee6b77c5da6`", status)
        self.assertIn("canonical release-candidate merge: `6cd8ed06f311b6cda0a6e06c4d63f1cf05a9aad5`", status)
        self.assertIn("R3_HOURLY_METADATA_INVENTORY_ATTESTED_SUCCESS", status)
        self.assertIn("CONSUMED_BY_RUN_31299905850_SUCCESS", status)
        self.assertIn("requests attempted / S3 HTTP / successful / failed: `14 / 14 / 14 / 0`", status)
        self.assertTrue(ACTIVATION.exists())
        self.assertTrue(CONSUMPTION.exists())
        activation = json.loads(ACTIVATION.read_text(encoding="utf-8"))
        consumption = json.loads(CONSUMPTION.read_text(encoding="utf-8"))
        self.assertEqual(activation["implementation_commit"], "3b1dd0df4c5194875e22c1b790e0b41961313aa8")
        self.assertEqual(consumption["status"], "CONSUMED_BY_RUN_31299905850_SUCCESS")
        self.assertFalse(consumption["rerun_authorized"])

    def test_dedicated_validator_passes(self) -> None:
        self.assertEqual(validator.main(), 0)


if __name__ == "__main__":
    unittest.main()
