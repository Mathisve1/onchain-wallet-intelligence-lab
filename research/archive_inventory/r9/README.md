# R9 modern wallet feature pilot

R9 is the first proposed fill-derived **feature mechanics** gate after the R8A wallet-index bridge and R8B cutover forensics.

It is deliberately not a wallet-ranking or profitability study. The target `node_fills_by_block/hourly/20250727/8.lz4` is transition-censored by R8B and is therefore used only as an already integrity-bound serializer/feature-pipeline fixture. A successful R9 run would show that selected fill fields can be reduced deterministically to a bounded one-row-per-wallet aggregate table; it would not make the hour historically representative or identify good traders.

The proposed output retains only:

- wallet address and fill count;
- per-wallet first/last fill time;
- distinct coin count;
- A/B side counts;
- crossed-true count;
- liquidation-associated fill count;
- duplicate-TID count;
- exact-decimal sum of `abs(px * sz)` as a notional proxy;
- exact-decimal sum of the raw `closedPnl` field as a fill-derived statistic.

Individual coins, sides, prices, sizes, `closedPnl` values, TIDs, liquidation payloads and raw fills are not proposed for retention. Fees, `dir`, `startPosition`, transaction hashes and order identifiers are not processed in this pilot.

`sum_closed_pnl_fill_statistic` is explicitly **not** exact account return or a ranking score. R9 authorizes no multi-hour ingestion, shortlist, public-API enrichment, PnL/alpha analysis, copyability analysis, strategy inference or trading/capital action.

Current state: preregistered with zero runtime authority, awaiting a separate exact human approval after canonical merge.
