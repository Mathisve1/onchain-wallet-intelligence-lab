# HL-ARCHIVE-INVENTORY-001 status

- phase: `R3_HOURLY_METADATA_INVENTORY_ATTESTED_SUCCESS`
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
- canonical release-candidate merge: `6cd8ed06f311b6cda0a6e06c4d63f1cf05a9aad5`
- release PR / exact head / CI: `43` / `95dd5765728d2977cdf51b3ae13d6d76af93af2d` / `31299183537`
- canonical activation merge / dispatch SHA: `d2cc879ceb789c33ea7c6fe6ace17d1636de80ef`
- activation anchor / single-use window start: `4bc99701f6a24a045c84b205963685a2fe8c3122` / `2026-08-09T06:38:46Z`
- exact target / Region: `hl-mainnet-node-data` / `ap-northeast-1`
- exact prefixes: `node_fills_by_block/hourly/`, `node_fills/hourly/`, `node_trades/hourly/`
- approved hard envelope: max `48` LIST requests, `16` pages/family, `1000` keys/request, `48000` entries, `33554432` response bytes, `300` seconds, `0` retries
- approved one-time / monthly budget: `EUR 0.10 / EUR 0`

## R3 executed result

- release status: `CONSUMED_BY_RUN_31299905850_SUCCESS`
- rerun authorized: `false`
- run / job / artifact: `31299905850` / `93210902329` / `9034170863`
- artifact name: `hyperliquid-archive-hourly-metadata-r3-31299905850-1`
- artifact size: `471178` bytes
- provider and independently downloaded ZIP SHA-256: `1049509ef12f1ef2a312f6ded1d443b434e2ed860503a264f103a73c2a70cf88`
- terminal / technical result: `R3_HOURLY_METADATA_INVENTORY_PASS` / `THREE_HOURLY_FAMILIES_COMPLETE`
- requests attempted / S3 HTTP / successful / failed: `14 / 14 / 14 / 0`
- continuation requests: `11`
- total metadata entries / response bytes: `12119 / 3997072`
- collector runtime: `17.313515 sec`
- retries / redirects / StartAfter / Delimiter: `0 / 0 / false / false`
- Requester Pays requested: `true`
- continuation token values retained: `false`
- object body requested / decompression / market-data ingestion: `false / false / false`

### Complete family inventory

| family | pages | entries | earliest path hour UTC | latest path hour UTC | gap result |
|---|---:|---:|---|---|---|
| `node_fills_by_block` | 10 | 9070 | `2025-07-27T08:00:00Z` | `2026-08-09T05:00:00Z` | `NO_GAP_CLAIM` |
| `node_fills` | 2 | 1507 | `2025-05-25T14:00:00Z` | `2025-07-27T08:00:00Z` | `NO_GAP_CLAIM` |
| `node_trades` | 2 | 1542 | `2025-03-22T10:00:00Z` | `2025-06-21T09:00:00Z` | `PROVEN_KEY_GAP` |

The preregistered internal-hour gap rule proves `633` missing internal `node_trades` hourly keys from `2025-05-25T15:00:00Z` through `2025-06-20T23:00:00Z`. Boundary-day hours are intentionally excluded from that count; no broader completeness claim is made beyond the enumerated prefix.

The legacy `node_fills` latest path hour and modern `node_fills_by_block` earliest path hour are both exactly `2025-07-27T08:00:00Z` (`delta_hours=0`). This proves a metadata boundary overlap/same-hour transition, but does **not** prove body-schema equivalence or semantic continuity.

## Evidence integrity

- context raw SHA-256: `b117a43f991db5bab0e2721e936b1cf536ef918747fe87e90ad1c2974439a54b`
- result raw SHA-256: `94c3e77a05de2363b95abdce718dfd61f1b440f3d9c3972a0d03ce28a9edc479`
- return-code raw SHA-256: `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`
- internal artifact ledger: `PASS`
- provider digest vs independently downloaded ZIP: `MATCH`
- compact durable summary: `research/archive_inventory/r3/evidence/run-31299905850/R3_COMPACT_INVENTORY_SUMMARY.json`
- independent verification: `research/archive_inventory/r3/evidence/run-31299905850/INDEPENDENT_ARTIFACT_VERIFICATION.json`

## Closed capabilities after R3

- R3 execution ready / Requester Pays / ListObjectsV2: `false / false / false`; release consumed
- GetObject / HeadObject / GetObjectAttributes / range GET: `false`
- object-version or account-wide bucket listing: `false`
- explorer-block / replica-command inventory: `false / false`
- object-body download / decompression: `false / false`
- market-data ingestion: `false`
- larger 300-request inventory: `false`
- integration / paper / shadow / live / leverage / capital allocation: all `false`
- empirical trading result: `null`

## Next gate

R3 metadata inventory is complete and consumed. Do not rerun it. The next research gate is a separately preregistered, separately human-approved **minimal object-body/schema pilot** if body access is needed to determine whether the hourly archives can reconstruct wallet fills/trades. Any such pilot must bind exact object keys selected from this R3 metadata evidence, minimize bytes/objects, define decompression/schema limits, retain no unnecessary payload, and keep market ingestion and all trading/capital authorizations closed until separately reviewed.
