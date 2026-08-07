# DEX-COPY-AUTONOMY-001 — bounded autonomous execution design lane

Status: `DESIGN_STAGING_NO_EXECUTION_AUTHORIZATION`

Base commit at branch creation: `c11046bf288687c6945fe9b8f17141204d24aae6`.

## Purpose

Design the execution, policy, signer, latency and adversarial-security architecture for a future bounded-autonomous copy-trading system without touching the currently active canonical data/evidence lane.

The human remains governor and capital owner. A future AI agent may originate typed trade intents only inside a separately approved deterministic risk envelope. The AI never receives raw master-key access and never receives a generic exchange-action capability.

## Isolation contract

This branch MUST NOT modify or promote:

- `PROJECT_STATE.md`;
- canonical public-probe evidence or attestation;
- `research/wallet_copyability/probe_r1/**`;
- archive-access or metadata-canary work;
- canonical historical-data release state;
- parent wallet-copyability empirical results;
- repository-wide manifest/governance files while the parallel data lane is active.

No PR is opened from this branch until the parallel evidence/data lane reaches a stable canonical main and this branch is rebased/reconciled.

## Current authorization state

```text
research design                    allowed
historical replay                  not authorized here
non-signing shadow                 not authorized here
signed testnet/fork                not authorized here
live execution                     not authorized
capital allocation                 not authorized
leverage/margin changes            not authorized
client funds                       forbidden
AI self-modification of policy     forbidden
```

## Design deliverables

1. system trust-boundary architecture;
2. machine-readable AI/human/deterministic authority model;
3. closed Hyperliquid action surface;
4. typed trade-intent and one-time permit contracts;
5. signer, API-wallet and nonce isolation model;
6. kill-switch and recovery model;
7. component-level latency budget and research arms;
8. threat model and adversarial test matrix;
9. current official-source register;
10. execution-infrastructure vendor bake-off.

## Research principle

Autonomy may reduce execution delay, missed signals and inconsistent handling. It does not create alpha. The canonical economic estimand remains future **net follower expectancy after realistic latency and execution costs**, and that value must come from the separate parent data/research lane.

## Promotion rule

This directory is design evidence only. Nothing here becomes executable merely because the design is complete. Every later stage requires a separate, explicit human promotion and exact version/hash binding.