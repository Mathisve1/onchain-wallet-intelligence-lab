# Project State

Verified: 2026-08-08 against canonical public-probe evidence, canonical R0 evidence, Region-probe preregistration `910997423f5e008f3c7bca65fd739d6aa14d25a7`, approval merge `b86156d71ef438441e6d3903a8bbc2da564a2046`, and canonical Region-probe implementation merge `91687b4c803e331d4b2ef8493df731c99e25a0e5`.

## Current status

| Dimension | State |
|---|---|
| program | `ONCHAIN-WALLET-INTELLIGENCE` |
| current study | `WALLET-COPYABILITY-STUDY-001` |
| research status | `REQUIRES_FURTHER_TESTING` |
| lifecycle stage | `PRE_ARCHIVE_INVENTORY` |
| experiment status | `PUBLIC_TECHNICAL_PROBE_ATTESTED_ARCHIVE_ACCESS_RESTRICTED` |
| public-probe result | `PUBLIC_PROBE_PASS` |
| public-probe run / job / artifact | `31200124642` / `92937868268` / `9002459643` |
| archive inventory parent status | `PREREGISTERED_METADATA_ONLY_NO_EXECUTION` |
| AWS identity | `ATTESTED_STS_IDENTITY_MATCH` |
| STS run / job / artifact | `31250176507` / `93085194965` / `9019744292` |
| R0 result | `ATTESTED_CONSUMED_PARTIAL_FAILURE_REGION_UNRESOLVED` |
| R0 run / job / artifact | `31260043109` / `93109335453` / `9022511541` |
| R0 S3 requests | `7` |
| R0 success / failure | `2` / `5` |
| R0 release | `CONSUMED` |
| `hyperliquid-archive` | `US_EAST_1_SUCCEEDED_FOR_R0` |
| `hl-mainnet-node-data` exact Region | `UNRESOLVED` |
| Region probe | `HL-ARCHIVE-REGION-PROBE-R1-001` |
| Region probe purpose | `RESOLVE_HL_MAINNET_NODE_DATA_BUCKET_REGION_ONLY` |
| Region probe preregistration | `910997423f5e008f3c7bca65fd739d6aa14d25a7` |
| Region probe approval merge | `b86156d71ef438441e6d3903a8bbc2da564a2046` |
| Region probe approval SHA-256 | `56c8d01396b12d0dd783dbc1646ebbca947e51a024bb5c8f091cd0b7a889c541` |
| Region probe approval timestamp | `2026-08-08T14:52:00Z` |
| Region probe implementation | `CANONICAL` |
| Region probe implementation PR | `29` |
| Region probe implementation merge | `91687b4c803e331d4b2ef8493df731c99e25a0e5` |
| Region probe implementation exact-head CI | `4354f9a4e80c77b7250f95f79cab3f107ee8b54a` |
| Region probe implementation CI run / job | `31271673630` / `93138596154` |
| Region probe implementation tests | `143/143 PASS` |
| Region probe execution release | `RELEASE_HL_ARCHIVE_REGION_PROBE_R1_001` |
| Region probe release state | `SINGLE_USE_RELEASE_CANDIDATE_READY_FOR_CANONICAL_MERGE` |
| Region probe target | `hl-mainnet-node-data` |
| Region probe operation | `HeadBucket` / `HEAD /` |
| Region probe request cap | `1` |
| Region probe budget ceiling | `EUR 0.10` one-time / `EUR 0` monthly |
| Region probe runtime / retries / redirects | `30 sec` / `0` / `false` |
| Region probe request/response body | `false` / `false` |
| Region probe session S3 boundary | `EXPLICIT_DENY_ALL_S3` |
| persistent IAM expansion required | `false` |
| Region probe request executed | `false` |
| Region probe exact bucket Region | `null` |
| fresh LIST attempt authorized | `false` |
| larger 300-request inventory | `false` |
| object-body access | `false` |
| market-data ingestion | `false` |
| empirical result | `null` |
| integration / paper / shadow / live / leverage / capital | all `false` |

## Evidence and boundary

The public probe remains canonically attested and the archive successor remains pre-market-data. `market_data_ingested = false` and no alpha, P&L, wallet ranking, clustering or trading result exists.

R0 is immutable evidence. Its single-use release was consumed by run `31260043109`; it cannot be rerun under the old approval. Two `hyperliquid-archive` prefixes succeeded and all five `hl-mainnet-node-data` prefixes returned `S3_AuthorizationHeaderMalformed`, strongly consistent with a signing-Region mismatch but not proof of the exact Region.

Region probe R1 is a separate successor. The immutable preregistration and approval snapshots remain non-self-authorizing. PR #29 separately reviewed and canonically installed a one-request direct SigV4 `HEAD /` implementation. The separate release candidate binds that implementation and the existing approval. Its workflow is manual-only, exact-main-SHA bound, single-use before OIDC, and the temporary AWS session carries an explicit `Deny s3:*` with no S3 Allow. The direct HTTPS HEAD may still return `x-amz-bucket-region`; no response body is read.

A successful Region observation authorizes nothing downstream by itself. In particular, no fresh `ListObjectsV2` request is authorized by this release.

## Hard boundary

```text
human_r0_scope_budget_approved = true
r0_execution_release_consumed = true
r0_execution_ready = false
r0_s3_requests_executed = 7
r0_requester_pays_authorized = false
r0_list_objects_v2_authorized = false
r0_paid_request_authorized = false
region_probe_r1_preregistered = true
region_probe_r1_human_approved = true
region_probe_r1_approval_reviewed_commit = 910997423f5e008f3c7bca65fd739d6aa14d25a7
region_probe_r1_approval_text_sha256 = 56c8d01396b12d0dd783dbc1646ebbca947e51a024bb5c8f091cd0b7a889c541
region_probe_r1_maximum_one_time_budget_eur = 0.10
region_probe_r1_maximum_monthly_budget_eur = 0
region_probe_r1_maximum_s3_http_requests = 1
region_probe_r1_implementation_phase_authorized = true
region_probe_r1_implementation_candidate_present = true
region_probe_r1_workflow_candidate_present = true
region_probe_r1_executable_candidate_present = true
region_probe_r1_implementation_canonical = true
region_probe_r1_implementation_commit = 91687b4c803e331d4b2ef8493df731c99e25a0e5
region_probe_r1_execution_release_present = true
region_probe_r1_execution_ready = true
region_probe_r1_head_bucket_authorized = true
region_probe_r1_requester_pays_acknowledgement_authorized = true
region_probe_r1_request_executed = false
region_probe_r1_exact_bucket_region = null
fresh_paid_attempt_authorized = false
fresh_list_attempt_authorized = false
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

1. Validate this single-use Region-probe release with exact-head CI, byte-exact manifest validation and clean-context review.
2. Merge only if the release remains bound to implementation `91687b4c803e331d4b2ef8493df731c99e25a0e5`, one HEAD request, EUR 0.10, zero retries/redirects/body and deny-all-S3 session policy.
3. Verify the actual release merge SHA on canonical `main`.
4. Manually dispatch `Hyperliquid Archive Region Probe R1` exactly once against that exact release merge SHA.
5. The first dispatch consumes the release regardless of PASS/FAIL; do not rerun it.
6. Attest the resulting Region header before considering any fresh LIST canary.
7. The 300-request inventory, object-body access, market-data ingestion, wallet analysis and all trading/capital stages remain separately gated.
