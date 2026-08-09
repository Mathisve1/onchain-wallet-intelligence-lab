from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R6A = ROOT / "research/archive_inventory/r6a"
EVIDENCE = R6A / "evidence/run-31327463448"
PREDECESSOR = R6A / "R6A_EXECUTION_RELEASE_001_CONSUMPTION.json"
SUCCESSOR = R6A / "R6A_EXECUTION_RELEASE_002_CANONICALIZATION.json"
VALIDATOR = ROOT / "governance/validate_r6a_successor_release.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-legacy-user-key-lexical-r6a-successor.yml"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


class ArchiveR6ASuccessorReleaseTests(unittest.TestCase):
    def test_failed_dispatch_is_exact_zero_s3_pre_oidc_evidence(self) -> None:
        context = load(EVIDENCE / "r6a-lexical-context.json")
        result = load(EVIDENCE / "r6a-lexical-result.json")
        verification = load(EVIDENCE / "INDEPENDENT_ARTIFACT_VERIFICATION.json")
        self.assertEqual(context["dispatch_sha"], "87d326e80ccc0820696a7fe479190ccade4c69e8")
        self.assertEqual(context["terminal_status"], "PRE_OIDC_GATE_FAILED")
        self.assertEqual(context["configure_aws_outcome"], "skipped")
        self.assertEqual(result["request_attempt_count"], 0)
        self.assertEqual(result["s3_http_request_count"], 0)
        self.assertEqual(result["compressed_bytes"], 0)
        self.assertEqual(result["decompressed_bytes"], 0)
        self.assertIsNone(result["lexical_aggregates"])
        self.assertEqual(verification["workflow_run_id"], 31327463448)
        self.assertEqual(verification["workflow_job_id"], 93280039214)
        self.assertEqual(verification["artifact_id"], 9041936336)
        self.assertEqual(verification["provider_artifact_zip_sha256"], "f452be5eb53ac111118da29fa886306dfc34f5698613d01ae5b06e2251622749")
        self.assertEqual(verification["provider_artifact_zip_sha256"], verification["independently_computed_artifact_zip_sha256"])
        self.assertFalse(verification["aws_oidc_role_assumption_attempted"])
        self.assertFalse(verification["collector_executed"])
        self.assertEqual(verification["s3_http_request_count"], 0)

    def test_retained_failure_artifact_ledger_is_byte_exact(self) -> None:
        expected = {
            "r6a-lexical-context.json": "9c2f8b84db972f365bd1763f0d85829d3387343a8d930cab6bf4b3eb670e355b",
            "r6a-lexical-result.json": "6279365ef93e227207cff2fa010618f2c694d1e7895bda090b56afa50c0ff90f",
            "r6a-lexical.rc": "6950980e3aca96f4dc400eb2e47cc5c343e0d3f483a4e70adcae1d7e6bb22d9c",
        }
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest(), digest)
        ledger = (EVIDENCE / "R6A_LEXICAL_FILES.sha256").read_text(encoding="utf-8")
        for name, digest in expected.items():
            self.assertIn(f"{digest}  {name}\n", ledger)
        self.assertEqual((EVIDENCE / "r6a-lexical.rc").read_text(encoding="utf-8"), "82\n")

    def test_release_001_is_consumed_but_network_budget_is_unused(self) -> None:
        predecessor = load(PREDECESSOR)
        self.assertEqual(predecessor["status"], "CONSUMED_BY_PRE_OIDC_FAILED_DISPATCH_ZERO_S3")
        self.assertTrue(predecessor["dispatch_consumed_release"])
        self.assertFalse(predecessor["rerun_authorized"])
        self.assertFalse(predecessor["aws_oidc_role_assumption_attempted"])
        self.assertFalse(predecessor["collector_executed"])
        self.assertEqual(predecessor["get_object_requests_executed"], 0)
        self.assertEqual(predecessor["s3_requests_executed"], 0)
        self.assertFalse(predecessor["network_budget_consumed"])
        self.assertEqual(predecessor["remaining_approved_get_object_budget"], 1)
        self.assertTrue(predecessor["successor_policy"]["successor_release_permitted"])
        self.assertEqual(predecessor["successor_policy"]["maximum_aggregate_get_object_requests_across_r6a_release_chain"], 1)

    def test_successor_preserves_exact_human_approved_network_and_retention_scope(self) -> None:
        successor = load(SUCCESSOR)
        self.assertEqual(successor["status"], "RELEASED_FOR_EXACTLY_ONE_CANONICAL_R6A_SUCCESSOR_RUN")
        self.assertEqual(successor["canonical_implementation_commit"], "806a054129de1f7d2480373be739ba7eea13258d")
        self.assertEqual(successor["object_key"], "node_fills/hourly/20250727/8.lz4")
        self.assertEqual(successor["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(successor["maximum_monthly_budget_eur"], 0)
        self.assertEqual(successor["maximum_get_object_requests_this_successor"], 1)
        self.assertEqual(successor["maximum_aggregate_get_object_requests_across_r6a_chain"], 1)
        self.assertEqual(successor["remaining_get_object_request_budget"], 1)
        self.assertEqual(successor["maximum_retries_per_request"], 0)
        self.assertTrue(successor["single_workflow_dispatch_authorized"])
        self.assertFalse(successor["rerun_authorized"])
        self.assertFalse(successor["scope_expansion_authorized"])
        self.assertFalse(successor["new_human_budget_authority_created"])
        forbidden = (
            "raw_compressed_object_retention_authorized", "raw_decompressed_payload_retention_authorized",
            "record_payload_retention_authorized", "payload_values_in_evidence_authorized",
            "string_values_in_evidence_authorized", "numeric_values_in_evidence_authorized",
            "leading_string_retention_authorized", "wallet_address_retention_authorized",
            "leading_string_hash_retention_authorized", "distinct_address_set_retention_authorized",
            "wallet_reconstruction_authorized", "entity_clustering_authorized",
            "copyability_analysis_authorized", "pnl_or_alpha_analysis_authorized",
            "market_data_ingestion_authorized",
        )
        self.assertTrue(all(successor[key] is False for key in forbidden))
        self.assertTrue(all(value is False for value in successor["trading_authorizations"].values()))

    def test_successor_workflow_is_distinct_manual_single_use_exact_object_lane(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("name: Hyperliquid Archive Hourly Body Schema Pilot R4\nrun-name: R6A successor legacy user-key lexical confirmation\n"))
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("push:", text)
        self.assertIn("EXPECTED_IMPLEMENTATION_COMMIT: 806a054129de1f7d2480373be739ba7eea13258d", text)
        self.assertNotIn("PENDING_CANONICAL_IMPLEMENTATION_MERGE", text)
        self.assertIn("R6A_EXECUTION_RELEASE_001_CONSUMPTION.json", text)
        self.assertIn("R6A_EXECUTION_RELEASE_002_CANONICALIZATION.json", text)
        self.assertIn("hyperliquid-archive-legacy-user-key-lexical-r6a-successor.yml/runs", text)
        self.assertNotIn("hyperliquid-archive-legacy-user-key-lexical-r6a.yml/runs", text)
        self.assertIn('"Action":"s3:GetObject"', text)
        self.assertIn("arn:aws:s3:::hl-mainnet-node-data/node_fills/hourly/20250727/8.lz4", text)
        self.assertIn("re-runs are forbidden", text)

    def test_dedicated_successor_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=False
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R6A_SUCCESSOR_RELEASE_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
