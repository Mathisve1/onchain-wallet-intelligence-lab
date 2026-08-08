# Project State

Verified: 2026-08-08 against canonical public-probe evidence, canonical R0 evidence, Region-probe preregistration `910997423f5e008f3c7bca65fd739d6aa14d25a7`, approval merge `b86156d71ef438441e6d3903a8bbc2da564a2046`, implementation merge `91687b4c803e331d4b2ef8493df731c99e25a0e5`, release merge `f32901ac1946ff6456c44b3a1f75e4a7b641fa39`, successful single-use Region-probe run `31273770895`, Region-probe attestation merge `9378f625648592bd4a5890f47a98b36028cbd433`, canonical R2 preregistration merge `39b40cccc7e9a3fdbc439d06fb188e946d9da2aa`, canonical R2 approval merge `151e08f54037ca7d3a0a9c17d3bdfb84d707a66e`, canonical R2 implementation merge `142ce50be20507761c4cce37b325ac69d57f8b25`, and canonical first R2 release merge `0dd6f32ab3a202b0c58f37821d1038ac917d84ce` plus operator-supplied first-dispatch step evidence proving fail-closed pre-OIDC / zero-S3 execution.

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
| Region probe | `HL-ARCHIVE-REGION-PROBE-R1-001` |
| Region probe release | `CONSUMED_BY_RUN_31273770895` |
| Region probe run / job / artifact | `31273770895` / `93143945097` / `9026393705` |
| Region probe artifact SHA-256 | `5f66d4a961c3f32804af3d40adcd2d2c3f3b35e93896c9861839465e2d83d405` |
| Region probe terminal result | `REGION_PROBE_R1_PASS` |
| Region probe HTTP result | `400` / `4xx` |
| `hl-mainnet-node-data` exact Region | `ap-northeast-1` |
| Region probe requests / retries / redirects | `1` / `0` / `false` |
| Region probe runtime | `0.688386 sec` |
| Region probe response body read | `false` |
| Region probe LIST/object data requested | `false` |
| R2 canary | `HL-ARCHIVE-NODEDATA-METADATA-CANARY-R2-001` |
| R2 preregistration commit | `39b40cccc7e9a3fdbc439d06fb188e946d9da2aa` |
| R2 approval canonical commit | `151e08f54037ca7d3a0a9c17d3bdfb84d707a66e` |
| R2 implementation canonical commit | `142ce50be20507761c4cce37b325ac69d57f8b25` |
| R2 first release canonical commit | `0dd6f32ab3a202b0c58f37821d1038ac917d84ce` |
| R2 status | `RELEASE_001_CONSUMED_PRE_OIDC_ZERO_S3_SUCCESSOR_002_UNDER_REVIEW` |
| R2 parent Region attestation | `9378f625648592bd4a5890f47a98b36028cbd433` |
| R2 target / signing Region | `hl-mainnet-node-data` / `ap-northeast-1` |
| R2 regional endpoint | `hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com` |
| R2 frozen prefixes | `5` previously failing node-data families |
| R2 request envelope | `5 x ListObjectsV2`, max `25` keys each / `125` entries total |
| R2 response/runtime cap | `8 MiB` / `120 sec` |
| R2 retries / pagination / redirects | `0` / `false` / `false` |
| R2 approval ID | `APPROVE_HL_ARCHIVE_NODEDATA_CANARY_R2_001` |
| R2 approval timestamp | `2026-08-08T19:48:00Z` |
| R2 approval text SHA-256 | `728f4e21c045eb10e883bdf0f2e970686f0e6b6cc4dc67a4f214a882cf1831c6` |
| R2 maximum one-time / monthly budget | `EUR 0.10` / `EUR 0` |
| R2 canonical implementation | `INSTALLED_RELEASE_GATED` |
| R2 collector | `INSTALLED_DIRECT_SIGV4_REGIONAL_LIST_ONLY` |
| R2 workflow candidate | `MANUAL_ONLY_GITHUB_NATIVE_MAIN_SHA_SUCCESSOR_GATE` |
| R2 temporary S3 session boundary | `LISTBUCKET_EXACT_FIVE_PREFIXES_MAX25_ONLY` |
| R2 release 001 | `CONSUMED_BY_FIRST_DISPATCH_PRE_OIDC_NO_S3_EXECUTION` |
| R2 release 001 AWS OIDC / collector | `false` / `false` |
| R2 release 001 S3 requests / metadata entries | `0` / `0` |
| R2 release 001 rerun | `false` |
| R2 successor release 002 | `CANDIDATE_UNDER_REVIEW_NOT_CANONICAL` |
| R2 successor manual SHA input | `removed`; identity derives from `github.event_name`, `github.ref`, `github.sha` and checked-out HEAD |
| R2 execution ready | `false` while successor PR is unmerged |
| R2 current scoped paid request / Requester Pays / LIST | `false` / `false` / `false` |
| R2 aggregate S3 requests / metadata entries observed | `0` / `0` |
| larger 300-request inventory | `false` |
| object-body access | `false` |
| market-data ingestion | `false` |
| empirical result | `null` |
| integration / paper / shadow / live / leverage / capital | all `false` |

