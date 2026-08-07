# Hyperliquid Public Probe R1 Methodology

Status: frozen technical feasibility test. This is not a market backtest and cannot produce alpha evidence.

## Decision question

Can the project retrieve the minimum public Hyperliquid account, market and archive response classes with a bounded, credential-free, order-free client while preserving enough point-in-time evidence to justify a separate archive-inventory study?

## Evidence minimization

Raw response bodies are processed in memory and discarded. The output retains request and response SHA-256 hashes, UTC request times, HTTP status, byte length, content type, elapsed time, top-level response type, top-level keys, element count, parse/transport errors and retry count. It must not retain balances, positions, exact fills, P&L, owner claims or authentication material.

## Network boundary

Only the three origins enumerated in `PROBE_CONTRACT.json` are allowed. Redirects are accepted only within the same origin. Authorization or Cookie headers, private keys, signed actions, `/exchange`, orders and withdrawals are forbidden.

## Retry and capacity rule

A request receives at most two attempts. Retry is allowed only after transport failure, HTTP 429 or HTTP 5xx. Both the total request count and declared request weight remain bounded by the frozen contract.

## Derived terminal result

- `PUBLIC_PROBE_PASS`: all registered probes pass and all security assertions remain false;
- `PUBLIC_PROBE_PARTIAL`: every core probe passes while one or more non-core probes fail or have unsupported shape;
- `PUBLIC_PROBE_FAIL`: a core probe fails, coverage/order is incomplete, hashes differ, capacity is exceeded or a forbidden capability is observed.

A successful result proves route and coarse-schema availability at one governed timestamp only. It does not prove archive completeness, stable schemas, wallet skill, hidden-position visibility, copyability or profitability.

## Evidence lifecycle

The workflow has repository read permission only. It creates an artifact containing the exact probe output, validation log, validation return code, run context and file hashes. A later attestation must bind the reviewed commit, workflow run/job, artifact ID/digest and output SHA-256 before this gate can be considered closed.
