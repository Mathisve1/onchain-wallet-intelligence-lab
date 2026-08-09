# R10 dedicated-role creation runbook

This runbook is an operator gate. It does **not** authorize execution of the R10 archive pilot and it does not permit any S3 request until later STS-preflight, execution-release and activation gates are canonically completed.

## Frozen identity

- AWS account: `630956766927`
- role name: `onchain-wallet-intelligence-hl-archive-multihour-r10`
- expected role ARN: `arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-multihour-r10`
- trust policy source: `research/archive_inventory/r10_implementation/R10_OIDC_TRUST_POLICY.json`
- inline permission policy source: `research/archive_inventory/r10_implementation/R10_PERMISSION_POLICY.json`
- inline policy name: `HLArchivePostBoundaryMultiHourR10ExactSixOnly`
- role maximum session duration target: `900` seconds

Do not edit either JSON policy in the AWS console. If the role already exists, stop and inspect it rather than widening, reusing or overwriting it.

## CLI operator sequence

Run from an authenticated administrative AWS shell only after this implementation is canonical on `main`:

```bash
aws iam get-role \
  --role-name onchain-wallet-intelligence-hl-archive-multihour-r10
```

If and only if AWS reports that the role does not exist, create it from the canonical trust policy file:

```bash
aws iam create-role \
  --role-name onchain-wallet-intelligence-hl-archive-multihour-r10 \
  --assume-role-policy-document file://research/archive_inventory/r10_implementation/R10_OIDC_TRUST_POLICY.json \
  --max-session-duration 900
```

Attach exactly one inline permission policy from the canonical file:

```bash
aws iam put-role-policy \
  --role-name onchain-wallet-intelligence-hl-archive-multihour-r10 \
  --policy-name HLArchivePostBoundaryMultiHourR10ExactSixOnly \
  --policy-document file://research/archive_inventory/r10_implementation/R10_PERMISSION_POLICY.json
```

Then retrieve the configured role and inline policy for operator inspection:

```bash
aws iam get-role \
  --role-name onchain-wallet-intelligence-hl-archive-multihour-r10

aws iam get-role-policy \
  --role-name onchain-wallet-intelligence-hl-archive-multihour-r10 \
  --policy-name HLArchivePostBoundaryMultiHourR10ExactSixOnly
```

Do **not** run `aws s3`, `aws s3api`, or any object request during this operator step. Do not manually trigger either R10 workflow yet.

## Required operator attestation

After creation, compare the installed trust and permission documents with the canonical source files and complete `R10_OPERATOR_ATTESTATION_TEMPLATE.txt`. The attestation must bind:

1. the canonical implementation merge commit;
2. SHA-256 of both canonical policy files;
3. exact role ARN and inline policy name;
4. confirmation that no existing R4 role was changed;
5. confirmation that no S3 request was made;
6. confirmation that no extra managed/inline permission policy was attached for this R10 role.

Only after that attestation is reviewed and merged may a separate STS-only preflight release be prepared. The preflight session policy will explicitly deny all S3 actions and may call only STS identity inspection. A successful preflight still does not authorize the six archive downloads.
