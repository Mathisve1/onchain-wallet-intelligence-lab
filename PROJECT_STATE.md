# Project State

Verified: 2026-08-08 against canonical implementation merge `cd5c46b25502b671693dd5ebb091e7273399bccf`, canonical public-probe evidence, attested AWS OIDC identity run `31250176507`, and explicit human approval `APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001`.

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
| exact bucket Regions | `UNRESOLVED_PRE_S3` |
| R0 canary | `HL-ARCHIVE-METADATA-CANARY-R0-001` |
| R0 human approval | `APPROVED_SCOPE_AND_BUDGET` |
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
| R0 implementation tests | `108/108 PASS` |
| R0 transport | `DIRECT_SIGV4_HTTPS_NO_REDIRECT_FOLLOW` |
| R0 S3 HTTP request cap | `7` |
| R0 workflow on canonical main | `true` |
| R0 workflow manual-only | `true` |
| R0 execution release | `RELEASE_HL_ARCHIVE_METADATA_CANARY_R0_001` |
| R0 release status | `SINGLE_USE_RELEASE_CANDIDATE_FOR_CANONICAL_MAIN` |
| R0 single-use window start | `2026-08-08T10:10:00Z` |
| R0 release single-use enforced | `true` |
| R0 execution on noncanonical branch | `false` |
| R0 scoped Requester Pays | `AUTHORIZED_BY_RELEASE_ONLY` |
| R0 scoped ListObjectsV2 | `AUTHORIZED_BY_RELEASE_ONLY` |
| broader archive Requester Pays/LIST | `NOT_AUTHORIZED` |
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

## Canonical evidence and approval

The canonical public probe and AWS OIDC identity evidence remain immutable and attested. The STS gate proves GitHub-to-AWS federation and role identity; it does not independently prove the persistent S3 policy. No historical archive object has been downloaded and no market data has been ingested.

The exact R0 scope/budget approval is canonical and hash-bound. It permits only the seven-family first-page metadata envelope under a EUR 1.00 one-time ceiling. The approval snapshot remains immutable; current runtime authority is represented separately by `research/archive_inventory/r0/R0_EXECUTION_RELEASE.json`.

## R0 implementation and release

PR #22 is canonical at `cd5c46b25502b671693dd5ebb091e7273399bccf`. Its collector creates at most seven direct SigV4 HTTPS `ListObjectsV2` GET requests, one per frozen family, with `x-amz-request-payer: requester` and `max-keys=25`. It follows no redirect and performs no retry; wrong-Region responses therefore fail without adding an extra S3 request.

The separate R0 release is deliberately single-use. Its consumption window begins at the immutable approval timestamp `2026-08-08T10:10:00Z`, not at release authoring time. Before AWS OIDC, the manual workflow requires run attempt 1 and verifies through the read-only GitHub Actions API that the current run is the only R0 `workflow_dispatch` on `main` since that timestamp. A first dispatch consumes the release whether it passes or fails.

The release opens only R0-scoped Requester Pays and `ListObjectsV2`. The broader 300-request inventory remains unauthorized, as do object-body access, market-data ingestion and every trading/capital stage.

## Hard boundary

```text
human_r0_scope_budget_approved = true
human_maximum_one_time_budget_eur = 1.00
maximum_one_time_budget_eur = null
maximum_monthly_budget_eur = 0
r0_implementation_canonical = true
r0_implementation_commit = cd5c46b25502b671693dd5ebb091e7273399bccf
r0_execution_release_present = true
r0_execution_ready = true
r0_single_use_window_start_utc = 2026-08-08T10:10:00Z
r0_maximum_one_time_budget_eur = 1.00
r0_s3_http_request_cap = 7
r0_retries_authorized = 0
r0_pagination_authorized = false
r0_http_redirect_following_authorized = false
r0_requester_pays_authorized = true
r0_list_objects_v2_authorized = true
r0_paid_request_authorized = true
requester_pays_authorized = false
list_objects_authorized = false
paid_request_authorized = false
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

1. Validate this single-use release candidate with exact-head CI, byte-exact manifest validation and clean-context review.
2. Merge the release only if all release/workflow/collector/governance gates pass and no scope expands beyond the approved seven LIST requests.
3. Verify the exact release merge SHA on canonical `main`.
4. Manually dispatch `Hyperliquid Archive Metadata Canary R0` exactly once against that exact `main` SHA.
5. The first dispatch consumes the release regardless of PASS/FAIL; do not rerun it.
6. Independently attest the resulting run/job/artifact and retained metadata before considering any new paid attempt or larger inventory.
7. The 300-request inventory, object-body access, market-data ingestion, wallet P&L, clustering and all trading stages remain separately gated.

Entity-resolution research remains downstream of demonstrated individual-wallet copyability. No probabilistic wallet merge may create false consensus in the first study.
