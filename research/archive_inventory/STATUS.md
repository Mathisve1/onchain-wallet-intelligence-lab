# HL-ARCHIVE-INVENTORY-001 status

- phase: `R3_HOURLY_METADATA_IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION`
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
- approved one-time / monthly budget: `EUR 0.10 / EUR 0`
- exact target / Region: `hl-mainnet-node-data` / `ap-northeast-1`
- exact prefixes:
  - `node_fills_by_block/hourly/`
  - `node_fills/hourly/`
  - `node_trades/hourly/`
- hard envelope: max `48` LIST requests, `16` pages/family, `1000` keys/request, `48000` entries, `33554432` response bytes, `300` seconds, `0` retries
- approved pagination / continuation following: `true / true` only inside the same frozen prefix
- continuation token values retained: `false`
- repeated continuation token fails closed: `true`
- redirect / StartAfter / Delimiter: `false / false / false`

## R3 implementation candidate

- implementation contract: `PRESENT_UNDER_REVIEW`
- collector: `PRESENT_DIRECT_SIGV4_BOUNDED_PAGINATION`
- workflow: `PRESENT_MANUAL_ONLY_RELEASE_GATED_BEFORE_OIDC`
- expected canonical implementation commit: `PENDING_CANONICAL_IMPLEMENTATION_MERGE`
- execution release required: `true`
- execution release present: `false`
- implementation merge itself authorizes execution: `false`
- current network execution authorized: `false`
- current paid request / Requester Pays / ListObjectsV2 runtime authorization: `false / false / false`
- R3 S3 requests executed / entries observed: `0 / 0`
- R3 empirical result: `null`

The collector increments the request count before transport, never retries, never follows HTTP redirects, never uses `StartAfter` or `Delimiter`, retains continuation-token presence but not token values, rejects duplicate object keys, rejects repeated continuation tokens before another request, and stops a family at page 16 as `CENSORED_BY_LIMIT` rather than claiming completeness. Gap claims are allowed only for completely enumerated families with valid hourly key grammar; boundary dates are not automatically gap-tested.

The workflow is `workflow_dispatch` only and is deliberately unusable for AWS execution during this implementation review: `EXPECTED_IMPLEMENTATION_COMMIT` remains `PENDING_CANONICAL_IMPLEMENTATION_MERGE` and `R3_EXECUTION_RELEASE.json` is absent. The pre-OIDC gate must fail before role assumption if either binding is missing.

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

Run exact-head Research CI, byte-exact repository-manifest validation, the dedicated R3 implementation validator and clean-context review. Merge only an exact reviewed head. After merge, verify the actual canonical implementation SHA and create a separate exact-SHA-bound single-use R3 execution release. No AWS/S3 request is permitted before that later release is separately reviewed and canonical.
