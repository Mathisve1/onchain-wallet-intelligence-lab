# HL-ARCHIVE-INVENTORY-001 status

- phase: `R3_HOURLY_METADATA_APPROVAL_UNDER_REVIEW_NO_EXECUTION`
- parent public probe: `ATTESTED_PUBLIC_PROBE_PASS`
- AWS identity: `ATTESTED_STS_IDENTITY_MATCH`
- exact node-data Region: `ap-northeast-1`
- R0 release: `CONSUMED_BY_RUN_31260043109`
- R0 result: `ATTESTED_CONSUMED_PARTIAL_FAILURE_REGION_UNRESOLVED`
- Region probe release: `CONSUMED_BY_RUN_31273770895`
- Region probe result: `REGION_PROBE_R1_PASS`
- R2 first release: `CONSUMED_PRE_OIDC_ZERO_S3`
- R2 successor release: `CONSUMED_BY_RUN_31280640653_SUCCESS`
- R2 canonical attestation merge: `1790d6e3e2453cd96504b0f6624ca37c3847324a`
- R2 run / job / artifact: `31280640653` / `93161240213` / `9028305474`
- R2 artifact SHA-256: `491e651ab5b434c2c7489a4ec194a10f42cce50e80d801a3bb816c3e6b5144c8`
- R2 result: `R2_NODEDATA_METADATA_CANARY_PASS` / `FIVE_PREFIX_METADATA_LISTABLE`
- R2 observed requests / success / failure: `5 / 5 / 0`
- R2 observed metadata entries / response bytes / collector runtime: `125 / 38693 / 2.340922 sec`
- R2 first pages: `5/5 truncated`; continuation token present on all five; token values not retained
- R2 current execution ready: `false`
- R2 current Requester Pays / LIST / paid request authorization: `false / false / false`
- R2 rerun authorized: `false`
- R2 object-body / decompression / market-data ingestion: `false / false / false`
- larger 300-request inventory authorized: `false`
- all trading/capital authorizations: `false`

## R3 approval state

- R3 ID: `HL-ARCHIVE-HOURLY-METADATA-INVENTORY-R3-001`
- canonical preregistration commit: `ab4d42be02fe49d7f90f933317ef856f0322fd85`
- immutable preregistration status: `PREREGISTERED_STATIC_AWAITING_SEPARATE_HUMAN_SCOPE_BUDGET_APPROVAL`
- human approval ID: `APPROVE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001`
- human approval status on this branch: `EXACT_SCOPE_AND_BUDGET_APPROVAL_RECORDED_AWAITING_CANONICAL_MERGE`
- approval recorded at UTC: `2026-08-09T05:35:00Z`
- exact approval text SHA-256: `3c3931133fb8b0dd322d7a296b7b70fca65dd341401a6eda2b6372938ed6cd10`
- target bucket / Region: `hl-mainnet-node-data` / `ap-northeast-1`
- exact prefixes:
  - `node_fills_by_block/hourly/`
  - `node_fills/hourly/`
  - `node_trades/hourly/`
- approved maximum keys/request: `1000`
- approved maximum pages/family: `16`
- approved maximum total LIST requests: `48`
- approved maximum total entries: `48000`
- approved maximum aggregate response bytes: `33554432` (32 MiB)
- approved maximum runtime: `300 seconds`
- approved maximum retries/request: `0`
- approved pagination / continuation following: `true / true`, only within the same frozen prefix
- continuation token values retained: `false`
- repeated continuation token fails closed: `true`
- redirect following / StartAfter / Delimiter: `false / false / false`
- approved one-time / monthly budget: `EUR 0.10 / EUR 0`
- implementation/review lane authorized by human approval: `true`
- implementation installed: `false`
- workflow installed: `false`
- execution release present: `false`
- network execution authorized: `false`
- current paid request / Requester Pays / ListObjectsV2 runtime authorization: `false / false / false`
- R3 S3 requests executed / entries observed: `0 / 0`
- R3 empirical result: `null`
- explorer-block inventory authorized: `false`
- replica-cmd inventory authorized: `false`
- `hyperliquid-archive` market-data / asset-context inventory authorized: `false / false`
- object-body access / decompression / market-data ingestion: `false / false / false`
- larger 300-request inventory authorized: `false`
- all trading/capital authorizations: `false`

## Approval boundary

The exact user approval is bound to canonical R3 preregistration commit `ab4d42be02fe49d7f90f933317ef856f0322fd85` and the exact 48-request / 16-page / three-prefix / EUR 0.10 envelope. On this branch it is only an approval record under review. It does not install code, install a workflow, create a release or execute AWS/S3.

After this approval record is canonically merged, the next lane is implementation/review only. A separately reviewed implementation and separately reviewed single-use execution release remain mandatory before any R3 network request. The first later dispatch must consume that release regardless of PASS/FAIL.

The old 300-request inventory, explorer/replica inventory, object bodies, decompression, market-data ingestion, wallet analysis and all trading/capital stages remain unauthorized.
