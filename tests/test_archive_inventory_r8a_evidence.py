from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "research/archive_inventory/r8"
RUN = R8 / "evidence/run-31333421763"


class ArchiveR8AEvidenceTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_canonical_run_and_artifact_are_bound(self) -> None:
        context = self.load(RUN / "r8a-context.json")
        verify = self.load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
        self.assertEqual(context["workflow_run_id"], 31333421763)
        self.assertEqual(context["workflow_run_attempt"], 1)
        self.assertEqual(context["dispatch_sha"], "2f8237de806dcf149579aefc6ece1ae537ef7aeb")
        self.assertEqual(context["dispatch_ref"], "refs/heads/main")
        self.assertEqual(context["configure_aws_outcome"], "success")
        self.assertEqual(verify["workflow_job_id"], 93295166161)
        self.assertEqual(verify["artifact_id"], 9043584172)
        self.assertEqual(verify["artifact_zip_sha256"], "185037463a1eab27b35c5f8b6edad810a28bce599101e4d26734020717a392c8")
        self.assertEqual(verify["artifact_size_bytes"], 25269)
        self.assertTrue(verify["all_checks_pass"])

    def test_modern_wallet_index_is_exact_sorted_unique_and_conservative(self) -> None:
        result = self.load(RUN / "r8a-result.json")
        index = RUN / "r8a-wallet-index.ndjson"
        self.assertEqual(result["research_conclusion"], "MODERN_WALLET_INDEX_BRIDGE_COMPLETE")
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["retries_used"], 0)
        self.assertEqual(result["compressed_bytes"], 1517603)
        self.assertEqual(result["decompressed_bytes"], 7380378)
        summary = result["wallet_index_summary"]
        self.assertEqual(summary["top_level_block_record_count"], 4345)
        self.assertEqual(summary["valid_event_pair_count"], 17516)
        self.assertEqual(summary["unique_wallet_count"], 887)
        self.assertEqual(summary["sum_fill_count"], 17516)
        self.assertEqual(summary["wallet_index_bytes"], 70343)
        self.assertEqual(hashlib.sha256(index.read_bytes()).hexdigest(), summary["wallet_index_sha256"])
        rows = [json.loads(line) for line in index.read_text(encoding="utf-8").splitlines()]
        addresses = [row["wallet_address"] for row in rows]
        self.assertEqual(len(rows), 887)
        self.assertEqual(addresses, sorted(addresses))
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertEqual(sum(row["fill_count"] for row in rows), 17516)
        self.assertTrue(all(list(row.keys()) == ["wallet_address", "fill_count"] for row in rows))

    def test_payload_performance_ranking_copyability_and_trading_remain_absent(self) -> None:
        result = self.load(RUN / "r8a-result.json")
        for key in (
            "raw_compressed_object_persisted", "raw_decompressed_payload_retained", "record_payload_retained",
            "fill_object_retained", "payload_values_retained", "performance_field_values_retained",
            "block_number_values_retained", "local_time_values_retained", "block_time_values_retained",
            "coin_values_retained", "price_values_retained", "size_values_retained", "side_values_retained",
            "time_values_retained", "dir_values_retained", "closed_pnl_values_retained", "fee_values_retained",
            "fee_token_values_retained", "start_position_values_retained", "crossed_values_retained",
            "liquidation_values_retained", "transaction_hashes_retained", "order_ids_retained", "trade_ids_retained",
            "client_order_ids_retained", "historical_multi_hour_ingestion_performed", "public_api_enrichment_performed",
            "entity_clustering_performed", "wallet_ranking_performed", "copyability_analysis_performed",
            "pnl_or_alpha_analysis_performed", "market_data_ingested", "strategy_inference_performed",
        ):
            self.assertFalse(result[key], key)
        consumption = self.load(R8 / "R8A_EXECUTION_RELEASE_CONSUMPTION.json")
        self.assertTrue(all(value is False for value in consumption["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in consumption["trading_authorizations"].values()))

    def test_release_is_consumed_and_never_rerunnable(self) -> None:
        consumption = self.load(R8 / "R8A_EXECUTION_RELEASE_CONSUMPTION.json")
        self.assertEqual(consumption["status"], "CONSUMED_BY_CANONICAL_R8A_RUN")
        self.assertTrue(consumption["release_consumed"])
        self.assertEqual(consumption["workflow_run_id"], 31333421763)
        self.assertEqual(consumption["successful_get_object_requests"], 1)
        self.assertEqual(consumption["remaining_get_object_budget"], 0)
        self.assertFalse(consumption["future_r8a_dispatch_authorized"])
        self.assertFalse(consumption["rerun_authorized"])

    def test_bridge_comparison_is_aggregate_only_and_nonsemantic(self) -> None:
        comparison = self.load(R8 / "evidence/R8A_LEGACY_MODERN_BRIDGE_COMPARISON.json")
        self.assertEqual(comparison["legacy_unique_wallet_count"], 4637)
        self.assertEqual(comparison["legacy_sum_fill_count"], 162815)
        self.assertEqual(comparison["modern_unique_wallet_count"], 887)
        self.assertEqual(comparison["modern_sum_fill_count"], 17516)
        self.assertEqual(
            comparison["overlapping_wallet_count"] + comparison["modern_only_wallet_count"],
            comparison["modern_unique_wallet_count"],
        )
        self.assertFalse(comparison["exact_fill_identity_inferred"])
        self.assertFalse(comparison["temporal_subset_inferred"])
        self.assertFalse(comparison["schema_equivalence_inferred"])
        self.assertFalse(comparison["semantic_equivalence_inferred"])
        self.assertFalse(comparison["wallet_ranking_performed"])
        self.assertFalse(comparison["copyability_analysis_performed"])
        self.assertFalse(comparison["pnl_or_alpha_analysis_performed"])

    def test_dedicated_evidence_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r8a_evidence.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R8A_EVIDENCE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
