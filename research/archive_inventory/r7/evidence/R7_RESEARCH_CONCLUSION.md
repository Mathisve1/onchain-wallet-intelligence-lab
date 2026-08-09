# R7 research conclusion

## Terminal result

`WALLET_INDEX_RECONSTRUCTION_COMPLETE`

The canonical R7 run `31330248235` consumed the single-use R7 release and successfully reconstructed the exact approved one-hour legacy object into a deterministic wallet index.

The source object contained 162,815 nonempty `[string, object]` records. Those records were grouped into **4,637 unique lowercase address keys**. The retained output contains exactly two fields per row: `wallet_address` and `fill_count`. The wallet rows are unique, lexicographically sorted and the sum of all `fill_count` values is exactly 162,815.

The retained wallet-index file is 368,036 bytes with SHA-256 `2b8cbf709075aeda25394f22ee04b08656d5d165105976ed5d7e0890479e2d6d`.

## What R7 establishes

R7 gives the project its first durable, address-level Hyperliquid activity index for the frozen hour. It proves that the legacy archive can be deterministically reduced from global fill records to one row per address without retaining the fill payload itself.

## What R7 does not establish

R7 does **not** identify the human or economic entity behind an address. It does not classify bots, market makers, liquidators or discretionary traders. It does not calculate PnL, alpha, drawdown, consistency, copyability, slippage or follower profitability. It also says nothing about whether an address remains active outside the single observed hour.

No entity clustering, copyability analysis, PnL/alpha analysis, market-data ingestion, historical multi-hour ingestion or strategy inference was performed. All integration, paper, shadow, live, leverage and capital-allocation authorizations remain false.

## Next research gate

The next useful step is not to rank these 4,637 wallets yet. A one-hour fill count is only an activity signal. The next gate should be **static-first design and preregistration for historical persistence plus the minimum performance/copyability fields needed to evaluate wallets over time**. That design must decide the smallest defensible payload-field set, time horizon, sampling strategy, cost envelope and bot/market-maker exclusion logic before any broader archive download is authorized.

No further R7 dispatch or rerun is authorized. Any additional archive request requires a new preregistered successor scope and new human approval.
