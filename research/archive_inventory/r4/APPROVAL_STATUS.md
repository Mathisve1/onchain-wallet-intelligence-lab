# R4 approval status

- pilot: `HL-ARCHIVE-HOURLY-BODY-SCHEMA-PILOT-R4-001`
- canonical preregistration reviewed commit: `25a1f621d15cb708a485893025f03b991628aae1`
- human approval ID: `APPROVE_HL_ARCHIVE_HOURLY_BODY_SCHEMA_PILOT_R4_001`
- exact approval text SHA-256: `e52399feb7a0d36959089f556dd9f55062eb91d52feaa4c5af680d3c4e557264`
- approval status: `APPROVED_SCOPE_AND_BUDGET_AWAITING_IMPLEMENTATION`
- implementation phase authorized: `true`

The human approved the exact two-object, EUR 0.10 maximum one-time scope preregistered in R4. This approval may open only implementation and review work. It is not a network release and does not by itself authorize a paid S3 request.

## Approved implementation envelope

- bucket / Region: `hl-mainnet-node-data` / `ap-northeast-1`
- exact object count: `2`
- exact keys: `node_fills/hourly/20250727/8.lz4`; `node_fills_by_block/hourly/20250727/8.lz4`
- exact R3 compressed bytes: `14,243,987`
- maximum future GetObject requests: `2`; one request per object; zero retries
- exact ETag `If-Match` and exact content-length continuity required
- proposed-and-now-approved maximum one-time / monthly budget: `EUR 0.10 / EUR 0`
- bounded LZ4-frame streaming and bounded UTF-8 NDJSON-object schema aggregation are within approved implementation scope

## Current runtime authority remains closed

- paid S3 request currently authorized: `false`
- Requester Pays currently authorized: `false`
- GetObject currently authorized: `false`
- decompression currently authorized: `false`
- execution workflow installed: `false`
- execution release present: `false`
- execution ready: `false`
- requests executed / compressed bytes downloaded / decompressed bytes processed: `0 / 0 / 0`
- empirical result: `null`

HEAD, Range GET, LIST, object-version listing, account-wide listing, redirects, alternate decompressor fallback, raw compressed/decompressed payload retention, record payload retention, wallet-address retention, payload-value retention, semantic-equivalence inference, wallet reconstruction, clustering, copyability analysis, P&L/alpha analysis and market-data ingestion remain forbidden.

All integration, paper, shadow, live, leverage and capital-allocation authorizations remain `false`.

A separately reviewed implementation, exact-head CI, clean-context review and a later separately reviewed single-use execution release are mandatory before any R4 AWS/S3 request.
