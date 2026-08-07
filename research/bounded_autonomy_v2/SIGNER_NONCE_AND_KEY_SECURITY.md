# Signer, nonce and key-isolation design

Status: design only. No key creation, signer installation or action submission is authorized.

## Key hierarchy

### Human master authority

- kept outside the AI runtime and ordinary application process;
- never copied into model context, environment variables available to the model, logs, artifacts or CI;
- used only for explicit human governance/recovery operations;
- not online in the normal autonomous execution path.

### Isolated trading account/subaccount

The strategy operates only inside an isolated account or subaccount with an explicitly bounded capital blast radius. No long-term treasury or unrelated holdings belong in that account.

### Dedicated Hyperliquid API wallet

Official Hyperliquid documentation states that API wallets (agent wallets) are signing identities acting for a master/subaccount and that nonce state is stored per signer. It recommends separate API wallets per trading process/subaccount.

Design consequence:

```text
one strategy process
    -> one isolated trading account/subaccount
    -> one dedicated API-wallet signer
    -> one nonce allocator
```

A single API wallet MUST NOT be shared across unrelated strategy processes.

## Signer interface

Forbidden interface:

```text
sign(arbitrary_bytes)
sign(arbitrary_json)
post_exchange(arbitrary_action)
```

Required interface shape:

```text
sign_permitted_action(
    exact_trade_permit,
    compiled_action,
    permit_service_attestation
)
```

The signer independently verifies:

1. permit signature/authenticity;
2. permit is unexpired;
3. permit ID has never been consumed;
4. policy/model/risk/data hashes match the current approved set;
5. action hash equals `compiled_action_sha256`;
6. account and signer addresses match configured identities;
7. action type is in the closed allowlist;
8. instrument, side, reduce-only, quantity, price, cloid and nonce exactly match the permit;
9. global kill-switch state is `ACTIVE`;
10. no unreconciled risk-increasing action blocks issuance.

Any failure returns `DENY` without producing a signature.

## Nonce model

Hyperliquid documents nonces as signer-scoped and recommends an atomic counter that may be fast-forwarded to current Unix milliseconds. Nonces must remain in the venue's accepted time window.

Required properties:

- a single writer per API-wallet nonce domain;
- atomic compare-and-increment;
- durable journal before signature release;
- monotonic non-reuse across process restart;
- no model-generated nonce;
- no wall-clock rollback reuse;
- duplicate request idempotency keyed by permit ID;
- explicit recovery procedure when local and venue state are uncertain.

### Crash sequence

The nonce and permit must be journaled before a signature leaves the signer. If a process crashes after signing but before acknowledgement, the nonce/permit remains `POSSIBLY_SUBMITTED`, never reusable. Recovery queries order status/fills/position using the deterministic cloid before any new risk-increasing action.

## CLOID design

Hyperliquid supports 128-bit client order IDs. Strategy orders should always use a deterministic collision-resistant cloid derived from bounded identifiers, for example conceptually:

```text
cloid = first_128_bits(
    H(strategy_id || permit_id || action_sequence || environment)
)
```

The exact derivation must be frozen later and tested for collision/non-reuse. The AI never chooses a raw cloid.

## Expiry

The venue supports `expiresAfter` for many actions. The permit has its own expiry and the venue action has an expiry. The effective deadline is the earlier of the two.

Rules:

- no hidden default expiry;
- expiry must be derived from the registered latency arm/policy;
- a stale permit cannot be refreshed by the signer;
- refreshing requires a new risk snapshot and new permit;
- permit expiry is measured against a monotonic/local trusted clock plus explicit skew bound.

## Key storage candidate requirements

No implementation is selected yet. Any future signer must provide:

- non-exportable or strongly isolated secret where practicable;
- process identity/authentication separate from the AI model;
- access logs for every signing attempt including denies;
- explicit revocation/rotation path;
- backup/recovery that does not expose the key to the AI runtime;
- no plaintext private key in repository, notebook, CI artifact or prompt;
- deterministic startup self-checks before enabling signing.

A native API-wallet private key stored as a normal application secret is acceptable only for disposable testnet engineering if separately authorized; it is not the target production security architecture.

## Revocation and recovery

The human governor must be able to stop signing independently of the strategy process. Recovery order:

1. set global execution state to `PAUSED`;
2. stop permit issuance;
3. disable/revoke signer access where supported;
4. reconcile all strategy-owned open orders and fills;
5. rotate signer if compromise is suspected;
6. require explicit human promotion to resume.

AI may request a pause. AI cannot clear a pause, rotate master authority or approve a new signer.

## Required future tests

- replay the same permit twice;
- mutate one action byte after permit issuance;
- reuse a consumed nonce;
- parallel nonce allocation race;
- process restart between journal and post;
- clock rollback/forward jump;
- stale permit after policy promotion;
- wrong subaccount with valid signer;
- correct subaccount with wrong signer;
- compromised AI requests forbidden transfer/withdraw/leverage action;
- revoke signer while an intent is in flight;
- websocket disconnect immediately after submission;
- duplicate REST/WebSocket acknowledgements.

Every unauthorized signature is a critical failure and an immediate no-go for progression.