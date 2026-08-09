from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "research/archive_inventory/r8"


class ArchiveR8AImplementationTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_lineage_scope_and_caps(self) -> None:
        impl = self.load(R8 / "R8A_IMPLEMENTATION_CONTRACT.json")
        self.assertEqual(impl["pilot_id"], "HL-ARCHIVE-MODERN-WALLET-INDEX-BRIDGE-R8A-001")
        self.assertEqual(impl["r8_static_design_commit"], "526f92cf3666c8bb616ecb61b6f9881387c1d7ed")
        self.assertEqual(impl["approval_merge_commit"], "6c011cb604dec1f169d42b02de4ae67f3f8f8395")
        self.assertEqual(impl["object"]["key"], "node_fills_by_block/hourly/20250727/8.lz4")
        self.assertEqual(impl["object"]["expected_size_bytes"], 1517603)
        self.assertEqual(impl["object"]["expected_top_level_block_record_count"], 4345)
        self.assertEqual(impl["maximum_get_object_requests"], 1)
        self.assertEqual(impl["maximum_retries_per_request"], 0)
        self.assertEqual(impl["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(impl["maximum_monthly_budget_eur"], 0)

    def test_implementation_is_inert_until_separate_release(self) -> None:
        impl = self.load(R8 / "R8A_IMPLEMENTATION_CONTRACT.json")
        self.assertEqual(impl["status"], "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION")
        self.assertFalse(impl["execution_release_present"])
        self.assertEqual(impl["expected_canonical_implementation_commit"], "PENDING_CANONICAL_IMPLEMENTATION_MERGE")
        self.assertTrue(all(value is False for value in impl["current_runtime_authority"].values()))
        self.assertEqual(impl["s3_requests_executed"], 0)
        self.assertEqual(impl["wallet_addresses_retained"], 0)
        self.assertIsNone(impl["empirical_result"])
        release_path = R8 / "R8A_EXECUTION_RELEASE.json"
        if release_path.exists():
            release = self.load(release_path)
            self.assertEqual(release["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
            self.assertFalse(release["execution_ready"])
            self.assertFalse(release["single_workflow_dispatch_authorized"])
            self.assertEqual(release["s3_requests_executed"], 0)
            self.assertEqual(release["wallet_addresses_retained"], 0)
            self.assertIsNone(release["empirical_result"])
        activation_path = R8 / "R8A_EXECUTION_RELEASE_CANONICALIZATION.json"
        if activation_path.exists():
            activation = self.load(activation_path)
            self.assertEqual(activation["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R8A_RUN")
            self.assertTrue(activation["single_workflow_dispatch_authorized"])
            self.assertFalse(activation["rerun_authorized"])
            self.assertFalse(activation["release_consumed"])
            self.assertEqual(activation["s3_requests_executed"], 0)
            self.assertEqual(activation["wallet_addresses_retained"], 0)
            self.assertIsNone(activation["empirical_result"])

    def test_future_retention_matches_approved_minimum(self) -> None:
        impl = self.load(R8 / "R8A_IMPLEMENTATION_CONTRACT.json")
        future = impl["future_release_retention_authorizations"]
        self.assertTrue(all(value is True for value in future.values()))
        self.assertEqual(impl["wallet_index_fields_only"], ["wallet_address", "fill_count"])
        self.assertEqual(impl["wallet_address_normalization"], "LOWERCASE_EXACT_0X40HEX")
        self.assertTrue(all(value is False for value in impl["forbidden_retention_authorizations"].values()))

    def test_role_is_reused_without_iam_mutation(self) -> None:
        impl = self.load(R8 / "R8A_IMPLEMENTATION_CONTRACT.json")
        reuse = self.load(R8 / "R8A_AWS_ROLE_REUSE_ANALYSIS.json")
        self.assertEqual(impl["reused_dedicated_role_arn"], reuse["reused_role_arn"])
        self.assertFalse(impl["aws_role_mutation_required"])
        self.assertFalse(impl["aws_role_mutation_authorized"])
        self.assertFalse(reuse["aws_iam_mutation_performed"])
        self.assertFalse(reuse["new_sts_preflight_required"])
        self.assertEqual(len(reuse["r8a_session_scope"]["allowed_object_arns"]), 1)
        self.assertTrue(reuse["r8a_session_scope"]["strict_subset_of_persistent_role"])

    def test_downstream_and_trading_stay_closed(self) -> None:
        impl = self.load(R8 / "R8A_IMPLEMENTATION_CONTRACT.json")
        self.assertTrue(all(value is False for value in impl["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in impl["trading_authorizations"].values()))

    def test_dedicated_implementation_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r8a_implementation.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R8A_IMPLEMENTATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
