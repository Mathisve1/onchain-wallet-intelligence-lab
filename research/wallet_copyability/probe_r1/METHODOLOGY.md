# Hyperliquid Public Probe R1 Methodology

Status: frozen technical feasibility test. It is not a market backtest and cannot create alpha evidence.

## Decision question

Can the project retrieve the minimum public Hyperliquid account, market and archive response classes with a bounded, credential-free, order-free client while preserving enough point-in-time evidence to justify a separate archive-inventory study?

## Claim ceiling

A `PUBLIC_PROBE_PASS` proves only that each registered route produced its registered route-level response class during one exact governed run. It does not prove archive completeness, list permission, stable schemas, wallet skill, real-world identity, hidden-position visibility, copyability, profitability or execution readiness.

## Evidence minimization

Raw response bodies are processed in memory and discarded. The output retains request/response SHA-256, request timing, HTTP status, response length/content type, top-level schema features, S3 response class, parse/transport errors and retry count. It must not retain balances, positions, fills, prices, sizes, fees, funding, P&L, transfers, vault depositor records, owner names, secrets or raw order-book levels.

## Point-in-time rule

Each observation records its own request start and completion timestamp. No later response, later wallet performance or later entity relationship may be inserted. Exact output bytes are content-addressed in the workflow artifact.

## Network boundary

Only the three origins in `PROBE_CONTRACT.json` are constructible. Redirects are allowed only within the same origin. Authorization/Cookie headers, secrets, private keys, signed actions, `/exchange`, orders and withdrawals are terminal violations.

## Retry and capacity rule

Each request receives at most two attempts. Retry is allowed only after transport failure, HTTP 429 or HTTP 5xx. Total attempts, bytes and declared request weight stay under frozen ceilings.

## Derived results

- `PUBLIC_PROBE_PASS`: every registered route matches its response class and all security assertions are false;
- `PUBLIC_PROBE_PARTIAL`: all core probes pass while at least one non-core probe fails;
- `PUBLIC_PROBE_FAIL`: a core probe fails, coverage/order is incomplete, capacity is exceeded, hashes differ or a forbidden capability is observed.

Archive access is separately derived as `LISTINGS_AVAILABLE`, `ROUTES_CONFIRMED_ACCESS_RESTRICTED` or `ARCHIVE_ROUTE_FAILURE`.

## Evidence lifecycle

The workflow has repository read permission only. It uploads output, validation log/return code, exact run context and a SHA-256 file ledger. A later attestation must bind reviewed commit, run, job, artifact ID/digest, ZIP hash and output hash. Negative evidence is immutable.
