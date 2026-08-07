# System Architecture

## Current research plane

```text
official archives / public event streams
                  |
                  v
        immutable raw object store
                  |
                  v
         schema and gap validator
                  |
                  v
       deterministic wallet ledger
                  |
        +---------+----------+
        |                    |
        v                    v
wallet performance      entity graph
        |                    |
        +---------+----------+
                  v
          copyability engine
                  |
                  v
       independent cluster consensus
                  |
                  v
       AI-supported evidence memo
                  |
                  v
        governed research decision
```

This plane is the only currently authorized plane. It is read-only.

## Prospective bounded-autonomy execution plane

The following design is approved for research but not for signed use:

```text
realtime public source events
             |
             v
deterministic canonical state + point-in-time features
             |
             +------------------------------+
             |                              |
             v                              v
statistical follower-EV model        AI contextual critic
             |                              |
             +---------------+--------------+
                             v
                    typed trade intent
                             |
                             v
          deterministic policy and risk firewall
                             |
               +-------------+-------------+
               |                           |
             BLOCK                  one-time action permit
                                           |
                                           v
                                isolated restricted signer
                                           |
                                           v
                                  allowlisted venue adapter
                                           |
                                           v
                                  order/fill reconciliation
                                           |
                                           v
                           position, risk and incident ledger
```

## Separation of duties

| Component | May do | May not do |
|---|---|---|
| AI critic/orchestrator | rank evidence, flag anomalies, propose a typed intent | calculate canonical P&L, change policy, hold a key, call an action endpoint |
| statistical models | estimate follower return, tail loss, holding time and copyability | self-promote or change labels after the cutoff |
| canonical ledger | reconstruct balances, positions, P&L and cash flows | infer unsupported data or accept unreconciled state |
| policy/risk service | recompute limits, shrink or block an intent, issue an exact permit | increase human limits or accept missing evidence |
| restricted signer | sign one exact valid permit | accept arbitrary payloads, transfers, withdrawals or policy changes |
| venue adapter | submit/cancel allowlisted order actions and reconcile results | expose a generic exchange-action method |
| human governor | set capital, limits, allowlists, model/policy versions and stage | bypass immutable evidence or relabel failed results |
| emergency guardian | pause signing and trigger risk-reducing cancellation | originate exposure-increasing trades |

## Canonical-calculation boundary

The collector, ledger, P&L engine, cluster features, execution simulator,
follower-EV, sizing, policy evaluation, action construction and reconciliation
are deterministic, versioned and testable. An LLM may provide summaries,
counterarguments and anomaly hypotheses, and may prospectively originate a
typed intent, but cannot be the canonical calculator, merge authority or sole
execution gate.

## Scaling principle

The system processes the venue event stream once. It does not poll millions of
wallets. Wallets begin as compact cold records, become warm only after activity
and materiality filters, and enter the hot watchlist only after sufficient
point-in-time history and copyability evidence.

## Current enforcement

`governance/BOUND_AUTONOMY_POLICY.json` sets the maximum current stage to
`RESEARCH`. Every execution authorization is false. Architecture diagrams do
not override those machine-readable facts.
