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
- expected immutable subject: `repo:Mathisve1@163474992/onchain-wallet-intelligence-lab@1326362646:ref:refs/heads/main`
- expected role: `onchain-wallet-intelligence-hl-archive-metadata-canary`

GitHub documents that repositories created after 2026-07-15 use immutable default OIDC subjects containing both owner and repository IDs. This repository was created in August 2026, so the access design uses that format rather than the legacy name-only subject. The exact emitted subject remains unobserved until the separately reviewed STS-only identity verification runs; no assumption of successful role federation is made here.

The OIDC provider is user-confirmed as created in AWS but is not independently queryable from this repository or ChatGPT session.

## Security properties

The trust policy permits only `sts:AssumeRoleWithWebIdentity` from the exact GitHub OIDC provider and exact canonical-main identity. It independently binds audience, immutable subject, repository ID, repository-owner ID and ref.

The S3 permission policy permits only `s3:ListBucket` for the seven preregistered Hyperliquid prefixes, requires `s3:max-keys <= 1000`, explicitly denies prefix escape, version listing, account-wide bucket enumeration, object-body reads and mutations.

## Still forbidden

No workflow in this phase may request an OIDC token or assume the role. No AWS SDK/network adapter is added. No `ListObjectsV2`, Requester Pays request, object download, market-data ingestion or trading authorization is opened.

After this design is canonical, the human must create the exact role in AWS. A separate reviewed identity-only verification may then prove that GitHub OIDC can assume the role. That verification must not call S3. Pricing and human budget approval remain later gates.
