# Pure bounded-autonomy prototype

This staging prototype is deliberately incapable of producing a real Hyperliquid signature or making a network request.

## Control and reconciliation layer already present

- fail-closed risk-envelope and typed-intent evaluation;
- AI veto/timeout behavior for risk-increasing entries;
- model-independent `DETERMINISTIC_SAFETY` cancel/reduce-only lane;
- strategy-owned cancel validation;
- position-bounded reduce-only validation;
- single-use permit semantics;
- human-only upward execution-state transitions;
- explicit intent -> policy -> permit -> sign -> submit -> ack/fill reconciliation states;
- partial fills remain unresolved until terminal;
- crash-after-sign uncertainty becomes `POSSIBLY_SUBMITTED`, never blind retry;
- blocked intents are terminal and cannot deadlock the next decision.

## Durable execution sprint now added

- SQLite `WAL` + `synchronous=FULL` crash-durable prototype;
- signer registry and explicit revocation;
- signer-scoped atomic monotonic nonce allocation;
- `UNIQUE(signer_id, nonce)` database enforcement;
- one transaction for nonce reservation + permit + action + audit event;
- permit consumption is atomic and at-most-once;
- append-only SHA-256 hash-chained audit events with SQL update/delete denial triggers;
- persistent owned-order registry;
- durable action/fill state and unresolved-risk gate;
- non-cryptographic `RestrictedSignerSimulator` that accepts only an exact consumed permit/action hash;
- deterministic offline fake Hyperliquid venue;
- full-fill, partial-fill, reject, duplicate-ack and lost-ack scenarios;
- restart and uncertain-submission reconciliation by cloid;
- pinned official Hyperliquid order/cancel wire fixtures;
- separate offline execution-sprint validator.

## Explicitly absent

```text
urllib / requests / websocket
Hyperliquid SDK import in runtime prototype
private key
seed phrase
real signature function
/exchange post
wallet creation
mainnet/testnet connection
cloud KMS/HSM/MPC call
```

## Local engineering verification

Before the durable sprint, the control/reconciliation layer had:

```text
40 local regression tests
PASS
```

The new durable permit/signer/fake-venue/wire sprint was independently exercised with:

```text
30 new local regression/torture tests
PASS
```

The new set covers concurrent nonce allocation, at-most-one concurrent permit consumption, action mutation denial, policy rotation, signer revocation, kill switch, append-only audit enforcement, process restart, partial fills, lost acknowledgements, duplicate acknowledgements and official-wire structural fixtures.

These figures are **local engineering feedback**, not a single canonical CI run and not empirical market evidence. Before any promotion the branch must be reconciled onto stable canonical `main`, added to the repository manifest, run through repository CI/validators and reviewed in clean context.

## Golden serialization boundary

The official Hyperliquid Python SDK is pinned for research fixtures at commit:

```text
2fdb18f9517675ea03695a0962bd19eece9c83f0
```

The pure prototype implements only structural order/cancel wire fixtures. It intentionally does **not** fake msgpack + Ethereum-keccak + EIP-712 signing with standard-library substitutes. Exact cryptographic parity is a later separately gated fixture stage.

## Authorization

Nothing in this directory authorizes network access, signing, testnet actions, live actions, leverage or capital allocation.