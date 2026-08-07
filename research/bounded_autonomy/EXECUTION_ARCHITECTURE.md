# Prospective execution architecture

## Status

`DESIGN_ONLY_NO_SIGNING_AUTHORIZATION`

## End-to-end flow

```text
1. public source fill observed
2. raw bytes/object identity retained
3. deterministic source-position delta reconstructed
4. point-in-time wallet and market features frozen
5. statistical follower-EV and tail model evaluated
6. optional AI critic returns structured risk observations
7. deterministic intent builder creates a closed-schema candidate
8. policy/risk firewall reloads canonical state and recomputes every limit
9. if valid, one exact short-lived permit is created
10. isolated signer verifies permit and action semantics
11. allowlisted venue adapter submits the action
12. acknowledgement, order, fill and position are reconciled
13. no next exposure-increasing action until reconciliation completes
```

## Process and network boundaries

### AI/orchestration process

May read sanitized features and produce a typed recommendation. It has:

- no signing material;
- no master or agent key;
- no generic HTTP client to an action endpoint;
- no policy mutation capability;
- no direct database write to canonical ledgers;
- no ability to suppress a deterministic finding.

### Canonical state service

Provides immutable event identities, point-in-time feature snapshots, account
state, open orders, fills, positions and risk usage. All reads are versioned and
hashable.

### Policy and risk service

Recomputes:

- signal eligibility;
- source and cluster status;
- instrument and action allowlist;
- model and policy hashes;
- quote freshness and executable depth;
- follower-EV lower bound;
- size and concentration;
- loss, drawdown, leverage and frequency usage;
- outstanding and unreconciled actions;
- kill-switch and incident state.

It may only return `BLOCK`, `SHRINK_AND_REEVALUATE` or an exact permit.

### Permit issuer

A permit contains at least:

```text
permit_id
intent_id
strategy_id
strategy_version
model_version_sha256
policy_version_sha256
data_snapshot_sha256
risk_snapshot_sha256
source_event_ids
account_or_subaccount
venue
instrument
side
action_type
reduce_only
order_type
maximum_quantity
limit_price
maximum_slippage_bps
time_in_force
created_at
expires_at
client_order_id
nonce_domain
```

The permit is single-use. Any field mutation changes its hash and invalidates it.

### Restricted signer

The signer:

- accepts only authenticated permits from the policy service;
- revalidates policy, expiry, action type, account and kill-switch state;
- constructs or verifies the exact venue payload;
- never exposes its private key;
- rejects transfers, withdrawals, agent management, leverage changes, vault
  actions and arbitrary exchange actions;
- signs no second exposure-increasing action while required reconciliation is
  incomplete;
- records the payload hash, nonce and signature result.

### Venue adapter

The adapter has individual methods for exact allowed actions. It must not expose
a generic `exchange(action)` interface to upstream processes.

The initial candidate action surface, subject to later signed-stage review, is:

- place IOC limit order with an explicit worst price;
- place post-only order only in a separately tested mode;
- cancel by exact client/order identifier;
- cancel all open strategy orders;
- reduce or close an existing strategy position with `reduce_only`.

Everything else is denied.

## Entry state machine

```text
OBSERVED
-> DECODED
-> ELIGIBLE
-> QUOTED
-> POLICY_ALLOWED
-> PERMITTED
-> SIGNED
-> SUBMITTED
-> ACKNOWLEDGED
-> PARTIALLY_FILLED | FILLED | EXPIRED | REJECTED
-> RECONCILED
```

No transition may be skipped. A timeout does not imply failure or success; it
implies `UNKNOWN`, which pauses further exposure until reconciliation.

## Exit state machine

Exits can be triggered by:

- source reduction or close;
- follower risk stop;
- maximum holding time;
- follower-EV deterioration;
- wallet-style drift;
- liquidity or market-health deterioration;
- loss/drawdown/concentration limit;
- model or policy invalidation;
- emergency governance or guardian action.

Emergency exits may reduce risk under a separately specified fail-safe path.
They cannot reverse or increase exposure.

## Key hierarchy

Prospective only:

1. offline human master/recovery authority;
2. isolated venue account or subaccount;
3. disposable agent/API wallet dedicated to one process and subaccount;
4. restricted signer service;
5. emergency guardian able to disable signing and cancel orders.

The AI has no position in this key hierarchy.

## Observability

Every decision retains:

- source event and data cutoff;
- features and model outputs;
- AI structured output, if used;
- all policy findings;
- quote/depth snapshot;
- intent and permit;
- signed payload hash;
- venue acknowledgement;
- orders, cancels and fills;
- reconciliation state;
- final source and follower P&L;
- incident and human governance actions.

A missing record is an operational failure, not a successful trade.
