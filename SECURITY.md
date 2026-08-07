# Security

## Current boundary

Do not commit or expose:

- private keys, seed phrases or recovery material;
- Hyperliquid API-wallet credentials;
- exchange, RPC or cloud secrets;
- `.env` files;
- OAuth refresh tokens;
- signing shares, HSM/KMS credentials or session keys;
- raw vendor authentication responses;
- personally identifying wallet-owner claims without a lawful public source.

All current network scripts are read-only and capability-allowlisted. The
bounded-autonomy governance package does **not** authorize signing libraries,
`/exchange`, orders, cancels, transfers, withdrawals or capital.

## Prospective process isolation

A future implementation must use separate trust domains:

```text
untrusted data and AI process
        |
        v
deterministic intent validator
        |
        v
deterministic policy and risk service
        |
        v
restricted signer with no general-purpose interface
        |
        v
allowlisted venue adapter
```

The AI process receives no signing secret and no direct network route to an
action endpoint. It can emit only a schema-valid intent. The policy service must
recompute all risk fields from canonical data and may discard, shrink or block
the intent. The signer accepts only exact, short-lived, one-time action permits
from the policy service.

## Hyperliquid-specific requirements

Before any signed scope can open:

- use an isolated account or subaccount containing only explicitly allocated
  pilot capital;
- use a separate API/agent wallet per trading process and subaccount;
- never reuse a deregistered or expired API-wallet address;
- maintain an atomic nonce allocator and reject duplicate or stale nonces;
- deny transfers, withdrawals, agent approval/replacement, builder-fee changes,
  leverage changes, vault actions and arbitrary exchange actions;
- allow only preregistered order/cancel action schemas;
- require explicit `reduce_only` semantics for emergency risk reduction;
- stop signing when account, order or fill reconciliation is incomplete;
- keep the master key offline from the strategy, AI, policy and signer services.

The venue-native API wallet is a signing primitive, not by itself proof of a
granular risk envelope. Application-level controls must therefore fail closed
until exact venue permissions are independently verified.

## Model and prompt security

All external text, token metadata, wallet labels, social data, vendor responses
and model-generated explanations are untrusted. They cannot:

- create a tool or network capability;
- alter system or policy instructions;
- supply canonical arithmetic;
- choose a recipient or action type;
- change promoted model or policy hashes;
- suppress a risk flag;
- authorize a trade.

Prompt-injection resistance is enforced through data minimization, typed inputs,
tool isolation and deterministic policy checks, not through a longer prompt.

## Emergency controls

A future signed system requires:

- local and remote kill switches;
- automatic signer disablement;
- cancel-all where supported;
- expiry of outstanding permits;
- an offline recovery path;
- immutable incident and reconciliation logs;
- a tested rule that an uncertain kill-switch state means no new signature.

Any change that adds a signing dependency, action endpoint or credential must
fail review unless a separate governance decision explicitly opens that
development stage. No such execution authorization currently exists.
