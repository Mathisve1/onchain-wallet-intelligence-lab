# Restricted signer backend requirements

Status: design only. No cloud/HSM/MPC signer is selected or authorized.

## Objective

The production signer must be able to produce exactly the signature Hyperliquid expects for the already permit-bound L1 action **without exposing private key material or a generic signing primitive to the AI/runtime**.

Supporting secp256k1 alone is not sufficient. Acceptance requires exact parity for the Hyperliquid signing pipeline, including action serialization, msgpack bytes, nonce/vault/expiry binding, keccak action hash, phantom-agent EIP-712 payload, `r/s/v` or recoverable-signature semantics, low-S handling where relevant, signer-address recovery and venue acceptance on testnet.

## Mandatory backend properties

1. secp256k1/ECDSA signing capability compatible with the exact Hyperliquid digest/signature format;
2. private material non-exportable or strongly isolated where practicable;
3. no API that allows the AI process to submit arbitrary digests directly;
4. signer service accepts only our validated one-time permit plus compiled action;
5. key/version/public-address identity is pinned and auditable;
6. explicit disable/revoke/rotate procedure independent of the AI service;
7. complete allow/deny signing-attempt audit trail without secret leakage;
8. deterministic failure behavior during timeout, quota exhaustion and backend outage;
9. measured p50/p95/p99 signing latency;
10. recovery must preserve nonce/permit non-reuse.

## Candidates for later hands-on testing

### Dedicated Hyperliquid API-wallet key in isolated signer process

Reference baseline because it matches the official SDK key model directly. A plain application secret is acceptable only for a separately authorized disposable testnet experiment, not as the target production design.

### AWS KMS

Official AWS documentation exposes `ECC_SECG_P256K1` signing keys for cryptocurrency-oriented use. This is only a capability hypothesis. We still need to prove that the returned ECDSA signature can be transformed/used with exact Hyperliquid recovery semantics without exporting the private key.

Primary documentation: `https://docs.aws.amazon.com/kms/latest/developerguide/symm-asymm-choose-key-spec.html`

### Google Cloud KMS / Cloud HSM

Official Google documentation lists `EC_SIGN_SECP256K1_SHA256`; current documentation notes secp256k1 support in the HSM protection level and normalized/lower-S signatures. Exact Ethereum/Hyperliquid recovery-byte compatibility remains a test requirement.

Primary documentation: `https://docs.cloud.google.com/kms/docs/algorithms`

### Azure Key Vault / Managed HSM

Official Microsoft documentation lists EC-P256K / secp256k1 with `ES256K` signing. Exact raw/DER signature conversion and Hyperliquid recovery semantics remain unproven until fixture and testnet validation.

Primary documentation: `https://learn.microsoft.com/en-us/azure/key-vault/keys/about-keys-details`

### MPC / agent-wallet providers

Cobo and similar systems remain candidates only if the exact HyperCore action surface, key/recovery model, one-time permit binding, latency and deny semantics are demonstrable for the tested product/version.

## Required parity test

For each backend:

1. create disposable test key and record public address;
2. use one frozen official-SDK fixture set;
3. compute the exact Hyperliquid signing payload outside the backend;
4. request backend signing through a restricted adapter;
5. parse backend signature into the exact required form;
6. recover signer address locally and require exact match;
7. compare semantic signature acceptance against the official Python SDK fixture;
8. only after offline recovery succeeds, submit a separately authorized harmless testnet IOC/cancel flow;
9. measure latency and failure behavior;
10. attempt arbitrary-digest, wrong-policy, wrong-key-version, replay and revoked-key signing.

A backend that supports the curve but cannot satisfy exact recovery/venue semantics is `NO_GO`.

## Security ranking principle

Do not choose the backend by marketing labels such as "HSM" or "MPC" alone. The winning design is the one that gives the smallest effective signing authority, exact compatibility, independent revocation and the strongest empirically tested failure behavior at acceptable latency.