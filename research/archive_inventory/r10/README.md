# R10 — post-boundary multi-hour feature aggregation

R10 is the first deliberately bounded cross-object extension of the canonical R9 wallet-feature reducer.

## Why this exists

R9 proved one-object feature mechanics on the transition fixture but explicitly did not prove historical representativeness or cross-object aggregation. R8B excludes the shared `2025-07-27T08` path hour from canonical merged history. R3 independently retained a complete modern hourly metadata inventory with no internal missing path hour.

R10 therefore selects the first six contiguous **unambiguous** modern path hours after the censored boundary: 09, 10, 11, 12, 13 and 14 UTC on 27 July 2025. Selection is derived from retained R3 metadata only; this preregistration performs zero new S3 requests.

## What a later approved pilot would test

- six exact R3-bound objects are retrieved once each in path-hour order;
- each response must match its frozen ETag and content length;
- each object receives a retained compressed SHA-256 after retrieval;
- every fill timestamp must fall inside its source path hour;
- R9's selected fields are reduced into one cross-hour accumulator per wallet;
- `active_hour_count` is added as the only new per-wallet aggregate field;
- fill and side counts must conserve exactly;
- duplicate `(wallet_address, tid)` observations are counted and clean success requires zero duplicates;
- per-hour technical counts/hashes may be retained, but per-hour wallet rows and raw fills may not.

## What R10 is not

R10 is not a wallet-performance study, ranking pass, candidate shortlist, PnL/alpha analysis, copyability test or strategy inference. Six hours are deliberately insufficient for those claims. `closedPnl` remains a raw fill-derived statistic and the `abs(px*sz)` aggregate remains a notional proxy only.

## AWS boundary

The existing R4 role cannot be reused: its persistent policy explicitly denies `GetObject` outside the two exact 08 boundary objects. A future human-approved implementation must therefore define a **new** dedicated R10 role restricted to the six selected objects. Existing roles must not be widened. Role creation, operator attestation and an S3-denied STS-only preflight remain separate gates before any execution release.

## Current authority

None. No IAM mutation, STS call, S3 request, decompression, feature processing, ranking, trading or capital action is authorized by this preregistration.
