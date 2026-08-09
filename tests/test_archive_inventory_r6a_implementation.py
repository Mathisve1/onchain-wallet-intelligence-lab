from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r6a"
PREREG = BASE / "LEGACY_USER_KEY_LEXICAL_R6A_CONTRACT.json"
APPROVAL = BASE / "approvals/APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001.json"
APPROVAL_TEXT = BASE / "approvals/APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001.txt"
IMPLEMENTATION = BASE / "R6A_IMPLEMENTATION_CONTRACT.json"
ROLE_REUSE = BASE / "R6A_AWS_ROLE_REUSE_ANALYSIS.json"
VALIDATOR = ROOT / "governance/validate_r6a_implementation.py"
WORKFLOW = ROOT / ".github/workflows/hyperliquid-archive-legacy-user-key-lexical-r6a.yml"

PREREG_MERGE = "870fdf3e10a761d6c4589d43def8e436f3a129b5"
APPROVAL_MERGE = "06c0086f80cdbc3d058bdeea64b618da276e95ec"
APPROVAL_SHA = "b24c67f527a320e533408fd821d10b5e2ea01d020c837e87ae5e5bbd386c94ed"
ROLE_ARN = "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4"
OBJECT_ARN = "arn:aws:s3:::hl-mainnet-node-data/node_fills/hourly/20250727/8.lz4"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


class ArchiveR6AImplementationTests(unittest.TestCase):
    def test_exact_lineage_scope_and_caps(self) -> None:
        prereg = load(PREREG)
        approval = load(APPROVAL)
        impl = load(IMPLEMENTATION)
        self.assertEqual(hashlib.sha256(APPROVAL_TEXT.read_bytes()).hexdigest(), APPROVAL_SHA)
        self.assertEqual(approval["reviewed_commit"], PREREG_MERGE)
        self.assertEqual(impl["preregistration_commit"], PREREG_MERGE)
        self.assertEqual(impl["approval_merge_commit"], APPROVAL_MERGE)
        self.assertEqual(impl["approval_text_sha256"], APPROVAL_SHA)
        self.assertEqual(impl["pilot_id"], prereg["pilot_id"])
        self.assertEqual(impl["object"]["key"], "node_fills/hourly/20250727/8.lz4")
        self.assertEqual(impl["maximum_get_object_requests"], 1)
        self.assertEqual(impl["maximum_retries_per_request"], 0)
        self.assertEqual(impl["maximum_one_time_budget_eur"], 0.10)
        self.assertEqual(impl["maximum_monthly_budget_eur"], 0)
        self.assertEqual(impl["expected_nonempty_record_count"], 162815)

    def test_implementation_snapshot_is_inert_and_not_a_release(self) -> None:
        impl = load(IMPLEMENTATION)
        self.assertEqual(impl["status"], "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION")
        self.assertFalse(impl["execution_release_present"])
        self.assertFalse(impl["execution_authorized"])
        self.assertFalse(impl["paid_request_authorized"])
        self.assertFalse(impl["requester_pays_authorized"])
        self.assertFalse(impl["get_object_authorized"])
        self.assertFalse(impl["object_body_download_authorized"])
        self.assertFalse(impl["decompression_authorized"])
        self.assertFalse(impl["lexical_classification_authorized"])
        self.assertEqual(impl["expected_canonical_implementation_commit"], "PENDING_CANONICAL_IMPLEMENTATION_MERGE")
        self.assertEqual(impl["s3_requests_executed"], 0)
        self.assertIsNone(impl["empirical_result"])

    def test_retention_downstream_and_trading_boundaries_stay_closed(self) -> None:
        impl = load(IMPLEMENTATION)
        forbidden = (
            "raw_compressed_object_retention_authorized",
            "raw_decompressed_payload_retention_authorized",
            "record_payload_retention_authorized",
            "payload_values_in_evidence_authorized",
            "string_values_in_evidence_authorized",
            "numeric_values_in_evidence_authorized",
            "leading_string_retention_authorized",
            "wallet_address_retention_authorized",
            "leading_string_hash_retention_authorized",
            "distinct_address_set_retention_authorized",
            "wallet_reconstruction_authorized",
            "entity_clustering_authorized",
            "copyability_analysis_authorized",
            "pnl_or_alpha_analysis_authorized",
            "market_data_ingestion_authorized",
        )
        self.assertTrue(all(impl[key] is False for key in forbidden))
        self.assertTrue(all(value is False for value in impl["trading_authorizations"].values()))
        self.assertEqual(
            impl["retained_aggregates_only"],
            [
                "nonempty_record_count",
                "pair_string_object_record_count",
                "leading_string_count",
                "leading_string_length_42_count",
                "leading_string_0x40hex_count",
                "leading_string_lowercase_0x40hex_count",
                "leading_string_non_0x40hex_count",
            ],
        )

    def test_unchanged_role_is_reused_with_exact_one_object_session_scope(self) -> None:
        impl = load(IMPLEMENTATION)
        reuse = load(ROLE_REUSE)
        self.assertEqual(impl["reused_dedicated_role_arn"], ROLE_ARN)
        self.assertFalse(impl["aws_role_mutation_required"])
        self.assertFalse(impl["aws_role_mutation_authorized"])
        self.assertEqual(reuse["reused_role_arn"], ROLE_ARN)
        self.assertEqual(reuse["r6a_session_scope"]["allowed_object_arns"], [OBJECT_ARN])
        self.assertTrue(reuse["r6a_session_scope"]["strict_subset_of_persistent_role"])
        self.assertTrue(reuse["r6a_session_scope"]["same_exact_object_as_successful_r5_session"])
        self.assertFalse(reuse["aws_iam_mutation_performed"])
        self.assertFalse(reuse["new_sts_preflight_required"])
        self.assertEqual(reuse["independent_prior_network_proofs"]["r5_run"], 31321019885)
        self.assertTrue(reuse["independent_prior_network_proofs"]["r5_same_exact_legacy_get_succeeded"])

    def test_workflow_candidate_exists_but_release_gate_keeps_it_inert(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("EXPECTED_IMPLEMENTATION_COMMIT: PENDING_CANONICAL_IMPLEMENTATION_MERGE", text)
        self.assertIn("R6A_EXECUTION_RELEASE_CANONICALIZATION.json", text)
        self.assertIn("Implementation is not yet canonical; no AWS authentication is allowed", text)
        self.assertLess(
            text.index("Prove canonical R6A implementation and release before AWS OIDC"),
            text.index("Assume unchanged dedicated AWS role with exact-one-object R6A session permissions"),
        )

    def test_dedicated_implementation_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(VALIDATOR)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R6A_IMPLEMENTATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
