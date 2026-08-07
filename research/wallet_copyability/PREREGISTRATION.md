# Preregistration — WALLET-COPYABILITY-STUDY-001

## H1

There exists a point-in-time-identifiable subset of directional Hyperliquid
swing traders whose future positions retain positive follower expectancy after
executable bid/ask prices, latency, fees, funding and slippage.

## H0

Any apparent source-wallet skill disappears for the follower after correcting
for future-information leakage, survivorship, deposits, fees, funding, spread,
slippage, price impact, short holding periods, hidden hedges and false wallet
independence.

## Point-in-time rule

A feature or relationship is usable only when:

```text
first_seen_at <= selection_timestamp
```

Future wallet performance and future cluster links are forbidden. Oracle
analysis using later information must be reported separately and cannot support
an executable result.

## Initial market scope

- BTC, ETH and SOL perpetuals;
- directionally interpretable traders;
- no memecoin-sniper strategy;
- no presumption that a visible venue position is the trader's complete exposure.

## Selection development discipline

Selection thresholds may be developed only in a declared development interval.
They are frozen before validation. Every monthly or weekly re-ranking uses only
information available through its cutoff.

## Follower simulation

Simulate entries and exits at:

- 1 second;
- 5 seconds;
- 30 seconds;
- 2 minutes;
- 5 minutes; and
- 15 minutes.

The 30-second and 2-minute cases are required primary human-in-the-loop
feasibility checks.

## Required costs

- executable bid/ask side;
- spread;
- depth-based slippage;
- maker/taker fees under a frozen conservative tier;
- funding over the follower holding interval;
- partial fills and unfilled-trade logic;
- separate entry and exit latency.

## Required baselines

- no trade;
- BTC/ETH/SOL buy-and-hold where comparable;
- simple time-series momentum;
- matched-random wallets;
- matched-exposure random entries;
- matched-turnover random entries;
- hindsight-selected leaderboard wallets as a deliberately biased diagnostic.

## Required robustness

Report rolling stability, maximum drawdown, expectancy, profit factor,
P&L concentration, holding period, leverage, liquidations, market concentration,
copy-capture ratio and capacity. A high win rate is insufficient.

## Terminal decision

The study must end with exactly one of:

```text
GO_TO_ENTITY_CLUSTER_RESEARCH
REPAIR_AND_RERUN
NO_GO_NO_COPYABLE_ALPHA
```

A language model may later summarize evidence and produce counterarguments. It
may not calculate the canonical ledger, P&L, cluster or promotion decision.
