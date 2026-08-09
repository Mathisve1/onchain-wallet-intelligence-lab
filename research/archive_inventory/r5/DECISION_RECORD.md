# R5 decision record — legacy format fingerprint

## Decision

R5 will resolve only the serialization/container format of the exact legacy `node_fills/hourly/20250727/8.lz4` boundary object already observed in R4.

R5 is not a rerun of R4. R4 is consumed permanently. A future R5 execution, if separately approved and released, is a new experiment with a narrower research question and its own single-use gate.

## Why this is the next minimal experiment

R4 proved transport, object identity, LZ4 framing and decompression for the legacy object. It failed only at the preregistered requirement that every NDJSON record be a top-level JSON object.

R4 simultaneously proved that the modern `node_fills_by_block` body contains an `events` array whose event entries are arrays and whose members include both `string` and `object` types. Official Hyperliquid documentation states that `node_fills` matches API fills format and that `node_fills_by_block` is the block-batched form written by `--write-fills --batch-by-block`.

The most economical next hypothesis is therefore that legacy data writes the event array directly per line instead of wrapping events in a block object. That hypothesis is plausible but not yet evidence.

## Primary preregistered hypothesis

`LEGACY_IS_LINE_DELIMITED_TWO_ELEMENT_JSON_ARRAY_EVENTS`

The more specific candidate structure is one string member plus one object member. R5 may record the type signature `[string, object]` or `[object, string]`, but it may not label the string as a wallet/user address and may not retain its value.

## Fail-closed alternatives

The classifier has a fixed precedence and may identify another declared JSON container class. If none resolves under the frozen classifier, R5 ends `LEGACY_FORMAT_UNRESOLVED`. No ad-hoc parser or alternate decompressor may be introduced during the run.

## Data minimization

Only structural aggregates may survive the process: root-type counts, array arity/type-signature counts, object field names/type sets/presence counts, nesting depth and the final format class. Raw compressed data, decompressed data, record payloads, strings, numbers, wallet addresses and other payload values are not retained.

## What R5 cannot establish

Even a perfect `[string, object]` resolution does not establish that the string is a wallet, that the object has identical semantics to modern fills, that historical wallet reconstruction is correct, or that any wallet is copyable or profitable.

All wallet reconstruction, clustering, copyability, PnL/alpha, market-data ingestion, integration, paper, shadow, live, leverage and capital-allocation gates remain closed.
