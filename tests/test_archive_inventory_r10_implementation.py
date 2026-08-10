from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT / "research/archive_inventory/r10_implementation"


class ArchiveR10ImplementationTests(unittest.TestCase):
    def load(self, name: str) -> dict:
        return json.loads((IMPL / name).read_text(encoding="utf-8"))

    def test_exact_lineage_scope_and_zero_runtime(self) -> None:
        impl = self.load("R10_IMPLEMENTATION_CONTRACT.json")
        self.assertEqual(impl["status"], "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION")
        self.assertEqual(impl["r10_preregistration_merge_commit"], "37e4486a7f68982feafcb361bd40dffd546def05")
        self.assertEqual(impl["r10_approval_merge_commit"], "92761986d8dc6bf818eebf7dc0411d24649a27df")
        self.assertEqual(impl["approval_text_sha256"], "ec631e7e6d40cb63383afd012a989419f97cd603ff144e4c5dfb90c18ff90882")
        self.assertEqual(len(impl["exact_network_targets"]), 6)
        self.assertEqual(sum(row["expected_size_bytes"] for row in impl["exact_network_targets"]), 120999698)
        self.assertEqual(impl["s3_requests_executed"], 0)
        self.assertEqual(impl["aws_iam_mutations_executed"], 0)
        self.assertEqual(impl["aws_sts_requests_executed"], 0)
        self.assertEqual(impl["wallet_feature_rows_created"], 0)
        self.assertIsNone(impl["empirical_result"])
        self.assertTrue(all(value is False for value in impl["current_runtime_authority"].values()))

    def test_permission_policy_is_exact_six_getobject_only(self) -> None:
        policy = self.load("R10_PERMISSION_POLICY.json")
        by_sid = {row["Sid"]: row for row in policy["Statement"]}
        allow = by_sid["AllowExactSixR10ObjectsOnly"]
        self.assertEqual(allow["Action"], "s3:GetObject")
        self.assertEqual(len(allow["Resource"]), 6)
        self.assertEqual(by_sid["DenyGetObjectOutsideExactSixR10Objects"]["Effect"], "Deny")
        self.assertEqual(by_sid["DenyGetObjectOutsideExactSixR10Objects"]["NotResource"], allow["Resource"])
        self.assertEqual(by_sid["DenyOtherS3ReadCapabilities"]["Effect"], "Deny")
        self.assertEqual(by_sid["DenyS3MutationAndRestore"]["Effect"], "Deny")
        serialized = json.dumps(policy, sort_keys=True)
        self.assertNotIn('"Action": "s3:*"', serialized)
        self.assertNotIn('"Effect": "Allow", "Resource": "*"', serialized)

    def test_trust_policy_is_exact_main_and_workflow_bound(self) -> None:
        trust = self.load("R10_OIDC_TRUST_POLICY.json")
        statement = trust["Statement"][0]
        conditions = statement["Condition"]["StringEquals"]
        self.assertEqual(conditions["token.actions.githubusercontent.com:sub"], "repo:Mathisve1@163474992/onchain-wallet-intelligence-lab@1326362646:ref:refs/heads/main")
        self.assertEqual(conditions["token.actions.githubusercontent.com:repository_id"], "1326362646")
        self.assertEqual(conditions["token.actions.githubusercontent.com:repository_owner_id"], "163474992")
        self.assertEqual(conditions["token.actions.githubusercontent.com:ref"], "refs/heads/main")
        self.assertEqual(conditions["token.actions.githubusercontent.com:workflow"], "Hyperliquid Archive Post-Boundary Multi-Hour Feature Pilot R10")

    def test_role_max_session_duration_is_aws_valid_but_workflow_stays_900_seconds(self) -> None:
        runbook = (IMPL / "R10_ROLE_CREATION_RUNBOOK.md").read_text(encoding="utf-8")
        attestation = (IMPL / "R10_OPERATOR_ATTESTATION_TEMPLATE.txt").read_text(encoding="utf-8")
        self.assertIn("--max-session-duration 3600", runbook)
        self.assertNotIn("--max-session-duration 900", runbook)
        self.assertIn("role_max_session_duration_seconds=3600", attestation)
        self.assertIn("future_workflow_role_duration_seconds=900", attestation)
        for path in (IMPL / "workflows").glob("*.yml"):
            self.assertIn("role-duration-seconds: 900", path.read_text(encoding="utf-8"))

    def test_frozen_preflight_candidate_remains_installed_and_later_data_workflow_is_present(self) -> None:
        candidates = IMPL / "workflows"
        preflight_candidate = candidates / "hyperliquid-archive-post-boundary-multihour-role-preflight-r10.yml"
        data_candidate = candidates / "hyperliquid-archive-post-boundary-multihour-feature-r10.yml"
        preflight_installed = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-role-preflight-r10.yml"
        data_installed = ROOT / ".github/workflows/hyperliquid-archive-post-boundary-multihour-feature-r10.yml"
        self.assertTrue(preflight_candidate.is_file())
        self.assertTrue(data_candidate.is_file())
        self.assertTrue(preflight_installed.is_file())
        self.assertEqual(preflight_candidate.read_bytes(), preflight_installed.read_bytes())
        self.assertTrue(data_installed.is_file())
        for path in candidates.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            self.assertIn("workflow_dispatch:", text)
            self.assertIn("id-token: write", text)
            self.assertIn("persist-credentials: false", text)
            self.assertLess(text.index("test -f"), text.index("aws-actions/configure-aws-credentials"))

    def test_downstream_and_trading_remain_closed(self) -> None:
        impl = self.load("R10_IMPLEMENTATION_CONTRACT.json")
        self.assertTrue(all(value is False for value in impl["downstream_authorizations"].values()))
        self.assertTrue(all(value is False for value in impl["trading_authorizations"].values()))
        self.assertTrue(all(value is False for value in impl["semantic_boundaries"].values()))
        self.assertTrue(all(value is False for value in impl["forbidden_retention_authorizations"].values()))

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r10_implementation.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R10_IMPLEMENTATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