## Evidence and interpretation

The single-use Region probe executed against exact canonical release commit `f32901ac1946ff6456c44b3a1f75e4a7b641fa39`. All exact-main, release and single-use checks passed before AWS OIDC. AWS role assumption succeeded. The probe issued exactly one authenticated direct SigV4 `HEAD /` to `hl-mainnet-node-data.s3.amazonaws.com`, requested Requester Pays acknowledgement, used zero retries, followed zero redirects and did not read a response body.

AWS returned HTTP `400` together with `x-amz-bucket-region: ap-northeast-1`. Under the preregistered Region-probe contract this is a technical PASS because the purpose was solely to observe the authoritative bucket Region; a 2xx response was not required. The result therefore resolves the prior R0 `S3_AuthorizationHeaderMalformed` failures as consistent with signing `hl-mainnet-node-data` in `us-east-1` instead of its observed Region `ap-northeast-1`.

The artifact `9026393705` is independently verified. GitHub's provider digest and the independently downloaded ZIP SHA-256 both equal `5f66d4a961c3f32804af3d40adcd2d2c3f3b35e93896c9861839465e2d83d405`, and the internal hash ledger matches the retained context, result and return-code files.

R2 is the bounded successor to that consumed Region probe. Its immutable preregistration binds signing Region `ap-northeast-1` and exactly the five node-data prefixes that failed R0. The user's approval `APPROVE_HL_ARCHIVE_NODEDATA_CANARY_R2_001` is hash-bound to preregistration commit `39b40cccc7e9a3fdbc439d06fb188e946d9da2aa` and was canonically recorded as `151e08f54037ca7d3a0a9c17d3bdfb84d707a66e`. It approves five first-page `ListObjectsV2` requests maximum, 25 keys each, 125 entries total, 8 MiB aggregate response bytes, 120 seconds, zero retries, no pagination or redirect following, and EUR 0.10 one-time / EUR 0 monthly ceilings.

