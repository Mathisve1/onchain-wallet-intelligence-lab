from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R5 = ROOT / "research/archive_inventory/r5"
ACTIVATION = R5 / "R5_EXECUTION_RELEASE_CANONICALIZATION.json"
ANCHOR = R5 / "R5_EXECUTION_RELEASE_ACTIVATION_ANCHOR.json"
CANDIDATE = R5 / "R5_EXECUTION_RELEASE.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-legacy-format-fingerprint-r5.yml"


class ArchiveLegacyFormatFingerprintR5ActivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.activation = json.loads(ACTIVATION.read_text(encoding="utf-8"))
        cls.anchor = json.loads(ANCHOR.read_text(encoding="utf-8"))
        cls.candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))

    def test_dedicated_activation_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r5_activation.py")],
            cwd=ROOT, check=False, capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R5_ACTIVATION_VALID", completed.stdout)

    def test_activation_binds_release_candidate_and_new_window_anchor(self) -> None:
        self.assertEqual(self.activation["release_candidate_merge_commit"], "0ed4aed8f2361e995122a0fc57c84135952f70d5")
        self.assertEqual(self.activation["activation_anchor_commit"], "308054c3e69a79a4be2c395e3c47fe725b5abc6c")
        self.assertEqual(self.activation["single_use_window_start_utc"], "2026-08-09T14:54:18Z")
        self.assertEqual(self.anchor["status"], "R5_ACTIVATION_WINDOW_ANCHOR_ONLY_NO_AUTHORITY")
        self.assertFalse(self.anchor["execution_authorized"])
        self.assertEqual(self.anchor["s3_requests_executed"], 0)

    def test_activation_opens_exactly_one_manual_main_dispatch(self) -> None:
        self.assertEqual(self.activation["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R5_RUN")
        self.assertEqual(self.activation["github_event_required"], "workflow_dispatch")
        self.assertEqual(self.activation["canonical_dispatch_ref_required"], "refs/heads/main")
        self.assertEqual(self.activation["canonical_dispatch_sha_source"], "github.sha")
        self.assertTrue(self.activation["single_workflow_dispatch_authorized"])
        self.assertFalse(self.activation["rerun_authorized"])
        self.assertTrue(self.activation["execution_ready"])

    def test_activation_scope_is_exact_one_legacy_object_and_no_iam_mutation(self) -> None:
        self.assertEqual(self.activation["implementation_commit"], "40bc4d138c71a4367c9415982f58bcd24c5a57eb")
        self.assertEqual(self.activation["object_key"], "node_fills/hourly/20250727/8.lz4")
        self.assertEqual(self.activation["maximum_get_object_requests"], 1)
        self.assertEqual(self.activation["maximum_retries_per_request"], 0)
        self.assertTrue(self.activation["requester_pays_authorized"])
        self.assertTrue(self.activation["get_object_authorized"])
        self.assertTrue(self.activation["decompression_authorized"])
        self.assertTrue(self.activation["format_classification_authorized"])
        self.assertFalse(self.activation["aws_role_mutation_required"])
        self.assertFalse(self.activation["aws_role_mutation_authorized"])
        self.assertFalse(self.activation["aws_role_mutation_performed"])
        self.assertEqual(self.activation["session_s3_policy"], "ALLOW_GETOBJECT_EXACT_LEGACY_OBJECT_ONLY")
        self.assertTrue(self.activation["session_policy_strict_subset_of_persistent_role"])

    def test_candidate_remains_immutable_inert_snapshot(self) -> None:
        self.assertEqual(self.candidate["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertFalse(self.candidate["requester_pays_authorized_by_candidate"])
        self.assertFalse(self.candidate["get_object_authorized_by_candidate"])
        self.assertFalse(self.candidate["single_workflow_dispatch_authorized"])
        self.assertFalse(self.candidate["execution_ready"])
        self.assertIsNone(self.candidate["single_use_window_start_utc"])
        self.assertEqual(self.candidate["s3_requests_executed"], 0)
        self.assertIsNone(self.candidate["empirical_result"])

    def test_workflow_is_bound_to_canonical_implementation_and_single_object_session(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("EXPECTED_IMPLEMENTATION_COMMIT: 40bc4d138c71a4367c9415982f58bcd24c5a57eb", text)
        self.assertNotIn("EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE", text)
        self.assertIn('"Action":"s3:GetObject"', text)
        self.assertIn("arn:aws:s3:::hl-mainnet-node-data/node_fills/hourly/20250727/8.lz4", text)
        self.assertNotIn("node_fills_by_block/hourly/20250727/8.lz4", text)

    def test_all_broader_and_trading_capabilities_remain_closed(self) -> None:
        for key in (
            "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
            "list_object_versions_authorized", "list_all_my_buckets_authorized", "http_redirect_following_authorized",
            "raw_compressed_object_retention_authorized", "raw_decompressed_payload_retention_authorized",
            "record_payload_retention_authorized", "wallet_address_retention_from_body_authorized",
            "payload_values_in_evidence_authorized", "string_values_in_evidence_authorized",
            "numeric_values_in_evidence_authorized", "string_element_semantic_wallet_or_user_label_authorized",
            "schema_equivalence_inference_authorized", "semantic_equivalence_inference_authorized",
            "wallet_reconstruction_authorized", "entity_clustering_authorized", "copyability_analysis_authorized",
            "pnl_or_alpha_analysis_authorized", "market_data_ingestion_authorized",
        ):
            self.assertFalse(self.activation[key], key)
        self.assertTrue(all(value is False for value in self.activation["trading_authorizations"].values()))
        self.assertEqual(self.activation["s3_requests_executed"], 0)
        self.assertIsNone(self.activation["empirical_result"])


if __name__ == "__main__":
    unittest.main()
