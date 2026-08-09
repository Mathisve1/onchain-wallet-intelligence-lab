# HL-ARCHIVE-INVENTORY-001 status

- phase: `R3_RELEASE_CANDIDATE_UNDER_REVIEW_NO_EXECUTION`
- AWS identity: `ATTESTED_STS_IDENTITY_MATCH`
- exact node-data Region: `ap-northeast-1`
- R0 release: `CONSUMED_BY_RUN_31260043109`
- Region probe release: `CONSUMED_BY_RUN_31273770895`
- R2 successor release: `CONSUMED_BY_RUN_31280640653_SUCCESS`
- R2 canonical attestation merge: `1790d6e3e2453cd96504b0f6624ca37c3847324a`
- R2 result: `FIVE_PREFIX_METADATA_LISTABLE`
- R2 current execution ready / rerun authorized: `false / false`

## R3 canonical lineage

- R3 ID: `HL-ARCHIVE-HOURLY-METADATA-INVENTORY-R3-001`
- canonical preregistration commit: `ab4d42be02fe49d7f90f933317ef856f0322fd85`
- human approval ID: `APPROVE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001`
- canonical human approval merge: `e562f3fbd8f1dac1b4d7e93eed2f5ee6b77c5da6`
- exact approval text SHA-256: `3c3931133fb8b0dd322d7a296b7b70fca65dd341401a6eda2b6372938ed6cd10`
- canonical implementation merge: `3b1dd0df4c5194875e22c1b790e0b41961313aa8`
- implementation PR / exact head: `42` / `02681dbf13415f953fd3c79f66ee5de4919a169c`
- implementation CI run / job / tests: `31297902934` / `93205871178` / `236/236 PASS`
- implementation validator / manifest / governance: `R3_IMPLEMENTATION_VALID` / `BYTE_EXACT_PASS` / `PASS`
- exact target / Region: `hl-mainnet-node-data` / `ap-northeast-1`
- exact prefixes:
  - `node_fills_by_block/hourly/`
  - `node_fills/hourly/`
  - `node_trades/hourly/`
- approved hard envelope: max `48` LIST requests, `16` pages/family, `1000` keys/request, `48000` entries, `33554432` response bytes, `300` seconds, `0` retries
- approved one-time / monthly budget: `EUR 0.10 / EUR 0`
- pagination / continuation following after activation: `true / true`
- continuation token values retained: `false`
- repeated token / duplicate key: fail closed
- redirect / StartAfter / Delimiter: `false / false / false`

## R3 release candidate

- release candidate file: `research/archive_inventory/r3/R3_EXECUTION_RELEASE.json`
- release ID: `RELEASE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001`
- status: `RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION`
- exact implementation bound: `3b1dd0df4c5194875e22c1b790e0b41961313aa8`
- separate activation required: `true`
- activation record present: `false`
- canonical release merge: `null` until this release PR is merged
- single-use window start: `null` until separate activation record
- workflow expected implementation remains: `PENDING_CANONICAL_IMPLEMENTATION_MERGE`
- workflow therefore execution-capable after release-candidate merge alone: `false`
- current network execution authorized: `false`
- current paid request / Requester Pays / ListObjectsV2 runtime authorization: `false / false / false`
- current single workflow dispatch authorized: `false`
- rerun authorized: `false`
- R3 S3 requests executed / entries observed: `0 / 0`
- R3 empirical result: `null`

The release candidate is deliberately inert. It records the already-human-approved envelope and exact canonical implementation but does not activate it. Even after this release-candidate PR is merged, the workflow remains fail-closed before AWS OIDC because `EXPECTED_IMPLEMENTATION_COMMIT` is still `PENDING_CANONICAL_IMPLEMENTATION_MERGE` and the canonical activation record is absent.

A separate activation PR must be created from the actual release merge. That later PR must bind the exact release PR head, exact-head CI, actual canonical release merge SHA, a fresh single-use window start, and the unchanged scope. Only that later canonical activation may change the workflow gate from pending to the exact implementation commit and authorize exactly one `workflow_dispatch`.

## Closed capabilities

- GetObject / HeadObject / GetObjectAttributes / range GET: `false`
- object-version or account-wide bucket listing: `false`
- explorer-block / replica-command inventory: `false / false`
- object-body download / decompression: `false / false`
- `hyperliquid-archive` market-data or asset-context inventory: `false / false`
- market-data ingestion: `false`
- larger 300-request inventory: `false`
- integration / paper / shadow / live / leverage / capital allocation: all `false`

## Next gate

Require exact-head Research CI, `R3_RELEASE_CANDIDATE_VALID`, byte-exact repository-manifest validation and clean-context review. Merge only an exact reviewed release head. After merge, verify the actual canonical release SHA and build the separate activation PR. No AWS/S3 request is permitted during either release-candidate review or activation review.
