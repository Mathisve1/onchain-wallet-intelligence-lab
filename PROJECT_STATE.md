# Project State

Verified: 2026-08-11 against the canonical R0–R11 lineage, including consumed R10D run `31420197671`, canonical R11 dispatch `baca1925c23ef6b0136aa3d96d6d479ac7717bdf`, R11 run `31436753081` / job `93612467250` / artifact `9082810554`, independently reconstructed provider artifact SHA-256 `45ee57df7a63561bef1772d8612d5fe32b06b9c407d9c1464ce0a02b65a15cc5`, and canonical consumed-unresolved R11 evidence closure merge `f7aa612d2a5638cce0fd197f57efea4b787f87f1`.

## Current status

| Dimension | State |
|---|---|
| program | `ONCHAIN-WALLET-INTELLIGENCE` |
| current study | `WALLET-COPYABILITY-STUDY-001` |
| research status | `REQUIRES_FURTHER_TESTING` |
| lifecycle stage | `PRE_ARCHIVE_INVENTORY` |
| archive diagnostic gate | `R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_PREREGISTERED_NO_EXECUTION` |
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
| R2 successor release canonical commit | `6128e6a9974742113f74c6e17fba7159dc60bde5` |
| R2 canonical dispatch commit | `5cf612b2125877a097b9697c074ac82d66cb1635` |
| R2 status | `ATTESTED_CONSUMED_SUCCESS_FIVE_PREFIX_METADATA_LISTABLE` |
| R2 run / job / artifact | `31280640653` / `93161240213` / `9028305474` |
| R2 artifact SHA-256 | `491e651ab5b434c2c7489a4ec194a10f42cce50e80d801a3bb816c3e6b5144c8` |
| R2 terminal / technical result | `R2_NODEDATA_METADATA_CANARY_PASS` / `FIVE_PREFIX_METADATA_LISTABLE` |
| R2 parent Region attestation | `9378f625648592bd4a5890f47a98b36028cbd433` |
| R2 target / signing Region | `hl-mainnet-node-data` / `ap-northeast-1` |
| R2 regional endpoint | `hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com` |
| R2 frozen prefixes | `5` previously failing node-data families |
| R2 request envelope | `5 x ListObjectsV2`, max `25` keys each / `125` entries total |
| R2 observed requests / success / failure | `5` / `5` / `0` |
| R2 observed entries / response bytes / runtime | `125` / `38693` / `2.340922 sec` |
| R2 first-page truncation | all `5/5` `true`; continuation token present on all five, value not retained |
| R2 retries / pagination / redirects | `0` / `false` / `false` |
| R2 approval ID | `APPROVE_HL_ARCHIVE_NODEDATA_CANARY_R2_001` |
| R2 approval timestamp | `2026-08-08T19:48:00Z` |
| R2 approval text SHA-256 | `728f4e21c045eb10e883bdf0f2e970686f0e6b6cc4dc67a4f214a882cf1831c6` |
| R2 maximum one-time / monthly budget | `EUR 0.10` / `EUR 0` |
| R2 canonical implementation | `INSTALLED_RELEASE_GATED` |
| R2 collector | `INSTALLED_DIRECT_SIGV4_REGIONAL_LIST_ONLY` |
| R2 workflow | `INSTALLED_MANUAL_ONLY_GITHUB_NATIVE_MAIN_SHA_SUCCESSOR_GATE` |
| R2 temporary S3 session boundary | `LISTBUCKET_EXACT_FIVE_PREFIXES_MAX25_ONLY` |
| R2 release 001 | `CONSUMED_BY_FIRST_DISPATCH_PRE_OIDC_NO_S3_EXECUTION` |
| R2 release 001 AWS OIDC / collector | `false` / `false` |
| R2 release 001 S3 requests / metadata entries | `0` / `0` |
| R2 release 001 rerun | `false` |
| R2 successor release 002 | `CONSUMED_BY_RUN_31280640653_SUCCESS` |
| R2 successor release 002 exact-head CI | `d8e0a4102e26b12f64d7871b274e65891e81b431` / run `31279273339` / job `93157850604` / `185/185 PASS` |
| R2 successor manual SHA input | `removed`; identity derives from `github.event_name`, `github.ref`, `github.sha` and checked-out HEAD |
| R2 execution ready | `false`; release 002 consumed |
| R10D status | `CONSUMED_COMPLETE_LEGACY_REDUCER_MECHANICS`; canonical identity backward consistency remains separately unresolved |
| R10D run / artifact | `31420197671` / `9075129362` |
| R11 status | `CONSUMED_UNRESOLVED_IDENTITY_DIAGNOSTIC_REQUIRED` |
| R11 run / job / artifact | `31436753081` / `93612467250` / `9082810554` |
| R11 dispatch / attempt | `baca1925c23ef6b0136aa3d96d6d479ac7717bdf` / `1` |
| R11 requests / failures / retries | `72` / `0` / `0` |
| R11 hours / days | `72` / `3` |
| R11 wallet feature output | empty; `wallet_feature_retained=false` |
| R11 failure | repeated legacy `wallet+tid` observations; root cause and count absent from retained original result |
| R11 original release | `CONSUMED`; remaining request budget `0`; rerun forbidden |
| R11 evidence-retention deviation | preregistered duplicate count was not retained (`false`) |
| R11 closed / R12 ready | `false` / `false` |
| R11 evidence closure merge | `f7aa612d2a5638cce0fd197f57efea4b787f87f1` |
| R10D backward consistency | `C_R10D_UNCERTAIN_UNDER_CANONICAL_IDENTITY` |
| R10D legacy reducer reproduction | byte-exact; canonical unique-fill and event-time activity equivalence remain `UNKNOWN` |
| R11A diagnostic | `HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-002` |
| R11A status | `CORRECTIVE_R7_IMPLEMENTATION_SEALED_AWAITING_CLEAN_CONTEXT_REVIEW_NO_EXECUTION` |
| R11A exact input | same 72 R11 objects; no 73rd object or wider window |
| R11A owner approval | `NOT_PRESENT` |
| R11A workflow / release / activation | absent / absent / absent |
| R11A canonical Amendment 002 | `R11A-CORRECTIVE-PREREGISTRATION-AMENDMENT-002`; unchanged canonical V2 path; SHA-256 `bdd610c678189e8098381d8c4a0fd12296bf2e0cd8e9ec0fed375b073872552f`; V2-bound |
| R11A official pricing/EUR binding | `PENDING` |
| R11A empirical root cause | `UNKNOWN_PENDING_DIAGNOSTIC` |
| R11A repair selected / R11B authorized | `false` / `false` |
| R2 current scoped paid request / Requester Pays / LIST | `false` / `false` / `false` after consumption |
| R2 aggregate S3 requests / metadata entries observed | `5` / `125` |
| larger 300-request inventory | `false` |
| object-body access | `false` |
| market-data ingestion | `false` |
| empirical result | `null` |
| integration / paper / shadow / live / leverage / capital | all `false` |

