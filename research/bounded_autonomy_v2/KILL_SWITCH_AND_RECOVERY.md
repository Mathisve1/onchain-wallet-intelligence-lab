# Kill switch and recovery state machine

Status: design only. No live control is installed.

## State machine

```text
DISABLED
   |
   v  human promotion
RESEARCH_ONLY
   |
   v  human promotion
SHADOW_ONLY
   |
   v  human promotion
SIGNED_TEST_ONLY
   |
   v  human promotion + exact risk envelope
ACTIVE_BOUNDED

ANY STATE -----------------------> PAUSED
                                      |
                                      v
                            human-reviewed recovery
                                      |
                     +----------------+----------------+
                     |                                 |
                     v                                 v
              previous stage              LOCKED_REQUIRES_ROTATION
```

Only the human governor may move upward in authority. AI, policy services and automated monitors may always request or trigger a move to a more restrictive state.

## Immediate pause triggers

At minimum, a future implementation must pause new risk-increasing permits on:

- human kill-switch command;
- signer health unknown or signer revocation detected;
- policy/model/risk hash mismatch;
- market-data conflict or freshness breach;
- WebSocket gap with unreconciled action state;
- order/fill/position mismatch;
- unexpected account action not owned by the strategy;
- duplicate or replayed permit attempt;
- nonce allocator uncertainty;
- unknown venue response/action schema;
- daily loss/drawdown envelope breach;
- action-rate budget below the registered cancellation reserve;
- audit persistence failure;
- critical security detector event;
- dependency/version drift in execution-critical service.

## `PAUSED` semantics

`PAUSED` means:

```text
new entry permits              DENY
position-increasing permits    DENY
policy changes by AI           impossible
new signer enrollment by AI    impossible
withdraw/transfer               impossible through strategy path
cancel strategy orders          allowed only via deterministic emergency path
reduce-only exits               allowed only if separately enabled by the frozen emergency policy
read/reconciliation             allowed
human recovery                  allowed through separate governance path
```

A pause is not cleared automatically because prices recover, a provider reconnects or an AI model says the incident is resolved.

## Emergency cancel path

The emergency cancellation service must be independent of the AI model and receive higher scheduling priority than new entries.

Eligible target set:

- only orders proven to be strategy-owned through registered cloids/order IDs;
- no arbitrary user-wide operation unless a separately reviewed dead-man-switch policy explicitly permits it;
- every cancel is journaled and reconciled.

Hyperliquid documents `scheduleCancel` as a future cancellation mechanism. It is only a candidate infrastructure control. Testnet evidence must establish its precise operational behavior, limits and interaction with strategy-owned/non-strategy orders before use.

## Reduce-only emergency path

The safest general emergency behavior is often to stop adding risk, not to blindly market-close. A forced exit can itself be harmful during illiquidity or data failure.

Therefore a reduce-only emergency action requires all of:

- exact current venue position is known and reconciled;
- instrument is allowlisted;
- action cannot increase absolute exposure;
- deterministic quantity cap <= verified open position;
- bounded IOC limit price from a fresh quote/book;
- separate emergency max-slippage rule;
- exact permit and signer checks still succeed.

If these conditions are not available, state remains paused for human intervention rather than fabricating an exit.

## `LOCKED_REQUIRES_ROTATION`

Escalate to locked state after events such as:

- suspected API-wallet secret compromise;
- unauthorized signature observed;
- signer produced signature without valid permit;
- permit replay succeeded;
- audit evidence was rewritten or cannot be trusted;
- execution adapter emitted a forbidden action;
- account activity cannot be reconciled to strategy/human actions.

Recovery requires:

1. keep entries disabled;
2. independent account/order/position reconstruction;
3. revoke/replace the affected API wallet;
4. verify new signer identity and nonce domain;
5. produce an incident record;
6. rerun the critical adversarial suite;
7. human reauthorization of the exact new signer/policy versions.

## Human governor control path

The human control path must remain available without the AI service. It should expose only governance actions such as:

- `PAUSE`;
- revoke signer/API wallet;
- inspect current account/order/reconciliation status;
- approve a repaired policy/signer version;
- rotate/recover master authority.

It must not rely on the same credentials/process that may have been compromised.

## Recovery gates

A transition from `PAUSED` back to any active stage requires a machine-readable recovery record containing at least:

- incident/reason code;
- exact previous state;
- exact proposed state;
- reconciled account snapshot hash;
- open-order set hash;
- signer identity/version;
- policy version/hash;
- model version/hash where relevant;
- risk envelope hash;
- outstanding-permit count = 0;
- unresolved-reconciliation count = 0;
- adversarial regression result;
- human governor approval identity/time.

There is no `force_resume` path available to AI or ordinary strategy services.