# Project State

Verified: 2026-08-07 against canonical public-probe evidence commit `cf5585c45fc8f1ac5f79df6e210cf4d37a591452`.

## Current status

| Dimension | State |
|---|---|
| program | `ONCHAIN-WALLET-INTELLIGENCE` |
| current study | `WALLET-COPYABILITY-STUDY-001` |
| research status | `REQUIRES_FURTHER_TESTING` |
| lifecycle stage | `PRE_ARCHIVE_INVENTORY` |
| experiment status | `PUBLIC_TECHNICAL_PROBE_ATTESTED_ARCHIVE_ACCESS_RESTRICTED` |
| archive inventory study | `HL-ARCHIVE-INVENTORY-001` |
| archive inventory status | `PREREGISTERED_METADATA_ONLY_NO_EXECUTION` |
| public-probe implementation | `INSTALLED_ON_CANONICAL_MAIN` |
| canonical reviewed commit | `c11046bf288687c6945fe9b8f17141204d24aae6` |
| canonical workflow run / job | `31200124642` / `92937868268` |
| canonical artifact | `9002459643` |
| public-probe result | `PUBLIC_PROBE_PASS` |
| archive access result | `ROUTES_CONFIRMED_ACCESS_RESTRICTED` |
| AWS identity bound | `false` |
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

The canonical public probe was manually dispatched from `refs/heads/main` and proved exact identity before network access. It ended `PUBLIC_PROBE_PASS` with 16/16 registered probes passing and classified the official S3 archive routes as `ROUTES_CONFIRMED_ACCESS_RESTRICTED`.

The public-probe evidence remains immutable under `research/wallet_copyability/probe_r1/evidence/`.

## Archive inventory preregistration

`HL-ARCHIVE-INVENTORY-001` is preregistered as a metadata/access/cost-only successor. Its deterministic code can build and validate exact `ListObjectsV2` request plans and enforce request/page/entry/byte/runtime caps, but it contains no network-capable AWS SDK/client in this phase.

The proposed future canary is not authorized:

```text
network_execution_authorized = false
aws_identity_bound = false
requester_pays_authorized = false
list_objects_authorized = false
get_object_authorized = false
head_object_authorized = false
range_get_authorized = false
object_body_download_authorized = false
decompression_authorized = false
paid_request_authorized = false
maximum_one_time_budget_eur = null
maximum_monthly_budget_eur = 0
market_data_ingested = false
empirical_result = null
```

## Exact next gate

1. Review and merge the `HL-ARCHIVE-INVENTORY-001` metadata-only preregistration/implementation.
2. Refresh official AWS pricing and resolve the requesting AWS billing identity without exposing credentials.
3. Review a listing-only IAM boundary and bind an exact canonical commit.
4. Obtain a separate explicit human one-time euro budget/Requester Pays approval.
5. Only then implement/enable a network adapter and run a bounded metadata canary.

No paid S3 call, object-body retrieval, market-data ingestion, wallet performance calculation, entity clustering or trading stage is currently open.

Entity-resolution research remains downstream of demonstrated individual-wallet copyability. No probabilistic wallet merge may create false consensus in the first study.
