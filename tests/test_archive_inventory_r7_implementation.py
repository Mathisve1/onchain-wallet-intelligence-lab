from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R7 = ROOT / "research/archive_inventory/r7"


class ArchiveR7ImplementationTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_lineage_scope_and_caps(self) -> None:
        impl = self.load(R7 / "R7_IMPLEMENTATION_CONTRACT.json")
        self.assertEqual(impl["preregistration_commit"], "795281b2992466785ba48314d59feb61ac0b3aef")
        self.assertEqual(impl["approval_merge_commit"], "65a7b53796231b3aaea4c1dc1b41aa847b4ea3ba")
        self.assertEqual(impl["approval_text_sha256"], "43f32634859eb39e4b1e464276f9721ed4ef8bcc30161f1f301f82e0312042a6")
        self.assertEqual(impl["object"]["key"], "node_fills/hourly/20250727/8.lz4")
        self.assertEqual(impl["maximum_get_object_requests"], 1)
        self.assertEqual(impl["maximum_retries_per_request"], 0)
        self.assertEqual(impl["wallet_index_entry_cap"], 162815)
        self.assertEqual(impl["wallet_index_output_byte_cap"], 16777216)

    def test_future_retention_matches_approved_minimum(self) -> None:
        impl = self.load(R7 / "R7_IMPLEMENTATION_CONTRACT.json")
        self.assertTrue(all(value is True for value in impl["future_release_retention_authorizations"].values()))
        self.assertEqual(impl["wallet_index_fields_only"], ["wallet_address", "fill_count"])
        self.assertEqual(impl["wallet_address_normalization"], "LOWERCASE_EXACT_0X40HEX")
        self.assertTrue(all(value is False for value in impl["forbidden_retention_authorizations"].values()))

    def test_implementation_is_inert_until_separate_release(self) -> None:
        impl = self.load(R7 / "R7_IMPLEMENTATION_CONTRACT.json")
        self.assertEqual(impl["status"], "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION")
        self.assertTrue(impl["execution_release_required"])
        self.assertFalse(impl["execution_release_present"])
        self.assertEqual(impl["expected_canonical_implementation_commit"], "PENDING_CANONICAL_IMPLEMENTATION_MERGE")
        self.assertTrue(all(value is False for value in impl["current_runtime_authority"].values()))
        self.assertEqual(impl["s3_requests_executed"], 0)
        self.assertEqual(impl["wallet_addresses_retained"], 0)
        self.assertIsNone(impl["empirical_result"])

    def test_role_is_reused_without_iam_mutation(self) -> None:
        impl = self.load(R7 / "R7_IMPLEMENTATION_CONTRACT.json")
        reuse = self.load(R7 / "R7_AWS_ROLE_REUSE_ANALYSIS.json")
        self.assertEqual(impl["reused_dedicated_role_arn"], reuse["reused_role_arn"])
        self.assertFalse(impl["aws_role_mutation_required"])
        self.assertFalse(impl["aws_role_mutation_authorized"])
        self.assertFalse(reuse["aws_iam_mutation_performed"])
        self.assertFalse(reuse["new_sts_preflight_required"])
        self.assertTrue(reuse["r7_session_scope"]["strict_subset_of_persistent_role"])

    def test_downstream_and_trading_stay_closed(self) -> None:
        impl = self.load(R7 / "R7_IMPLEMENTATION_CONTRACT.json")
        self.assertTrue(all(value is False for value in impl["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in impl["trading_authorizations"].values()))

    def test_dedicated_implementation_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r7_implementation.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R7_IMPLEMENTATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
