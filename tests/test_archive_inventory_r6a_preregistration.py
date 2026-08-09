from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r6a"
CONTRACT = BASE / "LEGACY_USER_KEY_LEXICAL_R6A_CONTRACT.json"
DERIVATION = BASE / "R6_DERIVATION.json"


class ArchiveR6APreregistrationTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_parent_and_same_object_are_frozen(self) -> None:
        contract = self.load(CONTRACT)
        self.assertEqual(
            contract["parent_r6"]["canonical_commit"],
            "17a907923f63476c983b8c2dc131d34c491af913",
        )
        self.assertEqual(
            contract["parent_r5"]["canonical_evidence_commit"],
            "4400963aa972ed878650116202cc72880e667849",
        )
        target = contract["exact_future_network_target"]
        self.assertEqual(target["key"], "node_fills/hourly/20250727/8.lz4")
        self.assertEqual(target["expected_size_bytes"], 12726384)
        self.assertEqual(
            target["expected_compressed_sha256"],
            "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622",
        )
        self.assertEqual(target["expected_decompressed_byte_count"], 62169139)

    def test_future_request_envelope_is_exact_one_get_and_current_authority_zero(self) -> None:
        contract = self.load(CONTRACT)
        envelope = contract["proposed_future_execution_envelope"]
        self.assertEqual(envelope["maximum_one_time_budget_eur"], 0.1)
        self.assertEqual(envelope["maximum_monthly_budget_eur"], 0)
        self.assertEqual(envelope["maximum_get_object_requests"], 1)
        self.assertEqual(envelope["maximum_requests_per_object"], 1)
        self.assertEqual(envelope["maximum_retries_per_request"], 0)
        self.assertTrue(envelope["requester_pays_required"])
        self.assertFalse(envelope["range_get_authorized"])
        self.assertFalse(envelope["list_objects_v2_authorized"])

        authority = contract["current_runtime_authority"]
        self.assertFalse(authority["human_approval_recorded"])
        self.assertFalse(authority["execution_authorized"])
        self.assertFalse(authority["paid_request_authorized"])
        self.assertFalse(authority["get_object_authorized"])
        self.assertEqual(authority["s3_requests_executed"], 0)
        self.assertEqual(authority["compressed_bytes_downloaded"], 0)
        self.assertEqual(authority["decompressed_bytes_processed"], 0)
        self.assertIsNone(authority["empirical_result"])

    def test_classifier_retains_counts_but_no_addresses_or_values(self) -> None:
        classifier = self.load(CONTRACT)["proposed_streaming_lexical_classifier"]
        self.assertEqual(classifier["required_ordered_element_types"], ["string", "object"])
        self.assertEqual(classifier["expected_nonempty_record_count"], 162815)
        tests = classifier["leading_string_tests"]
        self.assertTrue(tests["count_length_42"])
        self.assertTrue(tests["count_regex_0x_40_hex_case_insensitive"])
        self.assertFalse(tests["retain_any_leading_string"])
        self.assertFalse(tests["retain_any_address"])
        self.assertFalse(tests["retain_any_hash_of_leading_string"])
        self.assertFalse(tests["retain_distinct_address_set"])
        self.assertFalse(classifier["wallet_address_retention_authorized"])
        self.assertFalse(classifier["record_payload_retention_authorized"])
        self.assertFalse(classifier["raw_compressed_object_retention_authorized"])
        self.assertFalse(classifier["raw_decompressed_payload_retention_authorized"])

    def test_lexical_result_cannot_self_open_wallet_or_trading_stages(self) -> None:
        contract = self.load(CONTRACT)
        interpretation = contract["interpretation_boundary"]
        self.assertTrue(interpretation["lexical_match_may_strengthen_parent_r6_semantic_inference"])
        self.assertFalse(interpretation["lexical_match_alone_proves_control_or_identity_of_human_owner"])
        self.assertFalse(interpretation["lexical_match_alone_authorizes_wallet_address_retention"])
        self.assertFalse(interpretation["wallet_reconstruction_authorized"])
        self.assertFalse(interpretation["entity_clustering_authorized"])
        self.assertFalse(interpretation["copyability_analysis_authorized"])
        self.assertFalse(interpretation["pnl_or_alpha_analysis_authorized"])
        self.assertFalse(interpretation["market_data_ingestion_authorized"])
        self.assertTrue(all(value is False for value in contract["trading_authorizations"].values()))

    def test_derivation_is_minimal_and_nonexecuting(self) -> None:
        derivation = self.load(DERIVATION)
        self.assertEqual(
            derivation["child_gate_id"],
            "HL-ARCHIVE-LEGACY-USER-KEY-LEXICAL-R6A-001",
        )
        self.assertFalse(derivation["current_network_authority"])
        self.assertFalse(derivation["current_paid_request_authority"])
        self.assertFalse(derivation["current_wallet_address_retention_authority"])
        self.assertFalse(derivation["current_wallet_reconstruction_authority"])
        self.assertFalse(derivation["current_trading_authority"])

    def test_dedicated_preregistration_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r6a_preregistration.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R6A_PREREGISTRATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
