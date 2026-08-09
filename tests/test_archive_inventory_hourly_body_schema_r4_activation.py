from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4"
ACTIVATION = BASE / "R4_EXECUTION_RELEASE_CANONICALIZATION.json"
ANCHOR = BASE / "R4_BODY_RELEASE_ACTIVATION_ANCHOR.json"
CANDIDATE = BASE / "R4_EXECUTION_RELEASE.json"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-hourly-body-schema-pilot-r4.yml"
IMPLEMENTATION = "180c89ead78f9a6f4560a1ec12575658e62586ee"


class ArchiveHourlyBodySchemaR4ActivationTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_activation_binds_preflight_evidence_and_new_single_use_anchor(self) -> None:
        a = self.load(ACTIVATION)
        anchor = self.load(ANCHOR)
        self.assertEqual(a["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R4_RUN")
        self.assertEqual(a["release_candidate_merge_commit"], "01521d1cad209263a217dbcca98ecd74ec16857c")
        self.assertEqual(a["activation_anchor_commit"], "c259a39f630e2ff59f8291483033e6213b470c3c")
        self.assertEqual(a["single_use_window_start_utc"], "2026-08-09T12:12:39Z")
        self.assertEqual(a["preflight_evidence_merge_commit"], "a91f0849e8cf14b6924da73ca2b72595deab5d8d")
        self.assertEqual(a["preflight_run_id"], 31312067367)
        self.assertEqual(a["preflight_artifact_sha256"], "6d30969525156ad3354c4a9abdb5d661cfc1b7b2d1a6cfd07eb02f4300f20376")
        self.assertEqual(a["preflight_terminal_status"], "R4_ROLE_STS_PREFLIGHT_PASS")
        self.assertTrue(a["preflight_release_consumed"])
        self.assertFalse(a["preflight_rerun_authorized"])
        self.assertEqual(a["preflight_s3_requests_executed"], 0)
        self.assertFalse(anchor["execution_authorized_by_this_file"])

    def test_activation_opens_only_exact_approved_two_object_envelope(self) -> None:
        a = self.load(ACTIVATION)
        self.assertEqual(a["implementation_commit"], IMPLEMENTATION)
        self.assertTrue(a["dedicated_r4_role_operator_attested"])
        self.assertTrue(a["dedicated_r4_role_independently_verified"])
        self.assertTrue(a["single_workflow_dispatch_authorized"])
        self.assertFalse(a["rerun_authorized"])
        self.assertTrue(a["requester_pays_authorized"])
        self.assertTrue(a["get_object_authorized"])
        self.assertTrue(a["object_body_download_authorized"])
        self.assertTrue(a["decompression_authorized"])
        self.assertTrue(a["execution_ready"])
        self.assertEqual(a["object_keys"], [
            "node_fills/hourly/20250727/8.lz4",
            "node_fills_by_block/hourly/20250727/8.lz4",
        ])
        self.assertEqual(a["object_sizes_bytes"], [12726384, 1517603])
        self.assertEqual(a["maximum_get_object_requests"], 2)
        self.assertEqual(a["maximum_total_compressed_bytes"], 14243987)
        self.assertEqual(a["maximum_retries_per_request"], 0)

    def test_broader_capabilities_and_all_trading_remain_closed(self) -> None:
        a = self.load(ACTIVATION)
        for key in (
            "head_object_authorized", "range_get_authorized", "list_objects_v2_authorized",
            "list_object_versions_authorized", "list_all_my_buckets_authorized",
            "http_redirect_following_authorized", "alternate_decompressor_fallback_authorized",
            "raw_compressed_object_retention_authorized", "raw_decompressed_payload_retention_authorized",
            "record_payload_retention_authorized", "wallet_address_retention_from_body_authorized",
            "payload_values_in_schema_evidence_authorized", "semantic_equivalence_inference_authorized",
            "wallet_reconstruction_authorized", "entity_clustering_authorized",
            "copyability_analysis_authorized", "pnl_or_alpha_analysis_authorized",
            "market_data_ingestion_authorized",
        ):
            self.assertFalse(a[key], key)
        self.assertTrue(all(value is False for value in a["trading_authorizations"].values()))
        self.assertEqual(a["s3_requests_executed"], 0)
        self.assertEqual(a["compressed_bytes_downloaded"], 0)
        self.assertEqual(a["decompressed_bytes_processed"], 0)
        self.assertIsNone(a["empirical_result"])

    def test_candidate_remains_immutable_inert_snapshot(self) -> None:
        c = self.load(CANDIDATE)
        self.assertEqual(c["status"], "RELEASE_CANDIDATE_AWAITING_DEDICATED_R4_ROLE_ATTESTATION")
        self.assertFalse(c["dedicated_r4_role_operator_attested"])
        self.assertFalse(c["dedicated_r4_role_independently_verified"])
        self.assertFalse(c["single_workflow_dispatch_authorized"])
        self.assertFalse(c["requester_pays_authorized"])
        self.assertFalse(c["get_object_authorized"])
        self.assertFalse(c["decompression_authorized"])
        self.assertFalse(c["execution_ready"])

    def test_body_workflow_is_bound_to_canonical_implementation_and_activation(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(f"EXPECTED_IMPLEMENTATION_COMMIT: {IMPLEMENTATION}", text)
        self.assertNotIn("EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE", text)
        self.assertIn("R4_EXECUTION_RELEASE_CANONICALIZATION.json", text)
        pre_oidc = text.index("Prove canonical R4 implementation and release before AWS OIDC")
        oidc = text.index("Assume dedicated R4 AWS role with exact-two-object session permissions")
        self.assertIn("python -m unittest discover -s tests -v", text[pre_oidc:oidc])
        self.assertLess(pre_oidc, oidc)

    def test_dedicated_activation_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r4_activation.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R4_BODY_ACTIVATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
