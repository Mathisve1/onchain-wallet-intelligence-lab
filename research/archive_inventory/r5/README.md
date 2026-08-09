# R5 — Legacy format fingerprint

R5 is the minimal successor to the consumed R4 body/schema pilot.

## Current state

`PREREGISTERED_STATIC_NO_EXECUTION`

There is no R5 workflow, collector, execution release, approval record or AWS role mutation in this stage. CI for this preregistration must remain network-free.

## Research question

What serialization/container shape is used by the exact legacy boundary object `node_fills/hourly/20250727/8.lz4` after standard LZ4 decompression?

R4 already proved the exact object is retrievable, integrity-bound and decompressible, but R4 intentionally required top-level-object NDJSON and therefore left the legacy body unresolved.

## Primary hypothesis

The legacy object is line-delimited JSON where each record is a two-element array containing one string and one fill-like object. This is inferred from the modern R4 structural evidence and current official Hyperliquid documentation; it is not yet an empirical R5 result.

## Future bounded execution if approved

A later, separately reviewed implementation may issue at most one Requester Pays `GetObject` for the exact R4-bound object, with exact ETag, content length, compressed SHA-256 and decompressed byte-count checks. No HEAD, Range, LIST, retries or redirects are proposed.

The classifier may retain structural aggregates only. It may not retain payload values, strings, numbers, wallet addresses, raw compressed/decompressed bytes or record payloads.

## Boundary

R5 cannot identify wallets, reconstruct entities, analyze copyability, compute PnL/alpha, ingest market data or authorize any trading stage. Those remain separate future gates.

R4 is consumed and must not be rerun.
