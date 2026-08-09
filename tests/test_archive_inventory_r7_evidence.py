from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R7 = ROOT / "research/archive_inventory/r7"
RUN = R7 / "evidence/run-31330248235"


class ArchiveR7EvidenceTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_run_job_artifact_and_result_are_bound(self) -> None:
        result = self.load(RUN / "r7-result.json")
        verify = self.load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
        self.assertEqual(verify["run_id"], 31330248235)
        self.assertEqual(verify["job_id"], 93287248593)
        self.assertEqual(verify["artifact_id"], 9042711108)
        self.assertEqual(verify["artifact_zip_sha256"], "fb36478cdff956f83efdd1d7ae8c7bb8b3a82e8226d3868ea877a99ffac46ea7")
        self.assertEqual(result["terminal_status"], "R7_WALLET_INDEX_STUDY_COMPLETE")
        self.assertEqual(result["research_conclusion"], "WALLET_INDEX_RECONSTRUCTION_COMPLETE")
        self.assertEqual(result["request_attempt_count"], 1)
        self.assertEqual(result["successful_request_count"], 1)
        self.assertEqual(result["failed_request_count"], 0)
        self.assertEqual(result["retries_used"], 0)

    def test_wallet_index_is_exact_unique_sorted_and_conserves_all_fills(self) -> None:
        result = self.load(RUN / "r7-result.json")
        index = RUN / "r7-wallet-index.ndjson"
        data = index.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), "2b8cbf709075aeda25394f22ee04b08656d5d165105976ed5d7e0890479e2d6d")
        self.assertEqual(len(data), 368036)
        rows = [json.loads(raw.decode("utf-8")) for raw in data.splitlines()]
        self.assertEqual(len(rows), 4637)
        addresses = [row["wallet_address"] for row in rows]
        self.assertEqual(addresses, sorted(addresses))
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertTrue(all(re.fullmatch(r"0x[0-9a-f]{40}", address) for address in addresses))
        self.assertTrue(all(list(row.keys()) == ["wallet_address", "fill_count"] for row in rows))
        self.assertTrue(all(isinstance(row["fill_count"], int) and row["fill_count"] > 0 for row in rows))
        self.assertEqual(sum(row["fill_count"] for row in rows), 162815)
        summary = result["wallet_index_summary"]
        self.assertEqual(summary["unique_wallet_count"], 4637)
        self.assertEqual(summary["sum_fill_count"], 162815)

    def test_payload_fields_and_downstream_analysis_remain_absent(self) -> None:
        result = self.load(RUN / "r7-result.json")
        for key in (
            "raw_compressed_object_persisted", "raw_decompressed_payload_retained",
            "record_payload_retained", "fill_object_retained", "payload_values_retained",
            "coin_values_retained", "price_values_retained", "size_values_retained",
            "side_values_retained", "time_values_retained", "closed_pnl_values_retained",
            "fee_values_retained", "transaction_hashes_retained", "order_ids_retained",
            "trade_ids_retained", "client_order_ids_retained", "entity_clustering_performed",
            "copyability_analysis_performed", "pnl_or_alpha_analysis_performed",
            "market_data_ingested", "historical_multi_hour_ingestion_performed",
            "strategy_inference_performed",
        ):
            self.assertFalse(result[key], key)

    def test_release_is_consumed_and_cannot_be_rerun(self) -> None:
        consumption = self.load(R7 / "R7_EXECUTION_RELEASE_CONSUMPTION.json")
        activation = self.load(R7 / "R7_EXECUTION_RELEASE_CANONICALIZATION.json")
        self.assertTrue(consumption["release_consumed"])
        self.assertFalse(consumption["future_r7_dispatch_authorized"])
        self.assertFalse(consumption["rerun_authorized"])
        self.assertEqual(consumption["remaining_approved_get_object_budget"], 0)
        self.assertFalse(activation["rerun_authorized"])
        self.assertTrue(all(value is False for value in consumption["downstream_authorizations_after_run"].values()))
        self.assertTrue(all(value is False for value in consumption["trading_authorizations_after_run"].values()))

    def test_independent_verification_is_all_pass(self) -> None:
        verify = self.load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
        self.assertEqual(verify["verification_status"], "PASS")
        self.assertTrue(all(value is True for value in verify["checks"].values()))

    def test_dedicated_evidence_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r7_evidence.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R7_EVIDENCE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
