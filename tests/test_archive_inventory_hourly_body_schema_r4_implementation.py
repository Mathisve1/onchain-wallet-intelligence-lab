from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory/r4"
IMPLEMENTATION = BASE / "R4_IMPLEMENTATION_CONTRACT.json"
TRUST = BASE / "R4_OIDC_TRUST_POLICY_TEMPLATE.json"
PERMISSION = BASE / "R4_IAM_POLICY_TEMPLATE.json"
PARENT = ROOT / "research/archive_inventory/IAM_POLICY_TEMPLATE.json"


class ArchiveHourlyBodySchemaR4ImplementationTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exact_lineage_scope_and_caps(self) -> None:
        impl = self.load(IMPLEMENTATION)
        self.assertEqual(impl["preregistration_commit"], "25a1f621d15cb708a485893025f03b991628aae1")
        self.assertEqual(impl["approval_merge_commit"], "0191350683c6c943d3538c8c51db176cd1d58211")
        self.assertEqual(impl["approval_text_sha256"], "e52399feb7a0d36959089f556dd9f55062eb91d52feaa4c5af680d3c4e557264")
        self.assertEqual([row["key"] for row in impl["selected_objects"]], [
            "node_fills/hourly/20250727/8.lz4",
            "node_fills_by_block/hourly/20250727/8.lz4",
        ])
        self.assertEqual([row["expected_size_bytes"] for row in impl["selected_objects"]], [12726384, 1517603])
        self.assertEqual(impl["maximum_get_object_requests"], 2)
        self.assertEqual(impl["maximum_requests_per_object"], 1)
        self.assertEqual(impl["maximum_total_compressed_bytes"], 14243987)
        self.assertEqual(impl["maximum_total_decompressed_bytes"], 536870912)
        self.assertEqual(impl["maximum_decompressed_bytes_per_object"], 268435456)
        self.assertEqual(impl["maximum_runtime_seconds"], 180)
        self.assertEqual(impl["maximum_retries_per_request"], 0)

    def test_immutable_implementation_snapshot_is_not_a_release(self) -> None:
        impl = self.load(IMPLEMENTATION)
        self.assertEqual(impl["status"], "IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION")
        self.assertEqual(impl["expected_canonical_implementation_commit"], "PENDING_CANONICAL_IMPLEMENTATION_MERGE")
        self.assertTrue(impl["execution_release_required"])
        self.assertFalse(impl["execution_release_present"])
        for name in (
            "execution_authorized", "paid_request_authorized", "requester_pays_authorized",
            "get_object_authorized", "object_body_download_authorized", "decompression_authorized",
        ):
            self.assertFalse(impl[name])
        self.assertEqual(impl["s3_requests_executed"], 0)
        self.assertEqual(impl["compressed_bytes_downloaded"], 0)
        self.assertEqual(impl["decompressed_bytes_processed"], 0)
        self.assertIsNone(impl["empirical_result"])
        self.assertTrue(all(value is False for value in impl["trading_authorizations"].values()))

    def test_current_metadata_role_is_proven_unusable_and_not_weakened(self) -> None:
        impl = self.load(IMPLEMENTATION)
        parent = self.load(PARENT)
        denied = set()
        for statement in parent["Statement"]:
            actions = statement["Action"] if isinstance(statement["Action"], list) else [statement["Action"]]
            if statement["Effect"] == "Deny":
                denied.update(actions)
        self.assertIn("s3:GetObject", denied)
        self.assertFalse(impl["current_metadata_role_usable_for_r4"])
        self.assertTrue(impl["dedicated_r4_role_required"])
        self.assertEqual(impl["expected_dedicated_r4_role_arn"], "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4")
        self.assertFalse(impl["dedicated_r4_role_currently_verified"])

    def test_dedicated_trust_is_exact_repo_main_and_workflow_bound(self) -> None:
        trust = self.load(TRUST)
        row = trust["Statement"][0]
        self.assertEqual(row["Action"], "sts:AssumeRoleWithWebIdentity")
        self.assertEqual(row["Condition"]["StringEquals"], {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
            "token.actions.githubusercontent.com:sub": "repo:Mathisve1@163474992/onchain-wallet-intelligence-lab@1326362646:ref:refs/heads/main",
            "token.actions.githubusercontent.com:repository_id": "1326362646",
            "token.actions.githubusercontent.com:repository_owner_id": "163474992",
            "token.actions.githubusercontent.com:ref": "refs/heads/main",
            "token.actions.githubusercontent.com:workflow": "Hyperliquid Archive Hourly Body Schema Pilot R4",
        })

    def test_dedicated_permission_has_one_allow_on_exact_two_objects(self) -> None:
        policy = self.load(PERMISSION)
        allows = [row for row in policy["Statement"] if row["Effect"] == "Allow"]
        self.assertEqual(len(allows), 1)
        self.assertEqual(allows[0]["Action"], "s3:GetObject")
        self.assertEqual(allows[0]["Resource"], [
            "arn:aws:s3:::hl-mainnet-node-data/node_fills/hourly/20250727/8.lz4",
            "arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/8.lz4",
        ])
        outside = next(row for row in policy["Statement"] if row["Sid"] == "DenyGetObjectOutsideExactTwo")
        self.assertEqual(outside["NotResource"], allows[0]["Resource"])
        serialized = json.dumps(policy)
        self.assertIn("s3:ListBucket", serialized)
        self.assertIn("s3:GetObjectVersion", serialized)
        self.assertIn("s3:PutObject", serialized)

    def test_dedicated_validator_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "governance/validate_r4_implementation.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("R4_IMPLEMENTATION_VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
