# R10B static primary-source assessment

Date: 2026-08-10

Status: **STATIC_SOURCE_ASSESSMENT_ONLY — NO NETWORK EXECUTION AUTHORITY**

## Canonical empirical parent

R10A canonical evidence merge: `93e47e23b50068b24bcc0aa3aa1cc9d99891b8e6`.

R10A run `31386230522` made exactly one approved Requester Pays `GetObject` for `node_fills_by_block/hourly/20250727/9.lz4`. It observed 223,950 fill timestamps: 223,948 inside `[09:00:00Z,10:00:00Z)`, exactly two before the lower bound, no fills after the upper bound, and an earliest fill at `08:59:59.949Z` (51 ms before the path-hour lower bound). Under R10A's preregistered rule requiring an explicit `Z` or numeric timezone offset, all 36,029 `block_time` strings were unparseable and all 36,029 `local_time` strings lacked an explicit timezone.

This proves that exact fill-time/path-hour equality is false for that object. It does not prove what timestamp defines the hourly file partition and does not justify a 51 ms tolerance.

## Primary sources reviewed

1. Hyperliquid official Historical data documentation:
   `https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data`

   Directly supports that `s3://hl-mainnet-node-data/node_fills_by_block` contains fills streamed from a non-validating node using `--write-fills --batch-by-block`.

2. Hyperliquid official node repository README:
   `https://github.com/hyperliquid-dex/node`

   Directly supports that `--write-fills` streams fills to the node's hourly fill output and that `--batch-by-block` writes one block per line using the schema `{local_time, block_time, block_number, events}`. The README also distinguishes `--batch-by-block` from `--stream-with-block-info`, which writes events as they are processed while using the same block-metadata schema.

3. Hyperliquid official L1 data schemas documentation:
   `https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/nodes/l1-data-schemas`

   Directly documents node hourly output schemas and shows timestamp strings elsewhere in node outputs without an explicit timezone suffix. It does not define the semantics or timezone of `local_time` or `block_time` in the batched fill schema.

## What the primary sources do and do not establish

The sources establish the producer lineage and the existence of block-level metadata. They do **not** state that the `[date]/[hour]` path is partitioned by each fill's API `time`, nor do they define the timezone or exact rollover semantics of `local_time` or `block_time`.

Therefore the R10 failure must not be repaired by silently adding a fill-time grace interval. The next empirical question should be narrower: characterize the lexical forms and path-prefix relationship of the two batch metadata fields without inferring a timezone or retaining individual values.

## Proposed R10B purpose

R10B is a one-object lexical-format diagnostic over the same immutable hour-9 object. It would inspect only top-level `local_time` and `block_time` strings and aggregate lexical classifications/prefix counts. It would not inspect event-pair contents, retain wallet addresses, process economic fill fields, infer timezones, amend the R10 rule, or authorize a six-hour rerun.

Any R10B network request requires a new human approval and a later separate execution release/canonical activation.
