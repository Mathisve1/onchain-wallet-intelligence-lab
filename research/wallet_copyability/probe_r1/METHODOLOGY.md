# Hyperliquid Public Probe R1 Methodology

Status: frozen technical feasibility test. It is not a market backtest and cannot create alpha evidence.

## Decision question

Can the project retrieve the minimum public Hyperliquid account, market and official archive response classes with a bounded, credential-free, order-free client while preserving enough point-in-time evidence to justify a separate archive-inventory study?

## Claim ceiling

A `PUBLIC_PROBE_PASS` proves only that every registered route produced its registered coarse response class during one exact governed run. It does not prove:

- archive completeness, timeliness or list permission;
- stable future schemas or pagination;
- wallet skill, copyability or profitability;
- complete cross-wallet or cross-venue exposure;
- real-world identity; or
- execution readiness.

## Evidence minimization

Raw response bodies are processed in memory and discarded. The output retains only:

- request and response SHA-256;
- request start/completion UTC timestamps and elapsed time;
- HTTP status, response length and content type;
- top-level JSON type, sorted keys, element count and bounded sample type names;
- S3 response class;
- transport/parse errors and retry count;
- declared planning weight.

It must not retain balances, positions, exact fills, prices, sizes, fees, funding, P&L, deposits, withdrawals, transfers, vault depositors, owner names, raw order-book levels, credentials or signed payloads.

## Point-in-time rule

Each observation records its own request window. No later response, wallet performance, entity relationship or corrected schema may be inserted into the run. Exact output bytes are content-addressed in the workflow artifact.

## Request scope

Only three HTTPS origins and exactly 16 ordered requests are constructible. Historical account routes use the frozen one-day interval. The unbounded recent `userFills` route is excluded.

## Security boundary

- same-origin redirects only;
- no Authorization or Cookie header;
- no private key or environment secret;
- no signed action, `/exchange`, order or withdrawal;
- read-only repository workflow permission;
- no raw response persistence or AI prompt transmission.

## Retry and capacity rule

A probe receives at most two attempts. Retry is allowed only after transport failure, HTTP 429 or HTTP 5xx. The 16-request, 586-base-weight contract has a frozen two-attempt worst case of 1,172 under the captured 1,200/minute planning budget.

## Derived results

- `PUBLIC_PROBE_PASS`: every registered response class matches and every security assertion is false;
- `PUBLIC_PROBE_PARTIAL`: every core route matches, but at least one non-core route fails;
- `PUBLIC_PROBE_FAIL`: a core route fails, coverage/order is incomplete, capacity/integrity fails or forbidden capability appears.

Archive access is independently derived:

- `LISTINGS_AVAILABLE`;
- `ROUTES_CONFIRMED_ACCESS_RESTRICTED`; or
- `ARCHIVE_ROUTE_FAILURE`.

A recognized S3 access/requester-pays error can confirm route behavior but is never archive-listing or completeness evidence.

## Evidence lifecycle

The workflow cannot write repository state. It uploads output, validation log/return code, exact run context and a SHA-256 file ledger. A later reviewed attestation must bind exact commit, run, job, artifact ID/digest, downloaded artifact ZIP hash and output hash.

## Next-gate discipline

Even a fully attested `PUBLIC_PROBE_PASS` opens no data partition automatically. It only allows a separately preregistered archive-inventory proposal.
