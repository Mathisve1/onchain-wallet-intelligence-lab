# Data Minimization — Hyperliquid Public Probe R1

## Purpose limitation

R1 exists only to test public-route reachability and coarse response schemas. It is not a wallet surveillance dataset, account-performance dataset or address-labeling exercise.

## Raw response handling

Raw HTTP response bodies may exist only in process memory for the duration needed to:

1. enforce the byte ceiling;
2. calculate SHA-256;
3. parse the top-level response type;
4. list top-level keys;
5. count top-level elements; and
6. classify the response against its frozen expected family.

The collector must not write raw response bodies to disk, logs, workflow artifacts, repository files or model prompts.

## Retained fields

The minimized evidence may retain:

- probe identity and whether it is core;
- method, origin and path;
- hash of exact request payload or path/query;
- request attempt count and declared request weight;
- UTC start/completion timestamps and elapsed milliseconds;
- HTTP status, response byte length and SHA-256;
- content type;
- parse status;
- top-level type, sorted top-level keys, top-level element count and bounded sample item-type names;
- transport error class and truncated error message.

## Forbidden retained fields

- wallet balances, positions or margin values;
- exact fills, prices, sizes, fees, funding payments or P&L;
- deposit, withdrawal or transfer details;
- vault depositor data;
- owner names or inferred natural-person identities;
- cookies, Authorization headers, tokens, secrets, private keys or signed payloads;
- raw market order-book levels;
- any data used to rank or select a wallet.

## Artifact retention

The minimized artifact is retained for 90 days through the pinned GitHub artifact action. Permanent repository evidence will contain only the later reviewed attestation and the minimum exact output required by governance. Any broader retention requires a separate reviewed raw-retention contract.

## AI boundary

No R1 raw response or minimized wallet-specific response is supplied to a language model. AI may later review methodology and already minimized aggregate evidence, but cannot calculate canonical P&L, infer ownership or decide a cluster merge.
