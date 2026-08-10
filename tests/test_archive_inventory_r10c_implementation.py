from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
IMPL = BASE / "r10c_implementation/R10C_IMPLEMENTATION_CONTRACT.json"
APPROVAL = BASE / "r10c_approval/APPROVE_HL_ARCHIVE_R10C_BOUNDARY_RECORD_CORRELATION_001.json"


class R10CImplementationTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(value, dict)
        return value

    def test_exact_lineage_scope_and_role_reuse(self) -> None:
        i = self.load(IMPL)
        a = self.load(APPROVAL)
        self.assertEqual(i["status"], "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE")
        self.assertEqual(i["r10c_preregistration_merge_commit"], "a812f7d5b67203c801f856c85b046af8e136c8f3")
        self.assertEqual(i["r10c_approval_merge_commit"], "00dbe69b5c17df8ef42a9b573589add290e559d8")
        self.assertEqual(i["approval_text_sha256"], a["exact_approval_text_sha256"])
        self.assertTrue(i["role_reused_without_mutation"])
        self.assertFalse(i["new_role_created"])
        self.assertEqual(i["exact_network_target"]["key"], "node_fills_by_block/hourly/20250727/9.lz4")
        self.assertEqual(i["exact_network_target"]["expected_size_bytes"], 18147822)
        self.assertEqual(i["execution_envelope"]["maximum_get_object_requests"], 1)
        self.assertEqual(i["execution_envelope"]["maximum_retries_per_request"], 0)

    def test_processing_is_exact_approved_correlation_boundary(self) -> None:
        p = self.load(IMPL)["processing_contract"]
        self.assertTrue(p["metadata_prefix_processing"])
        self.assertTrue(p["event_array_contents_inspection"])
        self.assertEqual(p["event_array_contents_inspection_scope"], "PAIR_SHAPE_AND_FILL_TIME_ONLY")
        self.assertEqual(p["fill_object_field_allowlist"], ["time"])
        self.assertTrue(p["fill_time_integer_milliseconds_processing"])
        self.assertTrue(p["aggregate_boundary_correlation_retention"])
        self.assertFalse(p["metadata_timezone_parsing"])
        self.assertFalse(p["metadata_timezone_inference"])
        self.assertFalse(p["metadata_datetime_conversion"])
        self.assertFalse(p["individual_metadata_value_retention"])
        self.assertFalse(p["individual_fill_time_retention"])
        self.assertFalse(p["leading_event_string_wallet_semantics"])
        self.assertFalse(p["wallet_address_retention"])
        self.assertFalse(p["economic_fill_field_processing"])
        self.assertFalse(p["block_number_value_retention"])
        self.assertFalse(p["per_block_identity_retention"])

    def test_implementation_is_inert_and_cannot_self_execute(self) -> None:
        i = self.load(IMPL)
        self.assertTrue(i["execution_release_required"])
        self.assertFalse(i["execution_release_present"])
        self.assertFalse(i["canonical_activation_present"])
        self.assertFalse(i["single_workflow_dispatch_authorized"])
        self.assertFalse(i["aws_oidc_authorized_now"])
        self.assertFalse(i["requester_pays_authorized_now"])
        self.assertFalse(i["get_object_authorized_now"])
        self.assertEqual(i["network_requests_executed"], 0)
        self.assertEqual(i["aws_iam_mutations_executed"], 0)
        self.assertIsNone(i["empirical_result"])
        self.assertTrue(all(v is False for v in i["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in i["trading_authorizations"].values()))

    def test_parent_counts_and_terminal_classes_are_frozen(self) -> None:
        i = self.load(IMPL)
        self.assertEqual(i["parent_aggregate_preconditions"]["block_record_count"], 36029)
        self.assertEqual(i["parent_aggregate_preconditions"]["fill_time_count"], 223950)
        self.assertEqual(i["parent_aggregate_preconditions"]["fill_time_before_path_hour_count"], 2)
        self.assertEqual(i["parent_aggregate_preconditions"]["block_time_previous_prefix_count"], 1)
        self.assertEqual(i["allowed_boundary_record_correlation_classifications"], [
            "EXACT_TWO_PRE_HOUR_FILLS_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD",
            "PRE_HOUR_FILLS_DO_NOT_EXACTLY_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD",
            "BOUNDARY_RECORD_CORRELATION_UNRESOLVED",
        ])

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10c_implementation.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10C_IMPLEMENTATION_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
