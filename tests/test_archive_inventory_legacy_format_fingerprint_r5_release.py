from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R5 = ROOT / "research/archive_inventory/r5"
RELEASE = R5 / "R5_EXECUTION_RELEASE.json"
APPROVAL_TEXT = R5 / "approvals/APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001.txt"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-legacy-format-fingerprint-r5.yml"


class ArchiveLegacyFormatFingerprintR5ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.release = json.loads(RELEASE.read_text(encoding="utf-8"))

    def test_release_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r5_release.py")],
            cwd=ROOT, check=False, capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R5_RELEASE_CANDIDATE_VALID", completed.stdout)

    def test_release_binds_exact_canonical_lineage(self) -> None:
        self.assertEqual(self.release["preregistration_commit"], "58f724d7f0208a43f7462abd80e1e69d995acff9")
        self.assertEqual(self.release["approval_merge_commit"], "c22e28074ba2e95e1fe88912c364124e01eb0ff7")
        self.assertEqual(self.release["implementation_reviewed_exact_head"], "defc33f7316acee3640cbba360690f4fc969b13a")
        self.assertEqual(self.release["implementation_commit"], "40bc4d138c71a4367c9415982f58bcd24c5a57eb")
        self.assertEqual(
            hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest(),
            "667f94a66ea07296162ae0627a9cf7fc5b439b3f8312c8617ece923159f5ddc8",
        )

    def test_candidate_is_inert_and_cannot_self_execute(self) -> None:
        self.assertEqual(self.release["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertFalse(self.release["requester_pays_authorized_by_candidate"])
        self.assertFalse(self.release["get_object_authorized_by_candidate"])
        self.assertFalse(self.release["decompression_authorized_by_candidate"])
        self.assertFalse(self.release["format_classification_authorized_by_candidate"])
        self.assertFalse(self.release["single_workflow_dispatch_authorized"])
        self.assertFalse(self.release["rerun_authorized"])
        self.assertIsNone(self.release["single_use_window_start_utc"])
        self.assertFalse(self.release["execution_ready"])
        self.assertEqual(self.release["s3_requests_executed"], 0)
        self.assertIsNone(self.release["empirical_result"])
        activation_path = R5 / "R5_EXECUTION_RELEASE_CANONICALIZATION.json"
        text = WORKFLOW.read_text(encoding="utf-8")
        if activation_path.exists():
            activation = json.loads(activation_path.read_text(encoding="utf-8"))
            self.assertEqual(activation["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R5_RUN")
            self.assertTrue(activation["single_workflow_dispatch_authorized"])
            self.assertFalse(activation["rerun_authorized"])
            self.assertIn("EXPECTED_IMPLEMENTATION_COMMIT: 40bc4d138c71a4367c9415982f58bcd24c5a57eb", text)
            self.assertNotIn("EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE", text)
        else:
            self.assertIn("EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE", text)

    def test_release_scope_is_exactly_one_r4_bound_legacy_object(self) -> None:
        self.assertEqual(self.release["object_key"], "node_fills/hourly/20250727/8.lz4")
        self.assertEqual(self.release["object_size_bytes"], 12726384)
        self.assertEqual(self.release["object_etag"], '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"')
        self.assertEqual(self.release["expected_compressed_sha256"], "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622")
        self.assertEqual(self.release["expected_decompressed_byte_count"], 62169139)
        self.assertEqual(self.release["maximum_get_object_requests"], 1)
        self.assertEqual(self.release["maximum_retries_per_request"], 0)
        self.assertEqual(self.release["session_s3_policy"], "ALLOW_GETOBJECT_EXACT_LEGACY_OBJECT_ONLY")
        self.assertTrue(self.release["session_policy_strict_subset_of_persistent_role"])

    def test_role_reuse_is_bound_without_iam_mutation(self) -> None:
        self.assertEqual(
            self.release["dedicated_role_arn"],
            "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4",
        )
        role = self.release["role_reuse_evidence"]
        self.assertEqual(role["r4_sts_preflight_evidence_merge"], "a91f0849e8cf14b6924da73ca2b72595deab5d8d")
        self.assertEqual(role["r4_body_evidence_merge"], "fe06874aeeb958d375a27100378f89bd25b4741b")
        self.assertFalse(role["aws_role_mutation_required"])
        self.assertFalse(role["aws_role_mutation_authorized"])
        self.assertFalse(role["aws_role_mutation_performed"])

    def test_payload_semantic_market_and_trading_boundaries_remain_closed(self) -> None:
        for key in (
            "raw_compressed_object_retention_authorized", "raw_decompressed_payload_retention_authorized",
            "record_payload_retention_authorized", "wallet_address_retention_from_body_authorized",
            "payload_values_in_evidence_authorized", "string_values_in_evidence_authorized",
            "numeric_values_in_evidence_authorized", "string_element_semantic_wallet_or_user_label_authorized",
            "schema_equivalence_inference_authorized", "semantic_equivalence_inference_authorized",
            "wallet_reconstruction_authorized", "entity_clustering_authorized", "copyability_analysis_authorized",
            "pnl_or_alpha_analysis_authorized", "market_data_ingestion_authorized",
        ):
            self.assertFalse(self.release[key], key)
        self.assertTrue(all(value is False for value in self.release["trading_authorizations"].values()))


if __name__ == "__main__":
    unittest.main()
