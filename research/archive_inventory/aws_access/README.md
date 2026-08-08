# AWS OIDC access boundary

This directory freezes the proposed AWS identity boundary for `HL-ARCHIVE-INVENTORY-001`.

It does not prove that the AWS role exists and it does not authorize any AWS network call.

## Bound identity

- AWS account: `630956766927`
- GitHub repository: `Mathisve1/onchain-wallet-intelligence-lab`
- GitHub repository ID: `1326362646`
- repository owner ID: `163474992`
- only ref: `refs/heads/main`
- OIDC audience: `sts.amazonaws.com`
- exact subject: `repo:Mathisve1/onchain-wallet-intelligence-lab:ref:refs/heads/main`
- expected role: `onchain-wallet-intelligence-hl-archive-metadata-canary`

The OIDC provider is user-confirmed as created in AWS but is not independently queryable from this repository or ChatGPT session.

## Security properties

The trust policy permits only `sts:AssumeRoleWithWebIdentity` from the exact GitHub OIDC provider and exact canonical-main identity.

The S3 permission policy permits only `s3:ListBucket` for the seven preregistered Hyperliquid prefixes, requires `s3:max-keys <= 1000`, explicitly denies prefix escape, version listing, account-wide bucket enumeration, object-body reads and mutations.

## Still forbidden

No workflow in this phase may request an OIDC token or assume the role. No AWS SDK/network adapter is added. No `ListObjectsV2`, Requester Pays request, object download, market-data ingestion or trading authorization is opened.

After this design is canonical, the human must create the exact role in AWS. A separate reviewed identity-only verification may then prove that GitHub OIDC can assume the role. That verification must not call S3. Pricing and human budget approval remain later gates.
