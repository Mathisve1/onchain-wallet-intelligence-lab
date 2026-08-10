# R10C static primary-source assessment

## Scope

This assessment is intentionally narrower than a timestamp-semantics study. It asks whether official Hyperliquid sources resolve the exact R10A/R10B boundary anomaly strongly enough to change the existing fail-closed rule without another bounded observation.

## What the official sources support

The official `hyperliquid-dex/node` repository documents `--write-fills` as streaming fills in API fills format to the node fill output. It documents `--batch-by-block` as writing the relevant node outputs with one block per line and gives the batched schema as `{local_time, block_time, block_number, events}`, where `events` is a list.

The official Hyperliquid latency documentation additionally states that `--batch-by-block` waits until the end of the block to write the data.

The official Hyperliquid historical-data documentation states that `s3://hl-mainnet-node-data/node_fills_by_block` contains fills streamed via `--write-fills --batch-by-block` from a non-validating node and notes that the requester pays data-transfer costs.

Primary sources reviewed:

- https://github.com/hyperliquid-dex/node
- https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data
- https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/optimizing-latency

## What the reviewed sources do not establish

The reviewed official sources do **not** define the timezone semantics of the serialized `local_time` or `block_time` strings in the batch record.

They do **not** state that the S3 hourly path partition for `node_fills_by_block` is defined by `local_time`, `block_time`, or the fill payload's integer `time` field.

They do **not** define a safe timestamp tolerance for fills that fall just outside a path-hour boundary. The R10A observation of an earliest `-51 ms` offset therefore does not justify a 51 ms tolerance or any other general boundary rule.

They also do not establish whether the single R10B record whose raw `block_time` prefix is `2025-07-27T08:` is the same record that contains the two R10A fill timestamps below the frozen path-hour lower bound.

## Consequence for R10C

Static primary sources therefore cannot resolve the exact anomaly without an additional observation. R10C is preregistered as the smallest empirical correlation that can answer the remaining record-level question without retaining individual metadata values, fill timestamps, addresses, block numbers, raw events, or economic fill fields.

R10C may classify only aggregate co-location under frozen raw-prefix and integer-millisecond partition rules. It may not infer timezone semantics, declare which field defines S3 partitioning, authorize a tolerance, amend R10, rerun R10, execute the six-hour feature pipeline, rank wallets, analyze PnL/alpha or copyability, ingest market data, infer strategy, or open any trading/capital authority.
