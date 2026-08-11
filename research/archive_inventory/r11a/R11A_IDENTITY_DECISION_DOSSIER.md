# R11A canonical identity decision dossier

## Decision

R11A must keep four identities separate: raw observation, archive block, protocol matched trade and wallet user-fill. The legacy R10D/R11 key `wallet + tid` is superseded as a canonical event identity but preserved as a diagnostic weak key so the original R11 failure can be reproduced and classified.

| Layer | Canonical key or locator | Role |
|---|---|---|
| raw observation | object key + verified compressed SHA-256 + record ordinal + event ordinal | lossless source provenance |
| archive block | block number, checked against exact block time and ordered-event fingerprint | replay/conflict classification |
| protocol matched trade | exact wrapper block time + exact schema-validated source `coin` namespace + validated integer `tid` | documented global trade identity |
| wallet user-fill | wallet + exact wrapper block time + exact schema-validated source `coin` namespace + validated integer `tid` | one user side of a matched trade |

Hyperliquid documents `tid` as a 50-bit hash of buyer and seller order IDs and documents `(block_time, coin, tid)` as the globally unique trade ID. Wallet is added only to identify a user side; it does not replace block time or coin. An official-organization reference consumer strongly corroborates the adjacent A/B two-wallet representation, but that repository explicitly disclaims normative completeness; the diagnostic therefore tests this structure rather than assuming it.

## Fingerprint boundary

Raw-record, ordered-block-event and full wallet-fill payload fingerprints are equality and conflict invariants. They are not semantic primary keys. Two identical payload hashes may be reduced only if the block-provenance layer first proves exact replay. Any payload difference under the same canonical key remains fail-closed.

## Schema boundary

R11A accepts `tid` only as a raw JSON integer in `[0, 2^50)`. Strings, decimals, floats, booleans and out-of-domain values are schema violations; no type coercion is allowed. Block-time tolerance and timezone inference are forbidden.

## Decision still deferred

This dossier does not decide a repair. It defines what the R11A diagnostic must prove. Exact block replay, weak-key scope collapse, a mixture of both, or a conflict remain competing outcomes. Only complete occurrence-level evidence may inform a later and separately preregistered R11B repair.

No wallet features, ranking, PnL/alpha interpretation, copyability analysis, historical expansion or trading authority are opened.

## Boundary status

`local_time`, source path hour, wrapper `block_time` and inner fill `time` are distinct clocks. A previous-hour block observed in a later path-hour object does not by itself prove replay; it may be rotation/write-time placement. Exact replay remains `UNKNOWN` until the same `block_number` is found at multiple raw locators with identical wrapper time and ordered event vector. A repeated block number with divergent invariants is a conflict, not a deduplication candidate.
