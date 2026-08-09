from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R5 = ROOT / "research/archive_inventory/r5"
IMPL = R5 / "R5_IMPLEMENTATION_CONTRACT.json"
REUSE = R5 / "R5_AWS_ROLE_REUSE_ANALYSIS.json"
R4_PERMISSION = ROOT / "research/archive_inventory/r4/R4_IAM_POLICY_TEMPLATE.json"
R4_TRUST = ROOT / "research/archive_inventory/r4/R4_OIDC_TRUST_POLICY_TEMPLATE.json"


class ArchiveLegacyFormatFingerprintR5ImplementationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.impl = json.loads(IMPL.read_text(encoding="utf-8"))
        cls.reuse = json.loads(REUSE.read_text(encoding="utf-8"))

    def test_dedicated_implementation_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r5_implementation.py")],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R5_IMPLEMENTATION_VALID", completed.stdout)

    def test_exact_lineage_object_and_caps(self) -> None:
        self.assertEqual(self.impl["preregistration_commit"], "58f724d7f0208a43f7462abd80e1e69d995acff9")
        self.assertEqual(self.impl["approval_merge_commit"], "c22e28074ba2e95e1fe88912c364124e01eb0ff7")
        self.assertEqual(self.impl["approval_text_sha256"], "667f94a66ea07296162ae0627a9cf7fc5b439b3f8312c8617ece923159f5ddc8")
        self.assertEqual(self.impl["object"]["key"], "node_fills/hourly/20250727/8.lz4")
        self.assertEqual(self.impl["object"]["expected_compressed_sha256"], "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622")
        self.assertEqual(self.impl["object"]["expected_decompressed_byte_count"], 62169139)
        self.assertEqual(self.impl["maximum_get_object_requests"], 1)
        self.assertEqual(self.impl["maximum_retries_per_request"], 0)
        self.assertEqual(self.impl["maximum_total_decompressed_bytes"], 134217728)

    def test_unchanged_r4_role_is_reused_only_with_stricter_session_scope(self) -> None:
        role = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
        legacy = "arn:aws:s3:::hl-mainnet-node-data/node_fills/hourly/20250727/8.lz4"
        self.assertEqual(self.impl["reused_dedicated_role_arn"], role)
        self.assertFalse(self.impl["aws_role_mutation_required"])
        self.assertFalse(self.impl["aws_role_mutation_authorized"])
        self.assertEqual(self.impl["session_s3_policy"], "ALLOW_GETOBJECT_EXACT_LEGACY_OBJECT_ONLY")
        self.assertTrue(self.impl["session_policy_strict_subset_of_persistent_role"])
        self.assertEqual(self.reuse["r5_session_scope"]["allowed_object_arns"], [legacy])
        self.assertTrue(self.reuse["r5_session_scope"]["strict_subset_of_persistent_role"])
        self.assertFalse(self.reuse["aws_iam_mutation_performed"])
        self.assertFalse(self.reuse["new_sts_preflight_required"])
        self.assertEqual(
            hashlib.sha256(R4_TRUST.read_bytes()).hexdigest(),
            "2ebb60a7747a636a475a23016951265fe377fd9d68f2d9f3a63e33f3bc0189b4",
        )
        self.assertEqual(
            hashlib.sha256(R4_PERMISSION.read_bytes()).hexdigest(),
            "14d055105b80e0c41462d4934bbaa8d860b0aeda9f2f1b9529267fd0d4d3613d",
        )

    def test_implementation_snapshot_is_inert_and_not_a_release(self) -> None:
        self.assertEqual(self.impl["status"], "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION")
        self.assertFalse(self.impl["execution_release_present"])
        self.assertEqual(self.impl["expected_canonical_implementation_commit"], "PENDING_CANONICAL_IMPLEMENTATION_MERGE")
        for key in (
            "execution_authorized", "paid_request_authorized", "requester_pays_authorized",
            "get_object_authorized", "object_body_download_authorized", "decompression_authorized",
            "format_classification_authorized",
        ):
            self.assertFalse(self.impl[key], key)
        self.assertEqual(self.impl["s3_requests_executed"], 0)
        self.assertEqual(self.impl["compressed_bytes_downloaded"], 0)
        self.assertEqual(self.impl["decompressed_bytes_processed"], 0)
        self.assertIsNone(self.impl["empirical_result"])
        release_path = R5 / "R5_EXECUTION_RELEASE.json"
        if release_path.exists():
            release = json.loads(release_path.read_text(encoding="utf-8"))
            self.assertEqual(release["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
            self.assertEqual(release["implementation_commit"], "40bc4d138c71a4367c9415982f58bcd24c5a57eb")
            self.assertFalse(release["execution_ready"])
            self.assertFalse(release["single_workflow_dispatch_authorized"])
            self.assertEqual(release["s3_requests_executed"], 0)
        activation_path = R5 / "R5_EXECUTION_RELEASE_CANONICALIZATION.json"
        if activation_path.exists():
            activation = json.loads(activation_path.read_text(encoding="utf-8"))
            self.assertEqual(activation["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R5_RUN")
            self.assertEqual(activation["implementation_commit"], "40bc4d138c71a4367c9415982f58bcd24c5a57eb")
            self.assertTrue(activation["single_workflow_dispatch_authorized"])
            self.assertFalse(activation["rerun_authorized"])
            self.assertEqual(activation["s3_requests_executed"], 0)

    def test_payload_semantic_market_and_trading_boundaries_stay_closed(self) -> None:
        for key in (
            "raw_compressed_object_retention_authorized", "raw_decompressed_payload_retention_authorized",
            "record_payload_retention_authorized", "wallet_address_retention_from_body_authorized",
            "payload_values_in_evidence_authorized", "string_values_in_evidence_authorized",
            "numeric_values_in_evidence_authorized", "string_element_semantic_wallet_or_user_label_authorized",
            "schema_equivalence_inference_authorized", "semantic_equivalence_inference_authorized",
            "wallet_reconstruction_authorized", "entity_clustering_authorized", "copyability_analysis_authorized",
            "pnl_or_alpha_analysis_authorized", "market_data_ingestion_authorized",
        ):
            self.assertFalse(self.impl[key], key)
        self.assertTrue(all(value is False for value in self.impl["trading_authorizations"].values()))


if __name__ == "__main__":
    unittest.main()
