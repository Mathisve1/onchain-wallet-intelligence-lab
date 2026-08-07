# Hyperliquid Public Probe R1 Methodology

Status: frozen technical feasibility test. This is not a market backtest and cannot produce alpha evidence.

## Decision question

Can the project retrieve the minimum public Hyperliquid account, market and archive response classes with a bounded, credential-free, order-free client while preserving enough point-in-time evidence to justify a separate archive-inventory study?

## What the probe proves

A `PUBLIC_PROBE_PASS` proves only that every registered public route was reachable during one governed run, that returned bodies matched the registered coarse response classes, and that response hashes and timing metadata were retained.

It does not prove historical completeness, stable schemas, wallet skill, real-world identity, hidden-position visibility, copyability, profitability or execution authorization.

## Evidence minimization

Raw response bodies are processed in memory and discarded. The output retains only:

- request and response SHA-256 hashes;
- UTC request start and completion timestamps;
- HTTP status, byte length, content type and elapsed time;
- top-level response type, top-level keys and element count;
- bounded timestamp extrema when they can be derived without retaining records;
- transport or parse error class; and
- retry count.

The output must not retain position values, balances, exact fills, P&L, wallet-owner claims or authentication material.

## Point-in-time rule

`collected_at_utc` is the time the governed run began. Each observation separately records request start and completion time. No later response, later wallet performance or later relationship discovery may be inserted into the run.

## Network boundary

Only the three origins enumerated in `PROBE_CONTRACT.json` are allowed. HTTP redirects are accepted only when the destination origin is unchanged. An Authorization header, Cookie header, private key, signed action or call to `/exchange` is a terminal failure.

## Retry rule

Each registered request receives at most two attempts. A retry is allowed only after a transport failure, HTTP 429 or HTTP 5xx. Other HTTP outcomes are recorded without retry. Total requests and declared request weight must remain under the frozen limits.

## Terminal result

The terminal result is derived, never manually selected:

- `PUBLIC_PROBE_PASS`: all registered probes pass and all security assertions remain false;
- `PUBLIC_PROBE_PARTIAL`: every core probe passes but at least one non-core probe fails or has an unsupported shape;
- `PUBLIC_PROBE_FAIL`: a core probe fails, evidence coverage/order is wrong, a contract or collector hash differs, or any forbidden capability is observed.

Both `PASS` and `PARTIAL` still require a separate archive inventory before any analytical market-data release. `FAIL` blocks that inventory until repaired and rerun under a new exact head.

## Review and release boundary

The workflow artifact is immutable evidence for the exact commit that produced it. Promotion requires the workflow run ID, job ID, artifact ID/digest, artifact-file SHA-256 and exact reviewed commit to be recorded in a later attestation. The probe workflow has read-only repository permission and cannot update its own evidence record.
