# Signer-provider hands-on parity runbook

Status: `PREREGISTERED_PROCEDURE_PROVIDER_NETWORK_NOT_AUTHORIZED`.

No AWS, Google Cloud or Azure request is authorized by this document. Provider spend budget is `UNSET_BLOCKER`. Hyperliquid testnet/mainnet remain out of scope.

## Purpose

When the human governor later authorizes a small provider-only budget and disposable credentials, this runbook tests whether a provider can sign the exact frozen 32-byte Hyperliquid phantom-agent EIP-712 digest without hidden transformation.

No candidate key is registered with Hyperliquid during this gate.

## Frozen input

Use only a fixture from `PROVIDER_PARITY_FIXTURES.json`. Begin with:

```text
fixture: HL-OFFICIAL-DUMMY-MAINNET
eip712 digest:
e0aabfac88a47d3e7028b6ba6a94b30c8afcfffac26cbce788cf362b1312eafa
```

Write the 32 raw bytes to a local temporary file. Hash/check the file before every provider series. Never substitute a prose message or hex text for the raw digest bytes unless the exact provider API explicitly expects that encoding.

## Common protocol

1. create one disposable, non-production secp256k1 signing key;
2. freeze an immutable key version/resource identity;
3. retrieve the public key;
4. normalize public key to either SPKI DER or JWK x/y capture form;
5. derive the Ethereum address independently before accepting any signature;
6. warm the provider with excluded warmup calls;
7. collect at least 100 measured signatures of the same exact frozen digest for an initial candidate decision;
8. preserve raw elapsed milliseconds for every measured call;
9. capture one raw signature and exact provider output encoding for evidence;
10. run the local evidence builder;
11. disable/revoke the disposable key and prove a later sign request is denied;
12. destroy or schedule destruction of the disposable key after evidence is frozen, subject to provider lifecycle rules.

Provider requests must use a principal with sign/public-key access only where practical. The runtime/execution identity must not have create/delete/policy-admin rights in a future production design.

## AWS KMS candidate

Paper-review target:

```text
KeySpec      ECC_SECG_P256K1
KeyUsage     SIGN_VERIFY
Algorithm    ECDSA_SHA_256
MessageType  DIGEST
Output       DER ECDSA
```

Official AWS documentation states that `MessageType=DIGEST` skips the signing-algorithm hash step and that ECDSA KMS signatures are DER encoded.

Representative disposable setup after explicit authorization:

```text
aws kms create-key \
  --key-spec ECC_SECG_P256K1 \
  --key-usage SIGN_VERIFY
```

Record the immutable key ID/ARN returned from creation. Do not use an alias in the evidence capture.

Retrieve public key with `GetPublicKey`/CLI equivalent and retain the DER SPKI bytes locally.

For the exact 32-byte digest, the intended signing semantics are equivalent to:

```text
aws kms sign \
  --key-id <IMMUTABLE_KEY_ID_OR_ARN> \
  --message fileb://<RAW_32_BYTE_DIGEST_FILE> \
  --message-type DIGEST \
  --signing-algorithm ECDSA_SHA_256
```

The raw DER signature bytes are decoded locally and passed to the offline evidence builder. A run that accidentally uses `RAW` instead of `DIGEST` is a different treatment and must not be silently accepted.

Negative controls:

- sign the exact digest only in the primary series;
- evidence adapter must reject the same signature against a one-byte-mutated digest;
- disable the disposable KMS key and prove subsequent `Sign` fails;
- no fallback to a local plaintext key.

## Google Cloud KMS candidate

Paper-review target:

```text
purpose       asymmetric-signing
algorithm     ec-sign-secp256k1-sha256
request       AsymmetricSign digest field
output        DER ECDSA
```

Google documentation explicitly states that ECDSA can sign non-SHA digests such as Keccak when the digest length matches the selected SHA family; it gives Keccak-256 with an SHA-256 ECDSA algorithm as an example.

Create a disposable key/key version only after budget authorization. Freeze the numeric/immutable `cryptoKeyVersions/<version>` resource, never just the CryptoKey's primary version.

For this parity test, prefer the direct `AsymmetricSign` API/gRPC request and place the **already computed Hyperliquid Keccak/EIP-712 32-byte digest** in the request digest field corresponding to 256-bit ECDSA.

