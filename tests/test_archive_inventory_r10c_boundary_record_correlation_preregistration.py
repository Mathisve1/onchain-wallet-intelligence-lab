from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CONTRACT = BASE / "r10c/R10C_BOUNDARY_RECORD_CORRELATION_PREREGISTRATION.json"
ATTEST_B = BASE / "r10b_evidence/HL-ARCHIVE-R10B-BATCH-METADATA-LEXICAL-DIAGNOSTIC-001-ATTESTATION.json"
CONSUMPTION_B = BASE / "r10b_runtime/R10B_EXECUTION_RELEASE_CONSUMPTION.json"
ATTEST_A = BASE / "r10a_evidence/HL-ARCHIVE-R10A-TIMESTAMP-PARTITION-DIAGNOSTIC-001-ATTESTATION.json"


class R10CBoundaryRecordCorrelationPreregistrationTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(value, dict)
        return value

    def test_exact_parent_r10a_and_r10b_evidence_is_bound(self) -> None:
        c = self.load(CONTRACT)
        b = self.load(ATTEST_B)
        bc = self.load(CONSUMPTION_B)
        a = self.load(ATTEST_A)
        self.assertEqual(c["parent_r10b_evidence_merge_commit"], "f7acce982681f7016cf16993ab506da89643ecfd")
        self.assertEqual(c["parent_r10b_run_id"], b["workflow_run_id"])
        self.assertEqual(c["parent_r10b_artifact_id"], b["artifact_id"])
        self.assertEqual(c["parent_r10b_block_record_count"], 36029)
        self.assertEqual(c["parent_r10b_local_time_path_prefix_count"], 36029)
        self.assertEqual(c["parent_r10b_block_time_path_prefix_count"], 36028)
        self.assertEqual(c["parent_r10b_block_time_previous_prefix_count"], 1)
        self.assertTrue(bc["release_consumed"])
        self.assertEqual(bc["remaining_get_object_budget_from_consumed_release"], 0)
        self.assertEqual(c["parent_r10a_evidence_merge_commit"], "93e47e23b50068b24bcc0aa3aa1cc9d99891b8e6")
        self.assertEqual(c["parent_r10a_run_id"], a["workflow_run_id"])
        self.assertEqual(c["parent_r10a_fill_time_count"], 223950)
        self.assertEqual(c["parent_r10a_fill_time_before_path_hour_count"], 2)
        self.assertEqual(c["parent_r10a_earliest_boundary_offset_ms"], -51)

    def test_future_request_is_exact_same_immutable_one_object(self) -> None:
        c = self.load(CONTRACT)
        t = c["exact_future_network_target"]
        e = c["proposed_request_envelope"]
        self.assertEqual(t["key"], "node_fills_by_block/hourly/20250727/9.lz4")
        self.assertEqual(t["expected_size_bytes"], 18147822)
        self.assertEqual(t["expected_compressed_sha256"], "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339")
        self.assertEqual(e["maximum_get_object_requests"], 1)
        self.assertEqual(e["maximum_requests_per_object"], 1)
        self.assertEqual(e["maximum_retries_per_request"], 0)
        self.assertFalse(e["head_object_authorized"])
        self.assertFalse(e["range_get_authorized"])
        self.assertFalse(e["list_objects_v2_authorized"])
        self.assertFalse(e["http_redirect_following_authorized"])

    def test_processing_is_minimal_record_correlation_without_retention(self) -> None:
        c = self.load(CONTRACT)
        p = c["correlation_processing_rules"]
        self.assertTrue(p["event_array_contents_inspection_authorized"])
        self.assertTrue(p["event_pair_shape_inspection_authorized"])
        self.assertEqual(p["fill_object_field_allowlist"], ["time"])
        self.assertTrue(p["fill_time_integer_milliseconds_processing_authorized"])
        self.assertFalse(p["individual_fill_time_retention_authorized"])
        self.assertFalse(p["individual_metadata_value_retention_authorized"])
        self.assertFalse(p["leading_event_string_value_retention_authorized"])
        self.assertFalse(p["leading_event_string_wallet_semantics_authorized"])
        self.assertFalse(p["economic_fill_field_processing_authorized"])
        self.assertFalse(p["block_number_value_retention_authorized"])
        self.assertFalse(p["per_block_identity_retention_authorized"])
        self.assertFalse(p["per_wallet_processing_authorized"])
        self.assertFalse(p["wallet_address_retention_authorized"])
        self.assertFalse(p["metadata_timezone_parsing_authorized"])
        self.assertFalse(p["metadata_timezone_inference_authorized"])
        self.assertFalse(p["metadata_datetime_conversion_authorized"])

    def test_aggregate_classification_is_predeclared_and_conservation_bound(self) -> None:
        c = self.load(CONTRACT)
        self.assertEqual(c["correlation_success_preconditions"]["exact_parent_block_record_count_required"], 36029)
        self.assertEqual(c["correlation_success_preconditions"]["exact_parent_fill_time_count_required"], 223950)
        self.assertEqual(c["correlation_success_preconditions"]["exact_parent_before_fill_count_required"], 2)
        self.assertTrue(c["correlation_success_preconditions"]["all_aggregate_conservation_checks_required"])
        self.assertEqual(
            c["allowed_boundary_record_correlation_classifications"],
            [
                "EXACT_TWO_PRE_HOUR_FILLS_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD",
                "PRE_HOUR_FILLS_DO_NOT_EXACTLY_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD",
                "BOUNDARY_RECORD_CORRELATION_UNRESOLVED",
            ],
        )

    def test_preregistration_opens_zero_runtime_or_downstream_authority(self) -> None:
        c = self.load(CONTRACT)
        self.assertEqual(c["status"], "PREREGISTERED_NO_EXECUTION")
        self.assertTrue(all(value is False for value in c["current_runtime_authority"].values()))
        self.assertTrue(all(value is False for value in c["interpretation_boundaries"].values()))
        self.assertTrue(all(value is False for value in c["raw_or_disallowed_retention"].values()))
        self.assertTrue(all(value is False for value in c["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in c["trading_authorizations"].values()))
        self.assertEqual(c["network_requests_executed_by_preregistration"], 0)
        self.assertEqual(c["aws_iam_mutations_executed_by_preregistration"], 0)
        self.assertIsNone(c["empirical_result"])
        self.assertTrue(c["human_approval_required_before_implementation"])
        self.assertTrue(c["separate_execution_release_required"])
        self.assertTrue(c["separate_canonical_activation_required"])

    def test_primary_sources_do_not_self_resolve_semantics(self) -> None:
        c = self.load(CONTRACT)
        s = c["primary_source_assessment"]
        self.assertTrue(s["node_fills_by_block_is_write_fills_plus_batch_by_block_supported"])
        self.assertTrue(s["batch_schema_local_time_block_time_block_number_events_supported"])
        self.assertTrue(s["batch_by_block_waits_until_end_of_block_supported"])
        self.assertFalse(s["local_time_timezone_semantics_defined_by_sources"])
        self.assertFalse(s["block_time_timezone_semantics_defined_by_sources"])
        self.assertFalse(s["s3_path_hour_partition_field_defined_by_sources"])
        self.assertFalse(s["safe_fill_time_tolerance_defined_by_sources"])

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10c_boundary_record_correlation_preregistration.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10C_BOUNDARY_RECORD_CORRELATION_PREREGISTRATION_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
