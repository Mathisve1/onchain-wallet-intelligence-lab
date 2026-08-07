# Hyperliquid Public Probe R1 Methodology

Status: frozen technical feasibility test. It is not a market backtest and cannot create alpha evidence.

## Decision question

Can the project retrieve the minimum public Hyperliquid account, market and archive response classes with a bounded, credential-free, order-free client while preserving enough point-in-time evidence to justify a separate archive-inventory study?

## Claim ceiling

A `PUBLIC_PROBE_PASS` proves only that each registered route produced its registered route-level response class during one exact governed run. It does not prove archive completeness, list permission, stable schemas, wallet skill, real-world identity, hidden-position visibility, copyability, profitability or execution readiness.

## Evidence minimization

Raw response bodies are processed in memory and discarded. The output retains:

- request/response SHA-256;
- request start and completion UTC timestamps;
- HTTP status, response length, content type and elapsed time;
- top-level JSON type, sorted top-level keys, element count and bounded item-type names;
- S3 response class (`S3_LISTING`, `S3_ERROR_RESPONSE` or `UNSUPPORTED`);
- transport/parse error class and truncated error text;
- retry count and declared request weight.

It must not retain balances, positions, fills, prices, sizes, fees, funding, P&L, transfers, vault depositor records, owner names, cookies, secrets or raw order-book levels.

## Point-in-time rule

Each observation records its own request start and completion timestamp. No later response, later wallet performance or later entity relationship may be inserted into the run. Exact output bytes are content-addressed in the workflow artifact.

## Network boundary

Only the three origins in `PROBE_CONTRACT.json` are constructible. Redirects are allowed only within the same origin. Authorization/Cookie headers, secrets, private keys, signed actions, `/exchange`, orders and withdrawals are terminal violations.

## Retry and capacity rule

Each registered request receives at most two attempts. Retry is allowed only for a transport failure, HTTP 429 or HTTP 5xx. Total attempts, bytes and declared request weight must remain under the frozen ceilings.

## Derived results

- `PUBLIC_PROBE_PASS`: all registered probes match their route-level response class and all security assertions remain false;
- `PUBLIC_PROBE_PARTIAL`: all core probes pass but one or more non-core probes fail or return an unsupported class;
- `PUBLIC_PROBE_FAIL`: a core probe fails, coverage/order is incomplete, capacity is exceeded, hashes differ or a forbidden capability is observed.

Archive access is separately derived:

- `LISTINGS_AVAILABLE`: all three S3 routes return actual listing responses;
- `ROUTES_CONFIRMED_ACCESS_RESTRICTED`: all three routes return valid S3 response classes but at least one is an error response, such as requester-pays/access control;
- `ARCHIVE_ROUTE_FAILURE`: at least one archive route does not return a recognized S3 response class.

## Evidence lifecycle

The workflow has repository read permission only. It uploads output, independent validation log, validation return code, exact run context and SHA-256 file ledger. A later attestation must bind reviewed commit, run, job, artifact ID/digest, ZIP hash and output hash. Historical negative evidence is never overwritten.
