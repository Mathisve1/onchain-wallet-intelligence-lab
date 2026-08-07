# Pure bounded-autonomy prototype

This staging prototype remains incapable of making a Hyperliquid network request or using a live/private signer key.

It now contains two deliberately separated zones:

```text
runtime-like offline control plane
fixture-only cryptographic parity oracle
```

The fixture oracle is test evidence only and is explicitly forbidden from import by the runtime-like executor/signer simulator.

## Control and reconciliation layer

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

## Durable execution layer

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

## Fixture-only cryptographic parity layer

The pinned official Hyperliquid SDK reference is:

```text
hyperliquid-dex/hyperliquid-python-sdk
commit 2fdb18f9517675ea03695a0962bd19eece9c83f0
version lineage 0.24.0
```

`crypto_fixture_oracle.py` independently implements only the primitives required to verify the public official vectors:

- Ethereum Keccak-256;
- pinned `float_to_wire` behavior;
- msgpack L1 action hashing;
- phantom-agent EIP-712 digest;
- secp256k1 deterministic test signing;
- low-S normalization;
- signer-address recovery.

It reproduces official public test signatures and the production phantom connection-ID fixture. It is **not** a candidate production signer implementation.

`signature_backend_adapter.py` then verifies external ECDSA output without trusting a backend-supplied Ethereum recovery ID. It supports strict DER and generic fixed-width P1363 parsing for fixtures, normalizes low-S and requires exactly one of `v=27/28` to recover the pre-registered signer address.

`provider_fixture_harness.py` additionally proves that a signature over a double-hashed or wrong-network digest is rejected when checked against the exact frozen Hyperliquid digest.

## Explicitly absent from runtime-like code

```text
urllib / requests / websocket
Hyperliquid SDK runtime import
live private key
seed phrase
real KMS/HSM/MPC call
real signature release
/exchange POST
wallet creation
testnet/mainnet venue connection
```

The fixture oracle contains test signing math only; the runtime validator forbids the runtime-like files from importing it or the backend signature adapter.

## Local engineering verification

Earlier control/reconciliation run:

```text
40 local regression tests
PASS
```

Durable permit/signer/fake-venue/wire run:

```text
31 local regression/torture tests
PASS
```

That second run includes a 1,000-case deterministic one-field action mutation torture test and a 32-way concurrent attempt to consume/sign one permit, where exactly one may succeed.

Crypto/backend fixture runs:

```text
14 Hyperliquid crypto parity tests          PASS
 8 signature encoding/recovery tests        PASS
 6 provider digest-compatibility tests      PASS
```

Across these separate local engineering runs there are currently **99 test cases**. This is not one canonical `99/99` GitHub CI result; the tests were executed in separate local construction runs and have not yet been reconciled into canonical repository CI.

## Critical findings retained

- Python SHA3-256 is not Ethereum Keccak-256.
- msgpack dictionary insertion order is signature-relevant.
- the pinned SDK currently serializes Python negative zero as `"-0"` rather than `"0"` in the observed `float_to_wire` path;
- a backend supporting secp256k1 does not automatically prove it signs the exact Hyperliquid EIP-712 digest without extra transformation;
- backend `v` is never trusted; recovery must match the registered signer address.

## Authorization

Nothing in this directory authorizes:

```text
provider network signing
Hyperliquid testnet actions
Hyperliquid mainnet actions
capital allocation
leverage
client funds
```

Before any promotion, this branch must be reconciled onto stable canonical `main`, added to the repository manifest, run through canonical CI/validators and independently reviewed in clean context.