## Evidence and interpretation

R11's exact single-use run completed all 72 approved object reads, all three source-path UTC dates and all transport/alignment mechanics without a failed request or retry. The collector then detected at least one repeated legacy `(wallet, tid)` projection and deliberately emitted no wallet-feature rows. The canonical conclusion remains `R11_72H_PERSISTENCE_PIPELINE_UNRESOLVED`.

The provider ZIP is retained reconstructably together with all five exact entries, including the zero-byte feature artifact and internal ledger. A separate immutable consumption record binds the run, job, artifact, dispatch SHA and artifact digest and leaves no reusable R11 request budget. The original pre-run release snapshot remains unchanged.

The preregistration promised to retain the duplicate count, but the historical exception path discarded the aggregate summary. That promise was not met. The retained original evidence therefore proves neither the repeat count nor its locations, payload equality, block replay status or root cause. It also does not validate the success-path active-day output: the historical `DayTrackingStates.__getitem__` mutates on reads, although the duplicate guard fired before that render loop in the canonical run and the retained feature file is empty.

R11 is not closed and R12 is not ready. Any new object read requires a new preregistration, explicit owner approval and separate single-use release. The consumed R11 release cannot be rerun.

R11A freezes a diagnostic identity model but does not authorize execution. The legacy `wallet+tid` projection is semantically under-keyed: the diagnostic preserves raw observation provenance, validates archive-block invariants, uses exact wrapper `block_time` plus exact source `coin` plus strict JSON uint50 `tid` for protocol-trade identity, and adds the validated wallet for wallet-user-fill identity. It must retain complete repeat provenance and classify every group without deduplication or repair.

The R10D artifact is reproducible byte-for-byte under its historical reducer. That does not prove equivalence under canonical block/wallet-fill identity or event-time activity because R10D did not retain the necessary occurrence-level ledger. Its backward-consistency class is therefore `C_R10D_UNCERTAIN_UNDER_CANONICAL_IDENTITY`.

