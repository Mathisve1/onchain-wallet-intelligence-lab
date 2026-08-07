# Threat model

## Protected assets

- research integrity and point-in-time lineage;
- master and agent signing material;
- allocated pilot capital;
- policy, model and allowlist integrity;
- order, fill, position and cash reconciliation;
- audit and incident evidence;
- availability of the kill switch and recovery path;
- privacy of wallet and account data.

## Trust zones

1. public venue and blockchain data;
2. immutable raw storage;
3. canonical deterministic ledger;
4. statistical models;
5. AI/LLM process;
6. policy and risk service;
7. permit issuer;
8. restricted signer;
9. venue adapter;
10. human governance and offline recovery.

Public data, vendor APIs and the AI process are untrusted. The policy service,
signer and human recovery path require independent hardening.

## Threat catalogue

| ID | Threat | Primary control | Failure result |
|---|---|---|---|
| T01 | Prompt injection through labels, metadata, websites or model context | structured sanitized inputs; no tool/key in AI process | `BLOCK` |
| T02 | Hallucinated instrument, size, price or action | closed intent schema; deterministic reconstruction | `BLOCK` |
| T03 | AI expands its policy or risk limit | immutable promoted policy hash; no policy tool | `BLOCK` and incident |
| T04 | Source wallet manipulates followers | copyability/cluster filters; follower-EV; concentration limits | skip source/event |
| T05 | Hidden hedge or service wallet mistaken for directional skill | wallet-style and entity controls | exclude |
| T06 | Future-information or survivorship leakage | `first_seen_at <= selection_timestamp`; walk-forward | reject result |
| T07 | Stale or inconsistent market/source state | expiry, provider comparison, backfill and sequence checks | `BLOCK` |
| T08 | Compromised AI/orchestrator | no signing secret or direct action egress | contained; signer denies |
| T09 | Compromised policy service | independent signer verification and hard action allowlist | deny; revoke |
| T10 | Compromised signer | isolated capital; action-type denial; rate/size caps; kill switch | contain and revoke |
| T11 | API-wallet replay after deregistration/pruning | never reuse addresses; nonce ledger; expiry; rotation protocol | deny and burn key |
| T12 | Duplicate order after timeout/retry | client order ID, idempotency record and reconciliation | pause |
| T13 | Partial fill or source reversal | explicit partial-fill state machine and reduce-only exit | reconcile or reduce |
| T14 | Transfer, withdrawal or agent-approval payload | action discriminator allowlist; no generic exchange call | `BLOCK` |
| T15 | Leverage or margin-mode mutation | deny action type; human-only promotion | `BLOCK` |
| T16 | Quote or permit expires during signing | short expiry and final pre-submit check | discard |
| T17 | Provider outage or reconnect gap | redundant observation, snapshot/backfill and gap report | pause |
| T18 | Model drift or out-of-distribution signal | versioned drift detector; confidence gate | skip source/event |
| T19 | Correlated agents crowd the same trade | capacity, crowding and concentration stress | shrink or skip |
| T20 | Kill switch unavailable or ambiguous | independent guardian and signer-default-off | no new signature |
| T21 | Reconciliation mismatch or orphan position | exact order/fill/position ledger | global pause |
| T22 | Vendor policy or API behavior changes | versioned capability probe and contract tests | block integration |
| T23 | Secret exfiltration through logs or traces | structured redaction and no secret in strategy process | revoke and incident |
| T24 | Dependency or supply-chain compromise | pinned dependencies, minimal stack, provenance and scans | block release |
| T25 | Human governance mistake | two-step review, bounded pilot and recovery path | contain/pause |

## Hyperliquid API-wallet boundary

Official documentation describes API/agent wallets as signers on behalf of a
master account or subaccount and recommends separate wallets per process. It
also documents nonce-state pruning and warns against reusing deregistered
addresses.

The current evidence does not establish a venue-native, fine-grained
order-only/spend-limit policy sufficient for this project. Therefore:

- use an isolated subaccount;
- expose only a closed set of order/cancel actions through our adapter;
- deny every transfer, withdrawal, agent-management, builder-fee, leverage,
  vault and arbitrary exchange action before signing;
- use a new API wallet for every key lifecycle;
- maintain an independent nonce and signed-action ledger;
- adversarially test exact permissions on testnet before any capital.

An undocumented capability is treated as potentially available and therefore
unsafe until proven otherwise.

## AI-specific red team

The test plan must attempt:

- direct and indirect prompt injection;
- fake system messages in source metadata;
- malformed JSON and duplicate keys;
- non-finite numbers and integer overflows;
- Unicode-confusable instruments and addresses;
- model request timeout and partial output;
- contradictory model agents;
- confidence fabrication;
- tool-call argument mutation;
- reuse of a prior permit;
- model/policy hash mismatch;
- attempts to submit an action after a kill switch.

Success means the AI can be wrong, compromised or unavailable without obtaining
authority outside the deterministic envelope.

## Residual risk

No architecture removes market loss, model error, venue failure, chain failure,
software bugs or key compromise. The objective is to reduce the probability and
blast radius, detect failures quickly, and make uncertain state fail closed.
