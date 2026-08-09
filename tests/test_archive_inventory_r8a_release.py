from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "research/archive_inventory/r8"


class ArchiveR8AReleaseTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_candidate_is_inert_and_separate_from_activation(self) -> None:
        release = self.load(R8 / "R8A_EXECUTION_RELEASE.json")
        self.assertEqual(release["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertFalse(release["execution_ready"])
        self.assertFalse(release["single_workflow_dispatch_authorized"])
        self.assertFalse(release["rerun_authorized"])
        self.assertFalse((R8 / "R8A_EXECUTION_RELEASE_CANONICALIZATION.json").exists())
        self.assertEqual(release["s3_requests_executed"], 0)
        self.assertEqual(release["wallet_addresses_retained"], 0)
        self.assertIsNone(release["empirical_result"])

    def test_exact_canonical_lineage_and_object_scope(self) -> None:
        release = self.load(R8 / "R8A_EXECUTION_RELEASE.json")
        self.assertEqual(release["r8_static_design_commit"], "526f92cf3666c8bb616ecb61b6f9881387c1d7ed")
        self.assertEqual(release["approval_merge_commit"], "6c011cb604dec1f169d42b02de4ae67f3f8f8395")
        self.assertEqual(release["canonical_implementation_merge_commit"], "cb4f0e3272917aa27f53c85432107b21d2d242b9")
        self.assertEqual(release["object_key"], "node_fills_by_block/hourly/20250727/8.lz4")
        self.assertEqual(release["maximum_get_object_requests"], 1)
        self.assertEqual(release["maximum_retries_per_request"], 0)
        self.assertEqual(release["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(release["maximum_monthly_budget_eur"], 0)

    def test_retention_boundary_is_exact_address_plus_fill_count(self) -> None:
        release = self.load(R8 / "R8A_EXECUTION_RELEASE.json")
        self.assertTrue(release["wallet_address_retention_authorized"])
        self.assertTrue(release["leading_string_value_retention_authorized"])
        self.assertTrue(release["per_wallet_fill_count_retention_authorized"])
        self.assertTrue(release["unique_wallet_count_retention_authorized"])
        self.assertTrue(release["valid_event_pair_count_retention_authorized"])
        self.assertEqual(release["wallet_address_normalization"], "LOWERCASE_EXACT_0X40HEX")
        self.assertEqual(release["retained_wallet_index_fields_only"], ["wallet_address", "fill_count"])
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
            self.assertFalse(release[key], key)

    def test_downstream_and_trading_remain_closed(self) -> None:
        release = self.load(R8 / "R8A_EXECUTION_RELEASE.json")
        self.assertTrue(all(value is False for value in release["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in release["trading_authorizations"].values()))

    def test_dedicated_release_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r8a_release.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R8A_RELEASE_CANDIDATE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
