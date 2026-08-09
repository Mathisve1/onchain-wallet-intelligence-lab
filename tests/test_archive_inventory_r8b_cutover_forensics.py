from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8B = ROOT / "research/archive_inventory/r8b"


class ArchiveR8BCutoverForensicsTests(unittest.TestCase):
    def load(self, name: str) -> dict:
        return json.loads((R8B / name).read_text(encoding="utf-8"))

    def test_same_hour_boundary_is_directly_bound(self) -> None:
        c = self.load("CUTOVER_FORENSICS_R8B_CONTRACT.json")
        self.assertEqual(c["direct_findings"]["legacy_latest_path_hour_utc"], "2025-07-27T08:00:00Z")
        self.assertEqual(c["direct_findings"]["modern_earliest_path_hour_utc"], "2025-07-27T08:00:00Z")
        self.assertTrue(c["direct_findings"]["shared_boundary_path_hour"])

    def test_modern_boundary_is_extreme_size_minimum(self) -> None:
        a = self.load("METADATA_BOUNDARY_ANALYSIS.json")
        m = a["modern_boundary_object"]
        self.assertTrue(m["is_family_global_minimum"])
        self.assertEqual(m["global_minimum_rank"], 1)
        self.assertEqual(m["family_entry_count"], 9070)
        self.assertLess(m["boundary_to_next_hour_size_ratio"], 0.09)
        self.assertLess(m["boundary_to_next_24_median_size_ratio"], 0.07)

    def test_boundary_wallet_sets_are_not_nested(self) -> None:
        a = self.load("METADATA_BOUNDARY_ANALYSIS.json")
        comp = a["address_set_comparison"]
        self.assertEqual(comp["overlapping_wallet_count"], 688)
        self.assertEqual(comp["modern_only_wallet_count"], 199)
        self.assertEqual(comp["legacy_only_wallet_count"], 3949)
        self.assertFalse(comp["modern_address_set_subset_of_legacy"])
        self.assertFalse(comp["exact_fill_identity_inferred"])
        self.assertFalse(comp["temporal_subset_inferred"])

    def test_conclusion_is_supported_inference_not_direct_cutover_proof(self) -> None:
        c = self.load("CUTOVER_FORENSICS_R8B_CONTRACT.json")
        i = c["interpretation"]
        self.assertIn("HIGH_CONFIDENCE", i["classification"])
        self.assertFalse(i["direct_serializer_cutover_proven"])
        self.assertFalse(i["exact_temporal_partition_proven"])
        self.assertFalse(i["exact_fill_overlap_or_gap_proven"])

    def test_fail_closed_boundary_rule_censors_shared_hour(self) -> None:
        c = self.load("CUTOVER_FORENSICS_R8B_CONTRACT.json")
        r = c["canonical_cross_format_rule"]
        self.assertFalse(r["include_legacy_boundary_hour"])
        self.assertFalse(r["include_modern_boundary_hour"])
        self.assertFalse(r["double_count_boundary_hour"])
        self.assertFalse(r["claim_continuous_market_time_history"])
        self.assertEqual(r["legacy_last_format_boundary_unambiguous_path_hour_utc"], "2025-07-27T07:00:00Z")
        self.assertEqual(r["modern_first_format_boundary_unambiguous_path_hour_utc"], "2025-07-27T09:00:00Z")

    def test_static_study_opens_no_new_authority(self) -> None:
        c = self.load("CUTOVER_FORENSICS_R8B_CONTRACT.json")
        self.assertEqual(c["new_s3_requests_executed"], 0)
        self.assertEqual(c["new_requester_pays_cost_eur"], 0)
        self.assertTrue(all(v is False for v in c["current_authority"].values()))
        self.assertTrue(all(v is False for v in c["trading_authorizations"].values()))

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r8b_cutover_forensics.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R8B_CUTOVER_FORENSICS_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
