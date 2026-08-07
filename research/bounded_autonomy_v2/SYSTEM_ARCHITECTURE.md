# Bounded-autonomous execution architecture

Status: design only. No execution authorization.

## Core rule

The system is not an LLM connected to a wallet. It is a set of independently constrained services in which an AI model can only propose a typed intent. Deterministic services decide whether that intent is admissible, construct the exact action, bind it to an expiring permit, and reconcile the result.

```text
read-only market + wallet streams
          |
          v
point-in-time feature cache
          |
          v
eligibility + follower-EV/risk arithmetic  <--- deterministic
          |
          +------------------------------+
          |                              |
          v                              v
AI contextual critic                deterministic baseline
(no keys, no raw action)                 |
          |                              |
          +------------> typed intent <--+
                            |
                            v
                   policy/risk firewall
                            |
                      ALLOW / BLOCK
                            |
                            v
                 exact action compiler
                            |
                            v
                  one-time TradePermit
                            |
                            v
                  isolated signer service
                            |
                            v
                   closed venue adapter
                            |
                            v
                 Hyperliquid /exchange
                            |
                            v
      order updates + fills + position state
                            |
                            v
                  exact reconciliation
                            |
                     next action unlocked
```

## Trust boundaries

### T0 — human governance

The human governor alone may promote stages, add capital, raise risk, install/rotate signers, alter allowlists or authorize leverage. These actions are not reachable from AI tools.

### T1 — read-only intelligence

Market/wallet collectors and feature stores may read venue state. They cannot sign, transfer or call `/exchange`.

### T2 — AI reasoning

The AI receives a minimized structured context. It cannot receive master secrets, seed phrases, API-wallet private keys, generic RPC credentials with write authority, raw signer handles or arbitrary action tools.

The AI output is accepted only if it conforms to a closed typed-intent schema. Natural-language text cannot become calldata or an exchange action.

### T3 — deterministic policy/risk firewall

The firewall re-derives every safety-critical field from canonical inputs. It must not trust AI-provided arithmetic for:

- eligible instrument/action;
- max quantity/notional;
- price/slippage band;
- reduce-only requirement;
- risk budget;
- data freshness;
- policy/model/risk hashes;
- previous-action reconciliation;
- kill-switch state.

Any mismatch is `BLOCK`.

### T4 — permit service

The permit service creates a single-use, short-lived authorization binding the exact intent to exact policy/risk/data/model identities and an exact account/action surface. The permit must be unusable after mutation, expiry, replay or policy-version change.

### T5 — signer

The signer owns only a dedicated API-wallet key for one isolated trading process/account. The signer accepts only a validated permit plus an action produced by the closed compiler. It has no generic `sign(bytes)` interface accessible to the AI process.

### T6 — venue adapter

The adapter exposes a deliberately tiny interface such as `place_ioc_limit`, `cancel_by_cloid`, and `reduce_only_ioc`. It does not expose arbitrary Hyperliquid exchange actions.

### T7 — reconciliation

A new risk-increasing action is blocked until the previous action is reconciled against acknowledgement, order update, fills and current position. WebSocket gaps require REST/backfill reconciliation before continuing.

## Proposed service separation

| Service | May read market | May call AI | May hold API key material | May call `/exchange` | May change policy |
|---|---:|---:|---:|---:|---:|
| collector | yes | no | no | no | no |
| feature/risk service | yes | no | no | no | no |
| AI critic | structured only | yes | no | no | no |
| policy firewall | yes | no | no | no | no |
| permit service | policy state | no | no | no | no |
| signer | no | no | dedicated API-wallet key only | through adapter only | no |
| venue adapter | venue responses | no | no | exact allowlisted actions | no |
| reconciliation service | yes | no | no | cancel/reduce emergency path only if separately authorized | no |
| governor console | yes | optional read-only | master authority via separate secure path | governance only | yes |

## Action lifecycle

1. A source signal is observed with exact first-seen time.
2. Point-in-time deterministic eligibility is calculated.
3. Risk service computes the maximum permissible exposure and execution envelope.
4. AI critic may veto or lower confidence; it cannot enlarge the envelope.
5. Intent compiler accepts only schema-valid values already bounded by deterministic outputs.
6. Policy firewall rechecks current state immediately before permit issuance.
7. Permit binds exact hashes, action, account, quantity, price band, expiry, cloid and nonce domain.
8. Signer verifies permit authenticity and one-time status.
9. Adapter constructs only the registered Hyperliquid action type.
10. Signed action is submitted with a short `expiresAfter` where supported.
11. Order/fill streams and read-back state are reconciled.
12. Permit is burned. Uncertain reconciliation blocks the next risk-increasing action.

## Emergency path

The emergency path is intentionally simpler than entry logic:

- set global state to `PAUSED`;
- stop new permits;
- revoke/disable session/API-wallet signing where available;
- cancel strategy orders through a deterministic allowlisted path;
- optionally permit only reduce-only close actions under a separately frozen emergency policy;
- require human recovery to return to `ACTIVE`.

An AI model may trigger a pause request, but it cannot unpause the system.

## Hyperliquid-specific implications

Official Hyperliquid documentation describes API wallets as signers for a master or subaccount, with nonces stored per signer. It recommends separate API wallets for different trading processes/subaccounts and an atomic nonce counter. This supports one dedicated signer per isolated process rather than a shared agent key.

The official exchange API includes many actions beyond orders and cancels, including transfers, withdrawals, leverage changes, agent management and builder-fee actions. Therefore the adapter must be an explicit allowlist rather than a generic pass-through wrapper.

Official WebSocket subscriptions provide order updates, fills, funding and ledger updates, but connections may disconnect and snapshots/backfill must be handled. Reconciliation is consequently a hard safety dependency rather than mere observability.