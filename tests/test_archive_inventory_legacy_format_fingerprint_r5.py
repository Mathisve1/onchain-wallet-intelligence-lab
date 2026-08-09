from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R5 = ROOT / "research/archive_inventory/r5"
CONTRACT = R5 / "LEGACY_FORMAT_FINGERPRINT_R5_CONTRACT.json"
DERIVATION = R5 / "R4_DERIVATION.json"
PARENT = ROOT / "research/archive_inventory/r4/evidence/run-31313913525/r4-body-result.json"
APPROVAL_TEXT = R5 / "approvals/APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001.txt"
APPROVAL_JSON = R5 / "approvals/APPROVE_HL_ARCHIVE_LEGACY_FORMAT_FINGERPRINT_R5_001.json"
IMPLEMENTATION = R5 / "R5_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = R5 / "R5_AWS_ROLE_REUSE_ANALYSIS.json"
COLLECTOR = R5 / "collector.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-legacy-format-fingerprint-r5.yml"
APPROVAL_SHA = "667f94a66ea07296162ae0627a9cf7fc5b439b3f8312c8617ece923159f5ddc8"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ArchiveLegacyFormatFingerprintR5Tests(unittest.TestCase):
    def test_dedicated_preregistration_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r5_preregistration.py")], cwd=ROOT,
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R5_PREREGISTRATION_VALID", completed.stdout)

    def test_r5_is_exactly_bound_to_consumed_r4_legacy_object(self) -> None:
        contract = load(CONTRACT)
        target = contract["exact_future_network_target"]
        self.assertEqual(contract["parent_r4"]["evidence_merge_commit"], "fe06874aeeb958d375a27100378f89bd25b4741b")
        self.assertEqual(contract["parent_r4"]["run_id"], 31313913525)
        self.assertEqual(target["key"], "node_fills/hourly/20250727/8.lz4")
        self.assertEqual(target["expected_size_bytes"], 12726384)
        self.assertEqual(target["expected_etag"], '"b21cdc16a4ec69d9c5b72c0c27ff148d-2"')
        self.assertEqual(target["expected_compressed_sha256"], "f12d33da9733dbb71f02f9910fc187b9dd4b8f9dae1102b7dfe7690094542622")
        self.assertEqual(target["expected_decompressed_byte_count"], 62169139)

    def test_primary_pair_hypothesis_is_evidence_derived_but_explicitly_unproven(self) -> None:
        contract = load(CONTRACT)
        derivation = load(DERIVATION)
        parent = load(PARENT)
        modern = next(row for row in parent["observations"] if row["dataset_family_id"] == "node_fills_by_block")
        self.assertEqual(modern["field_path_type_sets"]["/events/*"], ["array"])
        self.assertEqual(set(modern["field_path_type_sets"]["/events/*/*"]), {"object", "string"})
        self.assertEqual(contract["official_source_hypothesis"]["primary_hypothesis"], "LEGACY_IS_LINE_DELIMITED_TWO_ELEMENT_JSON_ARRAY_EVENTS")
        self.assertTrue(contract["official_source_hypothesis"]["hypothesis_is_inference_not_evidence"])
        self.assertEqual(derivation["inference_status"], "HYPOTHESIS_ONLY_NOT_EMPIRICALLY_PROVEN")

    def test_future_request_envelope_is_one_exact_get_and_current_authority_is_zero(self) -> None:
        contract = load(CONTRACT)
        envelope = contract["proposed_future_execution_envelope"]
        authority = contract["current_runtime_authority"]
        self.assertEqual(envelope["maximum_get_object_requests"], 1)
        self.assertEqual(envelope["maximum_requests_per_object"], 1)
        self.assertEqual(envelope["maximum_retries_per_request"], 0)
        self.assertFalse(envelope["head_object_authorized"])
        self.assertFalse(envelope["range_get_authorized"])
        self.assertFalse(envelope["list_objects_v2_authorized"])
        self.assertEqual(authority["s3_requests_executed"], 0)
        self.assertEqual(authority["compressed_bytes_downloaded"], 0)
        self.assertEqual(authority["decompressed_bytes_processed"], 0)
        self.assertIsNone(authority["empirical_result"])
        self.assertFalse(authority["execution_authorized"])
        self.assertFalse(authority["get_object_authorized"])
        self.assertFalse(authority["decompression_authorized"])
        self.assertFalse(authority["format_classification_authorized"])

    def test_classifier_is_structural_only_and_never_retains_payload_values(self) -> None:
        classifier = load(CONTRACT)["proposed_format_classifier"]
        self.assertEqual(classifier["classifier_precedence"][0], "UTF8_NDJSON_PAIR_STRING_OBJECT")
        self.assertEqual(classifier["classifier_precedence"][1], "UTF8_NDJSON_PAIR_OBJECT_STRING")
        for key in (
            "payload_values_in_evidence_authorized", "string_values_in_evidence_authorized",
            "numeric_values_in_evidence_authorized", "wallet_address_retention_from_body_authorized",
            "record_payload_retention_authorized", "raw_compressed_object_retention_authorized",
            "raw_decompressed_payload_retention_authorized",
        ):
            self.assertFalse(classifier[key], key)

    def test_preregistration_snapshot_remains_inert_after_separate_approval_and_implementation(self) -> None:
        contract = load(CONTRACT)
        self.assertEqual(contract["status"], "PREREGISTERED_STATIC_NO_EXECUTION")
        self.assertTrue(all(
            value is False for key, value in contract["current_runtime_authority"].items()
            if key.endswith("authorized") or key in {"human_approval_recorded", "implementation_authorized", "execution_release_present"}
        ))
        self.assertTrue(APPROVAL_TEXT.exists() and APPROVAL_JSON.exists())
        approval = load(APPROVAL_JSON)
        self.assertEqual(hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest(), APPROVAL_SHA)
        self.assertEqual(approval["reviewed_commit"], "58f724d7f0208a43f7462abd80e1e69d995acff9")
        self.assertFalse(approval["execution_authorized_by_this_record"])
        self.assertFalse(approval["request_authorized_by_this_record"])
        for path in (IMPLEMENTATION, ROLE_REUSE, COLLECTOR, WORKFLOW):
            self.assertTrue(path.exists(), str(path))
        impl = load(IMPLEMENTATION)
        self.assertEqual(impl["status"], "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION")
        self.assertFalse(impl["execution_release_present"])
        self.assertFalse(impl["execution_authorized"])
        self.assertEqual(impl["s3_requests_executed"], 0)
        release_path = R5 / "R5_EXECUTION_RELEASE.json"
        if release_path.exists():
            release = load(release_path)
            self.assertEqual(release["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
            self.assertFalse(release["execution_ready"])
            self.assertFalse(release["single_workflow_dispatch_authorized"])
            self.assertEqual(release["s3_requests_executed"], 0)
        activation_path = R5 / "R5_EXECUTION_RELEASE_CANONICALIZATION.json"
        if activation_path.exists():
            activation = load(activation_path)
            self.assertEqual(activation["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R5_RUN")
            self.assertEqual(activation["implementation_commit"], "40bc4d138c71a4367c9415982f58bcd24c5a57eb")
            self.assertTrue(activation["single_workflow_dispatch_authorized"])
            self.assertFalse(activation["rerun_authorized"])
            self.assertEqual(activation["s3_requests_executed"], 0)

    def test_semantic_wallet_and_all_trading_gates_remain_closed(self) -> None:
        contract = load(CONTRACT)
        self.assertTrue(all(value is False for value in contract["semantic_boundaries"].values()))
        self.assertTrue(all(value is False for value in contract["trading_authorizations"].values()))


if __name__ == "__main__":
    unittest.main()
