# R9 research conclusion

## Result

**`MODERN_WALLET_FEATURE_PIPELINE_COMPLETE`**

Canonical R9 run `31336490854` successfully retrieved the exact frozen modern fixture once, with zero retries and zero redirects, and reduced all 17,516 valid event pairs into 887 unique lexicographically sorted per-wallet feature rows.

The output conserves all fills and sides exactly. It retains only the preregistered aggregate fields and does not retain raw compressed/decompressed archive bytes, raw block records, event pairs, fill objects, individual prices, sizes, closed-PnL values, trade IDs, coin values, side values, crossed values, or liquidation payloads.

## What R9 proves

R9 proves that the selected modern `node_fills_by_block` shape can feed a deterministic bounded per-wallet feature reducer using exact decimal arithmetic and the approved selected transient fields. The feature pipeline therefore has a technically validated building block for a future historical population screen.

R9 also yields a new direct boundary observation from the permitted per-wallet time extrema: the earliest retained fill is `2025-07-27T08:50:10.273Z` and the latest is `2025-07-27T08:59:59.895Z`. The modern boundary object's observed fills therefore span only 589.622 seconds near the end of the shared path hour. This strengthens R8B's cutover inference.

## What R9 does not prove

The boundary fixture is not treated as historically representative. The shared `2025-07-27T08` hour remains censored from canonical merged history. R9 does not prove the exact legacy/modern cutover instant, fill-level continuity, absence of overlap or gap, wallet quality, strategy quality, exact account return, alpha, or copyability.

`sum_closed_pnl_fill_statistic` remains only a fill-derived aggregate. `sum_abs_px_times_sz_notional_proxy` remains only a notional proxy. Neither is a wallet ranking score.

No wallet ranking, candidate shortlisting, public-API enrichment, PnL/alpha analysis, entity clustering, copyability analysis, strategy inference, market-data ingestion, paper trading, shadow trading, live trading, leverage, or capital allocation was authorized or performed.

## Next gate

The next research step should be a separately preregistered **post-boundary multi-hour feature aggregation pilot** using only unambiguous modern path hours beginning at `2025-07-27T09`. Object selection and total request/byte/cost caps must be derived statically from the already retained R3 inventory before any further Requester Pays execution is proposed.

A multi-hour pilot should validate cross-object aggregation, hour coverage, deterministic deduplication/conservation and active-hour statistics before any wallet-ranking gate is opened.
