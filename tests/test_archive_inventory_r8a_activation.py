from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "research/archive_inventory/r8"


class ArchiveR8AActivationTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_activation_binds_exact_candidate_and_canonical_lineage(self) -> None:
        candidate = self.load(R8 / "R8A_EXECUTION_RELEASE.json")
        activation = self.load(R8 / "R8A_EXECUTION_RELEASE_CANONICALIZATION.json")
        self.assertEqual(activation["release_id"], candidate["release_id"])
        self.assertEqual(activation["r8_static_design_commit"], "526f92cf3666c8bb616ecb61b6f9881387c1d7ed")
        self.assertEqual(activation["approval_merge_commit"], "6c011cb604dec1f169d42b02de4ae67f3f8f8395")
        self.assertEqual(activation["canonical_implementation_merge_commit"], "cb4f0e3272917aa27f53c85432107b21d2d242b9")
        self.assertEqual(activation["release_candidate_merge_commit"], "e98f7218682eaafbce1563d0bde3869b044d4476")
        self.assertEqual(activation["candidate_sha256"], "e50a798bf46fdf5fdb7b808d87cb2f548b07eafda2fddbbec1f81d088805b935")

    def test_candidate_remains_inert_and_activation_is_separate(self) -> None:
        candidate = self.load(R8 / "R8A_EXECUTION_RELEASE.json")
        activation = self.load(R8 / "R8A_EXECUTION_RELEASE_CANONICALIZATION.json")
        self.assertEqual(candidate["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertFalse(candidate["execution_ready"])
        self.assertFalse(candidate["single_workflow_dispatch_authorized"])
        self.assertFalse(candidate["rerun_authorized"])
        self.assertEqual(candidate["s3_requests_executed"], 0)
        self.assertEqual(candidate["wallet_addresses_retained"], 0)
        self.assertEqual(activation["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R8A_RUN")
        self.assertTrue(activation["single_workflow_dispatch_authorized"])
        self.assertFalse(activation["rerun_authorized"])
        self.assertFalse(activation["release_consumed"])

    def test_activation_opens_only_exact_approved_runtime_envelope(self) -> None:
        activation = self.load(R8 / "R8A_EXECUTION_RELEASE_CANONICALIZATION.json")
        self.assertEqual(activation["github_event_required"], "workflow_dispatch")
        self.assertEqual(activation["canonical_dispatch_ref_required"], "refs/heads/main")
        self.assertEqual(activation["object_key"], "node_fills_by_block/hourly/20250727/8.lz4")
        self.assertEqual(activation["maximum_get_object_requests"], 1)
        self.assertEqual(activation["maximum_requests_per_object"], 1)
        self.assertEqual(activation["maximum_retries_per_request"], 0)
        self.assertEqual(activation["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(activation["maximum_monthly_budget_eur"], 0)
        self.assertTrue(activation["requester_pays_authorized"])
        self.assertTrue(activation["get_object_authorized"])
        self.assertFalse(activation["head_object_authorized"])
        self.assertFalse(activation["range_get_authorized"])
        self.assertFalse(activation["list_objects_v2_authorized"])
        self.assertFalse(activation["http_redirect_following_authorized"])

    def test_activation_retention_is_only_address_plus_fill_count(self) -> None:
        activation = self.load(R8 / "R8A_EXECUTION_RELEASE_CANONICALIZATION.json")
        self.assertTrue(activation["wallet_address_retention_authorized"])
        self.assertTrue(activation["leading_string_value_retention_authorized"])
        self.assertTrue(activation["per_wallet_fill_count_retention_authorized"])
        self.assertTrue(activation["unique_wallet_count_retention_authorized"])
        self.assertTrue(activation["valid_event_pair_count_retention_authorized"])
        self.assertEqual(activation["retained_wallet_index_fields_only"], ["wallet_address", "fill_count"])
        for key in (
            "block_number_retention_authorized", "local_time_retention_authorized", "block_time_retention_authorized",
            "raw_compressed_object_retention_authorized", "raw_decompressed_payload_retention_authorized",
            "record_payload_retention_authorized", "fill_object_retention_authorized",
            "payload_values_in_evidence_authorized", "performance_field_values_retention_authorized",
            "coin_value_retention_authorized", "price_value_retention_authorized", "size_value_retention_authorized",
            "side_value_retention_authorized", "time_value_retention_authorized", "dir_value_retention_authorized",
            "closed_pnl_value_retention_authorized", "fee_value_retention_authorized",
            "fee_token_value_retention_authorized", "start_position_value_retention_authorized",
            "crossed_value_retention_authorized", "liquidation_value_retention_authorized",
            "transaction_hash_retention_authorized", "order_id_retention_authorized",
            "trade_id_retention_authorized", "client_order_id_retention_authorized",
        ):
            self.assertFalse(activation[key], key)

    def test_downstream_and_trading_authority_remains_closed(self) -> None:
        activation = self.load(R8 / "R8A_EXECUTION_RELEASE_CANONICALIZATION.json")
        self.assertTrue(all(value is False for value in activation["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in activation["trading_authorizations"].values()))
        self.assertEqual(activation["s3_requests_executed"], 0)
        self.assertEqual(activation["wallet_addresses_retained"], 0)
        self.assertIsNone(activation["empirical_result"])

    def test_dedicated_activation_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r8a_activation.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R8A_ACTIVATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
