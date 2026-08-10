from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
RUN = BASE / "r10b_evidence/run-31395720147"
ATTEST = BASE / "r10b_evidence/HL-ARCHIVE-R10B-BATCH-METADATA-LEXICAL-DIAGNOSTIC-001-ATTESTATION.json"
CONSUMPTION = BASE / "r10b_runtime/R10B_EXECUTION_RELEASE_CONSUMPTION.json"
RELEASE = BASE / "r10b_runtime/R10B_EXECUTION_RELEASE.json"


class R10BExecutionEvidenceTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(value, dict)
        return value

    def test_exact_run_job_artifact_and_hash_binding(self) -> None:
        verification = self.load(RUN / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
        self.assertEqual(verification["workflow_run_id"], 31395720147)
        self.assertEqual(verification["workflow_run_attempt"], 1)
        self.assertEqual(verification["workflow_job_id"], 93478017396)
        self.assertEqual(verification["artifact_id"], 9065535303)
        self.assertEqual(verification["artifact_size_bytes"], 2459)
        digest = "6fe553710846794176bc040c87937a719ab83c0cb10101892b3f23749cefc789"
        self.assertEqual(verification["provider_zip_sha256"], digest)
        self.assertEqual(verification["independently_downloaded_zip_sha256"], digest)
        self.assertTrue(verification["provider_digest_matches_independent_download"])
        for name, expected in verification["internal_ledger"].items():
            self.assertEqual(hashlib.sha256((RUN / name).read_bytes()).hexdigest(), expected)

    def test_exact_lexical_crossing_result_is_attested_without_semantic_overclaim(self) -> None:
        result = self.load(RUN / "r10b-result.json")
        attest = self.load(ATTEST)
        summary = result["diagnostic_summary"]
        self.assertEqual(result["technical_result"], "BATCH_METADATA_LEXICALLY_CROSSES_PATH_HOUR")
        self.assertEqual(summary["block_record_count"], 36029)
        self.assertEqual(summary["local_time_prefix_bucket_counts"]["MATCHES_PATH_DATE_HOUR_PREFIX"], 36029)
        self.assertEqual(summary["block_time_prefix_bucket_counts"]["MATCHES_PATH_DATE_HOUR_PREFIX"], 36028)
        self.assertEqual(summary["block_time_prefix_bucket_counts"]["MATCHES_PREVIOUS_DATE_HOUR_PREFIX"], 1)
        self.assertEqual(summary["local_time_equals_block_time_count"], 0)
        self.assertEqual(summary["local_time_differs_from_block_time_count"], 36029)
        self.assertTrue(attest["claims_proven"]["exactly_one_block_time_value_matches_previous_date_hour_prefix"])
        self.assertFalse(attest["claims_not_proven"]["local_time_timezone_semantics"])
        self.assertFalse(attest["claims_not_proven"]["block_time_timezone_semantics"])
        self.assertFalse(attest["claims_not_proven"]["previous_hour_block_time_is_the_record_containing_either_pre_hour_fill"])
        self.assertFalse(attest["claims_not_proven"]["a_51ms_fill_time_tolerance_is_safe_for_general_history"])
        self.assertFalse(attest["claims_not_proven"]["r10_rule_should_be_amended"])

    def test_release_is_consumed_separately_and_never_rerunnable(self) -> None:
        release = self.load(RELEASE)
        consumption = self.load(CONSUMPTION)
        self.assertEqual(release["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R10B_RUN")
        self.assertFalse(release["release_consumed"])
        self.assertFalse(release["rerun_authorized"])
        self.assertTrue(consumption["release_consumed"])
        self.assertFalse(consumption["future_r10b_dispatch_authorized"])
        self.assertFalse(consumption["rerun_authorized"])
        self.assertEqual(consumption["remaining_get_object_budget_from_consumed_release"], 0)
        self.assertTrue(consumption["new_network_request_requires_new_preregistration_approval_and_release"])

    def test_no_wallet_ranking_copyability_or_trading_authority_opened(self) -> None:
        result = self.load(RUN / "r10b-result.json")
        attest = self.load(ATTEST)
        consumption = self.load(CONSUMPTION)
        for key in (
            "wallet_address_retained", "wallet_aggregation_performed", "wallet_ranking_performed",
            "candidate_shortlisting_performed", "pnl_or_alpha_analysis_performed",
            "copyability_analysis_performed", "market_data_ingested", "strategy_inference_performed",
            "r10_rule_amendment_performed", "r10_rerun_performed", "six_hour_execution_performed",
        ):
            self.assertFalse(result[key], key)
        self.assertTrue(all(value is False for value in attest["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in attest["trading_authorizations"].values()))
        self.assertTrue(all(value is False for value in consumption["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in consumption["trading_authorizations"].values()))

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10b_execution_evidence.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R10B_EXECUTION_EVIDENCE_VALID_BATCH_METADATA_LEXICALLY_CROSSES_PATH_HOUR", done.stdout)


if __name__ == "__main__":
    unittest.main()
