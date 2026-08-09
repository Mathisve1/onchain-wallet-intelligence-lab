# R4 — minimal hourly body/schema pilot

`HL-ARCHIVE-HOURLY-BODY-SCHEMA-PILOT-R4-001` is the static successor to the fully attested R3 hourly metadata inventory.

## Parent evidence

Canonical R3 evidence merge: `98eca5b7b13b25aed3d11f006972acea2ee5c258`.

R3 proved complete metadata enumeration for the three hourly families and established that legacy `node_fills` ends at the exact hour modern `node_fills_by_block` begins: `2025-07-27T08:00:00Z`. R3 did not fetch any object body.

## Frozen R4 objects

| role | key | R3 size bytes | R3 ETag |
|---|---|---:|---|
| legacy boundary | `node_fills/hourly/20250727/8.lz4` | 12,726,384 | `"b21cdc16a4ec69d9c5b72c0c27ff148d-2"` |
| modern boundary | `node_fills_by_block/hourly/20250727/8.lz4` | 1,517,603 | `"60d4c1277f76651b5f04666bbe8d7594"` |

Total selected compressed size: `14,243,987` bytes.

## What a future approved pilot may test

1. Conditional Requester Pays `GetObject` for exactly the two frozen keys.
2. Exact content-length and ETag continuity with R3 metadata.
3. Streaming SHA-256 over compressed bytes.
4. Bounded LZ4-frame recognition/decompression.
5. Bounded UTF-8 newline-delimited JSON-object parsing.
6. Aggregate schema signatures only: field paths, observed JSON type sets, presence counts, nesting depth, record counts and a comparison class.

## What it may not do

No additional keys, LIST, HEAD, Range GET, retries, redirects, alternate decompressor/parser fallback, raw-body retention, record retention, wallet extraction, entity clustering, copyability analysis, P&L/alpha research, market-data ingestion or trading/capital action.

## Governance state

This directory contains preregistration only. `get_object_authorized=false`, `object_body_download_authorized=false`, `decompression_authorized=false`, `execution_authorized=false`.

A fresh exact human approval against the canonical R4 preregistration commit is mandatory before implementation. Even after approval, a separately reviewed single-use execution release remains mandatory before any AWS/S3 request.
