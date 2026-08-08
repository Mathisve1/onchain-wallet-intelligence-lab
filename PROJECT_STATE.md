# Project State

Verified: 2026-08-08 against canonical `main` commit `549e70dedc0eefb9336a9fcd86fc94142904ed3a`, canonical public-probe evidence, and attested AWS OIDC identity run `31250176507`.

## Current status

| Dimension | State |
|---|---|
| program | `ONCHAIN-WALLET-INTELLIGENCE` |
| current study | `WALLET-COPYABILITY-STUDY-001` |
| research status | `REQUIRES_FURTHER_TESTING` |
| lifecycle stage | `PRE_ARCHIVE_INVENTORY` |
| experiment status | `PUBLIC_TECHNICAL_PROBE_ATTESTED_ARCHIVE_ACCESS_RESTRICTED` |
| public-probe implementation | `INSTALLED_ON_CANONICAL_MAIN` |
| public-probe implementation commit | `33683532ca3e6cf7512a728157791d3bfef1375f` |
| canonical public-probe reviewed commit | `c11046bf288687c6945fe9b8f17141204d24aae6` |
| canonical public-probe workflow run / job | `31200124642` / `92937868268` |
| canonical public-probe artifact | `9002459643` |
| public-probe result | `PUBLIC_PROBE_PASS` |
| archive access result | `ROUTES_CONFIRMED_ACCESS_RESTRICTED` |
| archive inventory study | `HL-ARCHIVE-INVENTORY-001` |
| archive inventory status | `PREREGISTERED_METADATA_ONLY_NO_EXECUTION` |
| archive preregistration commit | `0e8a678644c29548a38ebfa1c0af91d4a9a92c09` |
| AWS account ID | `630956766927` |
| GitHub OIDC provider/federation | `PROVEN_BY_CANONICAL_STS_RUN` |
| expected GitHub OIDC subject | `repo:Mathisve1@163474992/onchain-wallet-intelligence-lab@1326362646:ref:refs/heads/main` |
| OIDC token subject directly observed | `false` |
| expected AWS role | `onchain-wallet-intelligence-hl-archive-metadata-canary` |
| expected role ARN | `arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-metadata-canary` |
| STS identity check | `HL-AWS-OIDC-IDENTITY-001` |
| canonical STS run / job | `31250176507` / `93085194965` |
| canonical STS artifact | `9019744292` |
| STS identity check status | `ATTESTED_STS_IDENTITY_MATCH` |
| AWS identity bound | `true` |
| persistent S3 inline policy | `USER_CONFIRMED_NOT_API_VERIFIED` |
| OIDC identity check authorized | `true` |
| exact bucket Regions | `UNRESOLVED_PRE_S3` |
| conservative pricing freeze | `FROZEN_CONSERVATIVE_R0_PRE_APPROVAL` |
| R0 canary | `HL-ARCHIVE-METADATA-CANARY-R0-001` |
| R0 status | `PREREGISTERED_MICRO_CANARY_NOT_AUTHORIZED` |
| proposed one-time budget | `EUR 1.00` |
| authorized one-time budget | `null` |
| requester-pays authorized | `false` |
| ListObjectsV2 authorized | `false` |
| GetObject authorized | `false` |
| object-body download authorized | `false` |
| empirical result | `null` |
| integration authorized | `false` |
| paper authorized | `false` |
| shadow authorized | `false` |
| live authorized | `false` |
| leverage authorized | `false` |
| capital allocation authorized | `false` |

## Canonical technical evidence

The canonical public probe remains immutable and attested. `HL-ARCHIVE-INVENTORY-001` remains metadata/access/cost-only research. No historical archive object has been listed or downloaded.

The AWS OIDC identity gate is independently attested. Canonical run `31250176507` was dispatched from `refs/heads/main` against exact commit `f34786eafd3689b575bdd3d2ada932b8ce204a61`. The checked-out commit, dispatch SHA and reviewed commit matched. AWS returned account `630956766927` and the exact expected assumed-role ARN.

The identity-check session carried an inline `Deny s3:*` policy and made exactly one explicit AWS identity call, `aws sts get-caller-identity`. No S3 request and no Requester Pays request occurred. The downloaded artifact ZIP SHA-256 independently matched GitHub's provider digest `3ebb71763783135c2c21bb7c0f8a801e0d873208e5a8b9afff473b208a2dc607`.

This evidence proves GitHub-to-AWS federation and the role identity. It does not independently verify the persistent inline S3 permission policy; that remains user-confirmed until a later separately approved metadata canary exercises only the frozen listing boundary.

## R0 pricing freeze

Current official AWS documentation states that S3 LIST requests are billed at the S3 Standard PUT/COPY/POST request rate; an official AWS current cost reference uses USD 0.005 per 1,000 PUT/COPY/POST/LIST requests. Requester Pays charges the authenticated requester for successful eligible request and data-transfer costs. `ListObjectsV2` supports `RequestPayer=requester` and returns at most 1,000 keys.

The Hyperliquid bucket Regions remain deliberately unknown because discovering them via S3 would cross the current no-S3 gate. Therefore `HL-ARCHIVE-METADATA-CANARY-R0-001` uses deliberately conservative stress prices instead of assuming a favorable Region or free transfer:

```text
stress_list_rate_usd_per_1000 = 0.05
stress_transfer_rate_usd_per_gb = 0.50
maximum_list_requests = 7
maximum_keys_per_request = 25
maximum_total_entries = 175
maximum_total_response_bytes = 8388608
maximum_runtime_seconds = 180
maximum_retries_per_request = 0
pagination_authorized = false
modeled_stress_total_usd = 0.004544304
proposed_maximum_one_time_budget_eur = 1.00
```

The EUR 1.00 value is a proposal only. No FX assumption, free-transfer allowance, credit or discount is required for the stress model.

## Hard boundary

```text
aws_identity_bound = true
requester_pays_authorized = false
list_objects_authorized = false
paid_request_authorized = false
get_object_authorized = false
head_object_authorized = false
range_get_authorized = false
object_body_download_authorized = false
decompression_authorized = false
maximum_one_time_budget_eur = null
maximum_monthly_budget_eur = 0
market_data_ingested = false
empirical_result = null
```

## Exact next gate

1. Review and merge the conservative R0 pricing/budget design.
2. Obtain separate explicit human approval binding the exact resulting canonical `main` SHA and a EUR 1.00 one-time ceiling.
3. Only after that approval may a network-capable R0 implementation be created. R0 may make exactly seven first-page `ListObjectsV2` calls with `RequestPayer=requester`, no pagination and no retries.
4. Attest the R0 result and only then decide whether a larger paginated archive inventory deserves a separate budget and release.
5. Object-body access, market-data ingestion, wallet P&L, clustering and all trading stages remain downstream and separately gated.

No S3 call, Requester Pays request, object-body retrieval, market-data ingestion, wallet performance calculation, entity clustering or trading stage is currently open.

Entity-resolution research remains downstream of demonstrated individual-wallet copyability. No probabilistic wallet merge may create false consensus in the first study.
