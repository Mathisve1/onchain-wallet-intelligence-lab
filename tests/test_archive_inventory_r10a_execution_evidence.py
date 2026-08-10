from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RUN = BASE / "r10a_evidence/run-31386230522"
ATTEST = BASE / "r10a_evidence/HL-ARCHIVE-R10A-TIMESTAMP-PARTITION-DIAGNOSTIC-001-ATTESTATION.json"
CONSUMPTION = BASE / "r10a_runtime/R10A_EXECUTION_RELEASE_CONSUMPTION.json"


class R10AExecutionEvidenceTests(unittest.TestCase):
    @staticmethod
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_run_artifact_and_result_are_bound(self) -> None:
        v = self.load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
        self.assertEqual(v["run_id"], 31386230522)
        self.assertEqual(v["job_id"], 93447175508)
        self.assertEqual(v["artifact_id"], 9061819935)
        self.assertEqual(v["provider_zip_sha256"], "c52344b911b439db08a9a369f9016bde87f2925091ce83b97c0ee00744fb1e68")
        self.assertTrue(v["provider_digest_matches_independent_download"])
        self.assertEqual(v["job_conclusion"], "success")
        self.assertEqual(v["return_code_value"], 0)

    def test_fill_time_spill_is_precise_and_small_but_not_generalized(self) -> None:
        r = self.load(RUN / "r10a-result.json")
        s = r["diagnostic_summary"]
        self.assertEqual(r["research_conclusion"], "FILL_TIME_SPILLS_OUTSIDE_PATH_HOUR")
        self.assertEqual(s["fill_time_count"], 223950)
        self.assertEqual(s["fill_time_before_path_hour_count"], 2)
        self.assertEqual(s["fill_time_inside_path_hour_count"], 223948)
        self.assertEqual(s["fill_time_after_path_hour_count"], 0)
        self.assertEqual(s["fill_time_min_utc"], "2025-07-27T08:59:59.949Z")
        self.assertEqual(s["fill_time_max_utc"], "2025-07-27T09:59:59.594Z")
        a = self.load(ATTEST)
        self.assertEqual(a["exact_network_observation"]["fill_time_earliest_boundary_offset_ms"], -51)
        self.assertFalse(a["claims_not_proven"]["a_51ms_tolerance_is_safe_for_general_history"])
        self.assertFalse(a["claims_not_proven"]["r10_rule_should_be_amended"])

    def test_block_and_local_time_semantics_remain_unresolved(self) -> None:
        r = self.load(RUN / "r10a-result.json")
        s = r["diagnostic_summary"]
        self.assertEqual(s["block_time_parseable_count"], 0)
        self.assertEqual(s["block_time_unparseable_count"], 36029)
        self.assertEqual(s["local_time_parseable_with_explicit_timezone_count"], 0)
        self.assertEqual(s["local_time_not_explicitly_zoned_count"], 36029)
        self.assertEqual(s["fill_minus_block_time_delta_histogram"]["UNAVAILABLE"], 223950)
        a = self.load(ATTEST)
        self.assertFalse(a["claims_not_proven"]["path_hour_partition_is_defined_by_block_time"])
        self.assertFalse(a["claims_not_proven"]["path_hour_partition_is_defined_by_local_time"])

    def test_release_is_consumed_without_opening_downstream_authority(self) -> None:
        c = self.load(CONSUMPTION)
        self.assertTrue(c["release_consumed"])
        self.assertFalse(c["future_r10a_dispatch_authorized"])
        self.assertFalse(c["rerun_authorized"])
        self.assertEqual(c["remaining_get_object_budget_from_consumed_release"], 0)
        self.assertFalse(c["r10_rule_amendment_authorized"])
        self.assertFalse(c["six_hour_execution_authorized"])
        self.assertTrue(all(v is False for v in c["downstream_authorizations"].values()))
        self.assertTrue(all(v is False for v in c["trading_authorizations"].values()))

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10a_execution_evidence.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10A_EXECUTION_EVIDENCE_VALID_FILL_TIME_SPILL_OBSERVED", done.stdout)


if __name__ == "__main__":
    unittest.main()
