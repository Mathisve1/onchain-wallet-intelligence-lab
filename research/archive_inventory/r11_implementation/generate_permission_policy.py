from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SELECTION = ROOT / "research/archive_inventory/r11/R11_72H_SELECTION.json"
OUTPUT = ROOT / "research/archive_inventory/r11_implementation/R11_PERMISSION_POLICY.json"
BUCKET = "hl-mainnet-node-data"


def build_policy() -> dict:
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    targets = selection["exact_targets"]
    assert len(targets) == 72
    resources = [f"arn:aws:s3:::{BUCKET}/{row['key']}" for row in targets]
    assert len(resources) == len(set(resources)) == 72
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowExactSeventyTwoR11ObjectsOnly",
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


def main() -> int:
    policy = build_policy()
    compact = json.dumps(policy, separators=(",", ":"), ensure_ascii=True)
    if len(compact) > 10240:
        raise SystemExit(f"R11 inline policy non-whitespace character budget exceeded: {len(compact)}")
    OUTPUT.write_text(json.dumps(policy, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"R11_PERMISSION_POLICY_RESOURCES:72")
    print(f"R11_PERMISSION_POLICY_COMPACT_CHARS:{len(compact)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
