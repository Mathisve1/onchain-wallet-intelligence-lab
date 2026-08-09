from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCESS = ROOT / "research/archive_inventory/aws_access"
ARCHIVE = ROOT / "research/archive_inventory"
IMMUTABLE_SUBJECT = (
    "repo:Mathisve1@163474992/"
    "onchain-wallet-intelligence-lab@1326362646:ref:refs/heads/main"
)


class ArchiveAwsOidcAccessTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_identity_binding_is_exact_and_sts_attested(self) -> None:
        binding = self.load(ACCESS / "AWS_IDENTITY_BINDING.json")
        self.assertEqual(binding["aws_account_id"], "630956766927")
        self.assertEqual(binding["oidc_provider_arn"], "arn:aws:iam::630956766927:oidc-provider/token.actions.githubusercontent.com")
        self.assertEqual(binding["github_repository"], "Mathisve1/onchain-wallet-intelligence-lab")
        self.assertEqual(binding["github_repository_id"], "1326362646")
        self.assertEqual(binding["github_repository_owner_id"], "163474992")
        self.assertEqual(binding["github_ref"], "refs/heads/main")
        self.assertEqual(binding["github_subject"], IMMUTABLE_SUBJECT)
        self.assertFalse(binding["github_subject_independently_observed"])
        self.assertTrue(binding["github_federation_independently_proven"])
        self.assertEqual(binding["role_status"], "INDEPENDENTLY_PROVEN_ASSUMEABLE_FROM_CANONICAL_MAIN")
        self.assertEqual(binding["inline_policy_name"], "HLArchiveMetadataCanaryListOnly")
        self.assertEqual(binding["permission_policy_status"], "USER_CONFIRMED_INLINE_POLICY_APPLIED_NOT_API_VERIFIED")
        self.assertEqual(binding["planned_workflow_session_duration_seconds"], 900)
        self.assertEqual(binding["role_max_session_duration_seconds"], 3600)
        self.assertTrue(binding["network_identity_check_authorized"])
        self.assertTrue(binding["network_identity_check_completed"])
        self.assertEqual(binding["network_identity_check_id"], "HL-AWS-OIDC-IDENTITY-001")
        self.assertEqual(binding["network_identity_check_result"], "STS_IDENTITY_MATCH")
        self.assertEqual(binding["canonical_identity_run_id"], 31250176507)
        self.assertEqual(binding["canonical_identity_job_id"], 93085194965)
        self.assertEqual(binding["canonical_identity_artifact_id"], 9019744292)
        self.assertFalse(binding["requester_pays_authorized"])
        self.assertFalse(binding["list_objects_authorized"])
        self.assertFalse(binding["paid_request_authorized"])
        self.assertFalse(binding["get_object_authorized"])
        self.assertFalse(binding["object_body_download_authorized"])
        self.assertFalse(binding["market_data_ingested"])
        self.assertIsNone(binding["empirical_result"])
        self.assertTrue(all(value is False for value in binding["authorizations"].values()))

    def test_trust_policy_is_exact_immutable_main_only(self) -> None:
        policy = self.load(ACCESS / "OIDC_TRUST_POLICY.json")
        self.assertEqual(policy["Version"], "2012-10-17")
        self.assertEqual(len(policy["Statement"]), 1)
        statement = policy["Statement"][0]
        self.assertEqual(statement["Effect"], "Allow")
        self.assertEqual(statement["Action"], "sts:AssumeRoleWithWebIdentity")
        self.assertEqual(statement["Principal"]["Federated"], "arn:aws:iam::630956766927:oidc-provider/token.actions.githubusercontent.com")
        self.assertEqual(
            statement["Condition"]["StringEquals"],
            {
                "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                "token.actions.githubusercontent.com:sub": IMMUTABLE_SUBJECT,
                "token.actions.githubusercontent.com:repository_id": "1326362646",
                "token.actions.githubusercontent.com:repository_owner_id": "163474992",
                "token.actions.githubusercontent.com:ref": "refs/heads/main",
            },
        )
        serialized = json.dumps(policy, sort_keys=True)
        self.assertNotIn('"Principal": "*"', serialized)
        self.assertNotIn('refs/heads/*', serialized)

    def test_listing_policy_is_prefix_and_maxkeys_fail_closed(self) -> None:
        policy = self.load(ARCHIVE / "IAM_POLICY_TEMPLATE.json")
        by_sid = {row["Sid"]: row for row in policy["Statement"]}
        node = by_sid["AllowNodeDataExactPrefixListing"]
        archive = by_sid["AllowArchiveExactPrefixListing"]
        self.assertEqual(node["Action"], "s3:ListBucket")
        self.assertEqual(archive["Action"], "s3:ListBucket")
        self.assertEqual(node["Resource"], "arn:aws:s3:::hl-mainnet-node-data")
        self.assertEqual(archive["Resource"], "arn:aws:s3:::hyperliquid-archive")
        self.assertEqual(node["Condition"]["NumericLessThanEquals"]["s3:max-keys"], "1000")
        self.assertEqual(archive["Condition"]["NumericLessThanEquals"]["s3:max-keys"], "1000")
        self.assertEqual(by_sid["DenyNodeDataPrefixEscape"]["Effect"], "Deny")
        self.assertEqual(by_sid["DenyArchivePrefixEscape"]["Effect"], "Deny")
        self.assertEqual(by_sid["DenyOversizeListings"]["Condition"]["NumericGreaterThan"]["s3:max-keys"], "1000")

    def test_no_object_allow_exists(self) -> None:
        policy = self.load(ARCHIVE / "IAM_POLICY_TEMPLATE.json")
        allowed_actions: set[str] = set()
        denied_actions: set[str] = set()
        for statement in policy["Statement"]:
            actions = statement["Action"] if isinstance(statement["Action"], list) else [statement["Action"]]
            if statement["Effect"] == "Allow":
                allowed_actions.update(actions)
            elif statement["Effect"] == "Deny":
                denied_actions.update(actions)
        self.assertEqual(allowed_actions, {"s3:ListBucket"})
        for action in ("s3:GetObject", "s3:GetObjectVersion", "s3:GetObjectAttributes", "s3:PutObject", "s3:DeleteObject"):
            self.assertIn(action, denied_actions)
        self.assertNotIn("s3:SelectObjectContent", allowed_actions | denied_actions)

    def test_only_reviewed_archive_workflows_may_request_oidc(self) -> None:
        workflows = ROOT / ".github/workflows"
        identity = workflows / "hyperliquid-aws-oidc-identity-check.yml"
        r0 = workflows / "hyperliquid-archive-metadata-canary-r0.yml"
        region = workflows / "hyperliquid-archive-region-probe-r1.yml"
        r2 = workflows / "hyperliquid-archive-nodedata-canary-r2.yml"
        r3 = workflows / "hyperliquid-archive-hourly-metadata-inventory-r3.yml"
        r4 = workflows / "hyperliquid-archive-hourly-body-schema-pilot-r4.yml"
        r4_preflight = workflows / "hyperliquid-archive-hourly-body-schema-role-preflight-r4.yml"
        r5 = workflows / "hyperliquid-archive-legacy-format-fingerprint-r5.yml"
        r6a = workflows / "hyperliquid-archive-legacy-user-key-lexical-r6a.yml"
        r6a_successor = workflows / "hyperliquid-archive-legacy-user-key-lexical-r6a-successor.yml"
        r7 = workflows / "hyperliquid-archive-wallet-index-r7.yml"
        r8a = workflows / "hyperliquid-archive-modern-wallet-index-r8a.yml"
        r9 = workflows / "hyperliquid-archive-modern-wallet-feature-r9.yml"
        allowed = {identity, r0, region, r2, r3, r4, r4_preflight, r5, r6a, r6a_successor, r7, r8a, r9}
        for path in allowed:
            self.assertTrue(path.is_file(), path)
        self.assertFalse((workflows / "hyperliquid-archive-metadata-canary.yml").exists())
        other = "\n".join(path.read_text(encoding="utf-8") for path in sorted(workflows.glob("*.yml")) if path not in allowed)
        self.assertNotIn("id-token: write", other)
        self.assertNotIn("aws-actions/configure-aws-credentials", other)
        for path in allowed:
            text = path.read_text(encoding="utf-8")
            self.assertIn("id-token: write", text)
            self.assertIn("aws-actions/configure-aws-credentials", text)


if __name__ == "__main__":
    unittest.main()
