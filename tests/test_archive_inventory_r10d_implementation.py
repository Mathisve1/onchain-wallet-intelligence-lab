from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
IMPL = BASE / "r10d_implementation/R10D_IMPLEMENTATION_CONTRACT.json"


class R10DImplementationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.i = json.loads(IMPL.read_text(encoding="utf-8"))

    def test_exact_lineage_scope_and_role_reuse(self) -> None:
        self.assertEqual(self.i["r10d_preregistration_merge_commit"], "b8e8d1080be27ff9db3fb639804b4040fdc7c2a0")
        self.assertEqual(self.i["r10d_approval_merge_commit"], "95bc1a8c2f929e9266f0ae8c43e7cc2b38b40f11")
        self.assertEqual(self.i["approval_text_sha256"], "d8d1466a5da40c4fe32523ba81bfa165e0b88221cc70534f0f0a118870c1275f")
        self.assertEqual(self.i["parent_r10c_evidence_merge_commit"], "83842a3947e8eec518fa4a05ca71a2b81079976b")
        self.assertTrue(self.i["role_reused_without_mutation"])
        self.assertFalse(self.i["new_role_created"])
        self.assertEqual(len(self.i["exact_network_targets"]), 6)
        self.assertEqual(self.i["execution_envelope"]["maximum_get_object_requests"], 6)
        self.assertEqual(self.i["execution_envelope"]["maximum_retries_per_request"], 0)

    def test_record_anchored_repair_has_no_numeric_tolerance(self) -> None:
        r = self.i["record_anchored_alignment_rule"]
        self.assertEqual(r["rule_id"], "RAW_LOCAL_PREFIX_PLUS_BLOCK_PREFIX_NO_NUMERIC_TOLERANCE_V1")
        self.assertTrue(r["local_time_raw_prefix_must_match_source_path_hour_for_every_record"])
        self.assertEqual(r["block_time_raw_prefix_allowed_buckets"], ["MATCHES_PATH_DATE_HOUR_PREFIX", "MATCHES_PREVIOUS_DATE_HOUR_PREFIX"])
        self.assertFalse(r["numeric_tolerance_authorized"])
        self.assertIsNone(r["fill_time_numeric_tolerance_milliseconds"])
        self.assertEqual(r["path_block_record_allowed_fill_partitions"], ["INSIDE_PATH_HOUR"])
        self.assertEqual(r["previous_block_record_allowed_fill_partitions"], ["BEFORE_PATH_HOUR"])
        self.assertFalse(r["hours10_to14_boundary_pattern_predeclared"])

    def test_hour9_is_exactly_bound_to_r10c_fixture_and_sha(self) -> None:
        t = self.i["exact_network_targets"][0]
        self.assertEqual(t["known_compressed_sha256"], "42fa96f9d693eb93d184c24a830483cea2e4aa526fc2ffb999619d24e41cc339")
        fixture = self.i["record_anchored_alignment_rule"]["hour9_parent_fixture_required"]
        self.assertEqual(fixture["block_record_count"], 36029)
        self.assertEqual(fixture["fill_time_count"], 223950)
        self.assertEqual(fixture["fill_time_before_path_hour_count"], 2)
        self.assertEqual(fixture["local_path_block_previous_record_count"], 1)
        self.assertEqual(fixture["before_fills_in_local_path_block_previous_records"], 2)

    def test_feature_contract_is_preserved_without_ranking_authority(self) -> None:
        p = self.i["parse_and_aggregation"]
        self.assertEqual(p["selected_fill_fields_processed_transiently"], ["coin","side","time","px","sz","closedPnl","tid","crossed","liquidation"])
        self.assertTrue(p["exact_decimal_arithmetic_required"])
        self.assertFalse(p["floating_point_aggregation_authorized"])
        self.assertEqual(p["duplicate_wallet_tid_count_required_for_clean_success"], 0)
        self.assertTrue(self.i["wallet_feature_output"]["fields_only"])
        self.assertTrue(all(v is False for v in self.i["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in self.i["trading_authorizations"].values()))

    def test_implementation_is_inert_and_cannot_self_execute(self) -> None:
        self.assertEqual(self.i["status"], "IMPLEMENTED_AWAITING_SEPARATE_EXECUTION_RELEASE")
        self.assertFalse(self.i["execution_release_present"])
        self.assertFalse(self.i["canonical_activation_present"])
        self.assertFalse(self.i["single_workflow_dispatch_authorized"])
        self.assertTrue(all(v is False for v in self.i["current_runtime_authority"].values()))
        self.assertEqual(self.i["network_requests_executed"], 0)
        self.assertEqual(self.i["aws_iam_mutations_executed"], 0)
        self.assertEqual(self.i["wallet_feature_rows_created"], 0)
        self.assertIsNone(self.i["empirical_result"])

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run([sys.executable, "governance/validate_r10d_implementation.py"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10D_IMPLEMENTATION_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
