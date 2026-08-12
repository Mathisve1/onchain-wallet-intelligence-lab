# R11A corrective preregistration amendment V2

## Status

`PREREGISTERED_NO_EXECUTION`

This amendment does not authorize owner approval, IAM changes, workflow installation, OIDC, STS, S3, decompression, diagnostic execution or downstream research. It formally replaces the runtime and retention design that was implemented in PR #141 and rejected by the independent RED review. The original R11 unresolved evidence and the four-layer identity model remain unchanged.

## Why an amendment is necessary

The original R11A contract combined two different goals:

1. proving the root cause of the repeated historical `wallet + typed tid` projection that stopped R11; and
2. retaining detailed row-level evidence for every unrelated schema violation across more than 26 million raw event observations.

The RED review showed that the first implementation could not honestly satisfy the resulting terminal, foreign-key, failure-artifact and resource requirements. The representative workspace estimate already consumed about 4.73 GB before the data-dependent schema index and sort overhead were included, under a fixed 5 GiB cap. Continuing by silently dropping fields, hard-coding proof claims or allowing partial output is forbidden.

V2 therefore narrows detailed row retention to the evidence that can causally explain the original repeat trigger while retaining exact global counts and cryptographic commitments for all raw observations. This is a formal scientific amendment, not an implicit weakening.

## What remains unchanged

- Exactly the same 72 immutable Hyperliquid hourly objects.
- Exactly three complete UTC days: 2025-07-28 through 2025-07-30.
- At most one Requester Pays `GetObject` per object and zero retries.
- The same compressed-, decompressed-, workspace-, artifact-, runtime- and budget caps.
- The same four identity layers:
  - raw observation;
  - archive block;
  - protocol matched trade;
  - wallet user fill.
- The same nine primary taxa.
- No deduplication, first-seen-wins, last-seen-wins or heuristic tolerance.
- No wallet features, ranking, PnL, alpha, copyability, clustering, strategy or trading authority.

## Revised evidence boundary

Every raw event is still parsed twice and participates in exact validation counts and per-object/pass commitments. Detailed scientific rows are retained for:

- every complete repeated historical weak-key group and all of its members;
- every repeated block-number group;
- every protocol-trade group intersecting retained repeat evidence;
- every TID, coin or wallet schema violation that occurs inside retained repeat evidence.

Unrelated singleton schema violations are represented by exact counts and deterministic commitments rather than full row-level payload evidence. Such singleton violations cannot explain the original duplicate trigger, while their counts remain fully conserved across both local passes.

## Group-wide classification

V2 removes the rejected `first/current` shortcut. Classification is performed over complete groups:

- a conflicting user fill is detected from the full canonical wallet-fill subgroup;
- an intra-block repeat is detected from every member in that subgroup, not only against the group first;
- a replay reobservation requires every raw block locator in the complete subgroup to resolve to one exact block replay proof;
- a TID scope false positive requires the complete weak-key group to contain distinct protocol identities and no missing, conflicting or unresolved identity or proof.

## Bounded execution architecture

The corrected implementation must:

- retain each compressed object only until its second local parse completes;
- write fixed 256-way block and weak-key indexes;
- reserve workspace before every mutation and check it afterwards;
- verify external-sort multiset equality with an exact SQLite BLOB multiplicity ledger per partition;
- spool large groups to bounded temporary files rather than unbounded Python lists;
- stream scientific NDJSON directly to staging files;
- place every processing and artifact file under one metered workspace root;
- delete temporary data with checked cleanup;
- validate the complete artifact before any upload;
- produce a valid minimal artifact on every allowed failure path.

## Terminal semantics

A complete taxonomy may be claimed only when all 72 objects and three UTC days are complete, both local passes agree, every conservation equation holds, all retained foreign keys resolve exactly once, all referenced projections are byte-equal, every unit universe has separate zero unclassifiable counts and all caps are respected.

A fully processed but scientifically unresolved result retains complete science and ends as `R11A_V2_DIAGNOSTIC_INCOMPLETE`.

A transport, integrity, parse, workspace or runtime stop produces seven exact zero-byte scientific containers and a minimal evidence artifact.

A retention or projected artifact-cap stop after complete discovery also produces seven exact zero-byte scientific containers and a cap terminal. Sampling, truncating one group or silently raising a cap remains forbidden.

## Next gate

The next allowed step is an inert corrective implementation with new hashes, new exact-head CI and another independent clean-context review. Owner approval remains forbidden until that implementation, a provider-pricing/EUR snapshot, the successor-role decision and the exact workflow candidate are all hash-bound and independently reviewed.
