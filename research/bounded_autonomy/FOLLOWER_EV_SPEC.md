# Follower-EV specification

## Canonical question

The relevant economic object is not source-wallet return. It is the expected
return available to the follower at a specified latency and size.

```text
EV_follower(w, e, l, q, m) =
    E[net follower P&L |
      source wallet/cluster w,
      source event e,
      latency l,
      follower size q,
      execution mode m,
      information available at decision time]
```

No LLM may calculate or overwrite this estimand.

## Per-event identity

For each source event:

```text
gross_executable_pnl =
    signed_filled_quantity
  * (executable_exit_price - executable_entry_price)

net_follower_pnl =
    gross_executable_pnl
  - entry_fee
  - exit_fee
  - entry_spread_and_depth_cost
  - exit_spread_and_depth_cost
  - funding_paid
  + funding_received
  - attributable_failure_cost
  - attributable_execution_infrastructure_cost
```

A missed or blocked trade has zero position P&L and retains any directly
incurred failure cost. It may not be silently dropped from the denominator.

## Source versus follower

Required outputs:

- source entry, exit and net P&L;
- follower executable entry and exit;
- follower net P&L by latency and size;
- `copy_capture_ratio = follower_net_pnl / source_net_pnl` where interpretable;
- reason for any missed, blocked, expired or partial execution;
- complete cost decomposition;
- market impact and capacity.

The capture ratio is undefined when source P&L is zero or when cost basis is
unreconciled. Undefined is not zero and not safe.

## Latency decomposition

```text
end_to_end_latency =
    observation_latency
  + ingestion_latency
  + decoding_latency
  + feature_snapshot_latency
  + model_latency
  + policy_latency
  + intent_and_permit_latency
  + signing_latency
  + network_ack_latency
  + fill_latency
```

Historical replay must distinguish observed components from modeled components.

## Distribution, not point estimate

For every wallet, wallet class and aggregate:

- mean and median;
- lower and upper confidence bounds;
- downside quantiles;
- expected shortfall/CVaR;
- block-bootstrap distribution;
- sensitivity to wallet/cluster dependence;
- capacity by follower size;
- conditional results by volatility, liquidity and funding regime.

The primary gate uses the lower 95% block-bootstrap bound of net follower
expectancy. A positive point estimate with a non-positive lower bound is
inconclusive.

## Conservative sizing

The research size is the minimum of:

```text
account_limit
strategy_limit
instrument_limit
source_cluster_limit
liquidity_and_depth_limit
capacity_limit
edge_survival_limit
confidence_limit
operational_limit
```

For a given event, the selected size must be frozen before its result is known.
Sizing may not use the source wallet's absolute notional as a direct follower
percentage.

## Alpha decomposition

Report separately:

```text
source_alpha
signal_selection_alpha
latency_execution_alpha
AI_incremental_alpha
```

- `source_alpha`: source performance before follower frictions.
- `signal_selection_alpha`: value of selecting the source event point in time.
- `latency_execution_alpha`: difference between follower latency arms.
- `AI_incremental_alpha`: difference between deterministic autonomous and
  deterministic-plus-AI-critic arms.

This prevents fast infrastructure or a lucky wallet from being credited to AI.

## Capacity

For each size `q`, recompute entry and exit through executable depth. Report the
largest size for which the conservative net follower-EV remains positive and
risk gates pass.

A profitable result at one small size is not evidence that the strategy scales.

## Missing evidence

The following produce `EV_STATUS=BLOCKED`, not an imputed value:

- missing source or follower fill;
- unknown deposit/withdrawal adjustment;
- unresolved account or subaccount identity;
- incomplete market depth;
- fee or funding uncertainty outside the frozen bound;
- stale source event or quote;
- unmatched order, cancel or fill;
- policy/model/data hash mismatch;
- unclosed or unreconciled follower position.
