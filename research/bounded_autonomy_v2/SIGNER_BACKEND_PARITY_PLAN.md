# Candidate signer backend parity gate

Status: `DESIGN_ONLY_NO_EXTERNAL_KEY_NO_NETWORK_AUTHORIZATION`.

## Objective

Select a future signer backend only after it proves that it can sign the **exact frozen Hyperliquid phantom-agent EIP-712 digest** and that the returned signature can be converted to low-S `r/s/v` while recovering the exact pre-registered API-wallet address.

A provider supporting secp256k1 in marketing/documentation is not enough.

## Candidate order

Current paper-review priority:

1. AWS KMS secp256k1;
2. Google Cloud KMS secp256k1;
3. Azure Key Vault / Managed HSM P-256K;
4. provider/MPC alternatives only after an exact equivalent proof contract is written.

This order is provisional and creates no selection.

## Critical compatibility issue

Hyperliquid L1 signing does **not** sign a normal SHA-256 application message. The pinned SDK builds an action hash with msgpack + Ethereum Keccak, then signs a phantom-agent EIP-712 digest.

Cloud signer product names such as `ECDSA_SHA_256`, `EC_SIGN_SECP256K1_SHA256` and `ES256K` therefore do not by themselves prove compatibility with that 32-byte digest.

The hands-on test must answer only this concrete question:

> Can the exact candidate API call sign the exact 32 bytes produced by our frozen Hyperliquid EIP-712 digest contract without rehashing or transforming them, and can the result recover the candidate public key/address?

If not, the backend is `NO_GO` regardless of its general secp256k1 support.

## Disposable backend-test protocol

No exchange account or Hyperliquid API-wallet approval is needed for this gate.

1. create a disposable non-production secp256k1 signing key in the candidate provider;
2. retrieve/freeze its public key and derive the expected Ethereum address independently;
3. generate frozen Hyperliquid fixture action bytes locally;
4. compute msgpack action hash and phantom-agent EIP-712 digest locally;
5. send only that 32-byte digest to the provider's sign operation using its explicit digest/prehashed mode where documented;
6. retain raw signature bytes, provider key version, algorithm, request metadata and latency;
7. parse the exact observed provider encoding;
8. normalize to low-S if needed;
9. derive `v` only by recovery against the pre-registered expected address;
10. verify the resulting `{r,s,v}` against the digest;
11. repeat for mainnet/testnet-source fixtures, but do not send anything to Hyperliquid;
12. disable/revoke the disposable key and prove subsequent signing fails.

## Output-format handling

### DER

AWS and Google official documentation currently describe ECDSA signatures as DER encoded. The offline adapter implements a strict DER parser and rejects:

- non-minimal lengths;
- negative integers;
- trailing bytes;
- out-of-range `r` or `s`;
- wrong digest;
- wrong expected signer.

### Fixed-width `r||s`

A separate P1363-style parser exists only as a generic candidate adapter. It must not be assigned to a provider until the exact provider response bytes are observed and documented.

### Recovery ID

A cloud provider generally need not provide Ethereum `v`. Our adapter does not trust a supplied `v` even if one appears. It tests `27` and `28` after low-S normalization and requires exactly one to recover the registered address.

No unique recovery -> `BLOCK`.

## Latency benchmark

For every candidate that passes signature correctness, run a separately budgeted non-Hyperliquid benchmark with the disposable key.

Measure:

```text
request construction
network connect/TLS if applicable
provider queue/service time where exposed
round-trip sign latency
signature decode/normalization
address recovery
full client-side elapsed
```

Report p50/p75/p90/p95/p99 after warmup, plus cold-start and error distributions.

Do not compare provider marketing latency claims. Measure from our deployment region.

## Security benchmark

Required controls:

- key material non-exportable or provider-isolated according to exact key type;
- signer service identity scoped to sign only the exact key version;
- no key create/delete/policy-admin rights in the runtime principal;
- key version pinned, not `latest` in a production permit;
- outbound network allowlist to exact provider endpoint where practical;
- every provider signing request joined to permit/action/audit IDs;
- failed/retried provider requests are idempotently tracked;
- key disable/revoke tested;
- provider/API outage fails closed;
- no fallback to plaintext local key.

## Backend test outcomes

Per provider, terminal result is one of:

```text
COMPATIBLE_CANDIDATE
COMPATIBLE_BUT_LATENCY_NO_GO
COMPATIBLE_BUT_SECURITY_NO_GO
DIGEST_TRANSFORMATION_INCOMPATIBLE
SIGNATURE_ENCODING_UNRESOLVED
RECOVERY_FAILED
OPERATIONAL_NO_GO
```

`COMPATIBLE_CANDIDATE` still does not authorize Hyperliquid testnet.

## Required artifacts

A future provider run must freeze:

- provider and service;
- region/location;
- key type/curve;
- immutable key version/resource ID with sensitive account identifiers minimized;
- public key hash and derived signer address;
- algorithm;
- exact request mode (`DIGEST`, digest field, etc.);
- exact frozen input digest hash/value as allowed by evidence policy;
- raw signature SHA-256 and encoding classification;
- normalized `r/s/v` test result;
- recovered address;
- latency distribution;
- disable/revocation evidence;
- software/client/API versions;
- cost;
- terminal candidate decision.

No secret/private key bytes are retained.