# Final Pre-Run Checklist

## Identity and scope

- [x] unique frozen study/probe IDs;
- [x] exactly 16 ordered requests;
- [x] three HTTPS origins;
- [x] one fixed UTC day for fills/funding/ledger;
- [x] unbounded `userFills` absent;
- [x] identity claims forbidden.

## Exact-head authorization

Before the network run, verify all of the following against the current remote state:

- [ ] Research CI is green on the exact source-head SHA;
- [ ] PR remains draft, same-repository and based on `main`;
- [ ] the repository owner is the actor who edits the PR body;
- [ ] the PR body contains exactly `<!-- RUN_HL_PUBLIC_PROBE_R1:<head-sha> -->`;
- [ ] the marker SHA is 40 lowercase hexadecimal characters and equals the current PR head;
- [ ] checkout uses that exact source SHA rather than the synthetic PR merge ref;
- [ ] `git rev-parse HEAD` equals the authorized SHA before any public probe request;
- [ ] reviewed and checked-out commits are retained as separate evidence fields;
- [ ] the marker is removed after the intended run to prevent an accidental duplicate execution.

## Capacity

- [x] base declared `/info` weight `586`;
- [x] maximum attempts `2`;
- [x] worst declared weight `1,172`;
- [x] captured planning budget `1,200`;
- [x] contract ceiling `1,180`;
- [x] maximum HTTP requests `36` versus registered worst case `32`.

## Security and evidence

- [x] workflow `contents: read` only and checkout credentials not persisted;
- [x] no secret/auth/cookie/private-key/signing/order/withdrawal capability;
- [x] same-origin redirects only;
- [x] bounded bytes/time/retries/requests/weight;
- [x] strict duplicate-key and nonfinite JSON handling;
- [x] exact contract/collector/request/response/output/artifact hashes;
- [x] exact observation order and response-class derivation;
- [x] raw values discarded;
- [x] pending evidence/attestation contain no invented identities.

## Research boundary

- [x] market data not analytically ingested;
- [x] wallet P&L/copyability not calculated;
- [x] entity clustering closed;
- [x] empirical result null;
- [x] every trading authorization false.

The workflow must still prove actual route behavior. Archive completeness, pagination, schemas, requester-pays cost and gaps remain unresolved after any route-level PASS.
