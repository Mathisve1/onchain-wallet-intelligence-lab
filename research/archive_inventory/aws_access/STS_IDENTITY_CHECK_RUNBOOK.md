# STS-only GitHub OIDC identity check

Check ID: `HL-AWS-OIDC-IDENTITY-001`.

This gate verifies only that canonical GitHub `main` can assume the exact AWS role through OIDC and that AWS STS returns the expected account and assumed-role ARN.

## Hard boundary

The workflow is manual-only and requires the exact current canonical `main` SHA as input. Before requesting an OIDC token it re-runs repository tests and governance validation.

The assumed session carries an inline session policy with an explicit `Deny` on `s3:*` for `Resource: *`. Therefore the identity-check session cannot use the role's future S3 listing permission.

Only one explicit AWS CLI API operation is permitted after role assumption:

```text
aws sts get-caller-identity
```

No S3, Requester Pays, bucket listing, object metadata, object body, market-data or trading operation is part of this gate.

## Expected identity

```text
account = 630956766927
role = onchain-wallet-intelligence-hl-archive-metadata-canary
session = HLArchiveOidcIdentityCheck
assumed-role ARN = arn:aws:sts::630956766927:assumed-role/onchain-wallet-intelligence-hl-archive-metadata-canary/HLArchiveOidcIdentityCheck
```

## Evidence minimization

Retain only the exact GitHub run/commit identity, expected and observed AWS account, expected and observed assumed-role ARN, terminal validation status, and explicit assertions that S3 and Requester Pays were not used. Do not retain the OIDC token, AWS access key, secret access key, session token or raw STS `UserId`.

## Pass condition

`STS_IDENTITY_MATCH` requires all of the following:

- dispatch ref is `refs/heads/main`;
- dispatch SHA, reviewed SHA and checked-out SHA are identical;
- OIDC role assumption succeeds;
- AWS account is exactly `630956766927`;
- assumed-role ARN matches the exact expected role/session ARN;
- the workflow contains no S3/API body operation;
- all archive inventory market/trading gates remain closed.

A failure is an identity/configuration result only. It does not alter the public probe result and does not authorize a fallback to static AWS credentials.
