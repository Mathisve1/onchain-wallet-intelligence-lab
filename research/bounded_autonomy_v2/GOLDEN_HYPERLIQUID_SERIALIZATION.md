# Golden Hyperliquid serialization and signing contract

Status: `G1_G4_LOCAL_FIXTURE_PARITY_NO_SIGNER_AUTHORIZATION`.

No network request, venue action, testnet action or production signing capability is authorized by this document.

## Pinned primary reference

Official repository: `hyperliquid-dex/hyperliquid-python-sdk`

Pinned reviewed commit:

```text
2fdb18f9517675ea03695a0962bd19eece9c83f0
version lineage: 0.24.0
```

Primary files:

```text
hyperliquid/utils/signing.py
hyperliquid/exchange.py
tests/signing_test.py
pyproject.toml
```

The pin is an immutable research fixture. It is not a claim that version 0.24.0 will remain the correct production version.

## Official dependency range observed at the pin

```text
eth-utils   >=2.1.0,<6.0.0
eth-account >=0.10.0,<0.14.0
msgpack      ^1.0.5
```

Local fixture validation used Python 3.13.5 and msgpack 1.1.2. Exact future production dependencies remain separately gated.

## Order wire contract

Pinned SDK `order_request_to_order_wire` builds the mapping in this insertion order:

```text
a = asset integer
b = is-buy boolean
p = normalized limit-price string
s = normalized size string
r = reduce-only boolean
t = order-type wire
c = optional raw cloid
```

Example IOC wire:

```json
{
  "a": 0,
  "b": true,
  "p": "50000",
  "s": "0.01",
  "r": false,
  "t": {"limit": {"tif": "Ioc"}},
  "c": "0x00000000000000000000000000000001"
}
```

The order action is constructed in this insertion order:

```text
type
orders
grouping
```

Cancel-by-cloid uses:

```json
{
  "type": "cancelByCloid",
  "cancels": [
    {"asset": 0, "cloid": "0x00000000000000000000000000000001"}
  ]
}
```

### Critical ordering finding

`msgpack.packb(action)` serializes the mapping in insertion order. Two Python dictionaries with identical key/value sets but different insertion order can therefore produce different msgpack bytes and different Hyperliquid action hashes.

Consequences:

- action construction order is part of the signed protocol contract;
- the signer must never canonical-sort action keys;
- an arbitrary JSON-to-dict round trip cannot be assumed signature-neutral;
- the venue adapter must build each allowlisted action through a frozen typed compiler;
- golden tests must compare bytes/hash, not only semantic mapping equality.

## Numeric wire rule

Pinned SDK `float_to_wire`:

1. formats a float to eight decimal places;
2. rejects when the formatted float differs by at least `1e-12`;
3. contains an internal `rounded == "-0"` guard;
4. normalizes the resulting Decimal/trailing zeroes.

### Negative-zero finding

The current pin does **not** actually normalize Python `-0.0` to `"0"`: eight-decimal formatting first produces `"-0.00000000"`, so the narrower `"-0"` comparison does not fire and final Decimal normalization yields `"-0"`.

Our parity oracle reproduces that exact pinned behavior. The strategy/risk layer should preferably reject negative-zero numeric inputs before venue serialization rather than silently choosing a different representation.

Our canonical risk arithmetic continues to use decimal strings and does not rely on binary floats.

## L1 action-hash contract

Pinned SDK computes:

```text
msgpack.packb(action)
|| nonce as unsigned 8-byte big-endian
|| vault discriminator/address
|| optional expires-after discriminator + unsigned 8-byte big-endian expiry
then Ethereum Keccak-256
```

Python `hashlib.sha3_256` is not Ethereum Keccak-256.

The independent fixture oracle now contains a small test-only Keccak implementation and reproduces the official production phantom-agent connection ID:

```text
0fcbeda5ae3c4950a548021552a4fea2226858c4453571bf3f24ba017eac2908
```

for the frozen official production fixture.

## Phantom-agent EIP-712 contract

Pinned L1 signing transforms the action hash into:

