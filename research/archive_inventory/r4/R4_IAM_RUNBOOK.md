# R4 dedicated AWS role runbook

Status: implementation design only. Do not create or use the role from this document until the R4 implementation is canonical and the later release/activation gate explicitly calls for it.

## Why a dedicated role is required

The existing metadata-canary role is intentionally list-only. Its canonical persistent policy explicitly denies `s3:GetObject` on object resources. An inline session policy cannot override an explicit IAM deny, so R4 must not weaken or reuse that metadata role.

R4 instead uses a temporary-purpose role named:

`onchain-wallet-intelligence-hl-archive-body-schema-r4`

Expected ARN:

`arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-body-schema-r4`

## Trust policy

Apply **exactly** `R4_OIDC_TRUST_POLICY_TEMPLATE.json` to the dedicated role. It binds assumption to:

- AWS account `630956766927` and the already configured GitHub OIDC provider;
- immutable GitHub subject for repository ID `1326362646` and owner ID `163474992`;
- `refs/heads/main` only;
- repository ID and repository-owner ID again as independent claims;
- workflow name `Hyperliquid Archive Hourly Body Schema Pilot R4` only;
- audience `sts.amazonaws.com`.

Do not replace exact values with wildcards.

## Permission policy

Attach **exactly** `R4_IAM_POLICY_TEMPLATE.json`. The only allow is `s3:GetObject` on these two ARNs:

1. `arn:aws:s3:::hl-mainnet-node-data/node_fills/hourly/20250727/8.lz4`
2. `arn:aws:s3:::hl-mainnet-node-data/node_fills_by_block/hourly/20250727/8.lz4`

The policy explicitly denies `GetObject` outside those two objects plus other object-read/list/mutation capabilities. Do not add bucket listing, object versions, attributes, restore, write or delete permissions.

## Session duration

- role maximum session duration may remain `3600` seconds;
- the R4 workflow requests `900` seconds only;
- credential action retry is one attempt;
- the collector itself has zero S3 retries and a 180-second research runtime cap.

## Before activation

A later canonical activation must bind the exact implementation commit, approval hash, release and these IAM templates. Until then:

- do not dispatch the R4 body workflow;
- `GetObject`, Requester Pays, object-body download and decompression current authority remain false;
- no object-body evidence exists.

## After the single-use run

Regardless of PASS/COMPLETE/FAIL, the R4 workflow release is consumed by the first canonical dispatch. Do not rerun it. After evidence is secured, remove or disable the dedicated R4 role (or at minimum remove its permission policy) so the temporary object-read capability does not remain available.
