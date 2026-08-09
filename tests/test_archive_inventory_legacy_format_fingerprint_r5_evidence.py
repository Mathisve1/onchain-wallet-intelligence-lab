from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r5"
RUN = BASE / "evidence/run-31321019885"
RESULT = RUN / "r5-format-result.json"
ATTEST = BASE / "evidence/HL-ARCHIVE-LEGACY-FORMAT-FINGERPRINT-R5-001-ATTESTATION.json"
CONSUMPTION = BASE / "R5_EXECUTION_RELEASE_CONSUMPTION.json"


class ArchiveLegacyFormatFingerprintR5EvidenceTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_terminal_result_resolves_only_structural_legacy_format(self) -> None:
        result = self.load(RESULT)
        self.assertEqual(result["terminal_status"], "R5_LEGACY_FORMAT_FINGERPRINT_COMPLETE")
        self.assertEqual(result["technical_result"], "LEGACY_FORMAT_RESOLVED_AS_NDJSON_PAIR_STRING_OBJECT")
        self.assertEqual(result["research_conclusion"], result["technical_result"])
        self.assertEqual(result["format_class"], "UTF8_NDJSON_PAIR_STRING_OBJECT")
        self.assertFalse(result["semantic_wallet_or_user_label_inferred"])
        self.assertFalse(result["schema_equivalence_inferred"])
        self.assertFalse(result["semantic_equivalence_inferred"])

    def test_exact_object_was_retrieved_once_and_integrity_bound(self) -> None:
        result = self.load(RESULT)
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["s3_http_request_count"], 1)
        self.assertEqual(result["successful_request_count"], 1)
        self.assertEqual(result["failed_request_count"], 0)
        self.assertEqual(result["compressed_bytes"], 12726384)
        self.assertEqual(result["decompressed_bytes"], 62169139)
        self.assertEqual(result["compressed_sha256"], result["expected_compressed_sha256"])
        self.assertEqual(result["expected_content_length"], result["compressed_bytes"])
        self.assertEqual(result["expected_decompressed_byte_count"], result["decompressed_bytes"])
        self.assertTrue(result["requester_pays_requested"])
        self.assertEqual(result["retries_used"], 0)
        self.assertFalse(result["http_redirects_followed"])

    def test_all_observed_records_have_exact_pair_string_object_shape(self) -> None:
        structural = self.load(RESULT)["structural_evidence"]
        self.assertEqual(structural["nonempty_record_count"], 162815)
        self.assertEqual(structural["json_root_type_counts"], {"array": 162815})
        self.assertEqual(structural["array_arity_histogram"], {"2": 162815})
        self.assertEqual(structural["array_element_type_signature_counts"], {"string,object": 162815})
        self.assertEqual(structural["maximum_observed_nesting_depth"], 4)
        self.assertEqual(structural["resolved_format_class"], "UTF8_NDJSON_PAIR_STRING_OBJECT")
        self.assertEqual(len(structural["object_field_path_names"]), 22)
        self.assertEqual(
            structural["structural_signature_hash_counts"],
            {"67bd92e8a68448200dee809c42bca37256b7db99ef54c5c056e36fc7f6edf27f": 162815},
        )

    def test_payload_semantic_wallet_market_and_trading_analysis_remain_absent(self) -> None:
        result = self.load(RESULT)
        for key in (
            "raw_compressed_object_persisted", "raw_decompressed_payload_retained",
            "record_payload_retained", "wallet_addresses_retained_from_body",
            "payload_values_retained", "string_values_retained", "numeric_values_retained",
            "semantic_wallet_or_user_label_inferred", "schema_equivalence_inferred",
            "semantic_equivalence_inferred", "wallet_reconstruction_performed",
            "entity_clustering_performed", "copyability_analysis_performed",
            "pnl_or_alpha_analysis_performed", "market_data_ingested",
        ):
            self.assertFalse(result[key], key)

    def test_release_is_consumed_and_never_rerunnable(self) -> None:
        attestation = self.load(ATTEST)
        consumption = self.load(CONSUMPTION)
        self.assertTrue(attestation["release_consumed"])
        self.assertFalse(attestation["rerun_authorized"])
        self.assertTrue(consumption["release_consumed"])
        self.assertFalse(consumption["rerun_authorized"])
        self.assertFalse(consumption["future_r5_dispatch_authorized"])
        self.assertFalse(consumption["future_r5_rerun_authorized"])
        self.assertTrue(all(value is False for value in consumption["trading_authorizations_after_run"].values()))

    def test_dedicated_evidence_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r5_evidence.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R5_LEGACY_FORMAT_EVIDENCE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
