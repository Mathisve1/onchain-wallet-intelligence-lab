from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R7 = ROOT / "research/archive_inventory/r7"


class ArchiveR7ReleaseTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_candidate_is_inert_and_separate_from_activation(self) -> None:
        release = self.load(R7 / "R7_EXECUTION_RELEASE.json")
        self.assertEqual(release["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertFalse(release["execution_ready"])
        self.assertFalse(release["single_workflow_dispatch_authorized"])
        self.assertFalse(release["rerun_authorized"])
        self.assertEqual(release["s3_requests_executed"], 0)
        self.assertEqual(release["wallet_addresses_retained"], 0)
        self.assertIsNone(release["empirical_result"])

        activation_path = R7 / "R7_EXECUTION_RELEASE_CANONICALIZATION.json"
        if activation_path.exists():
            activation = self.load(activation_path)
            self.assertEqual(activation["release_id"], release["release_id"])
            self.assertEqual(activation["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R7_RUN")
            self.assertTrue(activation["single_workflow_dispatch_authorized"])
            self.assertFalse(activation["rerun_authorized"])

    def test_exact_canonical_lineage_and_object_scope(self) -> None:
        release = self.load(R7 / "R7_EXECUTION_RELEASE.json")
        self.assertEqual(release["preregistration_commit"], "795281b2992466785ba48314d59feb61ac0b3aef")
        self.assertEqual(release["approval_merge_commit"], "65a7b53796231b3aaea4c1dc1b41aa847b4ea3ba")
        self.assertEqual(release["canonical_implementation_merge_commit"], "0a7d9821d6844439d95c7a79cf09673a0ed05329")
        self.assertEqual(release["object_key"], "node_fills/hourly/20250727/8.lz4")
        self.assertEqual(release["maximum_get_object_requests"], 1)
        self.assertEqual(release["maximum_retries_per_request"], 0)
        self.assertEqual(release["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(release["maximum_monthly_budget_eur"], 0)

    def test_retention_boundary_is_exact_address_plus_fill_count(self) -> None:
        release = self.load(R7 / "R7_EXECUTION_RELEASE.json")
        self.assertTrue(release["wallet_address_retention_authorized"])
        self.assertTrue(release["leading_string_value_retention_authorized"])
        self.assertTrue(release["per_wallet_fill_count_retention_authorized"])
        self.assertTrue(release["unique_wallet_count_retention_authorized"])
        self.assertEqual(release["wallet_address_normalization"], "LOWERCASE_EXACT_0X40HEX")
        self.assertEqual(release["retained_wallet_index_fields_only"], ["wallet_address", "fill_count"])
        for key in (
            "raw_compressed_object_retention_authorized", "raw_decompressed_payload_retention_authorized",
            "record_payload_retention_authorized", "fill_object_retention_authorized",
            "payload_values_in_evidence_authorized", "coin_value_retention_authorized",
            "price_value_retention_authorized", "size_value_retention_authorized",
            "side_value_retention_authorized", "time_value_retention_authorized",
            "closed_pnl_value_retention_authorized", "fee_value_retention_authorized",
            "transaction_hash_retention_authorized", "order_id_retention_authorized",
            "trade_id_retention_authorized", "client_order_id_retention_authorized",
        ):
            self.assertFalse(release[key], key)

    def test_downstream_and_trading_remain_closed(self) -> None:
        release = self.load(R7 / "R7_EXECUTION_RELEASE.json")
        self.assertTrue(all(value is False for value in release["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in release["trading_authorizations"].values()))

    def test_dedicated_release_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r7_release.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R7_RELEASE_CANDIDATE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