The single-use Region probe executed against exact canonical release commit `f32901ac1946ff6456c44b3a1f75e4a7b641fa39`. All exact-main, release and single-use checks passed before AWS OIDC. AWS role assumption succeeded. The probe issued exactly one authenticated direct SigV4 `HEAD /` to `hl-mainnet-node-data.s3.amazonaws.com`, requested Requester Pays acknowledgement, used zero retries, followed zero redirects and did not read a response body.

AWS returned HTTP `400` together with `x-amz-bucket-region: ap-northeast-1`. Under the preregistered Region-probe contract this is a technical PASS because the purpose was solely to observe the authoritative bucket Region; a 2xx response was not required. The result therefore resolves the prior R0 `S3_AuthorizationHeaderMalformed` failures as consistent with signing `hl-mainnet-node-data` in `us-east-1` instead of its observed Region `ap-northeast-1`.

The artifact `9026393705` is independently verified. GitHub's provider digest and the independently downloaded ZIP SHA-256 both equal `5f66d4a961c3f32804af3d40adcd2d2c3f3b35e93896c9861839465e2d83d405`, and the internal hash ledger matches the retained context, result and return-code files.

R2 is the bounded successor to that consumed Region probe. Its immutable preregistration binds signing Region `ap-northeast-1` and exactly the five node-data prefixes that failed R0. The user's approval `APPROVE_HL_ARCHIVE_NODEDATA_CANARY_R2_001` is hash-bound to preregistration commit `39b40cccc7e9a3fdbc439d06fb188e946d9da2aa` and was canonically recorded as `151e08f54037ca7d3a0a9c17d3bdfb84d707a66e`. It approves five first-page `ListObjectsV2` requests maximum, 25 keys each, 125 entries total, 8 MiB aggregate response bytes, 120 seconds, zero retries, no pagination or redirect following, and EUR 0.10 one-time / EUR 0 monthly ceilings.

