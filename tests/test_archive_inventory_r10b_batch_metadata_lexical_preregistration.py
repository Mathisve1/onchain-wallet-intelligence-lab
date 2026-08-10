from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
R10B = BASE / "r10b"
CONTRACT = R10B / "R10B_BATCH_METADATA_LEXICAL_PREREGISTRATION.json"


class R10BBatchMetadataLexicalPreregistrationTests(unittest.TestCase):
    @staticmethod
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_parent_is_exact_r10a_fill_time_spill_evidence(self) -> None:
        c = self.load(CONTRACT)
        self.assertEqual(c["parent_r10a_evidence_merge_commit"], "93e47e23b50068b24bcc0aa3aa1cc9d99891b8e6")
        self.assertEqual(c["parent_r10a_run_id"], 31386230522)
        self.assertEqual(c["parent_r10a_research_conclusion"], "FILL_TIME_SPILLS_OUTSIDE_PATH_HOUR")
        self.assertEqual(c["parent_r10a_fill_time_count"], 223950)
        self.assertEqual(c["parent_r10a_fill_time_before_path_hour_count"], 2)
        self.assertEqual(c["parent_r10a_fill_time_after_path_hour_count"], 0)
        self.assertEqual(c["parent_r10a_earliest_boundary_offset_ms"], -51)
        self.assertTrue(c["parent_r10a_release_consumed"])
        self.assertFalse(c["parent_r10a_rerun_authorized"])

    def test_primary_sources_do_not_resolve_partition_semantics(self) -> None:
        c = self.load(CONTRACT)
        s = c["primary_source_assessment"]
        self.assertTrue(s["node_fills_by_block_is_write_fills_plus_batch_by_block_supported"])
        self.assertTrue(s["batch_schema_local_time_block_time_block_number_events_supported"])
        self.assertFalse(s["path_hour_defined_by_fill_time_supported"])
        self.assertFalse(s["batch_metadata_timezone_defined_by_sources"])
        self.assertFalse(s["safe_fill_time_tolerance_defined_by_sources"])

    def test_future_request_is_exact_one_same_immutable_object(self) -> None:
        c = self.load(CONTRACT)
        t = c["exact_future_network_target"]
        e = c["proposed_request_envelope"]
        self.assertEqual(t["key"], "node_fills_by_block/hourly/20250727/9.lz4")
        self.assertEqual(t["expected_size_bytes"], 18147822)
        self.assertEqual(t["expected_etag"], '"5a9941a240118a57f77a4c3ee95b8430-3"')
        self.assertEqual(t["expected_compressed_sha256_from_r10a"], "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339")
        self.assertEqual(e["maximum_get_object_requests"], 1)
        self.assertEqual(e["maximum_requests_per_object"], 1)
        self.assertEqual(e["maximum_retries_per_request"], 0)
        self.assertTrue(e["requester_pays_required"])
        self.assertTrue(e["compressed_sha256_must_match_parent_r10a"])

    def test_processing_is_lexical_only_without_event_or_wallet_inspection(self) -> None:
        c = self.load(CONTRACT)
        r = c["decompression_and_record_rules"]
        l = c["lexical_classification_rules"]
        self.assertFalse(r["event_array_contents_inspection_authorized"])
        self.assertFalse(r["event_pair_count_retention_authorized"])
        self.assertFalse(r["block_number_value_retention_authorized"])
        self.assertFalse(l["timezone_parsing_authorized"])
        self.assertFalse(l["timezone_inference_authorized"])
        self.assertFalse(l["datetime_conversion_authorized"])
        self.assertFalse(l["individual_metadata_value_retention_authorized"])
        retained = set(c["retained_aggregate_fields_only"])
        self.assertIn("local_time_lexical_class_counts", retained)
        self.assertIn("block_time_lexical_class_counts", retained)
        self.assertIn("local_time_prefix_bucket_counts", retained)
        self.assertNotIn("wallet_address", retained)
        self.assertNotIn("fill_time", retained)
        self.assertNotIn("closedPnl", retained)
        self.assertTrue(all(v is False for v in c["raw_or_disallowed_retention"].values()))

    def test_preregistration_opens_zero_runtime_or_downstream_authority(self) -> None:
        c = self.load(CONTRACT)
        self.assertEqual(c["status"], "PREREGISTERED_NO_EXECUTION")
        self.assertTrue(all(v is False for v in c["current_runtime_authority"].values()))
        self.assertTrue(all(v is False for v in c["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in c["trading_authorizations"].values()))
        self.assertEqual(c["network_requests_executed_by_preregistration"], 0)
        self.assertEqual(c["aws_iam_mutations_executed_by_preregistration"], 0)
        self.assertIsNone(c["empirical_result"])

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10b_batch_metadata_lexical_preregistration.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10B_BATCH_METADATA_LEXICAL_PREREGISTRATION_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
