# Credential-free bounded-autonomy gate status

Verified: 2026-08-07 after the provider-capture/evidence hardening sprint.

Status: `CREDENTIAL_FREE_DESIGN_AND_OFFLINE_ENGINEERING_COMPLETE_PROVIDER_RUN_BLOCKED`.

## Repository coordination

```text
canonical main observed:
0e8a678644c29548a38ebfa1c0af91d4a9a92c09

canonical main meaning:
HL-ARCHIVE-INVENTORY-001 preregistered metadata/access/cost-only
by the parallel data lane

autonomy branch:
research/bounded-autonomy-execution-v2-20260807

branch relation at final verification:
ahead of main = 108 commits
behind main = 2 commits
merge base = c11046bf288687c6945fe9b8f17141204d24aae6
```

Every current autonomy-branch difference from `main` remains under:

```text
research/bounded_autonomy_v2/
```

No canonical archive, probe-evidence, parent wallet-data or `PROJECT_STATE` file is modified by this lane.

The only intentionally open stale autonomy PR is #6. It must not be merged or force-updated. Accidental PRs #11 and #12 are closed without merge.

## Credential-free work completed

### Governance and authority

- human governor/capital-owner/recovery authority;
- AI authority ceiling and permanent forbidden powers;
- deterministic fail-closed risk/policy authority;
- all execution/capital/leverage/client-fund authorizations false.

### Execution control plane

- closed `PLACE_IOC_LIMIT`, `CANCEL_BY_CLOID`, `REDUCE_ONLY_IOC` surface;
- entry versus deterministic-safety separation;
- typed Trade Intent and one-time Trade Permit;
- risk envelope;
- kill switch and recovery state machine;
- durable reconciliation state machine;
- append-only hash-chained audit design.

### Offline durable prototype

- SQLite WAL + FULL synchronous durability;
- atomic signer-scoped nonce allocation;
- atomic permit/action/audit issuance;
- at-most-once permit consumption;
- signer registry/revocation;
- persistent strategy-owned order registry;
- restricted non-cryptographic signer simulator;
- fake Hyperliquid venue;
- crash/lost-ack/partial-fill recovery;
- deterministic mutation/concurrency torture tests.

### Hyperliquid serialization/crypto parity

Pinned official SDK fixture:

```text
hyperliquid-dex/hyperliquid-python-sdk
2fdb18f9517675ea03695a0962bd19eece9c83f0
version lineage 0.24.0
```

Locally demonstrated against public official vectors:

- exact order/action structural parity;
- pinned numeric wire behavior;
- msgpack action-hash parity;
- Ethereum Keccak-256 parity;
- phantom-agent EIP-712 parity;
- mainnet/testnet source separation;
- official public r/s/v vectors;
- public signer-address recovery;
- vault and schedule-cancel fixture parity.

The test-only crypto oracle is not a production signer and is forbidden from runtime-like executor imports.

### Candidate signer adaptation

Offline adapters now support:

- strict DER ECDSA parsing;
- fixed-width P1363 fixture parsing;
- high-S to low-S normalization;
- Ethereum `v` derivation only by exact expected-address recovery;
- rejection of malformed signatures, wrong digest and wrong signer;
- explicit double-hash detection;
- secp256k1 public-key normalization from SPKI DER or JWK x/y;
- Ethereum address derivation from normalized public point.

### Provider evidence preparation

Prepared but not executed:

- AWS KMS candidate protocol;
- Google Cloud KMS candidate protocol;
- Azure Key Vault / Managed HSM candidate protocol;
- eight frozen exact Hyperliquid provider-parity digests;
- ephemeral raw capture schema;
- sanitized evidence schema;
- offline evidence builder/CLI;
- provider-specific immutable key-version checks;
- p50/p75/p90/p95/p99 latency evidence contract;
- disable/revoke test requirement;
- raw capture `.gitignore` and committed-capture rejection.

## Test evidence boundary

Previously executed local construction runs remain:

```text
40 control/reconciliation tests                 PASS
31 durable execution/torture tests              PASS
14 Hyperliquid crypto parity tests              PASS
 8 signature encoding/recovery tests            PASS
 6 provider digest-compatibility tests          PASS
----------------------------------------------------
99 tests across separate local runs
```

This is **not** one canonical `99/99` GitHub CI run.

Additional SPKI/JWK/capture/evidence tests and validators were added after those runs. Their primitives were sanity-checked during construction, but they are **not added to the 99 count** until a later formal consolidated test run is actually executed and recorded.

## Current blockers

```text
provider_network_call_authorized = false
AWS_KMS_authorized = false
GOOGLE_CLOUD_KMS_authorized = false
AZURE_KV_OR_HSM_authorized = false
provider_budget_eur = UNSET_BLOCKER
maximum_provider_sign_requests = UNSET_BLOCKER
credentials_registered = false
Hyperliquid_testnet_authorized = false
Hyperliquid_mainnet_authorized = false
capital_allocation_authorized = false
```

No code path may interpret successful offline cryptographic parity as permission to create a cloud key, incur provider cost, register a Hyperliquid API wallet or submit a signed exchange action.

## Exact next gate

The next new capability is **not technical implementation**. It is an explicit human-governed provider-only experiment authorization.

Before one provider request, freeze:

1. selected provider(s);
2. disposable account/project/subscription context;
3. maximum one-time EUR budget;
4. maximum provider-sign request count;
5. exact region/location;
6. minimum-privilege runtime identity;
7. key-admin identity separated from runtime identity where practical;
8. disposable key teardown/destruction plan;
9. current provider pricing evidence;
10. exact autonomy source commit after later reconciliation with stable canonical `main`.

Even if this provider-only parity gate succeeds, it authorizes no Hyperliquid testnet action. Testnet remains a later independent gate.