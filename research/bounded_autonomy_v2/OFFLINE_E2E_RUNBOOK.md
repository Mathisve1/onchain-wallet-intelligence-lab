# Offline end-to-end bounded-autonomy runbook

Status: offline laboratory only. No external endpoint, signature, testnet or capital action is authorized.

## Purpose

Exercise the complete future control flow without a real wallet or network:

```text
typed candidate
  -> deterministic policy evaluator
  -> PermitService
  -> SQLite journal + nonce reservation + audit hash chain
  -> RestrictedSignerSimulator
  -> FakeHyperliquidVenue
  -> ack / fill / reject / timeout
  -> durable reconciliation
```

## Preconditions

- disposable temporary SQLite database;
- simulated signer identity only;
- execution state may be set to `SIGNED_TEST_ONLY` only inside this offline test harness;
- no private key or SDK import;
- fake venue object exists only in memory;
- exact test policy hash is frozen.

## Happy-path test

1. register simulated signer;
2. activate offline signed-test state;
3. construct a deterministic entry intent;
4. issue a one-time permit;
5. verify permit/action/nonce persisted before simulated signature;
6. RestrictedSignerSimulator rechecks exact action hash and atomically consumes permit;
7. transition `SIGNED -> SUBMITTED`;
8. fake venue emits `ACKNOWLEDGED` and full `FILL`;
9. persist exact fill quantity;
10. require action `FILLED`;
11. require unresolved risk count = 0;
12. verify full audit hash chain.

## Partial fill

Expected:

```text
ACKNOWLEDGED
-> PARTIALLY_FILLED
-> no new risk-increasing permit
-> later fill/cancel/reconciliation
-> terminal state
```

Partial fill is never interpreted as full execution.

## Lost acknowledgement after venue acceptance

Fake venue behavior `TIMEOUT_AFTER_ACCEPT` deliberately accepts the cloid but raises a client timeout.

Required sequence:

```text
SIGNED
-> SUBMITTED
-> POSSIBLY_SUBMITTED
-> restart allowed
-> RECONCILING
-> query by cloid
-> ACKNOWLEDGED / PARTIALLY_FILLED / FILLED / terminal
```

Blind resubmission is forbidden.

## Duplicate acknowledgement

A duplicate ack must be audit-recorded and ignored without a second economic state transition.

## Reject

A venue reject is terminal for that action and releases the unresolved-new-risk gate. It does not create a fill.

## Mutation torture

A single valid unconsumed permit is retained while 1,000 deterministic one-field mutations are attempted across:

- instrument/coin;
- side;
- size;
- price;
- reduce-only bit;
- cloid;
- action type including forbidden withdrawal/leverage-like values.

Every mutation must be denied and the original permit must remain `ISSUED`.

## Concurrent consume torture

Thirty-two simultaneous signer requests target the same valid permit. Exactly one may succeed; all others must deny because permit state changes atomically from `ISSUED` to `CONSUMED`.

## Nonce concurrency

Multiple workers issue distinct permits against one signer at the same nominal millisecond. SQLite `BEGIN IMMEDIATE`, signer-scoped durable nonce state and `UNIQUE(signer_id, nonce)` must yield unique monotonically increasing nonce reservations.

## Crash points to expand next

The next fault-injection harness should explicitly terminate/reopen the process after each durable boundary:

1. signer registered;
2. policy allow audit;
3. nonce reserved/permit transaction committed;
4. permit consumed;
5. simulated signature marker persisted;
6. submitted state persisted;
7. timeout uncertainty persisted;
8. ack persisted;
9. first partial fill persisted;
10. terminal fill/cancel persisted.

For each crash point, restart must produce exactly one of:

```text
SAFE_TO_CONTINUE_NO_ACTION
RECONCILIATION_REQUIRED
TERMINAL
PAUSED_REQUIRES_HUMAN
```

Never `blind retry because state is missing`.

## Exit criterion for this offline stage

Before proposing any real signing fixture stage:

- all local tests pass;
- execution-sprint validator passes;
- action and permit schemas remain closed;
- no network/signing dependencies exist in the pure prototype;
- official Hyperliquid serialization source is pinned;
- cryptographic hash/signature parity is still explicitly unclaimed;
- canonical market/data lane remains separate;
- a later clean branch reconciliation and canonical CI review are mandatory.