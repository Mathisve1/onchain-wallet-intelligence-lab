# Project State

Verified: 2026-08-08 against canonical R0 release commit `bc8a47a1cdeb1163657ea243d6694286d6612bed`, canonical R0 run `31260043109`, canonical public-probe evidence, attested AWS OIDC identity run `31250176507`, and explicit human approval `APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001`.

## Current status

| Dimension | State |
|---|---|
| program | `ONCHAIN-WALLET-INTELLIGENCE` |
| current study | `WALLET-COPYABILITY-STUDY-001` |
| research status | `REQUIRES_FURTHER_TESTING` |
| lifecycle stage | `PRE_ARCHIVE_INVENTORY` |
| experiment status | `PUBLIC_TECHNICAL_PROBE_ATTESTED_ARCHIVE_ACCESS_RESTRICTED` |
| R0 experiment status | `R0_METADATA_CANARY_ATTESTED_PARTIAL_FAILURE` |
| public-probe implementation | `INSTALLED_ON_CANONICAL_MAIN` |
| canonical public-probe workflow run / job / artifact | `31200124642` / `92937868268` / `9002459643` |
| public-probe result | `PUBLIC_PROBE_PASS` |
| archive access result | `ROUTES_CONFIRMED_ACCESS_RESTRICTED` |
| archive inventory study | `HL-ARCHIVE-INVENTORY-001` |
| archive inventory parent status | `PREREGISTERED_METADATA_ONLY_NO_EXECUTION` |
| archive preregistration commit | `0e8a678644c29548a38ebfa1c0af91d4a9a92c09` |
| AWS account ID | `630956766927` |
| GitHub OIDC federation | `PROVEN_BY_CANONICAL_STS_RUN` |
| expected GitHub OIDC subject | `repo:Mathisve1@163474992/onchain-wallet-intelligence-lab@1326362646:ref:refs/heads/main` |
| expected AWS role | `onchain-wallet-intelligence-hl-archive-metadata-canary` |
| STS identity check status | `ATTESTED_STS_IDENTITY_MATCH` |
| canonical STS run / job / artifact | `31250176507` / `93085194965` / `9019744292` |
| AWS identity bound | `true` |
| persistent S3 inline policy | `USER_CONFIRMED_NOT_API_VERIFIED` |
| `hyperliquid-archive` signing compatibility | `US_EAST_1_SUCCEEDED_FOR_R0` |
| `hl-mainnet-node-data` exact Region | `UNRESOLVED` |
| R0 canary | `HL-ARCHIVE-METADATA-CANARY-R0-001` |
| R0 human approval | `APPROVED_SCOPE_AND_BUDGET_CONSUMED` |
| R0 approval canonical record commit | `62e0750382216afb5875ad52cb7443d43265e862` |
| R0 approval reviewed commit | `9af4b21863e47fb3bb2997ce77b9940eecf4597f` |
| R0 approval timestamp | `2026-08-08T10:10:00Z` |
| R0 approval text SHA-256 | `d70008eac7521b324f61161bcc0075e28cc3a116dd30f0c52b48d8cf5eb6ed46` |
| human-approved one-time ceiling | `EUR 1.00` |
| monthly ceiling | `EUR 0` |
| R0 implementation | `INSTALLED_ON_CANONICAL_MAIN` |
| R0 implementation commit | `cd5c46b25502b671693dd5ebb091e7273399bccf` |
| R0 implementation exact-head CI | `41dcd5c2788af60ce9337b0c7eff4395264c4682` |
| R0 implementation CI run / job | `31257261899` / `93102453441` |
| R0 release canonical commit | `bc8a47a1cdeb1163657ea243d6694286d6612bed` |
| R0 release ID | `RELEASE_HL_ARCHIVE_METADATA_CANARY_R0_001` |
| R0 release status | `CONSUMED_BY_RUN_31260043109` |
| R0 run / job / artifact | `31260043109` / `93109335453` / `9022511541` |
| R0 artifact SHA-256 | `40b26e33833b54a872a75be066a87b7e57a0e2f3930adada76ca3829a1142c8e` |
| R0 terminal result | `ATTESTED_CONSUMED_PARTIAL_FAILURE_REGION_UNRESOLVED` |
| R0 S3 HTTP requests executed | `7` |
| R0 successful / failed requests | `2` / `5` |
| R0 retained metadata entries | `50` |
| R0 total S3 response bytes | `14229` |
| R0 runtime seconds | `2.439212` |
| R0 retries / pagination / redirects | `0` / `false` / `false` |
| `hyperliquid-archive/market_data/` | `SUCCESS_25_ENTRIES_TRUNCATED_REQUESTER_PAYS` |
| `hyperliquid-archive/asset_ctxs/` | `SUCCESS_25_ENTRIES_TRUNCATED_REQUESTER_PAYS` |
| `hl-mainnet-node-data` five families | `S3_AUTHORIZATION_HEADER_MALFORMED` |
| R0 root-cause assessment | `STRONGLY_CONSISTENT_WITH_SIGNING_REGION_MISMATCH_NOT_YET_PROVEN` |
| R0 execution ready | `false` |
| R0 scoped Requester Pays currently authorized | `false` |
| R0 scoped ListObjectsV2 currently authorized | `false` |
| fresh paid attempt authorized | `false` |
| broader archive Requester Pays/LIST | `NOT_AUTHORIZED` |
| larger 300-request inventory authorized | `false` |
| GetObject authorized | `false` |
| object-body download authorized | `false` |
| market data ingested | `false` |
| empirical result | `null` |
| integration authorized | `false` |
| paper authorized | `false` |
| shadow authorized | `false` |
| live authorized | `false` |
| leverage authorized | `false` |
| capital allocation authorized | `false` |

