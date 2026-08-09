from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R7 = ROOT / "research/archive_inventory/r7"


class ArchiveR7ActivationTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_candidate_remains_inert_and_activation_is_separate(self) -> None:
        candidate = self.load(R7 / "R7_EXECUTION_RELEASE.json")
        activation = self.load(R7 / "R7_EXECUTION_RELEASE_CANONICALIZATION.json")
        self.assertEqual(candidate["status"], "RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION")
        self.assertFalse(candidate["execution_ready"])
        self.assertFalse(candidate["single_workflow_dispatch_authorized"])
        self.assertEqual(activation["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R7_RUN")
        self.assertTrue(activation["single_workflow_dispatch_authorized"])
        self.assertFalse(activation["rerun_authorized"])
        self.assertFalse(activation["release_consumed"])

    def test_activation_binds_exact_candidate_and_canonical_lineage(self) -> None:
        candidate_path = R7 / "R7_EXECUTION_RELEASE.json"
        activation = self.load(R7 / "R7_EXECUTION_RELEASE_CANONICALIZATION.json")
        self.assertEqual(
            hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
            "6d238406d738b90d3f03bef63b830c01857562821518210541d666b163abdff9",
        )
        self.assertEqual(activation["candidate_sha256"], "6d238406d738b90d3f03bef63b830c01857562821518210541d666b163abdff9")
        self.assertEqual(activation["preregistration_commit"], "795281b2992466785ba48314d59feb61ac0b3aef")
        self.assertEqual(activation["approval_merge_commit"], "65a7b53796231b3aaea4c1dc1b41aa847b4ea3ba")
        self.assertEqual(activation["canonical_implementation_merge_commit"], "0a7d9821d6844439d95c7a79cf09673a0ed05329")
        self.assertEqual(activation["release_candidate_merge_commit"], "5f640cac2a8d1d9a6559bb6f69805489b5822d74")
        self.assertEqual(activation["single_use_window_start_utc"], "2026-08-09T18:48:00Z")

    def test_activation_opens_only_exact_approved_runtime_envelope(self) -> None:
        activation = self.load(R7 / "R7_EXECUTION_RELEASE_CANONICALIZATION.json")
        self.assertEqual(activation["github_event_required"], "workflow_dispatch")
        self.assertEqual(activation["canonical_dispatch_ref_required"], "refs/heads/main")
        self.assertEqual(activation["object_key"], "node_fills/hourly/20250727/8.lz4")
        self.assertEqual(activation["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(activation["maximum_monthly_budget_eur"], 0)
        self.assertEqual(activation["maximum_get_object_requests"], 1)
        self.assertEqual(activation["maximum_requests_per_object"], 1)
        self.assertEqual(activation["maximum_retries_per_request"], 0)
        self.assertTrue(activation["requester_pays_authorized"])
        self.assertTrue(activation["get_object_authorized"])
        self.assertTrue(activation["decompression_authorized"])
        self.assertTrue(activation["wallet_index_reconstruction_authorized"])
        self.assertFalse(activation["head_object_authorized"])
        self.assertFalse(activation["range_get_authorized"])
        self.assertFalse(activation["list_objects_v2_authorized"])
        self.assertFalse(activation["http_redirect_following_authorized"])

    def test_activation_retention_is_only_address_plus_fill_count(self) -> None:
        activation = self.load(R7 / "R7_EXECUTION_RELEASE_CANONICALIZATION.json")
        self.assertTrue(activation["wallet_address_retention_authorized"])
        self.assertTrue(activation["leading_string_value_retention_authorized"])
        self.assertTrue(activation["per_wallet_fill_count_retention_authorized"])
        self.assertTrue(activation["unique_wallet_count_retention_authorized"])
        self.assertEqual(activation["wallet_address_normalization"], "LOWERCASE_EXACT_0X40HEX")
        self.assertEqual(activation["retained_wallet_index_fields_only"], ["wallet_address", "fill_count"])
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
            self.assertFalse(activation[key], key)

    def test_downstream_and_trading_authority_remains_closed(self) -> None:
        activation = self.load(R7 / "R7_EXECUTION_RELEASE_CANONICALIZATION.json")
        self.assertTrue(all(value is False for value in activation["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in activation["trading_authorizations"].values()))
        self.assertEqual(activation["s3_requests_executed"], 0)
        self.assertEqual(activation["wallet_addresses_retained"], 0)
        self.assertIsNone(activation["empirical_result"])

    def test_dedicated_activation_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r7_activation.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R7_ACTIVATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