```text
source = "a" on mainnet
source = "b" on testnet
connectionId = action hash
```

Pinned EIP-712 domain:

```text
name = Exchange
version = 1
chainId = 1337
verifyingContract = 0x0000000000000000000000000000000000000000
```

The fixture oracle independently computes the EIP-712 digest, deterministic secp256k1 test signature, low-S form and public-key recovery.

The recovered address for the official public test-key fixture matches:

```text
0x14791697260e4c9a71f18484c9f997b308e59325
```

The repository does not store or use a live API-wallet private key for these tests. The known public SDK test secret is constructed inside the fixture test solely to reproduce the official public vectors.

## Exact official vectors now matched locally

The independent implementation reproduces the pinned SDK values for:

- production phantom-agent connection ID;
- dummy L1 mainnet and testnet `r/s/v`;
- order L1 mainnet and testnet `r/s/v`;
- order-with-CLOID mainnet and testnet `r/s/v`;
- vault-bound mainnet and testnet `r/s/v`;
- `scheduleCancel` mainnet and testnet `r/s/v`;
- `scheduleCancel(time=...)` mainnet and testnet `r/s/v`;
- recovered fixture signer address.

Local run:

```text
prototype/test_crypto_fixture_oracle.py
14 tests
PASS
```

This is engineering evidence only, not canonical repository CI.

## Backend-neutral ECDSA recovery adapter

A separate fixture adapter now demonstrates the conversion needed for signer backends that return `(r,s)` in strict DER form rather than Ethereum `r/s/v`:

1. strict DER parse;
2. scalar range validation;
3. high-S -> low-S normalization;
4. try recovery `v` values 27 and 28;
5. accept only when exactly one candidate recovers the pre-registered signer address;
6. reject wrong digest, wrong expected signer or malformed DER.

Local adapter run:

```text
prototype/test_signature_backend_adapter.py
6 tests
PASS
```

This adapter does not prove that any specific AWS/GCP/Azure/Cobo backend uses this exact output format. Provider-specific adapters remain unapproved until tested against their exact official APIs and outputs.

## POST envelope

Pinned official exchange client sends L1 actions to `/exchange` with:

```text
action
nonce
signature
vaultAddress
expiresAfter
```

Our future venue adapter may expose only the closed action surface registered elsewhere. The official SDK's broader exchange methods must not be reachable from the AI/runtime.

## Gate status

### G1 — structural wire parity: LOCAL PASS

Order/cancel structure, field order, IOC TIF, reduce-only and CLOID fixtures are frozen.

### G2 — numeric-wire parity: LOCAL PASS WITH FINDING

Pinned float behavior is reproduced, including the negative-zero compatibility finding. A broader instrument-precision corpus remains required before a production adapter.

### G3 — msgpack/action-hash parity: LOCAL PASS

The independent action hash exactly matches the official production fixture and signature vectors. Mapping insertion order is now a frozen safety constraint.

### G4 — EIP-712/signature/recovery parity: LOCAL PASS

Official `r/s/v` vectors and signer recovery match using an implementation independent from `eth-account`.

### G4B — candidate external signer backend parity: OPEN

No cloud KMS, HSM or MPC backend has yet signed the exact frozen digest and recovered to the approved API-wallet address.

### G5 — Hyperliquid testnet acceptance: NOT AUTHORIZED

Offline parity does not authorize any signed venue request.

## Mandatory negative fixtures for later adapters

- >8-decimal size/price that would round;
- negative zero;
- incorrect asset ID;
- `Gtc`/`Alo` substituted for registered `Ioc`;
- reduce-only bit mutation;
- CLOID mutation;
- grouping mutation;
- mapping field-order mutation;
- nonce mutation;
- vault-address mutation;
- expiry mutation;
- mainnet/testnet source mutation;
- extra action fields;
- cancel target not owned by strategy;
- wrong recovered signer;
- high-S backend signature;
- malformed DER or backend signature encoding.

Every mutation must change the bound bytes/hash or be rejected before a real signer can release an action.