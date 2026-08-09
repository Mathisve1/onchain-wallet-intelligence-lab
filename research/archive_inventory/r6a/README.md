# R6A — Legacy user-key lexical confirmation

R6A is the minimal empirical successor to the canonical R6 static provenance study.

## Current state

`PREREGISTERED_STATIC_NO_EXECUTION`

There is no R6A workflow, network collector, approval record, AWS/IAM mutation, execution release or runtime authority in this stage.

## Research question

Do **all** leading strings in the exact R5-bound legacy object `node_fills/hourly/20250727/8.lz4` match the lexical shape of a Hyperliquid onchain user address: exactly 42 characters and `0x` followed by 40 hexadecimal characters?

## Why this small empirical step exists

R6 established `HYPERLIQUID_USER_ADDRESS` as a **HIGH-confidence static inference** from historical official Hyperliquid sources that predate the target object. But R5 deliberately retained no string values or lexical-shape aggregates, so we have not directly confirmed the shape of the leading archive strings.

R6A closes only that remaining gap. It does not re-investigate the serialization format, does not inspect a second object and does not broaden into wallet intelligence.

## Proposed future execution if separately approved

A later reviewed implementation may issue at most **one** Requester Pays `GetObject` for the exact same integrity-bound object already used by R5. It must verify the exact ETag, content length, compressed SHA-256 and decompressed byte count before accepting a research result.

The classifier may retain **counts only**:

- nonempty record count;
- `[string, object]` record count;
- leading-string count;
- length-42 count;
- `0x` + 40-hex count;
- lowercase `0x` + 40-hex count;
- nonmatching count.

It may not retain any leading string, wallet address, hash of a leading string, distinct-address set, payload value, record payload, raw compressed object or decompressed body.

## Interpretation boundary

A result where every leading string matches the expected address shape may strengthen R6's semantic inference. It still does not prove the real-world identity or control of any address and does not authorize storing addresses, reconstructing wallets, clustering entities, testing copyability, calculating P&L/alpha, ingesting market data or trading.

## Human gate

Because the proposed confirmation requires a new paid Requester Pays object read, it must stop after preregistration until a new explicit human scope-and-budget approval is bound to the canonical R6A preregistration commit. Approval alone remains non-executing; reviewed implementation and a separate single-use release would still be required afterward.
