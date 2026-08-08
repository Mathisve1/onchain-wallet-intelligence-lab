# Project State

Verified: 2026-08-08 against canonical `main` commit `9af4b21863e47fb3bb2997ce77b9940eecf4597f`, canonical public-probe evidence, attested AWS OIDC identity run `31250176507`, and explicit human approval `APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001`.

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
| expected AWS role | `onchain-wallet-intelligence-hl-archive-metadata-canary` |
| STS identity check status | `ATTESTED_STS_IDENTITY_MATCH` |
| canonical STS run / job / artifact | `31250176507` / `93085194965` / `9019744292` |
| AWS identity bound | `true` |
| persistent S3 inline policy | `USER_CONFIRMED_NOT_API_VERIFIED` |
| exact bucket Regions | `UNRESOLVED_PRE_S3` |
| conservative pricing freeze | `FROZEN_CONSERVATIVE_R0_PRE_APPROVAL` |
| R0 canary | `HL-ARCHIVE-METADATA-CANARY-R0-001` |
| R0 human approval | `APPROVED_SCOPE_AND_BUDGET_AWAITING_IMPLEMENTATION` |
| R0 approval reviewed commit | `9af4b21863e47fb3bb2997ce77b9940eecf4597f` |
| R0 approval text SHA-256 | `d70008eac7521b324f61161bcc0075e28cc3a116dd30f0c52b48d8cf5eb6ed46` |
| human-approved one-time ceiling | `EUR 1.00` |
| monthly ceiling | `EUR 0` |
| R0 implementation installed | `false` |
| R0 execution workflow installed | `false` |
| R0 execution ready | `false` |
| operational requester-pays authorized | `false` |
| operational ListObjectsV2 authorized | `false` |
| GetObject authorized | `false` |
| object-body download authorized | `false` |
| S3 requests executed | `0` |
| empirical result | `null` |
| integration authorized | `false` |
| paper authorized | `false` |
| shadow authorized | `false` |
| live authorized | `false` |
| leverage authorized | `false` |
| capital allocation authorized | `false` |

## Canonical technical evidence

The canonical public probe and AWS OIDC identity evidence remain immutable and attested. No historical archive object has been listed or downloaded. The STS identity check proves GitHub-to-AWS federation and role identity but not the persistent S3 inline policy document.

The conservative R0 pricing model remains frozen with a modeled stress cost of `USD 0.004544304` at every R0 technical cap. The user has now explicitly approved a maximum one-time human ceiling of `EUR 1.00` for exactly seven first-page metadata LIST calls. The exact approval text is retained under `research/archive_inventory/approvals/` and hash-bound.

Human budget/scope approval is deliberately distinct from operational release. This approval authorizes the project to implement and review the bounded R0 workflow. It does not by itself make an S3 request executable.

## Hard boundary

```text
human_r0_scope_budget_approved = true
human_maximum_one_time_budget_eur = 1.00
maximum_monthly_budget_eur = 0
r0_implementation_installed = false
r0_execution_workflow_installed = false
r0_execution_ready = false
operational_requester_pays_authorized = false
operational_list_objects_authorized = false
get_object_authorized = false
head_object_authorized = false
get_object_attributes_authorized = false
range_get_authorized = false
list_object_versions_authorized = false
list_all_my_buckets_authorized = false
object_body_download_authorized = false
decompression_authorized = false
market_data_ingested = false
empirical_result = null
```

## Exact next gate

1. Merge the immutable approval record after CI and clean-context review.
2. From the resulting canonical `main`, implement a manual exact-main-SHA R0 workflow and deterministic collector that can issue only the seven approved first-page `ListObjectsV2` requests with `RequestPayer=requester`.
3. Add hard software counters for 7 requests, 25 keys/request, 175 entries, 8 MiB total response bytes, 180 seconds, zero retries and no continuation-token following.
4. Prove statically and by tests that no object-body, pagination, bucket-enumeration, mutation, market-data ingestion or trading capability exists.
5. Merge the implementation only after exact-head CI and clean-context review.
6. Only then may one manual canonical R0 workflow run be dispatched. The larger 300-request inventory remains separately unauthorized.

Entity-resolution research remains downstream of demonstrated individual-wallet copyability. No probabilistic wallet merge may create false consensus in the first study.