## Canonical R0 evidence

The single-use R0 dispatch ran against exact canonical release commit `bc8a47a1cdeb1163657ea243d6694286d6612bed`. All pre-OIDC approval, exact-main-SHA and single-use gates passed. AWS OIDC role assumption succeeded. The collector then completed exactly seven S3 HTTP requests under the frozen envelope. It used zero retries, followed zero pagination tokens, followed zero HTTP redirects, requested no object body and ingested no market data.

The retained artifact is independently verified: GitHub artifact `9022511541` reported provider digest `sha256:40b26e33833b54a872a75be066a87b7e57a0e2f3930adada76ca3829a1142c8e`, which matched the independently downloaded ZIP SHA-256. Its internal hash ledger also matched the retained context, result and return-code files.

Two requests succeeded on `hyperliquid-archive`: `market_data/` and `asset_ctxs/`. Each returned 25 first-page metadata entries, was truncated, reported a continuation token, and confirmed `request_charged=requester`. The continuation tokens were not retained or followed.

All five `hl-mainnet-node-data` requests failed with the same coarse class `S3_AuthorizationHeaderMalformed`. Because the same OIDC role, SigV4 code and `us-east-1` signing succeeded for both `hyperliquid-archive` prefixes, this is strongly consistent with a signing-Region mismatch for `hl-mainnet-node-data`. The exact Region is not attested because R0 deliberately discarded raw error bodies and bucket-Region headers.

This is an informative technical partial failure, not a market/alpha result. The first dispatch consumed `RELEASE_HL_ARCHIVE_METADATA_CANARY_R0_001` regardless of PASS/FAIL. A rerun or second paid attempt is not authorized.

## Hard boundary

```text
human_r0_scope_budget_approved = true
human_maximum_one_time_budget_eur = 1.00
maximum_monthly_budget_eur = 0
r0_implementation_canonical = true
r0_implementation_commit = cd5c46b25502b671693dd5ebb091e7273399bccf
r0_execution_release_present = true
r0_execution_release_consumed = true
r0_execution_ready = false
r0_run_id = 31260043109
r0_job_id = 93109335453
r0_artifact_id = 9022511541
r0_s3_requests_executed = 7
r0_successful_requests = 2
r0_failed_requests = 5
r0_requester_pays_authorized = false
r0_list_objects_v2_authorized = false
r0_paid_request_authorized = false
fresh_paid_attempt_authorized = false
requester_pays_authorized = false
list_objects_authorized = false
paid_request_authorized = false
larger_300_request_inventory_authorized = false
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
integration_authorized = false
paper_authorized = false
shadow_authorized = false
live_authorized = false
leverage_authorized = false
capital_allocation_authorized = false
```

## Exact next gate

1. Canonically attest run `31260043109` and preserve its minimized evidence.
2. Keep the consumed R0 release closed; do not rerun or redispatch it.
3. Preregister an exact Region-discovery successor for `hl-mainnet-node-data`. Preferred design: one direct `HeadBucket` request that retains only coarse HTTP status plus `x-amz-bucket-region`, with no object body, LIST pagination or market-data ingestion.
4. Obtain separate human approval before that new network request. No new paid request is authorized by the old EUR 1.00 release.
5. After exact Region discovery, separately review whether a fresh bounded LIST canary is justified.
6. The 300-request inventory, object-body access, market-data ingestion, wallet P&L, clustering and every trading/capital stage remain separately gated.

Entity-resolution research remains downstream of demonstrated individual-wallet copyability. No probabilistic wallet merge may create false consensus in the first study.
