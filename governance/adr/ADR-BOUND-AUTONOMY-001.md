# ADR-BOUND-AUTONOMY-001 — Human-governed bounded autonomy

- **Date:** 2026-08-07
- **Status:** `OWNER_APPROVED_RESEARCH_DIRECTION_PENDING_REPOSITORY_REVIEW`
- **Decision class:** governance and prospective system architecture
- **Parent program:** `ONCHAIN-WALLET-INTELLIGENCE`
- **Parent empirical study:** `WALLET-COPYABILITY-STUDY-001`
- **New study:** `DEX-COPY-AUTONOMY-001`
- **Current maximum stage:** `RESEARCH`
- **Live execution authorization:** `false`

## Context

The original architecture required a human to approve every exact trade. That
is a strong safety boundary but can consume a material share of short-lived
copying alpha. The research question is therefore whether a machine can execute
faster without receiving open-ended authority over capital.

A long natural-language instruction is not an enforceable risk boundary. The
system must separate probabilistic reasoning from deterministic accounting,
policy enforcement, signing and venue actions.

## Decision

Adopt **bounded autonomy** as the prospective execution architecture.

The human remains:

- owner of the capital;
- sole authority for stage promotion;
- sole authority for model and policy promotion;
- sole authority for instrument, venue, action and recipient allowlists;
- sole authority for risk-limit increases;
- sole authority for capital allocation, leverage authorization and recovery;
- holder of the offline master/recovery authority;
- able to stop the system immediately.

After separate stage authorization, the AI system may:

- monitor public markets and approved source wallets;
- rank opportunities using promoted models;
- generate a typed trade intent;
- manage an approved position and propose an exit;
- trigger a deterministic emergency-risk workflow;
- operate without per-trade human approval only when every deterministic gate
  passes inside the frozen envelope.

The AI system may never:

- access or reconstruct a master private key;
- transfer or withdraw funds;
- approve, replace or deregister an agent wallet;
- add a venue, protocol, instrument, action type or recipient;
- raise size, loss, leverage, slippage, concentration or frequency limits;
- install or replace a policy, model, signer or adapter;
- suppress, reinterpret or override `BLOCK`;
- continue from unknown, stale, conflicted or unreconciled state;
- promote its own model, strategy or result;
- conceal or rewrite its audit trail.

## Enforcement model

Bounded autonomy is enforced in at least three independent layers:

1. **Typed intent boundary** — the AI emits a closed-schema intent, not arbitrary
   code or calldata.
2. **Deterministic policy and risk firewall** — canonical data is reloaded and
   all arithmetic, limits, expiry and action semantics are recomputed.
3. **Restricted signer and adapter** — only a one-time, short-lived, exact permit
   can be signed and submitted through an action allowlist.

The LLM has no direct key and no direct action endpoint.

## Failure semantics

The following are equivalent to a veto:

```text
UNKNOWN
MISSING
STALE
CONFLICTED
OUT_OF_DISTRIBUTION
UNRECONCILED
POLICY_HASH_MISMATCH
MODEL_HASH_MISMATCH
QUOTE_EXPIRED
SIGNER_STATE_UNCERTAIN
KILL_SWITCH_STATE_UNCERTAIN
```

The system may reduce risk when an emergency condition is positively verified.
It may not increase exposure to “recover” from an uncertain state.

## Relationship to prior decisions

- `DEC-008` remains fully current: all execution authorizations are false.
- `DEC-009` remains current for canonical ledgers, P&L, clusters and risk.
- `DEC-009` is superseded only prospectively where it implied that AI could
  never originate or execute a trade under any future authorization.
- The original `WALLET-COPYABILITY-STUDY-001` remains unchanged.
- This ADR creates no market result and no trading permission.

## Rejected alternatives

### Unrestricted hot wallet

Rejected because compromise of the AI or orchestration process would imply
general asset and action authority.

### “Safety by prompt”

Rejected because natural-language instructions are not a non-bypassable policy
engine and can be affected by ambiguity, prompt injection and model drift.

### Human approval for every trade

Retained as a comparison arm and fallback mode, but not selected as the only
prospective execution architecture because latency may destroy copyability.

### Fully deterministic strategy with no AI

Retained as the primary baseline. AI is included only if its incremental value
survives identical data, cost, latency and risk controls.

## Consequences

Positive:

- execution latency can be studied independently from signal quality;
- human governance and capital ownership remain explicit;
- AI compromise is contained by deterministic and cryptographic boundaries;
- every action can be tied to exact data, model, policy, risk and permit hashes.

Costs and risks:

- substantially more engineering and security validation;
- signer, policy and reconciliation services become critical infrastructure;
- vendor controls must be independently tested rather than accepted from
  marketing claims;
- correlated agents may amplify crowding and market stress;
- a policy bug can block all trading or permit an unsafe action.

## Promotion rule

This ADR authorizes only documentation, tests, architecture comparison and
preregistration. Any higher stage requires a new decision that names:

- exact commit and reviewed tree;
- exact policy and model hashes;
- exact account/subaccount and venue;
- exact action allowlist;
- exact capital and risk envelope;
- exact key-management and recovery design;
- exact test, shadow and security evidence;
- exact rollback and kill-switch procedure.

Silence, elapsed time, a profitable backtest or a vendor integration can never
serve as stage authorization.
