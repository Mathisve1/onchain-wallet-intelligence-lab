# Project State

Verified: 2026-08-08 against canonical `main` approval commit `62e0750382216afb5875ad52cb7443d43265e862`, canonical public-probe evidence, attested AWS OIDC identity run `31250176507`, and explicit human approval `APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001`.

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
| conservative pricing freeze | `FROZEN_CONSERVATIVE_R0_PRE_APPROVAL` |
| R0 canary | `HL-ARCHIVE-METADATA-CANARY-R0-001` |
| R0 human approval | `APPROVED_SCOPE_AND_BUDGET_AWAITING_IMPLEMENTATION` |
| R0 approval canonical record commit | `62e0750382216afb5875ad52cb7443d43265e862` |
| R0 approval reviewed commit | `9af4b21863e47fb3bb2997ce77b9940eecf4597f` |
| R0 approval text SHA-256 | `d70008eac7521b324f61161bcc0075e28cc3a116dd30f0c52b48d8cf5eb6ed46` |
| human-approved one-time ceiling | `EUR 1.00` |
| monthly ceiling | `EUR 0` |
| R0 implementation | `CANDIDATE_ON_REVIEW_BRANCH_NOT_CANONICAL` |
| R0 implementation base | `62e0750382216afb5875ad52cb7443d43265e862` |
| R0 transport | `DIRECT_SIGV4_HTTPS_NO_REDIRECT_FOLLOW` |
| R0 S3 HTTP request cap | `7` |
| R0 workflow present on review branch | `true` |
| R0 workflow manual-only | `true` |
| R0 post-merge execution release required | `true` |
| R0 execution release present | `false` |
| R0 release single-use enforced | `true` |
| R0 execution on review branch | `false` |
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

## Canonical evidence and approval

The canonical public probe and AWS OIDC identity evidence remain immutable and attested. No historical archive object has been listed or downloaded. The STS gate proves GitHub-to-AWS federation and role identity, not the persistent S3 policy.

The user's exact R0 scope/budget approval is canonical and hash-bound. It permits a maximum one-time ceiling of `EUR 1.00` for the exact seven-family first-page R0 envelope. It does not authorize any object body, market-data ingestion, wallet analysis, clustering or trading stage.

## R0 implementation candidate

The review branch contains a manual-only exact-main-SHA workflow and deterministic metadata collector. The collector creates at most seven direct SigV4 HTTPS `ListObjectsV2` GET requests, one per frozen family, with `x-amz-request-payer: requester` and `max-keys=25`.

The implementation deliberately does not use AWS CLI/botocore for S3 LIST because S3 clients may implement Region redirects. The direct `http.client` transport follows no redirect and performs no retry. A wrong-Region response therefore becomes a coarse failure instead of an additional S3 request.

Merging this implementation will still **not** release execution. The workflow hard-requires a separately reviewed `R0_EXECUTION_RELEASE.json`, which is intentionally absent from this branch. That release is single-use: attempt >1 fails, and a read-only GitHub Actions history check requires the current run to be the only R0 dispatch since the release timestamp.

## Hard boundary

```text
human_r0_scope_budget_approved = true
human_maximum_one_time_budget_eur = 1.00
maximum_one_time_budget_eur = null
maximum_monthly_budget_eur = 0
r0_implementation_canonical = false
r0_execution_release_present = false
r0_execution_ready = false
r0_s3_http_request_cap = 7
r0_retries_authorized = 0
r0_pagination_authorized = false
r0_http_redirect_following_authorized = false
operational_requester_pays_authorized = false
operational_list_objects_authorized = false
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
```

## Exact next gate

1. Run exact-head CI and clean-context security review on the R0 implementation candidate.
2. Merge the implementation only if all static/unit/manifest/governance gates pass and no hidden S3/body/retry/pagination capability exists.
3. Verify the exact new canonical implementation merge SHA.
4. Create a separate post-merge execution-release PR that binds that implementation SHA and the already-approved limits; no S3 call occurs in that release PR.
5. Merge the release only after CI/review. The release permits exactly one manual R0 dispatch; reruns and second dispatches fail before OIDC.
6. Only then may one canonical R0 workflow run make the seven approved S3 HTTP requests.
7. Independently attest the R0 artifact/result before considering any larger paginated inventory.
8. The 300-request inventory, object-body access, market-data ingestion, wallet P&L, clustering and all trading stages remain separately gated.

Entity-resolution research remains downstream of demonstrated individual-wallet copyability. No probabilistic wallet merge may create false consensus in the first study.
