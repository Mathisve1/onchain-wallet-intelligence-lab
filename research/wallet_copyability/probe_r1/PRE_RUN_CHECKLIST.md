# Final Pre-Run Checklist

The workflow may access the public network only when every item below is true on the exact checked-out commit.

## Identity and scope

- [x] study and probe IDs are unique and frozen;
- [x] exactly 17 requests are registered and ordered;
- [x] three HTTPS origins are allowlisted;
- [x] fixture addresses and query window are frozen;
- [x] natural-person identity claims are forbidden.

## Security

- [x] repository permission is `contents: read` only;
- [x] checkout credentials are not persisted;
- [x] no secret, token, Authorization/Cookie header or private key is referenced;
- [x] no signing, `/exchange`, order or withdrawal code is constructible;
- [x] redirects are same-origin only;
- [x] bytes, timeout, retries, requests and declared weight are bounded.

## Evidence integrity

- [x] duplicate-key and nonfinite JSON fail closed;
- [x] exact contract and collector bundle hashes;
- [x] exact probe coverage and order;
- [x] per-request fingerprints and timestamps;
- [x] minimized response hashes/classes only;
- [x] terminal and archive-access states are derived;
- [x] immutable artifact and SHA-256 file ledger;
- [x] pending evidence and attestation contain no invented identities.

## Research boundary

- [x] raw response values are not persisted;
- [x] market data is not analytically ingested;
- [x] wallet performance/copyability are not calculated;
- [x] entity clustering remains closed;
- [x] empirical result is null;
- [x] every integration, paper, shadow, live, leverage and capital-allocation authorization is false.

The workflow must still prove actual route behavior. Completeness, pagination, schemas, requester-pays cost and historical gaps remain unresolved even after route-level PASS.
