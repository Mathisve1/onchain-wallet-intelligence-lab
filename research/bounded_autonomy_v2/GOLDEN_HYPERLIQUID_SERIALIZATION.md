# Golden Hyperliquid serialization and signing contract

Status: offline design/fixture contract only. No signing or venue request is authorized.

## Pinned primary reference

Official repository: `hyperliquid-dex/hyperliquid-python-sdk`

Pinned reviewed commit:

```text
2fdb18f9517675ea03695a0962bd19eece9c83f0
version lineage: 0.24.0
```

Key reference files:

```text
hyperliquid/utils/signing.py
hyperliquid/exchange.py
```

The source was reviewed from the official repository on 2026-08-07. This pin is a research fixture, not a statement that version 0.24.0 will remain the production version.

## Order wire contract observed in official SDK

For an order request the SDK converts to an order wire with these keys:

```text
a = asset integer
b = is-buy boolean
p = normalized limit-price string
s = normalized size string
r = reduce-only boolean
t = order-type wire
c = optional raw cloid
```

An IOC limit order therefore has the structural form:

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

The order action wraps one or more wires under:

```json
{
  "type": "order",
  "orders": [],
  "grouping": "na"
}
```

Cancel-by-cloid uses the official structure:

```json
{
  "type": "cancelByCloid",
  "cancels": [
    {"asset": 0, "cloid": "0x00000000000000000000000000000001"}
  ]
}
```

## Numeric wire rule

The official `float_to_wire` currently:

1. formats to eight decimal places;
2. rejects values whose rounding error is at least `1e-12`;
3. normalizes negative zero to zero;
4. normalizes trailing zeroes through `Decimal` formatting.

Our risk/intent layer stores canonical decimal strings to avoid binary-float arithmetic in risk decisions. A later adapter must prove that every accepted decimal input maps byte-for-byte to the same official wire string for the supported instrument precision. The adapter must reject rather than silently round an out-of-contract value.

## L1 action-hash contract

The official SDK currently computes the L1 action hash conceptually as:

```text
msgpack.packb(action)
|| nonce encoded as unsigned 8-byte big-endian
|| vault discriminator/address
|| optional expires-after discriminator + unsigned 8-byte big-endian expiry
then Ethereum keccak
```

Important: Python `hashlib.sha3_256` is **not** a substitute for Ethereum keccak. The pure standard-library prototype therefore does not pretend to implement this cryptographic step.

## Phantom-agent EIP-712 contract

For L1 actions, the official SDK converts the action hash into a phantom agent:

```text
source = "a" on mainnet, "b" on testnet
connectionId = action hash
```

The current EIP-712 domain in the official SDK is:

```text
name = Exchange
version = 1
chainId = 1337
verifyingContract = 0x0000000000000000000000000000000000000000
```

The signer must produce a signature whose recovered address equals the registered API-wallet signer.

## POST envelope

The official exchange client posts L1 actions to `/exchange` in an envelope containing:

```text
action
nonce
signature
vaultAddress
expiresAfter
```

Our future venue adapter must construct only the explicitly allowlisted action types. It must not expose the official SDK's broader action surface to the AI/runtime.

## Golden-fixture progression

### G1 — structural wire parity

No external cryptographic packages required. Verify order/cancel dictionary structure, exact keys, IOC TIF, reduce-only and cloid representation against frozen fixtures.

### G2 — numeric-wire parity

Run the exact official `float_to_wire` implementation from the pinned SDK in a dependency-isolated test environment and compare a broad edge-case corpus with our decimal adapter. Any mismatch is a blocker.

### G3 — msgpack/action-hash parity

Using pinned `msgpack` and Ethereum keccak dependencies, require byte-identical packed action bytes and identical action hash for frozen order/cancel fixtures.

### G4 — EIP-712 digest/signature recovery parity

Require identical phantom-agent structured payload and recover the disposable signer's exact address from both official-SDK and candidate-signer signatures.

### G5 — testnet acceptance

Only after a separate signed-testnet authorization, submit harmless bounded IOC/cancel fixtures and reconcile venue responses. Offline parity alone does not authorize submission.

## Mandatory negative fixtures

- >8-decimal size/price that would round;
- negative zero;
- incorrect asset ID;
- `Gtc` or `Alo` substituted for registered `Ioc`;
- reduce-only bit mutation;
- cloid mutation;
- grouping mutation;
- nonce mutation;
- vault-address mutation;
- expiry mutation;
- mainnet/testnet source mutation;
- action dictionary with additional fields;
- cancel target not owned by strategy.

Every mutation must change the bound payload/hash or be rejected before signing.