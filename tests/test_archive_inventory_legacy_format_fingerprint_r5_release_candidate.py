from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r5"
CANDIDATE = BASE / "R5_EXECUTION_RELEASE_CANDIDATE.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-legacy-format-fingerprint-r5.yml"


class ArchiveLegacyFormatFingerprintR5ReleaseCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))

    def test_release_candidate_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r5_release_candidate.py")],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R5_RELEASE_CANDIDATE_VALID", completed.stdout)

    def test_candidate_is_bound_to_exact_reviewed_implementation_bytes(self) -> None:
        self.assertEqual(self.candidate["implementation_pr"], 58)
        self.assertEqual(
            self.candidate["implementation_reviewed_exact_head"],
            "9128783516942ee40050986fb33c467279eba700",
        )
        for path_text, expected in self.candidate["implementation_file_sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / path_text).read_bytes()).hexdigest(), expected)

    def test_candidate_matches_approved_one_object_budget_and_caps(self) -> None:
        self.assertEqual(self.candidate["object_key"], "node_fills/hourly/20250727/8.lz4")
        self.assertEqual(self.candidate["object_size_bytes"], 12726384)
        self.assertEqual(self.candidate["maximum_get_object_requests"], 1)
        self.assertEqual(self.candidate["maximum_requests_per_object"], 1)
        self.assertEqual(self.candidate["maximum_total_compressed_bytes"], 12726384)
        self.assertEqual(self.candidate["maximum_total_decompressed_bytes"], 134217728)
        self.assertEqual(self.candidate["maximum_runtime_seconds"], 120)
        self.assertEqual(self.candidate["maximum_retries_per_request"], 0)
        self.assertEqual(self.candidate["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(self.candidate["maximum_monthly_budget_eur"], 0)

    def test_candidate_cannot_self_authorize_runtime(self) -> None:
        self.assertEqual(self.candidate["status"], "RELEASE_CANDIDATE_INERT_AWAITING_CANONICAL_ACTIVATION")
        for key in (
            "requester_pays_authorized_by_candidate", "get_object_authorized_by_candidate",
            "decompression_authorized_by_candidate", "format_classification_authorized_by_candidate",
            "single_workflow_dispatch_authorized", "rerun_authorized", "execution_ready",
        ):
            self.assertFalse(self.candidate[key], key)
        self.assertIsNone(self.candidate["single_use_window_start_utc"])
        self.assertEqual(self.candidate["s3_requests_executed"], 0)
        self.assertEqual(self.candidate["compressed_bytes_downloaded"], 0)
        self.assertEqual(self.candidate["decompressed_bytes_processed"], 0)
        self.assertIsNone(self.candidate["empirical_result"])
        self.assertFalse((BASE / "R5_EXECUTION_RELEASE.json").exists())
        self.assertFalse((BASE / "R5_EXECUTION_RELEASE_CANONICALIZATION.json").exists())
        self.assertIn("EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE", WORKFLOW.read_text(encoding="utf-8"))

    def test_broader_data_semantic_and_trading_scope_remain_closed(self) -> None:
        for key in (
            "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
            "list_object_versions_authorized", "list_all_my_buckets_authorized",
            "raw_compressed_object_retention_authorized", "raw_decompressed_payload_retention_authorized",
            "record_payload_retention_authorized", "wallet_address_retention_from_body_authorized",
            "payload_values_in_evidence_authorized", "string_values_in_evidence_authorized",
            "numeric_values_in_evidence_authorized", "string_element_semantic_wallet_or_user_label_authorized",
            "schema_equivalence_inference_authorized", "semantic_equivalence_inference_authorized",
            "wallet_reconstruction_authorized", "entity_clustering_authorized", "copyability_analysis_authorized",
            "pnl_or_alpha_analysis_authorized", "market_data_ingestion_authorized",
        ):
            self.assertFalse(self.candidate[key], key)
        self.assertTrue(all(value is False for value in self.candidate["trading_authorizations"].values()))


if __name__ == "__main__":
    unittest.main()
