# R8 performance/copyability data design

R8 follows canonical R7 evidence merge `7802d741f193671e50356c6001dcae149e0fc88a`.

R7 produced the first exact one-hour address index: 4,637 unique wallets accounting for all 162,815 fills. R8 deliberately does not rank those wallets. It defines the minimum data and sequencing required to make later profitability and copyability research defensible.

Key decision: use population-wide archive fills for the first screening layer, then enrich only a reduced shortlist through public user-specific endpoints. Treat fill-derived `closedPnl` as a screening statistic rather than exact account return, and keep copyability/execution research separate from source-wallet performance research.

The first empirical prerequisite is R8A, a one-object modern `node_fills_by_block` bridge. R8A is preregistered but inert and requires a new exact human approval after this R8 design is canonically merged.

No network, ranking, PnL scoring, copyability scoring, entity clustering, strategy inference or trading authority is opened by R8.
