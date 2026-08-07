# Risk Policy

## Current authorizations

| Authorization | State |
|---|---|
| historical/public research | `true` |
| bounded-autonomy governance research | `true` |
| historical analytical market release | `false` |
| integration | `false` |
| paper | `false` |
| shadow | `false` |
| signed testnet action | `false` |
| live | `false` |
| autonomous live execution | `false` |
| leverage | `false` |
| capital allocation | `false` |

A positive retrospective result cannot change any authorization automatically.

## Binding hierarchy

When multiple limits apply, the most restrictive valid limit wins:

```text
effective_limit =
    min(
        human_governance_limit,
        stage_limit,
        strategy_limit,
        instrument_limit,
        liquidity_limit,
        confidence_limit,
        operational_limit
    )
```

No AI, model, strategy process, signer or venue adapter may raise a limit. Only a
new human-governance record may do so, and that record must be versioned,
hash-bound, reviewed and activated through the stage-promotion process.

## Non-negotiable invariants

The current and every prospective system must enforce:

- `UNKNOWN`, stale, inconsistent, missing or unreconciled evidence -> `BLOCK`;
- no master-key, seed phrase or withdrawal credential in an AI or strategy
  process;
- no transfer, withdrawal, API-wallet approval, allowlist expansion, policy
  mutation or risk-limit mutation through the trading path;
- no arbitrary action payload or arbitrary recipient;
- no unbounded market order; every entry or exit has an explicit executable
  price boundary, size boundary and expiry;
- no order after its source signal, data snapshot, model, policy or quote expires;
- no order when the exact promoted model and policy hashes are unavailable;
- no autonomous increase in leverage, margin utilization or capital allocation;
- no continuation after a reconciliation error, duplicate-order uncertainty,
  kill-switch uncertainty or provider disagreement;
- exits may reduce risk, but an emergency path may never increase gross
  exposure.

## Research objective

No monthly income target is an optimization criterion. Research optimizes for
net follower expectancy subject to drawdown, tail loss, turnover, liquidity,
copy latency, capacity, model uncertainty and operational failure.

`NO_TRADE` is preferable to weak, stale, cost-dominated or poorly evidenced
signals.

## Live-envelope status

Exact live notional, leverage, loss, drawdown, concentration, frequency and
slippage limits are deliberately **unset**. They may be frozen only after the
historical, shadow, security and execution-reconciliation gates in
`research/bounded_autonomy/GO_NO_GO_GATES.md` pass. Unset limits are a live
blocker, never an invitation to use defaults.
