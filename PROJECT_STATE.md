# Project State

Verified: 2026-08-08 against canonical `main` commit `f34786eafd3689b575bdd3d2ada932b8ce204a61`, canonical public-probe evidence, and independently verified AWS OIDC identity run `31250176507`.

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

The AWS OIDC identity gate is now independently attested. Canonical run `31250176507` was dispatched from `refs/heads/main` against exact commit `f34786eafd3689b575bdd3d2ada932b8ce204a61`. The checked-out commit, dispatch SHA and reviewed commit matched. AWS returned account `630956766927` and the exact expected assumed-role ARN.

The identity-check session carried an inline `Deny s3:*` policy and made exactly one explicit AWS identity call, `aws sts get-caller-identity`. No S3 request and no Requester Pays request occurred. The downloaded artifact ZIP SHA-256 independently matched GitHub's provider digest `3ebb71763783135c2c21bb7c0f8a801e0d873208e5a8b9afff473b208a2dc607`.

This evidence proves GitHub-to-AWS federation and the role identity. It does not independently verify the persistent inline S3 permission policy; that remains user-confirmed until a later separately approved metadata canary exercises only the frozen listing boundary.

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

1. Freeze the exact applicable AWS S3 Requester Pays/LIST pricing evidence for the target buckets and expected request pattern.
2. Produce a bounded one-time metadata-canary cost model under the existing preregistered request/page/entry/byte/runtime caps.
3. Obtain separate explicit human approval for a one-time euro budget and Requester Pays usage.
4. Only after that approval may a network-capable `ListObjectsV2` canary be implemented/enabled.
5. Object-body access, market-data ingestion, wallet P&L, clustering and all trading stages remain downstream and separately gated.

No S3 call, Requester Pays request, object-body retrieval, market-data ingestion, wallet performance calculation, entity clustering or trading stage is currently open.

Entity-resolution research remains downstream of demonstrated individual-wallet copyability. No probabilistic wallet merge may create false consensus in the first study.
