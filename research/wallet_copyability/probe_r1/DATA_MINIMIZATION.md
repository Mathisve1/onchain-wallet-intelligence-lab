# Data Minimization — Hyperliquid Public Probe R1

R1 tests route reachability and coarse response classes only. It is not a
wallet-performance, surveillance or identity dataset.

Raw response bodies may exist only in process memory while the collector:

1. enforces the response-byte ceiling;
2. calculates SHA-256;
3. parses strict JSON or recognized S3 XML;
4. identifies the top-level response class;
5. extracts structural keys, counts and bounded type names.

The body is then discarded. It must not be written to disk, logs, artifacts,
repository files or model prompts.

## Retained evidence

- probe and core identity;
- method, origin and path;
- request fingerprint;
- attempts and declared weight;
- UTC timing and elapsed milliseconds;
- HTTP status;
- response byte length and SHA-256;
- content type and coarse response class;
- top-level type, sorted keys, count and bounded item-type names;
- bounded transport or parse error class/message.

## Forbidden retained values

- balances, margin values and positions;
- liquidation levels;
- exact fills, prices, sizes or order identifiers;
- fees, funding or P&L;
- deposits, withdrawals and transfers;
- vault participant records;
- raw order-book levels;
- credentials, cookies, tokens, private keys or signed payloads;
- natural-person identity claims;
- wallet ranking or copyability scores.

The workflow artifact is retained for 90 days. Any permanent raw-data retention
requires a separate reviewed contract and is not authorized by this
implementation.
