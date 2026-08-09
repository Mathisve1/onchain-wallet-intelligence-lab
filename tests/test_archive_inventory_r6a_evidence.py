from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r6a"
RUN = BASE / "evidence/run-31328268134"


class ArchiveR6AEvidenceTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_successor_run_and_artifact_are_bound(self) -> None:
        context = self.load(RUN / "r6a-successor-context.json")
        verification = self.load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
        self.assertEqual(context["workflow_run_id"], 31328268134)
        self.assertEqual(context["workflow_run_attempt"], 1)
        self.assertEqual(context["dispatch_sha"], "161b3ff76c3a1903a633f4b3317386ef1cc7b38b")
        self.assertEqual(context["configure_aws_outcome"], "success")
        self.assertEqual(verification["workflow_job_id"], 93282146403)
        self.assertEqual(verification["artifact_id"], 9042152700)
        self.assertEqual(verification["artifact_size_bytes"], 2360)
        self.assertTrue(verification["provider_and_independent_zip_digest_match"])
        self.assertEqual(
            verification["provider_artifact_zip_sha256"],
            "928a5d378a63f2da62d44f939e56a99a578637faa10e52c54b3fdc1556d0d93f",
        )

    def test_all_leading_strings_match_lowercase_address_shape(self) -> None:
        result = self.load(RUN / "r6a-successor-result.json")
        self.assertEqual(result["terminal_status"], "R6A_LEXICAL_CONFIRMATION_COMPLETE")
        self.assertEqual(result["research_conclusion"], "ALL_LEADING_STRINGS_MATCH_HYPERLIQUID_ADDRESS_SHAPE")
        lexical = result["lexical_aggregates"]
        self.assertEqual(lexical["nonempty_record_count"], 162815)
        self.assertEqual(lexical["pair_string_object_record_count"], 162815)
        self.assertEqual(lexical["leading_string_count"], 162815)
        self.assertEqual(lexical["leading_string_length_42_count"], 162815)
        self.assertEqual(lexical["leading_string_0x40hex_count"], 162815)
        self.assertEqual(lexical["leading_string_lowercase_0x40hex_count"], 162815)
        self.assertEqual(lexical["leading_string_non_0x40hex_count"], 0)

    def test_exact_one_getobject_consumed_r6a_chain_budget(self) -> None:
        result = self.load(RUN / "r6a-successor-result.json")
        consumption = self.load(BASE / "R6A_EXECUTION_RELEASE_002_CONSUMPTION.json")
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["s3_http_request_count"], 1)
        self.assertEqual(result["successful_request_count"], 1)
        self.assertEqual(result["failed_request_count"], 0)
        self.assertEqual(result["retries_used"], 0)
        self.assertFalse(result["http_redirects_followed"])
        self.assertTrue(consumption["release_consumed"])
        self.assertFalse(consumption["future_r6a_dispatch_authorized"])
        self.assertFalse(consumption["rerun_authorized"])
        self.assertEqual(consumption["aggregate_get_object_requests_across_r6a_release_chain_after_run"], 1)
        self.assertEqual(consumption["maximum_aggregate_get_object_requests_across_r6a_release_chain"], 1)
        self.assertEqual(consumption["remaining_approved_get_object_budget"], 0)

    def test_no_addresses_payload_or_downstream_analysis_were_retained(self) -> None:
        result = self.load(RUN / "r6a-successor-result.json")
        for key in (
            "raw_compressed_object_persisted",
            "raw_decompressed_payload_retained",
            "record_payload_retained",
            "payload_values_retained",
            "string_values_retained",
            "numeric_values_retained",
            "leading_string_values_retained",
            "wallet_addresses_retained",
            "leading_string_hashes_retained",
            "distinct_address_set_retained",
            "wallet_reconstruction_performed",
            "entity_clustering_performed",
            "copyability_analysis_performed",
            "pnl_or_alpha_analysis_performed",
            "market_data_ingested",
        ):
            self.assertFalse(result[key], key)

    def test_combined_semantic_claim_remains_precise(self) -> None:
        attestation = self.load(BASE / "evidence/HL-ARCHIVE-LEGACY-USER-KEY-LEXICAL-R6A-001-ATTESTATION.json")
        self.assertEqual(attestation["parent_r6_semantic_label"], "HYPERLIQUID_USER_ADDRESS")
        self.assertEqual(attestation["parent_r6_semantic_label_status"], "SUPPORTED_INFERENCE_NOT_DIRECT_SERIALIZER_PROOF")
        combined = attestation["combined_r6_r6a_interpretation"]
        self.assertEqual(combined["semantic_label"], "HYPERLIQUID_USER_ADDRESS")
        self.assertEqual(
            combined["status"],
            "HIGH_CONFIDENCE_CONVERGENT_STATIC_AND_LEXICAL_EVIDENCE_NOT_DIRECT_SERIALIZER_PROOF",
        )
        self.assertIn("unpublished node serializer", " ".join(attestation["claims_not_proven"]))

    def test_all_trading_authorizations_remain_closed(self) -> None:
        consumption = self.load(BASE / "R6A_EXECUTION_RELEASE_002_CONSUMPTION.json")
        attestation = self.load(BASE / "evidence/HL-ARCHIVE-LEGACY-USER-KEY-LEXICAL-R6A-001-ATTESTATION.json")
        self.assertTrue(all(value is False for value in consumption["trading_authorizations_after_run"].values()))
        self.assertTrue(all(value is False for value in attestation["trading_authorizations_after_run"].values()))

    def test_dedicated_evidence_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r6a_evidence.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R6A_EVIDENCE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
