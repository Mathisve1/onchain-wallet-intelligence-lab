from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r5"
APPROVAL = BASE / "approvals/APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001.json"
APPROVAL_TEXT = BASE / "approvals/APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001.txt"
CONTRACT = BASE / "LEGACY_FORMAT_FINGERPRINT_R5_CONTRACT.json"
IMPL = BASE / "R5_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = BASE / "R5_AWS_ROLE_REUSE_ANALYSIS.json"
COLLECTOR = BASE / "collector.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-legacy-format-fingerprint-r5.yml"
APPROVAL_SHA = "667f94a66ea07296162ae0627a9cf7fc5b439b3f8312c8617ece923159f5ddc8"


class ArchiveLegacyFormatFingerprintR5ApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.approval = json.loads(APPROVAL.read_text(encoding="utf-8"))
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exact_approval_text_is_hash_bound(self) -> None:
        self.assertEqual(hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest(), APPROVAL_SHA)
        self.assertEqual(self.approval["exact_approval_text_sha256"], APPROVAL_SHA)
        self.assertEqual(self.approval["reviewed_commit"], "58f724d7f0208a43f7462abd80e1e69d995acff9")

    def test_approval_exactly_matches_preregistered_one_object_envelope(self) -> None:
        target = self.contract["exact_future_network_target"]
        envelope = self.contract["proposed_future_execution_envelope"]
        classifier = self.contract["proposed_format_classifier"]
        self.assertEqual(self.approval["target_bucket"], target["bucket"])
        self.assertEqual(self.approval["signing_region"], target["signing_region"])
        self.assertEqual(self.approval["object_key"], target["key"])
        self.assertEqual(self.approval["object_size_bytes"], target["expected_size_bytes"])
        self.assertEqual(self.approval["object_etag"], target["expected_etag"])
        self.assertEqual(self.approval["expected_compressed_sha256"], target["expected_compressed_sha256"])
        self.assertEqual(self.approval["expected_decompressed_byte_count"], target["expected_decompressed_byte_count"])
        for key in (
            "maximum_get_object_requests", "maximum_requests_per_object", "maximum_total_compressed_bytes",
            "maximum_total_decompressed_bytes", "maximum_runtime_seconds", "maximum_retries_per_request",
        ):
            self.assertEqual(self.approval[key], envelope[key], key)
        for key in (
            "maximum_record_bytes", "maximum_records_parsed", "maximum_schema_nesting_depth",
            "maximum_unique_field_paths", "maximum_unique_structural_signatures",
        ):
            self.assertEqual(self.approval[key], classifier[key], key)

    def test_approval_opens_implementation_lane_but_not_runtime(self) -> None:
        self.assertEqual(self.approval["approval_scope"], "IMPLEMENTATION_AND_LATER_SEPARATE_RELEASE_PATH_ONLY")
        self.assertFalse(self.approval["execution_authorized_by_this_record"])
        self.assertFalse(self.approval["request_authorized_by_this_record"])
        self.assertFalse(self.approval["aws_role_mutation_authorized"])
        self.assertTrue(all(value is False for value in self.approval["current_runtime_authority"].values()))
        self.assertEqual(self.approval["s3_requests_executed_under_r5"], 0)
        self.assertFalse(self.contract["current_runtime_authority"]["execution_authorized"])

    def test_payload_semantics_wallet_and_trading_stay_closed(self) -> None:
        self.assertTrue(all(value is False for value in self.approval["retention_authorizations"].values()))
        self.assertTrue(all(value is False for value in self.approval["inference_authorizations"].values()))
        self.assertTrue(all(value is False for value in self.approval["trading_authorizations"].values()))

    def test_approval_snapshot_remains_inert_after_separate_implementation(self) -> None:
        for path in (IMPL, ROLE_REUSE, COLLECTOR, WORKFLOW):
            self.assertTrue(path.exists(), path)
        impl = json.loads(IMPL.read_text(encoding="utf-8"))
        reuse = json.loads(ROLE_REUSE.read_text(encoding="utf-8"))
        self.assertEqual(impl["status"], "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION")
        self.assertEqual(impl["approval_merge_commit"], "c22e28074ba2e95e1fe88912c364124e01eb0ff7")
        self.assertEqual(impl["approval_text_sha256"], APPROVAL_SHA)
        self.assertFalse(impl["execution_release_present"])
        self.assertFalse(impl["execution_authorized"])
        self.assertEqual(impl["s3_requests_executed"], 0)
        self.assertFalse(reuse["aws_iam_mutation_performed"])
        release_path = BASE / "R5_EXECUTION_RELEASE.json"
        if release_path.exists():
            release = json.loads(release_path.read_text(encoding="utf-8"))
            self.assertEqual(release["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
            self.assertFalse(release["execution_ready"])
            self.assertFalse(release["single_workflow_dispatch_authorized"])
            self.assertEqual(release["s3_requests_executed"], 0)
        activation_path = BASE / "R5_EXECUTION_RELEASE_CANONICALIZATION.json"
        if activation_path.exists():
            activation = json.loads(activation_path.read_text(encoding="utf-8"))
            self.assertEqual(activation["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R5_RUN")
            self.assertEqual(activation["implementation_commit"], "40bc4d138c71a4367c9415982f58bcd24c5a57eb")
            self.assertTrue(activation["single_workflow_dispatch_authorized"])
            self.assertFalse(activation["rerun_authorized"])
            self.assertEqual(activation["s3_requests_executed"], 0)
        self.assertFalse(self.approval["execution_authorized_by_this_record"])
        self.assertTrue(all(value is False for value in self.approval["current_runtime_authority"].values()))

    def test_dedicated_approval_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r5_approval.py")], cwd=ROOT,
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R5_APPROVAL_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
