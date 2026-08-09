# HL-ARCHIVE-INVENTORY-001 status

- phase: `R3_CANONICAL_ACTIVATION_UNDER_REVIEW_NO_EXECUTION`
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
- pagination / continuation following within activated scope: `true / true`
- continuation token values retained: `false`
- repeated token / duplicate key: fail closed
- redirect / StartAfter / Delimiter: `false / false / false`

## R3 canonical release candidate

- release candidate file: `research/archive_inventory/r3/R3_EXECUTION_RELEASE.json`
- release ID: `RELEASE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001`
- immutable candidate status: `RELEASE_CANDIDATE_AWAITING_CANONICAL_ACTIVATION`
- release PR / exact head: `43` / `95dd5765728d2977cdf51b3ae13d6d76af93af2d`
- release exact-head CI run / job / tests: `31299183537` / `93209089110` / `244/244 PASS`
- release validator / manifest / governance: `R3_RELEASE_CANDIDATE_VALID` / `BYTE_EXACT_PASS` / `PASS`
- canonical release-candidate merge: `6cd8ed06f311b6cda0a6e06c4d63f1cf05a9aad5`
- release merge independently compared with `main`: `identical`
- release candidate content SHA-256: `c64719a8e9b8a82a361dcc7e4b03c12fba8027cd8d1e72bfc05487a2ef6ad55b`
- candidate runtime Requester Pays / ListObjectsV2 / dispatch authority: `false / false / false`
- candidate execution ready: `false`
- candidate rerun authorized: `false`

The canonical release candidate remains an immutable, inert snapshot. It is not rewritten to create authority. Runtime scope is represented only by the separate activation overlay below.

## R3 canonical activation candidate

- activation overlay: `research/archive_inventory/r3/R3_EXECUTION_RELEASE_CANONICALIZATION.json`
- activation record present on review branch: `true`
- activation status: `RELEASED_FOR_EXACTLY_ONE_CANONICAL_R3_RUN`
- activation anchor commit: `4bc99701f6a24a045c84b205963685a2fe8c3122`
- single-use window start: `2026-08-09T06:38:46Z`
- activation is bound to canonical release merge: `6cd8ed06f311b6cda0a6e06c4d63f1cf05a9aad5`
- activation is bound to canonical implementation: `3b1dd0df4c5194875e22c1b790e0b41961313aa8`
- active overlay Requester Pays / ListObjectsV2 / single dispatch scope: `true / true / true`
- active overlay pagination / continuation-token following: `true / true`
- active overlay rerun authorized: `false`
- activation review branch itself network-executable: `false`; workflow requires `refs/heads/main`
- authority becomes effective only after exact activation head is reviewed, CI-green and canonically merged to `main`
- activation PR/CI AWS or S3 execution: `forbidden`
- R3 S3 requests executed / entries observed: `0 / 0`
- R3 empirical result: `null`

The workflow candidate is bound to the exact implementation commit and the separate canonicalization overlay. Before AWS OIDC it must re-run the complete tests, repository governance, implementation/release/activation lineage checks, the exact approved envelope, canonical `workflow_dispatch` + `refs/heads/main` identity and the single-use run-history gate. A re-run is forbidden. The first eligible canonical dispatch after the immutable anchor consumes the activation whether later execution passes or fails.

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

Complete the activation implementation without making any AWS/S3 request. Require exact-head Research CI, `R3_IMPLEMENTATION_VALID`, `R3_RELEASE_CANDIDATE_VALID`, `R3_ACTIVATION_VALID`, byte-exact repository-manifest validation and clean-context review. Merge only the exact reviewed activation head. After merge, verify the actual activation merge is canonical `main`; only then may exactly one manual R3 workflow dispatch occur within the approved envelope. The first eligible dispatch consumes the single-use activation regardless of PASS or FAIL.
