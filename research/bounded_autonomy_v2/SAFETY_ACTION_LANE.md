# Deterministic safety-action lane

Status: design only. No cancel, reduce or signed action is authorized.

## Why this lane exists

A risk control must not become unavailable merely because the AI critic is slow, unavailable or vetoes a decision. The system therefore distinguishes **risk-increasing entries** from **safety-preserving actions**.

## Risk-increasing entry

`PLACE_IOC_LIMIT` may increase exposure and must satisfy the full entry envelope:

- point-in-time deterministic eligibility;
- fresh market state;
- source-signal age;
- position/notional/exposure caps;
- daily loss/drawdown gates;
- cancellation/action-rate reserve;
- policy/model/risk/data version binding;
- AI critic when the active human policy marks it required;
- one-time permit and reconciliation gate.

A missing required AI response becomes `SKIP_AI_REQUIRED`/`SKIP_AI_TIMEOUT`. The system never silently falls back to a less restrictive entry path.

## Safety-preserving cancel

`CANCEL_BY_CLOID` in `DETERMINISTIC_SAFETY` mode:

- never depends on AI availability;
- has no invented price, quantity, side or slippage field;
- can target only a strategy-owned, non-terminal order with a registered cloid;
- does not count as risk-increasing;
- remains admissible when entry loss/exposure caps are already breached;
- remains admissible when the reserved entry/action budget has fallen below the threshold that blocks new entries.

The ordinary active path may still block on global integrity uncertainty. A separate emergency path governs behavior after a global pause or unresolved venue state.

## Safety-preserving reduce-only action

`REDUCE_ONLY_IOC` in `DETERMINISTIC_SAFETY` mode:

- never depends on AI availability;
- requires a fresh quote/book because it still executes economically;
- requires `reduce_only=true`;
- side must oppose the reconciled signed position;
- quantity cannot exceed the absolute reconciled position;
- remains available after entry loss/exposure/rate-reserve gates have tripped;
- cannot be used to open a new position or cross through zero into opposite exposure.

## AI-assisted strategic exits

A later research arm may separately study `DETERMINISTIC_PLUS_AI_CRITIC` for non-emergency reduce-only exits. This cannot replace the deterministic safety path. If the AI layer fails, the system must still retain a policy-controlled path to cancel owned orders and reduce known exposure.

## Governance boundary

AI cannot:

- reinterpret an entry as a safety action;
- set `DETERMINISTIC_SAFETY` on `PLACE_IOC_LIMIT`;
- create a cancel target not in the strategy-order ownership ledger;
- set reduce-only quantity above the reconciled position;
- remove freshness/slippage checks from an economically executing reduction;
- unpause the system or bypass reconciliation.

The intent schema, permit schema and deterministic policy prototype encode these distinctions explicitly.