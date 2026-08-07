from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "research/wallet_copyability/probe_r1/evidence"


class ProbeR1FailureLineageTests(unittest.TestCase):
    def load(self, name: str) -> dict:
        return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))

    def test_missing_module_failure_is_preserved_as_pre_network_only(self) -> None:
        record = self.load("R1-CI-001-MISSING-COLLECTOR-MODULES.json")
        self.assertEqual(record["classification"], "FAILED_PRE_NETWORK_PACKAGING")
        self.assertEqual(record["research_ci"]["workflow_run_id"], 31177378135)
        self.assertEqual(record["research_ci"]["workflow_job_id"], 92862280886)
        self.assertEqual(record["public_probe_workflow"]["workflow_run_id"], 31177376738)
        self.assertEqual(record["public_probe_workflow"]["workflow_job_id"], 92862275918)
        self.assertFalse(record["public_probe_workflow"]["network_execution_started"])
        self.assertFalse(record["public_probe_workflow"]["public_routes_contacted"])
        self.assertIsNone(record["technical_route_result"])
        self.assertIsNone(record["archive_access_result"])
        self.assertFalse(record["old_runs_may_be_relabelled_as_public_probe_fail"])
        self.assertTrue(all(record[key] is False for key in (
            "integration_authorized",
            "paper_authorized",
            "shadow_authorized",
            "live_authorized",
            "leverage_authorized",
            "capital_allocation_authorized",
        )))

    def test_merge_ref_defect_is_not_accepted_as_exact_head_evidence(self) -> None:
        record = self.load("R1-CI-002-PR-MERGE-REF-NOT-EXACT-HEAD.json")
        self.assertEqual(
            record["declared_source_head"],
            "2689e1b7b3ef46909b298230ee53499b30d13772",
        )
        self.assertEqual(
            record["observed_checked_out_commit"],
            "f60c13aba871295e886cc8aa816b11afd759f85a",
        )
        self.assertFalse(record["network_execution_started"])
        self.assertFalse(record["accepted_technical_evidence"])
        self.assertFalse(record["repair"]["old_run_reusable_as_exact_head_evidence"])


if __name__ == "__main__":
    unittest.main()
