# DEX-COPY-AUTONOMY-001 — bounded autonomous execution lane

Status: `CREDENTIAL_FREE_STAGING_PROVIDER_RUN_NOT_AUTHORIZED`

Branch created from:

```text
c11046bf288687c6945fe9b8f17141204d24aae6
```

Latest coordination snapshot is recorded in `CREDENTIAL_FREE_GATE_STATUS.md`.

## Purpose

Build and test the execution, policy, signer, latency and adversarial-security architecture for a future bounded-autonomous copy-trading system without modifying the parallel canonical data/evidence lane.

The human remains governor and capital owner. A future AI agent may originate typed trade intents only inside a separately approved deterministic risk envelope. The AI never receives master-key material, signer-key material or a generic exchange-action capability.

## Isolation contract

This branch MUST NOT modify or promote:

- `PROJECT_STATE.md`;
- canonical public-probe evidence or attestation;
- `research/wallet_copyability/probe_r1/**`;
- archive-access/inventory/canary work;
- canonical historical-data release state;
- parent wallet-copyability empirical results;
- repository-wide manifest/governance files while the parallel data lane is active.

No legitimate PR is opened from this branch until the parallel evidence/data lane reaches a sufficiently stable canonical `main` and this work is rebuilt/reconciled cleanly against that state.

## Current authorization state

```text
research/design                              allowed
pure offline implementation                 allowed
offline public fixture crypto parity        allowed
ephemeral provider capture preparation      allowed
provider network signing calls               NOT AUTHORIZED
cloud key creation                           NOT AUTHORIZED
provider spend                               NOT AUTHORIZED
historical replay here                       NOT AUTHORIZED
non-signing shadow                           NOT AUTHORIZED
signed testnet/fork                          NOT AUTHORIZED
Hyperliquid mainnet execution                NOT AUTHORIZED
capital allocation                           NOT AUTHORIZED
leverage/margin changes                      NOT AUTHORIZED
client funds                                 FORBIDDEN
AI self-modification of policy               FORBIDDEN
```

## Implemented deliverables

1. system trust-boundary architecture;
2. machine-readable AI/human/deterministic authority model;
3. closed Hyperliquid action surface;
4. typed trade-intent and one-time permit contracts;
5. human-frozen risk-envelope schema;
6. signer/API-wallet/nonce isolation model;
7. kill-switch and recovery model;
8. component-level latency contract and research arms;
9. threat model and adversarial test matrix;
10. execution-infrastructure vendor bake-off;
11. durable SQLite permit/action/audit prototype;
12. atomic nonce allocation and permit consumption;
13. restricted non-cryptographic signer simulator;
14. offline fake Hyperliquid venue and crash/reconciliation harness;
15. append-only hash-chain audit design;
16. pinned official Hyperliquid structural serialization fixtures;
17. independent test-only Keccak/msgpack/EIP-712/secp256k1 fixture parity;
18. backend-neutral DER/P1363 ECDSA recovery adapter;
19. SPKI/JWK secp256k1 public-key normalization and address derivation;
20. exact provider parity fixture digests;
21. ephemeral provider-capture and sanitized-evidence contracts;
22. AWS/GCP/Azure provider-only parity runbook;
23. machine-readable provider-spend/network authorization gate, currently closed;
24. fail-closed validators preventing fixture crypto leakage into runtime and raw provider capture commits.

## Execution architecture

```text
read-only point-in-time signal/data
        ↓
deterministic eligibility + follower-EV/risk
        ↓
optional registered AI critic: PASS / VETO only
        ↓
closed typed intent
        ↓
deterministic policy/risk firewall
        ↓
exact one-time TradePermit
        ↓
durable journal + nonce/CLOID allocation
        ↓
restricted signer boundary
        ↓
closed Hyperliquid action adapter
        ↓
venue acknowledgement/fills
        ↓
exact reconciliation
        ↓
new risk unlocked only when prior risk-increasing action is terminal
```

The production signer boundary is not implemented or authorized. The current runtime-like signer is a non-signature simulator. Cryptographic fixture code is test-only and cannot be imported by that runtime-like path.

## Safety-action separation

New risk:

```text
PLACE_IOC_LIMIT
→ full deterministic entry gates
→ registered AI critic if required
→ one-time permit
```

Safety preserving:

```text
CANCEL_BY_CLOID
REDUCE_ONLY_IOC
→ DETERMINISTIC_SAFETY
→ no AI dependency
→ cannot open/increase absolute risk
```

An AI/model/provider outage therefore cannot become the only mechanism preventing cancellation or deterministic risk reduction.

## Scientific boundary

Autonomy may reduce reaction time, missed signals and inconsistent execution. It does not create alpha.

The canonical economic estimand remains future:

```text
net follower expectancy
= executable follower outcome
- fees/funding/spread/slippage/impact
- failures/misses
- attributable execution cost
```

Whether copyable alpha exists is owned by the separate parent data/research lane. This execution lane may not invent wallet P&L, ranking, clusters or profitability results.

## Local engineering evidence

Previously executed separate local construction runs:

```text
40 control/reconciliation tests                 PASS
31 durable execution/torture tests              PASS
14 Hyperliquid crypto parity tests              PASS
 8 signature encoding/recovery tests            PASS
 6 provider digest-compatibility tests          PASS
----------------------------------------------------
99 tests across separate local runs
```

This is not canonical GitHub CI and must not be described as one `99/99` run. Additional provider-capture/public-key/evidence tests were added later and are deliberately not added to that count until formally rerun.

## Exact next gate

Credential-free engineering is complete through provider-capture/evidence preparation.

The next capability requires an **explicit human-governed provider-only experiment authorization** that sets provider(s), disposable cloud context, one-time EUR budget, maximum sign requests, region, minimum-privilege identities, teardown plan and current pricing evidence.

Even a successful AWS/GCP/Azure signer parity experiment would create only a `COMPATIBLE_CANDIDATE`; it would not authorize registration as a Hyperliquid agent, testnet orders, mainnet orders, leverage or capital.

## Promotion rule

Nothing in this directory becomes executable merely because a design, test fixture or provider comparison passes. Every higher stage requires a separate human promotion and exact version/hash binding.