The separately reviewed R2 implementation is canonical as `142ce50be20507761c4cce37b325ac69d57f8b25` (PR #35). Its exact-head evidence was `1a6c93d519625e1cdb378071c268298accc035b9`, Research CI run `31276731274`, job `93151401982`, with `170/170` tests passing. The collector uses direct standard-library SigV4 HTTPS, signs in `ap-northeast-1`, targets only `hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com`, increments the request counter before transport, retains only approved metadata, requires `x-amz-request-charged: requester` on successful Requester Pays responses, never retains a continuation-token value and never follows pagination or redirects.

The first R2 execution release `RELEASE_HL_ARCHIVE_NODEDATA_CANARY_R2_001` was canonically merged as `0dd6f32ab3a202b0c58f37821d1038ac917d84ce`. Its first dispatch failed at `Verify canonical main dispatch and exact reviewed identity`. Operator-supplied GitHub Actions step evidence shows the AWS OIDC role-assumption step and the collector step were both skipped. Therefore the first release is conservatively consumed while the observed R2 network usage remains exactly zero S3 requests, zero `ListObjectsV2` requests, zero Requester Pays S3 requests and zero metadata entries. The legacy release record remains immutable; consumption is recorded separately in `R2_EXECUTION_RELEASE_001_CONSUMPTION.json`. No rerun of release 001 is authorized.

Successor release `RELEASE_HL_ARCHIVE_NODEDATA_CANARY_R2_002` was reviewed in PR #37 at exact head `d8e0a4102e26b12f64d7871b274e65891e81b431`. Research CI run `31279273339`, job `93157850604`, passed all 185 tests, the byte-exact repository manifest, repository governance, the legacy R2 implementation validator and `R2_SUCCESSOR_RELEASE_VALID`. PR #37 was squash-merged as `6128e6a9974742113f74c6e17fba7159dc60bde5`, and remote `main` was independently compared as identical to that merge. The separate canonicalization record preserves those identities without rewriting the release snapshot.

Release 002 executed exactly once from canonical dispatch commit `5cf612b2125877a097b9697c074ac82d66cb1635` in run `31280640653`, job `93161240213`. The GitHub job completed successfully through canonical identity validation, successor single-use validation, AWS OIDC, the bounded five-prefix collector, artifact upload and the final exact-result gate. Artifact `9028305474` is 39,364 bytes and has provider SHA-256 `491e651ab5b434c2c7489a4ec194a10f42cce50e80d801a3bb816c3e6b5144c8`; the independently hashed uploaded ZIP matches exactly, and its internal ledger matches the retained context, raw result and return-code bytes.

The canary issued exactly five S3 HTTP requests, one first-page `ListObjectsV2` per frozen family, and all five succeeded with `request_charged=requester`. It retained 125 metadata entries in 38,693 response bytes over 2.340922 seconds, used zero retries, followed no pagination or redirects, requested no object body, performed no decompression and ingested no market data. Every family returned 25 objects with `IsTruncated=true` and a continuation token present. Therefore first-page metadata listability is proven, but archive completeness is explicitly not proven. No continuation-token value was retained and no continuation request occurred.

Release 002 is consumed by that successful first dispatch. No rerun is authorized. This infrastructure/access result is not object-body evidence, schema evidence, wallet intelligence, P&L or alpha evidence. The larger 300-request inventory, any pagination, object bodies, decompression, market-data ingestion, wallet analysis and all trading/capital stages remain separately unauthorized.

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
r2_successor_release_canonical = true
r2_successor_release_commit = 6128e6a9974742113f74c6e17fba7159dc60bde5
r2_successor_release_exact_head = d8e0a4102e26b12f64d7871b274e65891e81b431
r2_successor_release_consumed = true
r2_successor_release_consumption_status = CONSUMED_BY_RUN_31280640653_SUCCESS
r2_successor_run_id = 31280640653
r2_successor_job_id = 93161240213
r2_successor_artifact_id = 9028305474
r2_successor_artifact_sha256 = 491e651ab5b434c2c7489a4ec194a10f42cce50e80d801a3bb816c3e6b5144c8
r2_successor_terminal_status = R2_NODEDATA_METADATA_CANARY_PASS
r2_successor_technical_result = FIVE_PREFIX_METADATA_LISTABLE
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
r2_s3_requests_executed = 5
r2_metadata_entries_observed = 125
r10d_release_consumed = true
r10d_rerun_authorized = false
r10d_event_pair_observation_count = 1486542
r10d_legacy_wallet_tid_repeat_count = 0
r10d_canonical_identity_backward_consistency = UNKNOWN
r11_run_id = 31436753081
r11_job_id = 93612467250
r11_artifact_id = 9082810554
r11_dispatch_sha = baca1925c23ef6b0136aa3d96d6d479ac7717bdf
r11_run_attempt = 1
r11_release_consumed = true
r11_remaining_get_object_budget = 0
r11_rerun_authorized = false
r11_completed_hour_count = 72
r11_completed_day_count = 3
r11_successful_get_object_requests = 72
r11_failed_requests = 0
r11_retries_used = 0
r11_wallet_feature_retained = false
r11_preregistered_duplicate_count_retention_met = false
r11_duplicate_root_cause_known = false
r11_closed = false
r12_ready = false
r11_evidence_closure_merge = f7aa612d2a5638cce0fd197f57efea4b787f87f1
r10d_backward_consistency_class = C_R10D_UNCERTAIN_UNDER_CANONICAL_IDENTITY
r11a_preregistered_no_execution = true
r11a_corrective_implementation_id = R11A_CORRECTIVE_IMPLEMENTATION_R7
r11a_corrective_implementation_sealed = true
r11a_clean_context_review_complete = false
r11a_amendment_002_present = false
r11a_official_pricing_eur_binding_complete = false
r11a_owner_approval_present = false
r11a_workflow_installed = false
r11a_release_present = false
r11a_aws_oidc_authorized = false
r11a_get_object_authorized = false
r11a_decompression_authorized = false
r11a_empirical_root_cause_known = false
r11a_repair_authorized = false
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

All release-scoped R2 execution flags are false after consumption of release 002. The broader global archive flags remain false as well.

## Exact next gate

1. Preserve the canonical R11 evidence closure at merge `f7aa612d2a5638cce0fd197f57efea4b787f87f1`; never rerun or rewrite its immutable release snapshot.
2. Independently review the separately sealed corrective R11A V2 R7 implementation. Its workflow candidate must remain outside `.github/workflows`; no OIDC, S3 request or release may appear at this stage.
3. Preserve canonical Amendment 002 unchanged at its V2 path and exact binding. After exact-head CI, a new independent clean-context review and a later separate official pricing/EUR binding, request one new hash-bound owner approval for the dedicated successor role, exact 72-request / zero-retry envelope, byte/runtime/disk/artifact caps and EUR 0.50 one-time / EUR 0 monthly ceiling.
4. After approval, preserve separate workflow-installation, inert release-candidate and canonical single-use activation stages before one diagnostic run.
5. Root-cause-driven replay suppression or canonicalization, repaired wallet aggregation, repaired 72-hour validation, R11 closure and R12 readiness remain later evidence-gated stages. Wallet ranking, alpha/copyability claims and every trading/capital action remain unauthorized.
