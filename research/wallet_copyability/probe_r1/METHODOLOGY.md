# Hyperliquid Public Probe R1 Methodology

Status: implementation-only preregistration. No network result is accepted here.

## Decision question

Can the project retrieve the minimum registered public Hyperliquid account,
market and official archive response classes with a bounded, credential-free,
order-free client while preserving enough exact evidence to justify a later,
separately reviewed archive-inventory proposal?

## Claim ceiling

A later `PUBLIC_PROBE_PASS` may establish only that every registered route
produced its registered coarse response class during one exact governed run.
It cannot establish:

- archive completeness, timeliness or usable list permission;
- stable future schemas or pagination;
- wallet skill, copyability or profitability;
- complete cross-wallet or cross-venue exposure;
- real-world identity; or
- execution readiness.

## Point-in-time identity

The implementation is merged first. The actual run is then dispatched manually
with the exact canonical `main` SHA in `inputs.reviewed_commit`. The workflow
must check out that commit and prove equality with `git rev-parse HEAD` before
network access. The exact reviewed SHA is recorded in run context.

A temporary pull-request merge commit, branch name, moving tag or implicit
`github.sha` is insufficient.

## Request scope

- exactly three HTTPS origins;
- exactly 16 ordered requests;
- POST only to `/info`;
- GET only to the registered S3 bucket roots and query prefixes;
- fills, funding and non-funding ledger limited to one fixed UTC day;
- unbounded recent `userFills` forbidden.

## Evidence minimization

Raw responses are processed in memory only to enforce byte limits, compute
SHA-256, parse strict JSON or recognized S3 XML and extract coarse structural
metadata. Bodies are discarded.

Retained evidence is limited to request and response hashes, UTC timestamps,
elapsed time, HTTP status, response byte length, content type, response class,
top-level type/keys/count, bounded item-type names, attempts, declared weight
and bounded error metadata.

## Retry and capacity rule

A route receives at most two attempts. Retry is allowed only after transport
failure, HTTP 429 or HTTP 5xx. The registered workload has a first-attempt
weight of 586 and a two-attempt worst case of 1,172 under the captured 1,200
planning budget.

## Derived results

- `PUBLIC_PROBE_PASS`: all 16 response classes match;
- `PUBLIC_PROBE_PARTIAL`: all core routes match and at least one non-core route
  fails;
- `PUBLIC_PROBE_FAIL`: core, coverage, integrity, capacity or security failure.

Archive access is derived separately:

- `LISTINGS_AVAILABLE`;
- `ROUTES_CONFIRMED_ACCESS_RESTRICTED`; or
- `ARCHIVE_ROUTE_FAILURE`.

A recognized S3 access error can confirm route behavior but is never treated as
object-listing access or completeness evidence.

## Evidence lifecycle

The workflow has read-only repository permissions. It uploads minimized output,
validation log and return code, exact run context and a SHA-256 file ledger. A
later evidence PR must bind exact commit, run, attempt, job, artifact ID,
provider digest, independently downloaded ZIP hash and output hash.

No terminal status is canonical until that evidence PR passes independent
validation and clean-context review.
