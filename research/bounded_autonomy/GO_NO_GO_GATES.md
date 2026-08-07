# Go/no-go gates

Passing a gate opens only the next explicitly named research or engineering
proposal. No gate automatically opens execution or capital.

## G0 — governance and preregistration

Requirements:

- ADR and machine-readable policy agree;
- parent study remains unchanged;
- current execution authorizations are all false;
- threat model, latency grid, follower-EV and terminal decisions are frozen;
- repository tests and manifest validation pass;
- clean-context review has no unresolved blocker.

Result:

```text
PASS -> bounded-autonomy research architecture registered
FAIL -> repair this governance package
```

## G1 — public technical evidence

Requirements:

- final read-only Hyperliquid probe accepted;
- exact run/job/artifact and output hashes retained;
- no credentials, signed action or analytical market release;
- rate, pagination, response-shape and archive-route questions classified.

## G2 — deterministic market and wallet ledger

Requirements:

- content-addressed raw retention;
- schema and gap history;
- deterministic fill/funding/transfer/liquidation/vault ledger;
- deposits and transfers separated from profit;
- account, position and cash reconciliation;
- two byte-identical reruns;
- no unexplained balance or position residual.

## G3 — point-in-time follower alpha

Requirements:

- parent `WALLET-COPYABILITY-STUDY-001` completed;
- positive net follower expectancy in chronological out-of-sample tests;
- lower 95% block-bootstrap bound positive for the primary estimand;
- positive under 2x costs and p90 latency;
- at least three non-overlapping evaluation windows;
- no single wallet/entity cluster contributes more than 20% of aggregate
  positive P&L;
- no single calendar month contributes more than 25%;
- no single instrument contributes more than 50%;
- capacity remains positive at the proposed research size;
- result is not dependent on excluded wallet classes or oracle labels.

If parent follower alpha fails, bounded execution cannot rescue the strategy.

## G4 — incremental bounded-autonomy value

Requirements:

- exact same signal set across execution modes;
- deterministic-autonomous arm improves net follower expectancy over measured
  one-click and manual human modes;
- primary incremental lower 95% block-bootstrap bound is positive;
- p90 pipeline latency and 2x-cost cases remain positive;
- AI-critic arm is separately compared with deterministic autonomy;
- any AI improvement survives correction for the registered trial family;
- tail loss, drawdown and concentration do not worsen beyond frozen limits.

Terminal result:

```text
GO_TO_SHADOW_DESIGN
REPAIR_AND_RERUN
NO_GO_BOUNDED_AUTONOMY
NO_GO_NO_COPYABLE_ALPHA
```

## G5 — non-signing shadow evidence

Minimum evidence before a signed-stage proposal:

- at least 90 calendar days;
- at least 500 eligible source events after all filters;
- coverage of BTC, ETH and SOL unless an instrument is preregistered out before
  the shadow interval;
- p50/p75/p90/p95 latency by component;
- complete hypothetical intent, policy, quote, expiry and reconciliation record;
- zero unexplained decisions or state transitions;
- stable provider/backfill behavior;
- observed shadow follower results consistent in sign and order of magnitude
  with historical estimates;
- all stale, conflict and outage tests fail closed.

If the sample is too dependent after wallet/cluster/block adjustment, the gate
remains inconclusive despite 500 raw events.

## G6 — security and permission proof

Requirements:

- exact action surface enumerated;
- zero successful unauthorized actions in adversarial tests;
- transfer, withdrawal, agent-management, leverage, vault and arbitrary-action
  attempts blocked;
- AI compromise cannot reach a key or action endpoint;
- permit replay, mutation, expiry and duplicate tests blocked;
- API-wallet nonce lifecycle and non-reuse procedure proven;
- independent signer revocation and recovery drill;
- kill switch stops new signing under the frozen objective and cancels open
  strategy orders where supported;
- no secret in logs, artifacts or model context;
- independent review of the exact signer/policy/adapter version.

Any critical control failure is immediate `NO_GO`.

## G7 — fork or testnet signed execution

Requires separate governance authorization.

Requirements:

- disposable account and API wallet;
- no real capital;
- exact orders and fills reconcile;
- partial fill, reject, expiry, reconnect and duplicate flows pass;
- expected versus observed action payloads are byte/hash consistent;
- no orphan order, fill or position;
- two deterministic end-to-end replays from the same event set;
- emergency and recovery drills pass.

## G8 — isolated live pilot

Requires separate explicit owner decision and exact risk envelope.

Conditions:

- one isolated account/subaccount;
- canary capital whose total loss is acceptable;
- one venue and BTC/ETH/SOL only;
- no client funds, borrowing, bridges or withdrawals;
- no leverage expansion;
- automatic pause on any incident or reconciliation mismatch;
- execution correctness assessed before profitability;
- daily human review of the complete audit and risk ledger.

A profitable pilot does not authorize scale.

## G9 — scale decision

Requires:

- stable live execution and risk behavior over a separately frozen duration;
- net performance consistent with conservative expectations;
- capacity curve at proposed size;
- no unresolved incident;
- independent security and model review;
- new human-frozen capital and risk envelope.

The AI cannot initiate this decision.
