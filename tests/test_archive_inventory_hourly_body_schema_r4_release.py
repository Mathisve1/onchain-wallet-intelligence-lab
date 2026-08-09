from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4"
RELEASE = BASE / "R4_EXECUTION_RELEASE.json"
PRICING = BASE / "R4_PRICING_EVIDENCE.json"
ACTIVATION = BASE / "R4_EXECUTION_RELEASE_CANONICALIZATION.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-hourly-body-schema-pilot-r4.yml"
IMPLEMENTATION = "180c89ead78f9a6f4560a1ec12575658e62586ee"


class ArchiveHourlyBodySchemaR4ReleaseTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_release_binds_exact_canonical_lineage_and_pricing(self) -> None:
        release = self.load(RELEASE)
        pricing = self.load(PRICING)
        self.assertEqual(release["release_id"], "RELEASE_HL_ARCHIVE_HOURLY_BODY_SCHEMA_PILOT_R4_001")
        self.assertEqual(release["preregistration_commit"], "25a1f621d15cb708a485893025f03b991628aae1")
        self.assertEqual(release["approval_merge_commit"], "0191350683c6c943d3538c8c51db176cd1d58211")
        self.assertEqual(release["approval_text_sha256"], "e52399feb7a0d36959089f556dd9f55062eb91d52feaa4c5af680d3c4e557264")
        self.assertEqual(release["implementation_commit"], IMPLEMENTATION)
        self.assertEqual(release["pricing_status"], pricing["pricing_status"])
        self.assertTrue(pricing["checked_at_utc"].startswith("2026-08-09T"))
        self.assertFalse(pricing["execution_authorized_by_this_file"])
        self.assertEqual(pricing["requests_executed"], 0)
        self.assertIsNone(pricing["empirical_result"])

    def test_release_envelope_exactly_matches_approved_scope(self) -> None:
        release = self.load(RELEASE)
        self.assertEqual(release["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(release["maximum_monthly_budget_eur"], 0)
        self.assertEqual(release["object_keys"], [
            "node_fills/hourly/20250727/8.lz4",
            "node_fills_by_block/hourly/20250727/8.lz4",
        ])
        self.assertEqual(release["object_sizes_bytes"], [12726384, 1517603])
        self.assertEqual(release["maximum_get_object_requests"], 2)
        self.assertEqual(release["maximum_requests_per_object"], 1)
        self.assertEqual(release["maximum_total_compressed_bytes"], 14243987)
        self.assertEqual(release["maximum_total_decompressed_bytes"], 536870912)
        self.assertEqual(release["maximum_decompressed_bytes_per_object"], 268435456)
        self.assertEqual(release["maximum_runtime_seconds"], 180)
        self.assertEqual(release["maximum_retries_per_request"], 0)
        self.assertTrue(release["if_match_etag_required"])
        self.assertTrue(release["exact_content_length_required"])
        self.assertTrue(release["requester_pays_scope_approved"])
        self.assertTrue(release["get_object_scope_approved"])
        self.assertTrue(release["decompression_scope_approved"])

    def test_candidate_cannot_self_execute_and_later_activation_is_separate(self) -> None:
        release = self.load(RELEASE)
        self.assertEqual(release["status"], "RELEASE_CANDIDATE_AWAITING_DEDICATED_R4_ROLE_ATTESTATION")
        self.assertFalse(release["dedicated_r4_role_operator_attested"])
        self.assertFalse(release["dedicated_r4_role_independently_verified"])
        self.assertIsNone(release["single_use_window_start_utc"])
        self.assertFalse(release["single_workflow_dispatch_authorized"])
        self.assertFalse(release["requester_pays_authorized"])
        self.assertFalse(release["get_object_authorized"])
        self.assertFalse(release["decompression_authorized"])
        self.assertFalse(release["execution_ready"])
        workflow = WORKFLOW.read_text(encoding="utf-8")
        if ACTIVATION.exists():
            activation = self.load(ACTIVATION)
            self.assertTrue(activation["release_candidate_immutable"])
            self.assertEqual(activation["release_id"], release["release_id"])
            self.assertEqual(activation["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R4_RUN")
            self.assertEqual(activation["implementation_commit"], IMPLEMENTATION)
            self.assertEqual(activation["preflight_evidence_merge_commit"], "a91f0849e8cf14b6924da73ca2b72595deab5d8d")
            self.assertEqual(activation["preflight_run_id"], 31312067367)
            self.assertTrue(activation["dedicated_r4_role_independently_verified"])
            self.assertTrue(activation["single_workflow_dispatch_authorized"])
            self.assertFalse(activation["rerun_authorized"])
            self.assertTrue(activation["execution_ready"])
            self.assertIn(f"EXPECTED_IMPLEMENTATION_COMMIT: {IMPLEMENTATION}", workflow)
        else:
            self.assertIn("EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE", workflow)
        self.assertIn("R4 release gate 45", workflow)

    def test_all_broader_capabilities_and_trading_stay_closed(self) -> None:
        release = self.load(RELEASE)
        for key in (
            "object_body_download_authorized", "head_object_authorized", "range_get_authorized",
            "list_objects_v2_authorized", "list_object_versions_authorized", "list_all_my_buckets_authorized",
            "http_redirect_following_authorized", "alternate_decompressor_fallback_authorized",
            "raw_compressed_object_retention_authorized", "raw_decompressed_payload_retention_authorized",
            "record_payload_retention_authorized", "wallet_address_retention_from_body_authorized",
            "payload_values_in_schema_evidence_authorized", "semantic_equivalence_inference_authorized",
            "wallet_reconstruction_authorized", "entity_clustering_authorized", "copyability_analysis_authorized",
            "pnl_or_alpha_analysis_authorized", "market_data_ingestion_authorized",
        ):
            self.assertFalse(release[key], key)
        self.assertTrue(all(value is False for value in release["trading_authorizations"].values()))
        self.assertEqual(release["s3_requests_executed"], 0)
        self.assertEqual(release["compressed_bytes_downloaded"], 0)
        self.assertEqual(release["decompressed_bytes_processed"], 0)
        self.assertIsNone(release["empirical_result"])

    def test_r3_proves_both_selected_objects_are_standard_storage(self) -> None:
        pricing = self.load(PRICING)
        evidence = pricing["r3_storage_class_evidence"]
        self.assertEqual(evidence["source_run_id"], 31299905850)
        self.assertEqual(evidence["source_artifact_id"], 9034170863)
        self.assertEqual(evidence["source_raw_result_sha256"], "94c3e77a05de2363b95abdce718dfd61f1b440f3d9c3972a0d03ce28a9edc479")
        self.assertEqual(evidence["object_1_storage_class"], "STANDARD")
        self.assertEqual(evidence["object_2_storage_class"], "STANDARD")
        self.assertFalse(evidence["storage_class_retrieval_surcharge_inferred"])

    def test_dedicated_release_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r4_release.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R4_RELEASE_CANDIDATE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
