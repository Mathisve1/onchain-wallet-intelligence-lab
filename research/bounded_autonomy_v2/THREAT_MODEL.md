# Threat model — bounded autonomous execution

Status: design only. No live threat-control claim.

## Protected assets

- human master authority and recovery path;
- dedicated API-wallet signer secret;
- trading capital assigned to the isolated account;
- policy/risk/model version integrity;
- point-in-time market and wallet evidence;
- exact intent/permit/action lineage;
- nonce and cloid uniqueness;
- order/fill/position reconciliation state;
- kill-switch availability;
- audit evidence.

## Primary security invariant

Compromise or hallucination of the AI process must not be sufficient to:

1. obtain key material;
2. expand the allowed action surface;
3. increase risk/capital limits;
4. alter policy or model promotion state;
5. transfer or withdraw funds;
6. change leverage/margin configuration;
7. reuse or mutate a permit;
8. bypass a `BLOCK` decision;
9. create an unreconciled sequence of risk-increasing actions.

## Threat classes

### 1. Prompt/context injection

Attack: source-wallet metadata, token names, external webpages, logs or provider strings contain instructions intended for the model.

Controls:

- no raw untrusted prose in the execution-critical AI context unless explicitly quoted as data;
- schema-minimized structured context;
- external text has zero tool authority;
- model output cannot become raw action bytes;
- deterministic policy ignores natural-language instructions.

### 2. Model hallucination or compromised model endpoint

Attack: AI invents an instrument, size, price, policy version or action.

Controls:

- closed JSON schema;
- all safety-critical fields re-derived by deterministic services;
- exact instrument/action allowlists;
- model version pinned by hash/identifier;
- AI may only reduce eligibility in the primary critic arm.

### 3. Arbitrary-action escalation

Attack: an allowed order tool is generalized into transfer, withdrawal, agent-management, leverage, vault or builder-fee actions.

Controls:

- no generic `/exchange` tool exposed;
- adapter has a closed method set;
- compiled action hash is permit-bound;
- signer rejects unknown action type/fields;
- adversarial enumeration of every documented exchange action.

### 4. Key exfiltration

Attack: AI/runtime reads signer secret through environment, filesystem, exception, debug log or memory endpoint.

Controls:

- separate signer process/security domain;
- no key in model environment or prompt;
- no generic secret-read tool;
- redacted error contract;
- signer logs contain public identity and hashes only;
- production target prefers isolated/non-exportable key storage.

### 5. Replay and duplicate execution

Attack: valid signed request/permit is submitted twice, or an acknowledgement is lost and the client retries unsafely.

Controls:

- one-time permit registry;
- unique signer nonce;
- deterministic unique cloid;
- durable pre-sign journal;
- uncertain outcome enters `POSSIBLY_SUBMITTED` and must reconcile before retry;
- retries target status/reconciliation, not blind resubmission.

### 6. Nonce race or state loss

Attack: concurrent workers share signer nonce state; restart causes reuse or out-of-order corruption.

Controls:

- one nonce allocator per signer;
- atomic counter and durable journal;
- separate API wallet per process/subaccount;
- fail closed on allocator disagreement;
- no AI-provided nonce.

### 7. Stale market state / latency trap

Attack: source signal was valid but price, spread, book or position moved before execution.

Controls:

- strict data age;
- re-quote immediately before permit;
- explicit limit price and IOC;
- short permit/venue expiry;
- stale state forces new snapshot rather than automatic widening.

### 8. Price/slippage manipulation

Attack: thin book, temporary spoofing, copy followers or a malicious source wallet causes poor follower execution.

Controls:

- deterministic max slippage and capacity cap;
- IOC limit rather than unbounded market helper;
- source trade and follower execution measured separately;
- no automatic slippage widening;
- later follower-EV must include failed/missed trades.

### 9. Source-wallet manipulation

Attack: profitable-looking wallet changes behavior, coordinates with related accounts or trades to exploit copy followers.

Controls:

- source eligibility remains in parent research lane;
- point-in-time clustering/forensics;
- style-drift detection;
- source alpha cannot substitute for follower alpha;
- AI critic may veto suspicious context but cannot restore deterministically excluded source.

### 10. Position/account drift

Attack: local expected position differs from venue after partial fills, liquidation, manual action or missed event.

Controls:

- reconcile acknowledgements, order updates, fills and clearinghouse state;
- any unexplained residual blocks risk increase;
- manual external intervention requires explicit resync state;
- reduce-only semantics independently verified.

### 11. WebSocket disconnect / message loss

Attack: order or fill messages are missed and local state becomes stale.

Controls:

- sequence-independent idempotent ingestion where possible;
- reconnect snapshots;
- REST/info backfill;
- pause new risk until reconciliation completes;
- connection health is a hard policy input.

### 12. API schema/asset-ID drift

Attack: venue changes fields, instrument indexes, rounding or error behavior.

Controls:

- closed parser and schema version observations;
- unknown fields/types fail closed where execution-critical;
- instrument mapping refreshed from registered metadata and cross-checked;
- exact size/price rounding tested against venue rules;
- adapter version pinned.

### 13. Rate-limit exhaustion

Attack: strategy consumes action/IP budget and cannot cancel or reconcile safely.

Controls:

- explicit IP and address budget accounting;
- reserve capacity for cancel/reconciliation;
- no unnecessary polling where WebSocket exists;
- bounded retries/backoff;
- overload pauses new entries.

Hyperliquid documents separate IP and address-based action limits; cancellations receive additional allowance. These mechanics must be measured and encoded before signed progression.

### 14. Emergency-control denial of service

Attack: kill switch cannot run because the AI process, provider or signer is broken.

Controls:

- independent human pause/revoke path;
- emergency service isolated from AI;
- cancellation path has separate resource priority;
- regular recovery drills.

### 15. Malicious or erroneous human configuration

Attack: owner accidentally sets extreme limits or allowlists a wrong instrument/signer.

Controls:

- policy changes are versioned and diff-reviewed;
- high-impact changes require explicit confirmation and cooldown before activation;
- live policy has no hidden defaults;
- config change cannot be triggered by AI;
- maximum constitutional ceilings may require a separate governance layer.

### 16. Dependency/supply-chain compromise

Attack: SDK/package/action update introduces signing or payload behavior drift.

Controls:

- pin exact dependency versions/hashes for executable stages;
- minimize SDK surface used by adapter;
- golden action-serialization fixtures;
- dependency diff before promotion;
- no automatic dependency update to live signer.

## Safety states

Suggested state machine:

```text
DISABLED
  -> RESEARCH_ONLY
  -> SHADOW_ONLY
  -> SIGNED_TEST_ONLY
  -> ACTIVE_BOUNDED

any state -> PAUSED
PAUSED -> human-reviewed recovery only
critical integrity failure -> LOCKED_REQUIRES_ROTATION
```

No AI output can transition upward in this state machine.

## Catastrophic assumptions

Risk analysis must assume at least:

- the model can be fully malicious;
- one application service can be compromised;
- one market-data source can be stale or wrong;
- network responses can be delayed/duplicated;
- the source wallet can be adversarial;
- a trade can lose the full allocated position amount;
- emergency cancellation may not fill an exit.

The design is acceptable only if these assumptions remain bounded by the human-defined capital envelope and deterministic controls.