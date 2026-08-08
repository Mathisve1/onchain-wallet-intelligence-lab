# Exact AWS role creation runbook

This runbook is a human AWS-console action. It must not be automated with root/access-key credentials.

## Preconditions

- AWS account ID is `630956766927`.
- Root MFA and a valid payment method were user-confirmed.
- OIDC provider `token.actions.githubusercontent.com` with audience `sts.amazonaws.com` was user-confirmed as created.
- `HL-ARCHIVE-INVENTORY-001` remains non-executing.

## Create exactly one role

Role name:

```text
onchain-wallet-intelligence-hl-archive-metadata-canary
```

Expected ARN:

```text
arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-metadata-canary
```

Set the role maximum session duration to the AWS minimum role maximum of 1 hour. A later GitHub workflow, if separately approved, will request only a 900-second web-identity session.

## Trust policy

After creating/selecting the Web Identity role, replace its trust relationship with the byte-equivalent JSON in:

```text
research/archive_inventory/aws_access/OIDC_TRUST_POLICY.json
```

Do not broaden the provider, account, audience, repository, repository ID, owner ID, subject or branch.

## Permission policy

Attach exactly one customer inline policy using:

```text
research/archive_inventory/IAM_POLICY_TEMPLATE.json
```

Suggested inline policy name:

```text
HLArchiveMetadataCanaryListOnly
```

Do not attach AWS managed S3 policies such as `AmazonS3ReadOnlyAccess` or `AmazonS3FullAccess`.

## Do not create

- IAM users for this workflow;
- AWS access keys or secret keys;
- GitHub AWS credential secrets;
- S3 object-read permission;
- write/delete permission;
- extra bucket listing permissions.

## Stop after creation

After the role is created and both policies are visibly attached, stop. Do not test S3 and do not run Requester Pays.

The only information needed back in the research workflow is confirmation that the exact role exists. The role ARN is an identifier, not a secret. The next repository gate will be a separate STS identity-only verification that does not touch S3.
