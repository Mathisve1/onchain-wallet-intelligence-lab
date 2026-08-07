from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "research/wallet_copyability/probe_r1/evidence"


def load_record(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


class ProbeR1FailureLineageTests(unittest.TestCase):
    def test_missing_module_run_is_not_route_evidence(self) -> None:
        record = load_record("R1-CI-001-MISSING-COLLECTOR-MODULES.json")
        self.assertEqual(record["classification"], "FAILED_PRE_NETWORK_PACKAGING")
        self.assertFalse(record["public_probe_workflow"]["network_execution_started"])
        self.assertFalse(record["public_probe_workflow"]["public_routes_contacted"])
        self.assertIsNone(record["technical_route_result"])
        self.assertIsNone(record["archive_access_result"])

    def test_merge_ref_run_is_not_exact_head_evidence(self) -> None:
        record = load_record("R1-CI-002-PR-MERGE-REF-NOT-EXACT-HEAD.json")
        self.assertEqual(
            record["classification"],
            "INTEGRITY_DEFECT_REQUIRES_CANONICAL_MAIN_RERUN",
        )
        self.assertFalse(record["accepted_technical_evidence"])
        self.assertFalse(record["repair"]["old_run_reusable_as_exact_head_evidence"])

    def test_no_final_candidate_exists_before_main_run(self) -> None:
        lineage = load_record("RUN_LINEAGE.json")
        self.assertEqual(lineage["canonical_result_status"], "PENDING_CANONICAL_MAIN_RUN")
        self.assertEqual(lineage["accepted_final_candidate_count"], 0)
        self.assertFalse(any(row["accepted_for_final_attestation"] for row in lineage["runs"]))
        self.assertFalse(lineage["market_data_ingested"])
        self.assertIsNone(lineage["empirical_result"])
        self.assertTrue(all(value is False for value in lineage["authorizations"].values()))


if __name__ == "__main__":
    unittest.main()