The separately reviewed R2 implementation is canonical as `142ce50be20507761c4cce37b325ac69d57f8b25` (PR #35). Its exact-head evidence was `1a6c93d519625e1cdb378071c268298accc035b9`, Research CI run `31276731274`, job `93151401982`, with `170/170` tests passing. The collector uses direct standard-library SigV4 HTTPS, signs in `ap-northeast-1`, targets only `hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com`, increments the request counter before transport, retains only approved metadata, requires `x-amz-request-charged: requester` on successful Requester Pays responses, never retains a continuation-token value and never follows pagination or redirects.

The first R2 execution release `RELEASE_HL_ARCHIVE_NODEDATA_CANARY_R2_001` was canonically merged as `0dd6f32ab3a202b0c58f37821d1038ac917d84ce`. Its first dispatch failed at `Verify canonical main dispatch and exact reviewed identity`. Operator-supplied GitHub Actions step evidence shows the AWS OIDC role-assumption step and the collector step were both skipped. Therefore the first release is conservatively consumed while the observed R2 network usage remains exactly zero S3 requests, zero `ListObjectsV2` requests, zero Requester Pays S3 requests and zero metadata entries. The legacy release record remains immutable; consumption is recorded separately in `R2_EXECUTION_RELEASE_001_CONSUMPTION.json`. No rerun of release 001 is authorized.

The current branch contains successor release candidate `RELEASE_HL_ARCHIVE_NODEDATA_CANARY_R2_002`. It preserves the exact already-approved data/budget envelope and changes only the pre-OIDC identity/release layer. The redundant manual `reviewed_commit` input is removed. A future successor dispatch, if and only if this candidate becomes canonical, must be `workflow_dispatch` on `refs/heads/main`; checkout is bound directly to GitHub's own `github.sha`, and checked-out HEAD must equal that SHA. Distinct fail-closed error codes are emitted before AWS OIDC for event, ref, SHA-format or checkout-identity mismatch. The successor single-use window starts after the predecessor failure, so the consumed predecessor dispatch cannot be mistaken for the successor dispatch.

No AWS/S3 request occurs in this repair/release PR or its CI. Until the successor is canonically merged after exact-head CI and clean-context review, R2 execution, paid request, Requester Pays and LIST authorizations remain false. The larger 300-request inventory, object bodies, decompression, market-data ingestion, wallet analysis and all trading/capital stages remain separately unauthorized.

## Hard boundary

```text
human_r0_scope_budget_approved = true
r0_execution_release_consumed = true
r0_execution_ready = false
r0_s3_requests_executed = 7
r0_successful_requests = 2
r0_failed_requests = 5
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
region_probe_r1_execution_release_consumed = true
region_probe_r1_execution_ready = false
region_probe_r1_head_bucket_authorized = false
region_probe_r1_requester_pays_acknowledgement_authorized = false
region_probe_r1_request_executed = true
region_probe_r1_s3_http_requests_executed = 1
region_probe_r1_run_id = 31273770895
region_probe_r1_job_id = 93143945097
region_probe_r1_artifact_id = 9026393705
region_probe_r1_exact_bucket_region = ap-northeast-1
r2_canary_preregistered = true
r2_canary_id = HL-ARCHIVE-NODEDATA-METADATA-CANARY-R2-001
r2_preregistration_commit = 39b40cccc7e9a3fdbc439d06fb188e946d9da2aa
r2_approval_canonical_commit = 151e08f54037ca7d3a0a9c17d3bdfb84d707a66e
r2_parent_region_attestation_commit = 9378f625648592bd4a5890f47a98b36028cbd433
r2_target_bucket = hl-mainnet-node-data
r2_signing_region = ap-northeast-1
r2_regional_endpoint = hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com
r2_maximum_total_list_requests = 5
r2_maximum_keys_per_request = 25
r2_maximum_total_entries = 125
r2_maximum_total_response_bytes = 8388608
r2_maximum_runtime_seconds = 120
r2_maximum_retries_per_request = 0
r2_pagination_authorized = false
r2_http_redirect_following_authorized = false
r2_human_approved = true
r2_approval_id = APPROVE_HL_ARCHIVE_NODEDATA_CANARY_R2_001
r2_approval_reviewed_commit = 39b40cccc7e9a3fdbc439d06fb188e946d9da2aa
r2_approval_recorded_at_utc = 2026-08-08T19:48:00Z
r2_approval_text_sha256 = 728f4e21c045eb10e883bdf0f2e970686f0e6b6cc4dc67a4f214a882cf1831c6
r2_maximum_one_time_budget_eur = 0.10
r2_maximum_monthly_budget_eur = 0
r2_implementation_phase_authorized = true
r2_implementation_candidate_present = true
r2_collector_candidate_present = true
r2_workflow_candidate_present = true
r2_implementation_canonical = true
r2_implementation_commit = 142ce50be20507761c4cce37b325ac69d57f8b25
r2_expected_implementation_commit = 142ce50be20507761c4cce37b325ac69d57f8b25
r2_execution_release_present = true
r2_execution_release_id = RELEASE_HL_ARCHIVE_NODEDATA_CANARY_R2_001
r2_execution_release_consumed = true
r2_execution_release_consumption_status = CONSUMED_BY_FIRST_DISPATCH_PRE_OIDC_NO_S3_EXECUTION
r2_execution_release_001_s3_requests_executed = 0
r2_execution_release_001_metadata_entries_observed = 0
r2_execution_release_001_rerun_authorized = false
r2_successor_release_candidate_present = true
r2_successor_release_id = RELEASE_HL_ARCHIVE_NODEDATA_CANARY_R2_002
r2_successor_release_canonical = false
r2_successor_manual_reviewed_commit_input_required = false
r2_successor_identity_source = GITHUB_EVENT_REF_SHA_AND_CHECKED_OUT_HEAD
r2_execution_ready = false
r2_execution_authorized = false
r2_paid_request_authorized = false
r2_requester_pays_authorized = false
r2_list_objects_v2_authorized = false
r2_get_object_authorized = false
r2_head_object_authorized = false
r2_get_object_attributes_authorized = false
r2_range_get_authorized = false
r2_list_object_versions_authorized = false
r2_list_all_my_buckets_authorized = false
r2_object_body_download_authorized = false
r2_decompression_authorized = false
r2_market_data_ingestion_authorized = false
r2_larger_300_request_inventory_authorized = false
r2_s3_requests_executed = 0
r2_metadata_entries_observed = 0
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

1. Require exact-head Research CI, byte-exact repository-manifest validation, legacy R2 implementation validation, successor-release validation and clean-context review on PR #37.
2. Merge only if release 001 remains immutable/consumed, its separate consumption attestation remains zero-S3, successor release 002 remains bound to canonical implementation `142ce50be20507761c4cce37b325ac69d57f8b25` and approval `151e08f54037ca7d3a0a9c17d3bdfb84d707a66e`, and every approved cap/prohibition is unchanged.
3. After merge, verify the actual successor release squash SHA from remote `main`; do not predeclare it.
4. Only then may exactly one new manual `workflow_dispatch` on `main` be considered released. No SHA input should be supplied: GitHub `github.sha` is the canonical dispatch identity and checkout target. Run attempt must be `1`; the first successor dispatch consumes release 002 regardless of PASS/FAIL.
5. Immediately retain and independently attest the resulting minimized artifact, including exact run/job/artifact identities, request counts, status classes, metadata-entry count, response bytes, runtime and Requester Pays evidence.
6. Do not rerun release 001 or release 002. Any later dispatch requires a fresh reviewed successor release.
7. Even a successful R2 result does not authorize the 300-request inventory, object-body access, decompression, market-data ingestion, wallet analysis or any trading/capital stage.
