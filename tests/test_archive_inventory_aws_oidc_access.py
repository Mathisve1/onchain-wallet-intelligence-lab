from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCESS = ROOT / "research/archive_inventory/aws_access"
ARCHIVE = ROOT / "research/archive_inventory"


class ArchiveAwsOidcAccessTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_identity_binding_is_exact_and_nonexecuting(self) -> None:
        binding = self.load(ACCESS / "AWS_IDENTITY_BINDING.json")
        self.assertEqual(binding["aws_account_id"], "630956766927")
        self.assertEqual(
            binding["oidc_provider_arn"],
            "arn:aws:iam::630956766927:oidc-provider/token.actions.githubusercontent.com",
        )
        self.assertEqual(binding["github_repository"], "Mathisve1/onchain-wallet-intelligence-lab")
        self.assertEqual(binding["github_repository_id"], "1326362646")
        self.assertEqual(binding["github_repository_owner_id"], "163474992")
        self.assertEqual(binding["github_ref"], "refs/heads/main")
        self.assertEqual(
            binding["github_subject"],
            "repo:Mathisve1/onchain-wallet-intelligence-lab:ref:refs/heads/main",
        )
        self.assertEqual(binding["planned_workflow_session_duration_seconds"], 900)
        self.assertEqual(binding["role_max_session_duration_seconds"], 3600)
        self.assertFalse(binding["network_identity_check_authorized"])
        self.assertFalse(binding["requester_pays_authorized"])
        self.assertFalse(binding["list_objects_authorized"])
        self.assertFalse(binding["paid_request_authorized"])
        self.assertFalse(binding["get_object_authorized"])
        self.assertFalse(binding["object_body_download_authorized"])
        self.assertFalse(binding["market_data_ingested"])
        self.assertIsNone(binding["empirical_result"])
        self.assertTrue(all(value is False for value in binding["authorizations"].values()))

    def test_trust_policy_is_exact_main_only(self) -> None:
        policy = self.load(ACCESS / "OIDC_TRUST_POLICY.json")
        self.assertEqual(policy["Version"], "2012-10-17")
        self.assertEqual(len(policy["Statement"]), 1)
        statement = policy["Statement"][0]
        self.assertEqual(statement["Effect"], "Allow")
        self.assertEqual(statement["Action"], "sts:AssumeRoleWithWebIdentity")
        self.assertEqual(
            statement["Principal"]["Federated"],
            "arn:aws:iam::630956766927:oidc-provider/token.actions.githubusercontent.com",
        )
        self.assertEqual(
            statement["Condition"]["StringEquals"],
            {
                "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                "token.actions.githubusercontent.com:sub": "repo:Mathisve1/onchain-wallet-intelligence-lab:ref:refs/heads/main",
                "token.actions.githubusercontent.com:repository_id": "1326362646",
                "token.actions.githubusercontent.com:repository_owner_id": "163474992",
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
        self.assertEqual(
            set(node["Condition"]["StringLike"]["s3:prefix"]),
            {
                "node_fills_by_block/*",
                "node_fills/*",
                "node_trades/*",
                "explorer_blocks/*",
                "replica_cmds/*",
            },
        )
        self.assertEqual(
            set(archive["Condition"]["StringLike"]["s3:prefix"]),
            {"market_data/*", "asset_ctxs/*"},
        )
        self.assertEqual(by_sid["DenyNodeDataPrefixEscape"]["Effect"], "Deny")
        self.assertEqual(by_sid["DenyArchivePrefixEscape"]["Effect"], "Deny")
        self.assertEqual(
            by_sid["DenyOversizeListings"]["Condition"]["NumericGreaterThan"]["s3:max-keys"],
            "1000",
        )
        self.assertEqual(by_sid["DenyVersionListings"]["Action"], "s3:ListBucketVersions")
        self.assertEqual(by_sid["DenyAccountWideBucketEnumeration"]["Action"], "s3:ListAllMyBuckets")

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
        for action in (
            "s3:GetObject",
            "s3:GetObjectVersion",
            "s3:GetObjectAttributes",
            "s3:SelectObjectContent",
            "s3:PutObject",
            "s3:DeleteObject",
        ):
            self.assertIn(action, denied_actions)

    def test_no_oidc_or_aws_network_workflow_exists_in_design_phase(self) -> None:
        workflows = ROOT / ".github/workflows"
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(workflows.glob("*.yml"))
        )
        self.assertNotIn("id-token: write", combined)
        self.assertNotIn("aws-actions/configure-aws-credentials", combined)
        self.assertFalse((workflows / "hyperliquid-archive-metadata-canary.yml").exists())
        self.assertFalse((workflows / "hyperliquid-aws-oidc-identity-check.yml").exists())


if __name__ == "__main__":
    unittest.main()
