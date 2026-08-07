# Execution-infrastructure bake-off

Status: `UNSCORED_DESIGN_STAGE`.

Official vendor documentation defines only testable capability hypotheses. No vendor is accepted as secure, low-latency or production-ready from its own claims.

## Frozen scoring rubric

| Criterion | Weight | Critical no-go? |
|---|---:|---:|
| exact Hyperliquid HyperCore perpetual compatibility | 18 | yes |
| non-bypassable closed action surface | 18 | yes |
| key isolation from AI/application | 14 | yes |
| human revocation/recovery | 10 | yes |
| measured p50/p95 end-to-end signing/submission latency | 12 | no |
| exact audit/action/reconciliation evidence | 10 | yes |
| permit/expiry/replay/nonce controls | 8 | yes |
| outage/fail-closed behavior | 5 | yes |
| portability / vendor lock-in | 3 | no |
| engineering/operational cost | 2 | no |

A critical failure is `NO_GO` regardless of weighted score.

## Candidate A — native Hyperliquid API wallet + custom policy/signer gateway

Provisional role: `PRIMARY_ENGINEERING_CANDIDATE`.

### Why it is attractive

- venue-native action/signature format;
- official API-wallet model for automated trading;
- separate API wallets are recommended per trading process/subaccount;
- official docs expose IOC orders, cloids, expiry, order status, realtime order/fill streams and WebSocket action posting;
- likely minimum vendor/intermediation latency.

### Why it is not safe by default

The official SDK exposes far more than orders/cancels, including fund movement and governance-like actions. A normal SDK object with a private key is therefore too broad for an AI runtime.

Mandatory custom controls:

```text
AI
 -> typed intent only
 -> deterministic policy service
 -> exact one-time permit
 -> isolated signer
 -> tiny adapter exposing IOC/cancel/reduce-only only
```

### Tests required

- enumerate every exported/signable action in exact SDK version;
- prove forbidden action attempts never reach signing;
- measure HTTP vs WebSocket post latency;
- prove nonce behavior under parallelism/restart;
- prove signer/account mapping and revocation;
- exact cloid/order/fill reconciliation;
- dependency/serialization golden fixtures.

## Candidate B — MetaMask Agent Wallet

Provisional role: `CONTROLLED_VENDOR_COMPARATOR`.

Official material advertises Guard Mode with spend limits, protocol allowlists, security checks and human escalation, and includes Hyperliquid among agent use cases.

Unknowns that must be resolved hands-on:

- exact HyperCore action surface exposed to agents;
- whether leverage, transfer, withdrawal and agent-management actions can be technically denied rather than merely policy-reviewed;
- exact signer/custody boundary and export implications;
- whether we can bind our own immutable strategy/model/risk hashes;
- policy decision logs available to our audit ledger;
- programmatic latency, rate limits and availability;
- outage/2FA behavior;
- ability to use short-lived one-time permits rather than broad session authority.

No production selection until these are proven.

## Candidate C — Cobo Agentic Wallet

Provisional role: `POLICY_MPC_BENCHMARK`.

Official Cobo documentation describes owner-approved Pacts, per-operation policy evaluation, completion conditions, spending counters and MPC-backed wallet designs. This strongly resembles the desired bounded-authority pattern.

Unknowns:

- exact Hyperliquid HyperCore perpetual support;
- exact action granularity for non-EVM venue actions;
- end-to-end signing latency;
- whether our one-time permit/hash-binding model can be represented without losing guarantees;
- vendor availability/outage semantics;
- independent audit evidence for the exact deployed components;
- migration/export/recovery boundaries.

If HyperCore support is not explicit and testable, Cobo remains a conceptual policy benchmark rather than executor candidate.

## Candidate D — Almanak

Provisional role: `SOFTWARE_ARCHITECTURE_REFERENCE`.

Official docs describe intent-based strategy interfaces, a gateway-only architecture, secrets outside strategy containers, policy-enforced agent tooling, backtesting/fork tooling and HyperEVM among supported networks.

Important distinction:

`HyperEVM support != Hyperliquid HyperCore perpetual execution support`.

Use Almanak to study:

- intent vocabulary and compilation separation;
- gateway isolation;
- policy layering;
- fault/stuck detection;
- simulation/fork workflow;
- observability.

Do not assume its generic tools are safe to place in our signer boundary.

## Candidate E — Safe / modules / guards

Provisional role: `FUTURE_EVM_DEX_TRACK_REFERENCE`.

Safe officially documents AI-agent spending limits and programmable modules/guards. It is relevant when the project later studies Uniswap/PancakeSwap/Base/EVM execution.

It is not the initial HyperCore executor. Safe also explicitly warns that modules can execute powerful transactions and a broken guard can cause denial of service. Any future custom Safe module/guard requires audit and a recovery path.

## Hands-on protocol

For each candidate that survives paper review:

1. use a disposable test identity/account;
2. record exact software/service version and date;
3. enumerate every exposed read/write/signing operation;
4. prove the allowed IOC/cancel/reduce-only paths;
5. attempt every forbidden action class;
6. measure policy-check, signing, transport and acknowledgement latency separately;
7. test stale intent, expiry, replay, duplicate and mutation;
8. test nonce collision and process restart;
9. test service/network outage;
10. revoke authority and measure effective cutoff;
11. export/compare audit logs with our canonical ledger;
12. execute recovery without AI availability;
13. score only the exact tested version.

## Current provisional choice

For the first future signed-testnet prototype, the design should prefer:

```text
Hyperliquid testnet
+ disposable isolated account/subaccount
+ dedicated API wallet
+ our deterministic policy/risk service
+ our one-time permit contract
+ isolated restricted signer
+ our closed venue adapter
```

MetaMask is the highest-priority external comparator if exact programmatic Hyperliquid controls are accessible. Cobo is the strongest policy/MPC conceptual comparator. Almanak is an architecture reference. Safe is held for the later EVM DEX lane.

This provisional choice creates no execution authorization.