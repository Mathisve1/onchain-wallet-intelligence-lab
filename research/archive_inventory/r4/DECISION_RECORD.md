# R4 decision record

## Decision

Preregister `HL-ARCHIVE-HOURLY-BODY-SCHEMA-PILOT-R4-001` as a static, non-executing successor to the successful R3 metadata inventory.

R3 proved a same-hour metadata transition at `2025-07-27T08:00:00Z`: legacy `node_fills/hourly/20250727/8.lz4` exists at the final legacy hour, and modern `node_fills_by_block/hourly/20250727/8.lz4` exists at the first modern hour. R3 did not download object bodies and therefore did not establish container readability, decompression success, body format, schema, semantic equivalence or wallet reconstruction feasibility.

R4 freezes exactly those two objects and no others. Their R3-observed compressed sizes sum to `14,243,987` bytes. A future approved implementation must use conditional `GetObject` with the exact observed ETag and exact content-length check; any mismatch fails closed rather than silently testing a changed object.

## Why not a larger body sample

The first body-access question is structural, not statistical: can the exact legacy/modern boundary objects be fetched unchanged and decoded sufficiently to compare observed schemas? Two same-hour objects answer that with the minimum object count. Additional days, `node_trades`, explorer data, wallet reconstruction or market ingestion would widen scope before this prerequisite is known.

## Data minimization

The proposed pilot does not retain raw compressed objects, decompressed payloads, record payloads, wallet addresses or payload values in evidence. A future implementation may stream object bytes through hashing, bounded LZ4-frame decompression and bounded UTF-8 NDJSON schema aggregation, then retain only hashes, sizes, counts, field paths/type sets/presence counts and a schema-comparison class.

## Fail-closed boundaries

- exactly two GET candidates; one request per object; zero retries;
- Requester Pays only after separate human approval and later single-use execution release;
- no HEAD, LIST, Range, redirects, alternate decompressor or fallback parser;
- exact `If-Match` ETag and content-length match required;
- maximum 512 MiB total decompressed bytes and 256 MiB per object;
- unknown LZ4 container, invalid UTF-8 or non-NDJSON does not trigger broader parsing;
- full uncensored parse is required for an `IDENTICAL_OBSERVED_SCHEMA` or subset/superset claim;
- no semantic equivalence, wallet reconstruction, clustering, copyability, P&L/alpha or trading inference.

## Budget state

The preregistration proposes a conservative `EUR 0.10` one-time ceiling and `EUR 0` monthly ceiling. This is not an authorization. Pricing must be rechecked before any future execution approval because Requester Pays can charge the requester for both S3 requests and downloaded data.

## Current authority

All R4 network, body-download and decompression authority is `false`. No executable R4 workflow or collector is introduced by this preregistration.
