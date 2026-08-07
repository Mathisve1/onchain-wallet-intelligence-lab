# Preregistration — DEX-COPY-AUTONOMY-001

- **Version:** `1.0`
- **Date:** 2026-08-07
- **Parent study:** `WALLET-COPYABILITY-STUDY-001`
- **Initial venue:** `HYPERLIQUID_PUBLIC_MAINNET`
- **Products:** BTC, ETH and SOL perpetuals
- **Current stage:** `RESEARCH`
- **Empirical result:** `null`

## Decision question

For the exact same point-in-time eligible source signals, does a deterministic
policy-constrained executor operating without per-trade human approval produce
higher risk-adjusted **net follower performance** than one-click or manual human
execution after all costs, fill constraints and operational failures?

## H1 — incremental execution value

At one or more preregistered feasible latency arms, bounded-autonomous execution:

1. has positive net follower expectancy;
2. has a positive lower 95% block-bootstrap confidence bound for the primary
   follower-expectancy estimand;
3. outperforms the same signal set under measured one-click and manual human
   latency;
4. remains positive under the doubled-cost and p90-latency stress cases; and
5. does not breach preregistered drawdown, tail-loss, concentration, capacity or
   operational-risk gates.

## H0 — no deployable incremental value

Any apparent improvement disappears after correcting for:

- future-information leakage and survivorship;
- source/follower price differences;
- executable spread and depth;
- partial and missed fills;
- fees and funding;
- entry and exit latency;
- crowding and capacity;
- wallet-style changes and hidden hedges;
- model-selection and multiple-testing effects;
- data, policy, signer, order and reconciliation failures.

H0 also holds when bounded autonomy improves average return but worsens tail loss
or security beyond the accepted envelope.

## Immutable parent relationship

The parent study controls:

- wallet universe and point-in-time selection;
- source-event definition;
- source and follower ledger;
- fee and funding treatment;
- market-data lineage;
- wallet and cluster identity;
- baseline strategy definitions.

This study may not use a future source result, future cluster link or later
wallet label to improve an earlier decision.

## Execution modes

Every eligible signal is evaluated under the same size and market state:

1. `SOURCE_WALLET_DIAGNOSTIC` — source performance only; never a follower claim.
2. `THEORETICAL_ZERO_LATENCY` — unattainable upper-bound diagnostic.
3. `DETERMINISTIC_AUTONOMOUS` — no LLM input.
4. `DETERMINISTIC_PLUS_AI_CRITIC` — AI may veto or lower confidence; it cannot
   expand the deterministic eligible set or risk limit in the primary test.
5. `HUMAN_ONE_CLICK` — exact prepared proposal plus measured approval latency.
6. `HUMAN_MANUAL` — measured end-to-end human workflow.
7. `NO_TRADE`.
8. `MATCHED_RANDOM_WALLET`.
9. `MATCHED_EXPOSURE_RANDOM_ENTRY`.
10. `MATCHED_TURNOVER_RANDOM_ENTRY`.
11. `SIMPLE_PRICE_MOMENTUM`.

The AI arm is promoted only if it adds value over the deterministic-autonomous
arm on the same inputs. Faster execution alone cannot be credited to AI.

## Latency arms

```text
0.2 seconds  — engineering lower-bound diagnostic
1 second
3 seconds
5 seconds
10 seconds
15 seconds
30 seconds
60 seconds
120 seconds
300 seconds
```

The primary autonomy comparison is the best frozen feasible arm among 1, 3, 5
and 10 seconds versus measured one-click and manual human distributions.

The 0.2-second arm can diagnose alpha decay but cannot support a deployability
claim unless live shadow measurements independently show that the entire
pipeline reaches it at the required percentile.

## Primary estimand

```text
net_follower_expectancy(mode, latency, size)
```

computed only from executable follower entries and exits after:

- entry and exit fees;
- spread and depth-based slippage;
- funding over the follower holding interval;
- partial fills;
- missed trades;
- rejected, expired and failed actions;
- any directly attributable execution-infrastructure cost.

## Secondary estimands

- median net return;
- profit factor;
- maximum drawdown;
- downside CVaR;
- copy-capture ratio;
- P&L concentration by wallet, cluster, instrument and calendar period;
- fill and missed-fill rate;
- entry and exit markout;
- latency p50/p75/p90/p95;
- operational failure rate;
- capacity curve;
- time under water;
- turnover and funding decomposition.

Win rate is diagnostic only.

## Development and validation

- All thresholds are developed in a declared development interval.
- Wallet and latency models are frozen before validation.
- Evaluation is chronological and walk-forward.
- Overlapping positions and correlated source wallets are grouped for
  resampling.
- No random train/test split may support the terminal decision.
- All trial families, ablations and parameter variants are registered.
- A sealed holdout or prospective shadow interval is required before any live
  promotion.
- Oracle and hindsight analyses are separately labeled and non-executable.

## Required stress tests

- p90 and p95 observed pipeline latency;
- 2x fees and slippage;
- 50% lower available depth;
- missed first fill;
- partial entry and partial exit;
- source reversal before follower entry;
- one-provider outage;
- delayed source event;
- stale quote and stale policy snapshot;
- source-wallet style drift;
- clustered source signals;
- high-volatility and low-liquidity regimes;
- kill-switch and reconciliation interruption.

## Terminal decision

Exactly one terminal research decision is allowed:

```text
GO_TO_SHADOW_DESIGN
REPAIR_AND_RERUN
NO_GO_BOUNDED_AUTONOMY
NO_GO_NO_COPYABLE_ALPHA
```

`GO_TO_SHADOW_DESIGN` authorizes only a separately reviewed, non-signing shadow
proposal. It does not authorize credentials, signatures, paper orders, live
orders, leverage or capital.
