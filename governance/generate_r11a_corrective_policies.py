#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
CORRECTIVE = BASE / "r11a_corrective"
SELECTION = BASE / "r11/R11_72H_SELECTION.json"
TRUST = CORRECTIVE / "R11A_OIDC_TRUST_POLICY.json"
PERMISSION = CORRECTIVE / "R11A_PERMISSION_POLICY.json"
ROLE_DECISION = CORRECTIVE / "R11A_ROLE_DECISION.json"
ROLE_NAME = "onchain-wallet-intelligence-hl-archive-identity-r11a"
ROLE_ARN = f"arn:aws:iam::630956766927:role/{ROLE_NAME}"
WORKFLOW_NAME = "Hyperliquid Archive R11A Identity Boundary Diagnostic"


class GenerationError(ValueError):
    pass


def load(path: Path) -> dict:
    def pairs(rows: list[tuple[str, object]]) -> dict:
        result: dict[str, object] = {}
        for key, value in rows:
            if key in result:
                raise GenerationError(f"duplicate key in {path}: {key}")
            result[key] = value
        return result
    def constant(token: str) -> object:
        raise GenerationError(f"non-finite constant in {path}: {token}")
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise GenerationError(f"{path} root must be object")
    return value


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def expected() -> tuple[dict, dict, dict]:
    selection = load(SELECTION)
    targets = selection.get("exact_targets")
    if not isinstance(targets, list) or len(targets) != 72:
        raise GenerationError("selection must contain exact 72 targets")
    resources: list[str] = []
    for ordinal, row in enumerate(targets):
        if not isinstance(row, dict) or row.get("object_ordinal_zero_based", ordinal) not in (ordinal, None):
            raise GenerationError("selection target order or type drift")
        key = row.get("key")
        if not isinstance(key, str) or not key.startswith("node_fills_by_block/hourly/"):
            raise GenerationError("selection object key drift")
        resources.append(f"arn:aws:s3:::hl-mainnet-node-data/{key}")
    if len(set(resources)) != 72 or any("*" in value for value in resources):
        raise GenerationError("persistent permission resources are not exact unique objects")
    trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowExactR11ACanonicalMainWorkflow",
                "Effect": "Allow",
                "Principal": {
                    "Federated": "arn:aws:iam::630956766927:oidc-provider/token.actions.githubusercontent.com"
                },
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                        "token.actions.githubusercontent.com:sub": "repo:Mathisve1@163474992/onchain-wallet-intelligence-lab@1326362646:ref:refs/heads/main",
                        "token.actions.githubusercontent.com:repository_id": "1326362646",
                        "token.actions.githubusercontent.com:repository_owner_id": "163474992",
                        "token.actions.githubusercontent.com:ref": "refs/heads/main",
                        "token.actions.githubusercontent.com:workflow": WORKFLOW_NAME,
                    }
                },
            }
        ],
    }
    permission = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowExactSeventyTwoR11AObjectsOnly",
                "Effect": "Allow",
                "Action": "s3:GetObject",
                "Resource": resources,
            },
            {
                "Sid": "DenyOtherS3ReadCapabilities",
                "Effect": "Deny",
                "Action": [
                    "s3:GetObjectVersion",
                    "s3:GetObjectAttributes",
                    "s3:SelectObjectContent",
                    "s3:ListBucket",
                    "s3:ListBucketVersions",
                    "s3:ListAllMyBuckets",
                ],
                "Resource": "*",
            },
            {
                "Sid": "DenyS3MutationAndRestore",
                "Effect": "Deny",
                "Action": [
                    "s3:PutObject",
                    "s3:PutObjectAcl",
                    "s3:PutObjectTagging",
                    "s3:DeleteObject",
                    "s3:DeleteObjectVersion",
                    "s3:AbortMultipartUpload",
                    "s3:RestoreObject",
                ],
                "Resource": "*",
            },
        ],
    }
    role_decision = {
        "schema_version": "1.0",
        "decision_id": "R11A-SUCCESSOR-ROLE-DECISION-001",
        "status": "FROZEN_INERT_SUCCESSOR_ROLE_CANDIDATE_NO_IAM_MUTATION",
        "decision": "CREATE_NEW_DEDICATED_R11A_ROLE_ONLY_AFTER_EXACT_OWNER_APPROVAL",
        "successor_role": {
            "role_name": ROLE_NAME,
            "role_arn": ROLE_ARN,
            "workflow_name": WORKFLOW_NAME,
            "maximum_session_duration_seconds": 21600,
            "persistent_get_object_resource_count": 72,
            "persistent_permission_resources_are_exact_selection_objects": True,
            "additional_managed_policies_authorized": False,
            "additional_inline_policies_authorized": False,
        },
        "existing_r11_role_reused": False,
        "existing_r11_role_mutated": False,
        "new_role_created_by_this_decision": False,
        "owner_approval_required": True,
        "separate_sts_only_preflight_required": True,
        "current_authority": {
            "iam_role_creation": False,
            "iam_policy_application": False,
            "aws_oidc": False,
            "sts": False,
            "s3": False,
        },
        "network_or_iam_actions_executed_by_this_decision": 0,
    }
    return trust, permission, role_decision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    trust, permission, role_decision = expected()
    if arguments.write:
        dump(TRUST, trust)
        dump(PERMISSION, permission)
        dump(ROLE_DECISION, role_decision)
    else:
        if load(TRUST) != trust or load(PERMISSION) != permission or load(ROLE_DECISION) != role_decision:
            raise GenerationError("generated successor-role policies or decision drift")
    print("R11A_CORRECTIVE_SUCCESSOR_ROLE_POLICIES_VALID_INERT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
