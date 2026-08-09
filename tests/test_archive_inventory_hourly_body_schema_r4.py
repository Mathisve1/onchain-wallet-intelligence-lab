from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4"
CONTRACT = BASE / "HOURLY_BODY_SCHEMA_PILOT_R4_CONTRACT.json"
DERIVATION = BASE / "R3_DERIVATION.json"
APPROVAL_TEMPLATE = BASE / "HUMAN_APPROVAL_TEMPLATE.md"


class ArchiveHourlyBodySchemaR4Tests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(value, dict)
        return value

    def test_parent_r3_evidence_is_exactly_bound(self) -> None:
        c = self.load(CONTRACT)
        d = self.load(DERIVATION)
        self.assertEqual(c["pilot_id"], "HL-ARCHIVE-HOURLY-BODY-SCHEMA-PILOT-R4-001")
        self.assertEqual(c["parent_r3_evidence_merge_commit"], "98eca5b7b13b25aed3d11f006972acea2ee5c258")
        self.assertEqual(c["parent_r3_run_id"], 31299905850)
        self.assertEqual(c["parent_r3_artifact_id"], 9034170863)
        self.assertEqual(c["parent_r3_artifact_sha256"], "1049509ef12f1ef2a312f6ded1d443b434e2ed860503a264f103a73c2a70cf88")
        self.assertEqual(d["source_r3_evidence_merge_commit"], c["parent_r3_evidence_merge_commit"])
        self.assertEqual(d["source_r3_raw_result_sha256"], "94c3e77a05de2363b95abdce718dfd61f1b440f3d9c3972a0d03ce28a9edc479")
        self.assertEqual(d["source_r3_technical_result"], "THREE_HOURLY_FAMILIES_COMPLETE")

    def test_exact_same_hour_two_object_selection(self) -> None:
        c = self.load(CONTRACT)
        objects = c["selected_objects"]
        self.assertEqual(len(objects), 2)
        self.assertEqual(objects[0]["key"], "node_fills/hourly/20250727/8.lz4")
        self.assertEqual(objects[0]["path_hour_utc"], "2025-07-27T08:00:00Z")
        self.assertEqual(objects[0]["r3_observed_size_bytes"], 12726384)
        self.assertEqual(objects[0]["r3_observed_etag"], '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"')
        self.assertEqual(objects[1]["key"], "node_fills_by_block/hourly/20250727/8.lz4")
        self.assertEqual(objects[1]["path_hour_utc"], "2025-07-27T08:00:00Z")
        self.assertEqual(objects[1]["r3_observed_size_bytes"], 1517603)
        self.assertEqual(objects[1]["r3_observed_etag"], '"60d4c1277f76651b5f04666bbe8d7594"')
        self.assertEqual(sum(row["r3_observed_size_bytes"] for row in objects), 14243987)
        self.assertEqual(c["maximum_total_compressed_bytes"], 14243987)

    def test_request_and_object_identity_guards_are_fail_closed(self) -> None:
        c = self.load(CONTRACT)
        self.assertEqual(c["maximum_get_object_requests"], 2)
        self.assertEqual(c["maximum_requests_per_object"], 1)
        self.assertEqual(c["maximum_retries_per_request"], 0)
        self.assertTrue(c["require_exact_content_length_match_r3_metadata"])
        self.assertTrue(c["require_if_match_etag"])
        self.assertTrue(c["etag_mismatch_fails_before_body_acceptance"])
        self.assertFalse(c["http_redirect_following_authorized"])
        self.assertFalse(c["range_get_authorized"])
        self.assertFalse(c["head_object_authorized"])
        self.assertFalse(c["list_objects_v2_authorized"])
        self.assertFalse(c["list_object_versions_authorized"])
        self.assertFalse(c["list_all_my_buckets_authorized"])

    def test_decompression_and_schema_processing_are_bounded(self) -> None:
        c = self.load(CONTRACT)
        self.assertEqual(c["maximum_runtime_seconds"], 180)
        self.assertEqual(c["decompression_mode_after_separate_human_approval"], "LZ4_FRAME_STREAM_ONLY")
        self.assertTrue(c["unrecognized_container_fails_closed"])
        self.assertFalse(c["alternate_decompressor_fallback_authorized"])
        self.assertEqual(c["maximum_total_decompressed_bytes"], 536870912)
        self.assertEqual(c["maximum_decompressed_bytes_per_object"], 268435456)
        self.assertEqual(c["schema_parser_mode"], "UTF8_NDJSON_OBJECT_STREAM_ONLY")
        self.assertEqual(c["maximum_record_bytes"], 16777216)
        self.assertEqual(c["maximum_records_parsed_per_object"], 5000000)
        self.assertEqual(c["maximum_schema_nesting_depth"], 16)
        self.assertEqual(c["maximum_unique_field_paths"], 4096)
        self.assertTrue(c["schema_equivalence_requires_full_uncensored_parse_of_both_objects"])
        self.assertFalse(c["semantic_equivalence_inference_authorized"])

    def test_payload_retention_and_downstream_analysis_remain_closed(self) -> None:
        c = self.load(CONTRACT)
        for key in (
            "raw_compressed_object_retention_authorized",
            "raw_decompressed_payload_retention_authorized",
            "record_payload_retention_authorized",
            "wallet_address_retention_from_body_authorized",
            "payload_values_in_schema_evidence_authorized",
            "wallet_reconstruction_authorized",
            "entity_clustering_authorized",
            "copyability_analysis_authorized",
            "pnl_or_alpha_analysis_authorized",
            "market_data_ingestion_authorized",
            "integration_authorized",
            "paper_authorized",
            "shadow_authorized",
            "live_authorized",
            "leverage_authorized",
            "capital_allocation_authorized",
        ):
            self.assertFalse(c[key], key)

    def test_preregistration_has_zero_current_runtime_authority(self) -> None:
        c = self.load(CONTRACT)
        self.assertEqual(c["status"], "PREREGISTERED_STATIC_ONLY_NO_EXECUTION")
        self.assertTrue(c["human_approval_required_before_implementation"])
        self.assertFalse(c["get_object_authorized"])
        self.assertFalse(c["requester_pays_authorized"])
        self.assertFalse(c["object_body_download_authorized"])
        self.assertFalse(c["decompression_authorized"])
        self.assertFalse(c["execution_authorized"])
        self.assertEqual(c["requests_executed"], 0)
        self.assertEqual(c["compressed_bytes_downloaded"], 0)
        self.assertEqual(c["decompressed_bytes_processed"], 0)
        self.assertIsNone(c["empirical_result"])
        self.assertEqual(c["maximum_one_time_budget_eur_proposed"], 0.10)
        self.assertEqual(c["maximum_monthly_budget_eur_proposed"], 0)
        self.assertEqual(c["pricing_status"], "PROPOSED_CEILING_REQUIRES_FRESH_PRE_EXECUTION_VERIFICATION")

    def test_no_r4_executable_or_workflow_exists(self) -> None:
        self.assertFalse((BASE / "collector.py").exists())
        self.assertFalse((BASE / "R4_EXECUTION_RELEASE.json").exists())
        workflows = ROOT / ".github/workflows"
        self.assertFalse(any("r4" in path.name.lower() for path in workflows.glob("*.yml")))
        self.assertFalse(any("r4" in path.name.lower() for path in workflows.glob("*.yaml")))

    def test_approval_template_repeats_exact_frozen_boundary(self) -> None:
        text = APPROVAL_TEMPLATE.read_text(encoding="utf-8")
        for needle in (
            "APPROVE_HL_ARCHIVE_HOURLY_BODY_SCHEMA_PILOT_R4_001",
            "reviewed_commit=<CANONICAL_R4_PREREGISTRATION_COMMIT>",
            "maximum_get_object_requests=2",
            "maximum_total_compressed_bytes=14243987",
            "object_1_key=node_fills/hourly/20250727/8.lz4",
            'object_1_etag="b21cdc16a4ec69d9c5b72c0c27ff148d-2"',
            "object_2_key=node_fills_by_block/hourly/20250727/8.lz4",
            'object_2_etag="60d4c1277f76651b5f04666bbe8d7594"',
            "get_object_authorized=true",
            "decompression_authorized=true",
            "raw_compressed_object_retention_authorized=false",
            "wallet_reconstruction_authorized=false",
            "live_authorized=false",
        ):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
