# R11 dedicated-role creation runbook

This is an operator gate. It does **not** authorize the 72-object R11 data execution. Do not run any S3 command during this step.

## Frozen identity

- AWS account: `630956766927`
- role name: `onchain-wallet-intelligence-hl-archive-scaling-r11`
- expected role ARN: `arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-scaling-r11`
- trust policy: `research/archive_inventory/r11_implementation/R11_OIDC_TRUST_POLICY.json`
- inline permission policy: `research/archive_inventory/r11_implementation/R11_PERMISSION_POLICY.json`
- inline policy name: `HLArchiveR11Exact72Only`
- role `MaxSessionDuration`: `7200` seconds
- future workflow assumed-role session duration: `7200` seconds

The persistent permission policy contains exactly the 72 preregistered object ARNs once in its `Allow` statement. It does not use wildcard `GetObject` resources. Outside those exact objects, `GetObject` has no allow. Other S3 reads and mutations are explicitly denied. The future workflow session policy may use the three approved date-prefix ARNs only because session policies intersect with this exact persistent allowlist.

If the role already exists, stop and inspect it. Do not overwrite, widen or reuse another role.

## Operator sequence

Run only after the R11 implementation PR is canonical on `main`:

```bash
aws iam get-role \
  --role-name onchain-wallet-intelligence-hl-archive-scaling-r11
```

If and only if the role does not exist:

```bash
aws iam create-role \
  --role-name onchain-wallet-intelligence-hl-archive-scaling-r11 \
  --assume-role-policy-document file://research/archive_inventory/r11_implementation/R11_OIDC_TRUST_POLICY.json \
  --max-session-duration 7200
```

Attach exactly one inline policy from the canonical file:

```bash
aws iam put-role-policy \
  --role-name onchain-wallet-intelligence-hl-archive-scaling-r11 \
  --policy-name HLArchiveR11Exact72Only \
  --policy-document file://research/archive_inventory/r11_implementation/R11_PERMISSION_POLICY.json
```

Then inspect the installed configuration:

```bash
aws iam get-role \
  --role-name onchain-wallet-intelligence-hl-archive-scaling-r11

aws iam get-role-policy \
  --role-name onchain-wallet-intelligence-hl-archive-scaling-r11 \
  --policy-name HLArchiveR11Exact72Only

aws iam list-attached-role-policies \
  --role-name onchain-wallet-intelligence-hl-archive-scaling-r11

aws iam list-role-policies \
  --role-name onchain-wallet-intelligence-hl-archive-scaling-r11
```

Expected state: no managed policies, exactly one inline policy named `HLArchiveR11Exact72Only`, exact canonical trust policy, exact canonical permission policy, and `MaxSessionDuration=7200`.

Do **not** run `aws s3`, `aws s3api`, the R11 preflight workflow or the R11 data workflow during this operator step.

## Required attestation

Complete `R11_OPERATOR_ATTESTATION_TEMPLATE.txt` only after verifying the installed role against canonical `main`. The attestation must bind the canonical implementation merge commit and SHA-256 of both policy files, prove exactly 72 persistent GetObject resources, confirm no extra managed/inline policies, confirm the R10 role was not modified, and confirm zero S3 requests/object bytes during this operator step.

Only after that attestation is reviewed and merged may a separate S3-denied STS-only preflight be installed and separately released. A successful STS preflight still does not authorize the 72 object downloads.
