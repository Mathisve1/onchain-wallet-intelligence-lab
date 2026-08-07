# Data Minimization — Hyperliquid Public Probe R1

## Purpose limitation

R1 tests route reachability and coarse response classes only. It is not a wallet-surveillance, wallet-performance or address-labeling dataset.

## Raw response lifecycle

Raw response bodies may exist only in process memory while the collector:

1. enforces the byte ceiling;
2. calculates SHA-256;
3. identifies JSON or S3 XML/error class;
4. extracts top-level keys and counts; and
5. classifies the response against its registered family.

Bodies must not be written to disk, logs, workflow artifacts, repository files or model prompts.

## Retained evidence

- probe/core identity;
- method, origin and path;
- exact request fingerprint;
- attempt count and declared weight;
- UTC start/completion and elapsed time;
- HTTP status, response byte length and SHA-256;
- content type and response class;
- parse status, top-level type, sorted top-level keys and element count;
- bounded sample item-type names;
- transport error class and truncated message.

## Forbidden retained evidence

- balances, margin, positions, liquidation values or account equity;
- exact fills, prices, sizes, fees, funding or P&L;
- deposit, withdrawal, transfer or vault-depositor records;
- owner names or inferred natural-person identities;
- raw L2 levels;
- cookies, tokens, secrets, Authorization headers, private keys or signed payloads;
- any wallet ranking, selection or copyability score.

## Retention

The minimized artifact is retained for 90 days. Permanent repository evidence may retain only the reviewed attestation and the minimum minimized output required to reproduce the gate. Broader raw retention requires a separate immutable retention contract.

## AI boundary

No raw or wallet-specific R1 response is sent to a language model. AI may review methodology and minimized aggregate evidence, but cannot calculate canonical P&L, infer ownership, merge clusters or authorize a trade.
