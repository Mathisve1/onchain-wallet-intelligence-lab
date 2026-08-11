# R10D backward-consistency review after the R11 identity audit

## Decision

R10D is classified as `C_R10D_UNCERTAIN_UNDER_CANONICAL_IDENTITY`.

This does not invalidate the canonical R10D run. It preserves the run exactly as historical mechanics evidence while separating what the run actually observed from what it cannot prove about economic event identity.

## What remains proven

Canonical run `31420197671` processed the six selected hourly objects with six successful requests, zero failures, zero retries and zero record-anchored alignment violations. The retained result conserves 1,486,542 event-pair observations against the side observations and reports zero repeats under the legacy detector `(wallet_address, normalized typed tid)`.

The retained source-observation totals are:

| Metric | Retained value |
|---|---:|
| block-record observations | 241,414 |
| path-hour block-record observations | 241,409 |
| previous-hour block-record observations | 5 |
| event-pair observations | 1,486,542 |
| before / inside / after path-hour observations | 10 / 1,486,532 / 0 |
| wallet rows under the legacy reducer | 16,410 |
| repeats under wallet + typed tid | 0 |

These are valid R10D observation and legacy-reducer facts. They are not retroactively deleted or rewritten.

The still-retained provider artifact was also reconstructed byte-for-byte offline. Its ZIP SHA-256, wallet-feature SHA-256, 16,410 unique sorted wallet rows, fill/side sums, active-hour distribution and both exact decimal aggregate totals all reproduce. This proves the retained legacy output; it does not recreate the six raw S3 objects or retroactively supply the missing block/event provenance.

## Why exact backward reproduction is not proven

Hyperliquid documents `(block_time, coin, tid)` as the global matched-trade identity. The R10D reducer instead used wallet plus typed `tid`. R10D retained no occurrence-level block-overlap ledger that can answer whether the same exact block appeared in more than one source object, and it retained no canonical wallet-fill provenance ledger keyed by wallet, block time, coin and validated integer `tid`.

Consequently:

- option A, exact reproduction under the new identity architecture, is not proven;
- option B, a demonstrable correction to the R10D aggregate, is not proven;
- option C, uncertainty for canonical unique block and wallet-fill semantics, is the only evidence-supported classification.

The zero weak-key repeat count is evidence only for the exact six-hour run under that detector. It is not protocol evidence that wallet plus `tid` is unique.

There is a second semantic limit: the ten pre-path-hour fills were credited to their source object path hours. The retained feature rows do not expose enough occurrence-level evidence to prove that source-path `active_hour_count` equals an event-time or wrapper-block-time activity count. Raw `tid` JSON types and ranges likewise were not retained, so strict uint50 compatibility is unknown.

## Scientific consequence

R10D continues to support the record-anchored archive mechanics and the exact retained observation counts. Its wallet feature file and aggregate statistics must be labelled as products of a superseded weak identity assumption. They must not be presented as a proven canonical unique-fill ledger or used for wallet ranking, profitability, alpha or copyability claims.

R11A is deliberately restricted to R11's exact 72 objects and therefore cannot answer the remaining R10D six-object question. Full canonical-identity backward consistency would require a separately preregistered and approved diagnostic over exactly the same six R10D objects, with no additional hour. R10D itself is single-use and its consumed release is not authorized for rerun.

The machine-readable decision is in `R10D_BACKWARD_CONSISTENCY.json`.
