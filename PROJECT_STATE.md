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
| public-probe result | `PUBLIC_PROBE_PASS` |
| canonical public-probe run / job / artifact | `31200124642` / `92937868268` / `9002459643` |
| archive inventory study | `HL-ARCHIVE-INVENTORY-001` |
| archive inventory status | `PREREGISTERED_METADATA_ONLY_NO_EXECUTION` |
| AWS account ID | `630956766927` |
| GitHub OIDC federation | `PROVEN_BY_CANONICAL_STS_RUN` |
| canonical STS run / job / artifact | `31250176507` / `93085194965` / `9019744292` |
| STS identity status | `ATTESTED_STS_IDENTITY_MATCH` |
| AWS identity bound | `true` |
| persistent S3 inline policy | `USER_CONFIRMED_NOT_API_VERIFIED` |
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

The public probe and AWS OIDC identity evidence remain immutable and attested. No historical archive object has been listed or downloaded. The successful STS check proves GitHub-to-AWS federation and role identity but not the persistent S3 inline policy document.

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
5. Object-body access, market-data ingestion, wallet P&L, clustering and all trading stages remain separately gated.

No S3 or Requester Pays operation is currently authorized.
