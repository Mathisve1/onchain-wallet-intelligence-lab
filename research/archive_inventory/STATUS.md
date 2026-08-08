# HL-ARCHIVE-INVENTORY-001 status

- phase: `R3_HOURLY_METADATA_INVENTORY_PREREGISTRATION_UNDER_REVIEW_NO_EXECUTION`
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

## R3 static preregistration

- R3 ID: `HL-ARCHIVE-HOURLY-METADATA-INVENTORY-R3-001`
- status: `PREREGISTERED_STATIC_AWAITING_SEPARATE_HUMAN_SCOPE_BUDGET_APPROVAL`
- parent R2 attestation commit: `1790d6e3e2453cd96504b0f6624ca37c3847324a`
- purpose: complete-or-censored metadata enumeration of the three hourly fill/trade keyspaces before any object-body pilot
- target bucket / Region: `hl-mainnet-node-data` / `ap-northeast-1`
- exact prefixes:
  - `node_fills_by_block/hourly/`
  - `node_fills/hourly/`
  - `node_trades/hourly/`
- proposed maximum keys/request: `1000`
- proposed maximum pages/family: `16`
- proposed maximum total LIST requests: `48`
- proposed maximum total entries: `48000`
- proposed maximum aggregate response bytes: `33554432` (32 MiB)
- proposed maximum runtime: `300 seconds`
- proposed maximum retries/request: `0`
- proposed pagination / continuation following: `true / true`, only after separate approval and only within the same frozen prefix
- continuation token values retained: `false`
- proposed redirect following / StartAfter / Delimiter: `false / false / false`
- proposed one-time / monthly budget: `EUR 0.10 / EUR 0`
- current approved one-time budget: `null`
- current implementation authorization: `false`
- current workflow installation authorization: `false`
- current execution release present: `false`
- current network execution authorization: `false`
- current paid request / Requester Pays / ListObjectsV2 authorization: `false / false / false`
- R3 S3 requests executed / entries observed: `0 / 0`
- R3 empirical result: `null`
- explorer-block inventory authorized: `false`
- replica-cmd inventory authorized: `false`
- `hyperliquid-archive` market-data / asset-context inventory authorized: `false / false`
- object-body access / decompression / market-data ingestion: `false / false / false`
- larger 300-request inventory authorized: `false`
- all trading/capital authorizations: `false`

## Why R3 is narrower than the old parent proposal

R2 empirically showed an hourly path shape for `node_fills_by_block`, `node_fills` and `node_trades`. R3 therefore targets only those three families and raises `MaxKeys` to the S3 maximum of 1000 while fixing a hard 16-page cap per family. The maximum request count falls from the old parent proposal of 300 to 48, an 84% reduction. Response cap falls from 256 MiB to 32 MiB, entry cap from 250,000 to 48,000, runtime from 900 to 300 seconds and retries from one to zero.

Sixteen pages provide capacity for at most 16,000 keys per family. At an idealized one-key-per-hour cadence this is about 666.7 days. That is only sizing logic, not an empirical archive-start or completeness claim. A family is complete only if a terminal page with `IsTruncated=false` is reached before all caps. Otherwise the result must be `CENSORED_BY_LIMIT` or another explicit incomplete state.

## Next gate

1. Complete exact-head CI, byte-exact manifest validation and clean-context review for the static R3 preregistration.
2. Merge only if R3 remains non-executing and all object/body, larger-inventory and trading gates remain closed.
3. Verify the actual canonical R3 preregistration merge SHA.
4. Require a fresh human approval exactly bound to that canonical SHA and the proposed EUR 0.10 / 48-request envelope.
5. Human approval would open only a later implementation/review lane. It would not itself install a workflow or execute S3.
6. A separately reviewed implementation and separately reviewed single-use execution release remain mandatory before any R3 network request.
