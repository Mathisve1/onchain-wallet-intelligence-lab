from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_contract_is_closed_and_point_in_time(self) -> None:
        contract = json.loads((ROOT / "research/wallet_copyability/DATA_CONTRACT.json").read_text())
        self.assertEqual(contract["study_id"], "WALLET-COPYABILITY-STUDY-001")
        self.assertFalse(contract["market_data_ingested"])
        self.assertIsNone(contract["empirical_result"])
        self.assertEqual(contract["point_in_time"]["feature_cutoff_rule"], "first_seen_at <= selection_timestamp")
        self.assertFalse(contract["point_in_time"]["future_wallet_performance_allowed"])
        self.assertFalse(contract["point_in_time"]["future_cluster_links_allowed"])
        self.assertTrue(contract["execution_boundary"]["read_only"])
        for key, value in contract["execution_boundary"].items():
            if key != "read_only":
                self.assertFalse(value, key)
        for key, value in contract["authorizations"].items():
            self.assertFalse(value, key)
        probe = contract["technical_probe"]
        self.assertEqual(probe["probe_id"], "HL-PUBLIC-PROBE-001R1")
        self.assertTrue(probe["public_read_only_only"])
        self.assertFalse(probe["raw_response_bytes_retained"])
        self.assertFalse(probe["response_values_retained"])
        self.assertFalse(probe["analytical_market_partition_opened"])

    def test_probe_evidence_is_pending(self) -> None:
        evidence = json.loads((ROOT / "research/wallet_copyability/TECHNICAL_PROBE_EVIDENCE.json").read_text())
        self.assertEqual(evidence["status"], "PENDING_PUBLIC_PROBE")
        self.assertEqual(evidence["observation_count"], 0)
        self.assertIsNone(evidence["evidence_path"])
        self.assertIsNone(evidence["output_sha256"])
        self.assertIsNone(evidence["empirical_result"])
        for key, value in evidence["authorizations"].items():
            self.assertFalse(value, key)


if __name__ == "__main__":
    unittest.main()
