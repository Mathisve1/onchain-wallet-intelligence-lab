# Risk envelope specification

## Current state

All live numerical limits are `UNSET_LIVE_BLOCKER`. This document freezes the
required structure and precedence, not deployable values.

A future live proposal must name exact numbers and units. No model or AI may
choose defaults.

## Human-frozen fields

### Capital and account

- exact isolated account or subaccount;
- exact maximum funded capital;
- minimum unencumbered margin/cash reserve;
- maximum daily new capital allocation;
- permitted deposit source and recovery destination;
- withdrawals and transfers disabled in the trading path.

### Venue, product and action

- exact venue and network;
- exact instrument allowlist;
- exact product allowlist;
- exact order types and time-in-force;
- exact cancel and reduce-only actions;
- explicit denial of leverage, margin-mode, transfer, withdrawal, vault,
  builder-fee and agent-management actions.

### Exposure

- maximum notional per action;
- maximum gross and net exposure;
- maximum per-instrument exposure;
- maximum per source wallet and entity cluster;
- maximum correlated-bucket exposure;
- maximum open positions and open orders;
- maximum effective leverage and margin utilization.

### Loss and drawdown

- maximum realized daily loss;
- maximum mark-to-market daily loss;
- maximum strategy drawdown;
- maximum per-position risk;
- maximum gap/markout loss;
- maximum consecutive operational or economic failures;
- cooldown and reset authority.

### Execution

- maximum source-event age;
- maximum quote age;
- maximum end-to-end latency;
- maximum price drift from the source and from the policy quote;
- maximum slippage and depth utilization;
- minimum executable depth;
- minimum conservative follower-EV;
- maximum order and cancel frequency;
- maximum retry count;
- permit expiry.

### Model and data

- exact allowed model hashes;
- exact allowed feature and policy hashes;
- minimum confidence and effective sample;
- drift and out-of-distribution thresholds;
- required provider agreement;
- required ledger and reconciliation status.

## Position-size rule

```text
allowed_size =
    min(
        account_cap,
        action_cap,
        instrument_cap,
        source_cluster_cap,
        correlated_bucket_cap,
        liquidity_cap,
        capacity_cap,
        edge_survival_cap,
        loss_budget_cap,
        confidence_cap,
        operational_cap
    )
```

If the minimum cannot be computed from current canonical evidence, size is zero.

## Hard blockers

No order or permit when:

- source event, quote, policy, model or data snapshot is stale;
- follower-EV lower bound is non-positive;
- account, order, fill or position state is unreconciled;
- source wallet/cluster is ineligible or drifting;
- instrument/action/account is not allowlisted;
- a loss, drawdown, leverage, exposure, frequency or concentration limit is hit;
- expected price impact or slippage exceeds the limit;
- required exit capacity is absent;
- provider state conflicts;
- kill switch, signer, nonce or incident state is uncertain;
- any exact hash differs from the promoted values;
- a transfer, withdrawal, agent-management or leverage-changing action appears.

## Risk-limit changes

A decrease may be activated through an emergency human path. An increase
requires:

1. new versioned governance record;
2. exact numerical diff and rationale;
3. updated stress tests;
4. independent review;
5. explicit activation timestamp;
6. rollback plan.

The AI cannot propose and activate the same increase.

## Initial isolated-pilot principle

The first live envelope, if ever authorized, is restricted to one isolated
account/subaccount, one venue, BTC/ETH/SOL, no leverage expansion, no
transfers/withdrawals, no bridges, no client funds and a canary capital amount
small enough that total loss is acceptable.

The exact amount and limits are intentionally not set by this research-governance
decision.
