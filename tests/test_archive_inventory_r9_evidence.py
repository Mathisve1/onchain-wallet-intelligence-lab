from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R9 = ROOT / "research/archive_inventory/r9"
RUN = R9 / "evidence/run-31336490854"
DIAGNOSTICS = R9 / "evidence/R9_AGGREGATE_DIAGNOSTICS.json"
ATTESTATION = R9 / "evidence/HL-ARCHIVE-MODERN-WALLET-FEATURE-PILOT-R9-001-ATTESTATION.json"
CONSUMPTION = R9 / "R9_EXECUTION_RELEASE_CONSUMPTION.json"


class ArchiveR9EvidenceTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_run_job_artifact_and_terminal_result_are_bound(self) -> None:
        result = self.load(RUN / "r9-result.json")
        reconstruction = self.load(RUN / "ARTIFACT_RECONSTRUCTION.json")
        self.assertEqual(reconstruction["workflow_run_id"], 31336490854)
        self.assertEqual(reconstruction["workflow_job_id"], 93303097917)
        self.assertEqual(reconstruction["artifact_id"], 9044483094)
        self.assertEqual(reconstruction["artifact_zip_sha256"], "00c049def4ef2db334067f7f6ff00abaee7761fbc3de2e07dd742019119a3459")
        self.assertEqual(result["terminal_status"], "R9_MODERN_WALLET_FEATURE_STUDY_COMPLETE")
        self.assertEqual(result["technical_result"], "MODERN_WALLET_FEATURE_PIPELINE_COMPLETE")
        self.assertEqual(result["s3_http_request_count"], 1)
        self.assertEqual(result["retries_used"], 0)
        self.assertFalse(result["http_redirects_followed"])

    def test_feature_pipeline_conserves_all_events_without_ranking(self) -> None:
        result = self.load(RUN / "r9-result.json")
        summary = result["wallet_feature_summary"]
        self.assertEqual(summary["top_level_block_record_count"], 4345)
        self.assertEqual(summary["valid_event_pair_count"], 17516)
        self.assertEqual(summary["wallet_feature_row_count"], 887)
        self.assertEqual(summary["sum_fill_count"], 17516)
        self.assertEqual(summary["sum_side_count"], 17516)
        self.assertEqual(summary["wallet_feature_sha256"], "e8bf51556d3d2e08d3d79c6b23a20f9d1ef76018364c701c06f6abf9d993fec5")
        self.assertFalse(result["wallet_ranking_performed"])
        self.assertFalse(result["candidate_shortlisting_performed"])
        self.assertFalse(result["pnl_or_alpha_analysis_performed"])
        self.assertFalse(result["copyability_analysis_performed"])

    def test_raw_payloads_and_individual_selected_values_remain_absent(self) -> None:
        result = self.load(RUN / "r9-result.json")
        for key in (
            "raw_block_records_retained",
            "raw_compressed_object_persisted",
            "raw_decompressed_payload_retained",
            "raw_event_pairs_retained",
            "raw_fill_objects_retained",
            "coin_values_retained",
            "side_values_retained",
            "individual_time_values_retained",
            "individual_price_values_retained",
            "individual_size_values_retained",
            "individual_closed_pnl_values_retained",
            "trade_id_values_retained",
            "crossed_values_retained",
            "liquidation_payload_values_retained",
        ):
            self.assertFalse(result[key], key)

    def test_boundary_time_refinement_is_direct_but_still_fail_closed(self) -> None:
        diagnostics = self.load(DIAGNOSTICS)
        self.assertEqual(diagnostics["global_first_retained_fill_time_ms"], 1753606210273)
        self.assertEqual(diagnostics["global_first_retained_fill_time_utc"], "2025-07-27T08:50:10.273Z")
        self.assertEqual(diagnostics["global_last_retained_fill_time_ms"], 1753606799895)
        self.assertEqual(diagnostics["global_last_retained_fill_time_utc"], "2025-07-27T08:59:59.895Z")
        self.assertEqual(diagnostics["observed_feature_time_span_ms"], 589622)
        self.assertFalse(diagnostics["interpretation_boundaries"]["fixture_is_historically_representative"])
        self.assertFalse(diagnostics["interpretation_boundaries"]["single_fixture_feature_statistics_support_wallet_quality_ranking"])

    def test_aggregate_diagnostics_are_exact_and_nonsemantic(self) -> None:
        diagnostics = self.load(DIAGNOSTICS)
        self.assertEqual(diagnostics["crossed_true_count_total"], 8758)
        self.assertEqual(diagnostics["liquidation_associated_fill_count_total"], 0)
        self.assertEqual(diagnostics["duplicate_tid_count_total"], 0)
        self.assertEqual(diagnostics["sum_abs_px_times_sz_notional_proxy_total"], "41195607.73093746")
        self.assertEqual(diagnostics["sum_closed_pnl_fill_statistic_total"], "-8612.81910500")
        self.assertEqual(
            diagnostics["wallet_rows_with_positive_closed_pnl_fill_statistic"]
            + diagnostics["wallet_rows_with_zero_closed_pnl_fill_statistic"]
            + diagnostics["wallet_rows_with_negative_closed_pnl_fill_statistic"],
            887,
        )
        self.assertTrue(all(value is False for value in diagnostics["downstream_actions_performed"].values()))

    def test_release_is_consumed_and_never_rerunnable(self) -> None:
        consumption = self.load(CONSUMPTION)
        self.assertEqual(consumption["status"], "CONSUMED_BY_CANONICAL_R9_RUN")
        self.assertTrue(consumption["release_consumed"])
        self.assertEqual(consumption["successful_get_object_requests"], 1)
        self.assertEqual(consumption["remaining_get_object_budget"], 0)
        self.assertFalse(consumption["future_r9_dispatch_authorized"])
        self.assertFalse(consumption["rerun_authorized"])
        self.assertTrue(all(value is False for value in consumption["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in consumption["trading_authorizations"].values()))

    def test_attestation_keeps_semantic_overclaims_closed(self) -> None:
        attestation = self.load(ATTESTATION)
        self.assertEqual(attestation["technical_result"], "MODERN_WALLET_FEATURE_PIPELINE_COMPLETE")
        self.assertTrue(attestation["claims_proven"]["deterministic_per_wallet_feature_reducer_completed"])
        self.assertFalse(attestation["claims_not_proven"]["sum_closed_pnl_is_exact_account_return"])
        self.assertFalse(attestation["claims_not_proven"]["sum_closed_pnl_is_wallet_ranking_score"])
        self.assertFalse(attestation["claims_not_proven"]["notional_proxy_is_copyable_notional"])
        self.assertFalse(attestation["claims_not_proven"]["wallet_ranking_is_authorized"])
        self.assertTrue(attestation["all_trading_and_capital_authorizations_remain_false"])

    def test_dedicated_evidence_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r9_evidence.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R9_EVIDENCE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
