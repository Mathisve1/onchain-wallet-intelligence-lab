# Decision Log

| ID | Date | Status | Decision |
|---|---|---|---|
| DEC-001 | 2026-08-06 | accepted | Use a dedicated repository independent from `quant-trading-lab`. |
| DEC-002 | 2026-08-06 | accepted | `WALLET-COPYABILITY-STUDY-001` is pre-data and has no market result. |
| DEC-003 | 2026-08-06 | accepted | Select wallets point in time; future performance and future cluster links are forbidden. |
| DEC-004 | 2026-08-06 | accepted | Report source-wallet and follower performance separately after all follower costs. |
| DEC-005 | 2026-08-06 | accepted | The first study uses only confirmed master/subaccount, role and vault/service relationships. |
| DEC-006 | 2026-08-06 | accepted | Probabilistic entity clustering is a successor gate, not a prerequisite for the first copyability test. |
| DEC-007 | 2026-08-06 | accepted | The technical probe is public, bounded, read-only and cannot call an order/action endpoint. |
| DEC-008 | 2026-08-06 | accepted | No integration, paper, shadow, live, leverage or capital-allocation authorization exists. |
| DEC-009 | 2026-08-06 | accepted | AI may summarize and challenge; deterministic code is canonical for P&L, ledgers, clusters and risk. |
| DEC-010 | 2026-08-07 | accepted | `HL-ARCHIVE-INVENTORY-001` is metadata/access/cost-only; internal object schemas require a separate body-access pilot. |
| DEC-011 | 2026-08-07 | accepted | Inventory exactly seven documented archive prefix families: modern/legacy fills, legacy trades, explorer blocks, replica commands, L2 market data and asset contexts. |
| DEC-012 | 2026-08-07 | accepted | No AWS identity, Requester Pays charge, LIST execution, object GET, decompression or budget is authorized by the archive-inventory preregistration. |
| DEC-013 | 2026-08-07 | accepted | Future metadata listing must fail closed on exact bucket/prefix allowlists, 300 total LIST attempts, 40 pages per family, 250k entries, 256 MiB responses, 15 minutes and one retry. |
| DEC-014 | 2026-08-08 | accepted | Bind the proposed archive metadata identity to AWS account `630956766927` and expected role `onchain-wallet-intelligence-hl-archive-metadata-canary`; account/provider setup is human-attested until independently verified. |
| DEC-015 | 2026-08-08 | accepted | Because this August-2026 repository falls under GitHub's post-2026-07-15 immutable OIDC subject default, AWS trust must require `repo:Mathisve1@163474992/onchain-wallet-intelligence-lab@1326362646:ref:refs/heads/main`, plus audience `sts.amazonaws.com`, repository ID `1326362646`, repository-owner ID `163474992` and ref `refs/heads/main`; no branch/repository wildcard is permitted. The emitted subject remains unproven until the STS-only verification. |
| DEC-016 | 2026-08-08 | accepted | The metadata role may allow only `s3:ListBucket` for the seven frozen prefixes with `s3:max-keys <= 1000` and explicit denies for prefix escape, version listing, account-wide bucket enumeration, object-body reads and mutation. No OIDC/AWS network workflow is authorized until the role is created and a separate identity-only verification gate is reviewed. |
| DEC-017 | 2026-08-08 | accepted | Record the exact role, reviewed trust policy and inline policy `HLArchiveMetadataCanaryListOnly` as user-confirmed applied but not independently API-verified. No static AWS credential fallback is allowed. |
| DEC-018 | 2026-08-08 | accepted | Authorize only `HL-AWS-OIDC-IDENTITY-001` as a manual exact-main-SHA identity verification. The assumed 900-second session must carry an explicit session-level `Deny s3:*`; the only explicit AWS CLI API call is one `aws sts get-caller-identity`. Requester Pays, S3 listing/body access, market-data ingestion and all trading authorizations remain closed. |
