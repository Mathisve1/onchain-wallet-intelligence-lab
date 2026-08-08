# Project State

Verified: 2026-08-08 against canonical public-probe evidence, canonical R0 evidence, Region-probe preregistration `910997423f5e008f3c7bca65fd739d6aa14d25a7`, approval merge `b86156d71ef438441e6d3903a8bbc2da564a2046`, implementation merge `91687b4c803e331d4b2ef8493df731c99e25a0e5`, release merge `f32901ac1946ff6456c44b3a1f75e4a7b641fa39`, and successful single-use Region-probe run `31273770895`.

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
| fresh LIST attempt authorized | `false` |
| larger 300-request inventory | `false` |
| object-body access | `false` |
| market-data ingestion | `false` |
| empirical result | `null` |
| integration / paper / shadow / live / leverage / capital | all `false` |

## Evidence and interpretation

The single-use Region probe executed against exact canonical release commit `f32901ac1946ff6456c44b3a1f75e4a7b641fa39`. All exact-main, release and single-use checks passed before AWS OIDC. AWS role assumption succeeded. The probe issued exactly one authenticated direct SigV4 `HEAD /` to `hl-mainnet-node-data.s3.amazonaws.com`, requested Requester Pays acknowledgement, used zero retries, followed zero redirects and did not read a response body.

AWS returned HTTP `400` together with `x-amz-bucket-region: ap-northeast-1`. Under the preregistered Region-probe contract this is a technical PASS because the purpose was solely to observe the authoritative bucket Region; a 2xx response was not required. The result therefore resolves the prior R0 `S3_AuthorizationHeaderMalformed` failures as consistent with signing `hl-mainnet-node-data` in `us-east-1` instead of its observed Region `ap-northeast-1`.

The artifact `9026393705` is independently verified. GitHub's provider digest and the independently downloaded ZIP SHA-256 both equal `5f66d4a961c3f32804af3d40adcd2d2c3f3b35e93896c9861839465e2d83d405`, and the internal hash ledger matches the retained context, result and return-code files.

This is infrastructure/access evidence only. It is not market data, wallet intelligence, P&L or alpha evidence. The Region-probe release is consumed and may not be rerun. A correctly-regioned LIST request requires a fresh, separately reviewed and explicitly approved gate.

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

1. Canonically attest run `31273770895` and the observed Region `ap-northeast-1`.
2. Keep `RELEASE_HL_ARCHIVE_REGION_PROBE_R1_001` consumed; never rerun it.
3. Preregister a fresh corrected-region metadata LIST canary separately. It must bind signing Region `ap-northeast-1`, a new request/cost envelope and a new explicit human approval before any S3 LIST request.
4. The 300-request inventory, object-body access, market-data ingestion, wallet analysis and all trading/capital stages remain separately gated.