Do not use a CLI invocation that hashes an input file as part of `--digest-algorithm=sha256` and then claim it tested the frozen Hyperliquid digest. That would test a different message. The evidence builder contains an explicit double-hash detector for this failure mode.

Retrieve the public key and normalize its PEM/SPKI to DER for the capture. Google documents ECDSA signatures as DER and secp256k1 signatures as lower-S; the local adapter still independently validates both scalar ranges and address recovery.

Disable the disposable key version and prove subsequent signing fails before a `COMPATIBLE_CANDIDATE` result is allowed.

## Azure Key Vault / Managed HSM candidate

Paper-review target:

```text
curve        P-256K / secp256k1
algorithm    ES256K
operation    Sign supplied digest
```

Microsoft documents Key Vault Sign/Verify as sign-hash/verify-hash and states that the service does not hash the content as part of signature creation.

Representative disposable key shape after explicit authorization:

```text
az keyvault key create \
  --vault-name <DISPOSABLE_TEST_VAULT> \
  --name <DISPOSABLE_KEY_NAME> \
  --kty EC-HSM \
  --curve P-256K \
  --ops sign verify
```

An ordinary `EC` key may also be a separate candidate treatment if the goal is software-backed Key Vault rather than HSM-backed protection. Do not mix protection levels in one latency/security result.

Pin the exact returned key version. Retrieve the public JWK and capture its 32-byte x/y coordinates as base64url. The offline public-key adapter derives the secp256k1 point and Ethereum address without trusting a manually entered address.

Azure CLI/REST accepts a digest for `ES256K`. Capture the raw base64url result, decode it locally, and **classify the exact observed signature byte encoding before adapting it**. Our current official-source review does not assume DER versus fixed-width `r||s` for Azure EC results.

If the bytes match neither an explicitly documented/validated DER nor a 64-byte fixed-width form, terminal decision is `SIGNATURE_ENCODING_UNRESOLVED` until an exact provider-specific adapter is reviewed.

Disable the exact disposable key version and prove signing fails before candidate promotion.

## Ephemeral capture file

Actual provider run material is written locally to a file conforming to:

```text
SIGNER_BACKEND_CAPTURE_INPUT.schema.json
```

Instances of that schema must **not** be committed. They may contain raw provider key resource identifiers, full public-key containers and raw signatures.

The capture includes:

```text
provider/service/region
immutable key resource version
public key format + material
algorithm
provider-specific request mode
generic digest mode
signature encoding
fixture ID
raw signature
latency samples
revocation-test state
client/API versions
```

## Sanitization

Run locally:

```text
python provider_evidence_cli.py \
  --capture <EPHEMERAL_CAPTURE.json> \
  --output <SANITIZED_EVIDENCE.json>
```

The builder:

- derives the signer address from the provider public key;
- validates exact digest recovery;
- checks a mutated digest and wrong signer fail;
- detects a signature that instead validates over `SHA256(hyperliquid_digest)`;
- computes nearest-rank p50/p75/p90/p95/p99;
- hashes the raw key resource identity;
- hashes the normalized public point;
- hashes the raw signature;
- omits raw key resource, raw signature and raw public-key container from evidence;
- never authorizes another provider call or Hyperliquid action.

## Minimum candidate evidence

`COMPATIBLE_CANDIDATE` requires at least:

```text
exact digest recovery               PASS
wrong digest                        REJECTED
wrong signer                        REJECTED
double-hash detection               FALSE
>= 100 measured sign calls          YES
key disable/revoke test             PASS
immutable key version               YES
sanitized evidence                  VALID
```

This status means only “cryptographically compatible candidate”. It does not mean selected production signer and does not authorize Hyperliquid testnet.

## Stop rules

Immediately stop a provider series on:

- exact digest does not recover the derived public-key address;
- signature validates only after an extra SHA-256;
- key curve/public key is not secp256k1;
- signature encoding cannot be classified safely;
- mutable alias/primary/latest reference is used instead of exact key version;
- provider repeatedly returns inconsistent public-key identity;
- disable/revoke does not stop signing as expected;
- unexpected billable scope or credential permissions are discovered.

## Budget gate

```text
provider_network_call_authorized = false
provider_budget_eur = UNSET_BLOCKER
hyperliquid_testnet_authorized = false
hyperliquid_mainnet_authorized = false
```

A later human decision must explicitly set the provider(s), account/project/subscription, maximum one-time spend, maximum request count and teardown plan before any hands-on provider request is made.