from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4"
RUN = BASE / "evidence/run-31313913525"
RESULT = RUN / "r4-body-result.json"
ATTEST = BASE / "evidence/HL-ARCHIVE-HOURLY-BODY-SCHEMA-PILOT-R4-001-ATTESTATION.json"
CONSUMPTION = BASE / "R4_EXECUTION_RELEASE_CONSUMPTION.json"


class ArchiveHourlyBodySchemaR4EvidenceTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_terminal_result_is_unresolved_not_equivalent_or_incompatible(self) -> None:
        result = self.load(RESULT)
        self.assertEqual(result["terminal_status"], "R4_BODY_SCHEMA_PILOT_COMPLETE")
        self.assertEqual(result["technical_result"], "TWO_OBJECT_BODY_FORMAT_UNRESOLVED")
        self.assertEqual(result["schema_comparison_class"], "SCHEMA_UNRESOLVED")
        self.assertFalse(result["semantic_equivalence_inferred"])

    def test_both_exact_objects_were_successfully_retrieved_and_lz4_decompressed(self) -> None:
        result = self.load(RESULT)
        self.assertEqual(result["request_attempt_count"], 2)
        self.assertEqual(result["s3_http_request_count"], 2)
        self.assertEqual(result["successful_request_count"], 2)
        self.assertEqual(result["failed_request_count"], 0)
        self.assertEqual(result["total_compressed_bytes"], 14243987)
        self.assertEqual(len(result["observations"]), 2)
        for row in result["observations"]:
            self.assertEqual(row["status"], "OBJECT_PROCESSED")
            self.assertEqual(row["http_status"], 200)
            self.assertEqual(row["request_charged"], "requester")
            self.assertTrue(row["lz4_frame_recognized"])
            self.assertEqual(row["decompression_status"], "LZ4_FRAME_DECOMPRESSED")
            self.assertEqual(row["observed_etag"], row["expected_etag"])
            self.assertEqual(row["observed_content_length"], row["expected_content_length"])

    def test_legacy_format_is_unresolved_while_modern_schema_is_fully_parsed(self) -> None:
        legacy, modern = self.load(RESULT)["observations"]
        self.assertEqual(legacy["dataset_family_id"], "node_fills")
        self.assertEqual(legacy["decompressed_byte_count"], 62169139)
        self.assertEqual(legacy["schema_status"], "BODY_READABLE_SCHEMA_UNRESOLVED")
        self.assertEqual(legacy["failure_class"], "UTF8_NDJSON_OBJECT_SCHEMA_UNRESOLVED")
        self.assertEqual(legacy["record_count"], 0)
        self.assertEqual(modern["dataset_family_id"], "node_fills_by_block")
        self.assertEqual(modern["decompressed_byte_count"], 7380378)
        self.assertEqual(modern["schema_status"], "FULL_SCHEMA_PARSED")
        self.assertEqual(modern["record_count"], 4345)
        self.assertEqual(modern["maximum_observed_nesting_depth"], 4)
        self.assertEqual(len(modern["field_path_names"]), 23)

    def test_payload_and_downstream_analysis_remain_absent(self) -> None:
        result = self.load(RESULT)
        for key in (
            "raw_compressed_object_persisted", "raw_decompressed_payload_retained",
            "record_payload_retained", "wallet_addresses_retained_from_body",
            "payload_values_retained", "semantic_equivalence_inferred",
            "wallet_reconstruction_performed", "entity_clustering_performed",
            "copyability_analysis_performed", "pnl_or_alpha_analysis_performed",
            "market_data_ingested",
        ):
            self.assertFalse(result[key], key)
        self.assertIsNone(result["empirical_result"])

    def test_release_is_consumed_and_never_rerunnable(self) -> None:
        attestation = self.load(ATTEST)
        consumption = self.load(CONSUMPTION)
        self.assertTrue(attestation["release_consumed"])
        self.assertFalse(attestation["rerun_authorized"])
        self.assertTrue(consumption["release_consumed"])
        self.assertFalse(consumption["rerun_authorized"])
        self.assertFalse(consumption["future_r4_dispatch_authorized"])
        self.assertTrue(all(value is False for value in consumption["trading_authorizations_after_run"].values()))

    def test_dedicated_evidence_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r4_evidence.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R4_BODY_EVIDENCE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
