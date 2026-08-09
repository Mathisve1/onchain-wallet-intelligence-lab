from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r6a"
RELEASE = BASE / "R6A_EXECUTION_RELEASE.json"
VALIDATOR = ROOT / "governance/validate_r6a_release.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-legacy-user-key-lexical-r6a.yml"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


class ArchiveR6AReleaseTests(unittest.TestCase):
    def test_release_candidate_binds_approval_and_byte_exact_implementation(self) -> None:
        release = load(RELEASE)
        self.assertEqual(release["release_id"], "RELEASE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001")
        self.assertEqual(release["preregistration_commit"], "870fdf3e10a761d6c4589d43def8e436f3a129b5")
        self.assertEqual(release["approval_merge_commit"], "06c0086f80cdbc3d058bdeea64b618da276e95ec")
        self.assertEqual(release["approval_text_sha256"], "b24c67f527a320e533408fd821d10b5e2ea01d020c837e87ae5e5bbd386c94ed")
        binding = release["implementation_binding"]
        self.assertEqual(binding["canonical_pull_request_number"], 66)
        self.assertEqual(binding["implementation_contract_sha256"], "76fe0a35a4b1d89a6025a8d9889b38e5111db0f3ee44be8149d01812c6409f75")
        self.assertEqual(binding["collector_sha256"], "ef125c18ed73a6b592e02a1a37e36c76f8001d5408cf627342c94e87ee561746")
        self.assertEqual(binding["workflow_candidate_sha256"], "92307b7840163b01c51b0b6f2c8cac33f982cb8c9bf22ab219eb46ae7260dd5c")

    def test_release_candidate_exactly_repeats_approved_scope(self) -> None:
        scope = load(RELEASE)["approved_scope"]
        self.assertEqual(scope["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(scope["maximum_monthly_budget_eur"], 0)
        self.assertEqual(scope["maximum_get_object_requests"], 1)
        self.assertEqual(scope["maximum_requests_per_object"], 1)
        self.assertEqual(scope["maximum_retries_per_request"], 0)
        self.assertEqual(scope["object_key"], "node_fills/hourly/20250727/8.lz4")
        self.assertEqual(scope["object_size_bytes"], 12726384)
        self.assertEqual(scope["expected_decompressed_byte_count"], 62169139)
        self.assertEqual(scope["expected_nonempty_record_count"], 162815)
        self.assertEqual(scope["required_ordered_element_types"], ["string", "object"])
        self.assertEqual(len(scope["retained_aggregates_only"]), 7)

    def test_candidate_is_inert_until_separate_activation(self) -> None:
        release = load(RELEASE)
        self.assertEqual(release["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        for key in (
            "single_workflow_dispatch_authorized",
            "execution_ready",
            "requester_pays_authorized",
            "get_object_authorized",
            "object_body_download_authorized",
            "decompression_authorized",
            "lexical_classification_authorized",
            "rerun_authorized",
        ):
            self.assertFalse(release[key], key)
        self.assertEqual(release["s3_requests_executed"], 0)
        self.assertEqual(release["compressed_bytes_downloaded"], 0)
        self.assertEqual(release["decompressed_bytes_processed"], 0)
        self.assertIsNone(release["empirical_result"])
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE", text)

    def test_retention_downstream_and_trading_remain_closed(self) -> None:
        release = load(RELEASE)
        forbidden = (
            "raw_compressed_object_retention_authorized",
            "raw_decompressed_payload_retention_authorized",
            "record_payload_retention_authorized",
            "payload_values_in_evidence_authorized",
            "string_values_in_evidence_authorized",
            "numeric_values_in_evidence_authorized",
            "leading_string_retention_authorized",
            "wallet_address_retention_authorized",
            "leading_string_hash_retention_authorized",
            "distinct_address_set_retention_authorized",
            "wallet_reconstruction_authorized",
            "entity_clustering_authorized",
            "copyability_analysis_authorized",
            "pnl_or_alpha_analysis_authorized",
            "market_data_ingestion_authorized",
        )
        self.assertTrue(all(release[key] is False for key in forbidden))
        self.assertTrue(all(value is False for value in release["trading_authorizations"].values()))

    def test_role_is_unchanged_and_session_scope_remains_exact_one_object(self) -> None:
        release = load(RELEASE)
        self.assertEqual(
            release["dedicated_role_arn"],
            "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4",
        )
        self.assertFalse(release["aws_role_mutation_required"])
        self.assertFalse(release["aws_role_mutation_authorized"])
        self.assertFalse(release["aws_role_mutation_performed"])
        self.assertEqual(release["session_s3_policy"], "ALLOW_GETOBJECT_EXACT_R5_BOUND_LEGACY_OBJECT_ONLY")
        self.assertTrue(release["session_policy_strict_subset_of_persistent_role"])

    def test_dedicated_release_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(VALIDATOR)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R6A_RELEASE_CANDIDATE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
