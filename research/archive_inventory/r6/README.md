# R6 — Legacy user-key provenance

R6 follows the consumed R5 legacy-format fingerprint and asks one narrow question: **what does the leading string in each legacy `[string, object]` fill record represent?**

## Result

`LEADING_STRING_USER_ADDRESS_SEMANTICS_HIGH_CONFIDENCE_STATIC_INFERENCE`

The best-supported semantic label is `HYPERLIQUID_USER_ADDRESS`, but the status is deliberately limited to `SUPPORTED_INFERENCE_NOT_DIRECT_SERIALIZER_PROOF`.

## Why confidence is high

The evidence converges across independent official Hyperliquid surfaces and, importantly, the immutable historical evidence predates the exact archive object dated 2025-07-27:

1. On 2025-05-27, the official `hyperliquid-dex/node` repository documented `--write-fills` as writing fills in the **API fills format** to `node_fills/hourly/{date}/{hour}`.
2. On 2025-06-27, the same repository documented `--batch-by-block` as changing output from **one event per line** to one block per line. The legacy unbatched object is therefore from the one-event-per-line writer family.
3. Official Python SDK release `0.16.0`, published before the target object date, defines `Fill` without a `user` field while `UserFillsData` contains `user` separately from the list of fills.
4. The same historical SDK documents `user_fills(address)` with `address` as a 42-character onchain hexadecimal address and returns fill objects without an embedded user field.
5. The same SDK routes `userFills` websocket messages using `data.user`.
6. R5 empirically observed all 162,815 nonempty legacy records as exactly `[string, object]`, and the object carries the historical fill fields such as `coin`, `px`, `sz`, `side`, `time`, `startPosition`, `dir`, `closedPnl`, `hash`, `oid`, `crossed`, `fee`, `tid` and `feeToken`.

The convergent explanation is therefore that the first string is the Hyperliquid user/onchain account address associated with that fill.

## Why this is not called direct proof

The public node repository documents behavior but does not expose the node serializer implementation that would directly name the first tuple element. R5 also intentionally retained no string values, wallet addresses or lexical-shape aggregates. We therefore do **not** claim that we have directly inspected a value or proven that every first string is exactly `0x` plus 40 hexadecimal characters.

## Current boundary

R6 performs no AWS call, no S3 request, no object download and no payload inspection. It opens no authority to retain archive wallet addresses, reconstruct wallets, cluster entities, analyze copyability, calculate P&L/alpha, ingest market data, or enter integration/paper/shadow/live trading.

## Smallest remaining empirical gap

If we decide direct lexical confirmation is worth one additional paid archive access, the proposed R6A gate would re-read only the **same exact R5-bound object** and retain counts only: how many leading strings exist, how many are 42 characters, and how many match the `0x` + 40-hex address pattern. It would retain no actual string or wallet address.

R6A is only a proposal. It requires a separate explicit scope/budget approval and a separate release before any request can run.
