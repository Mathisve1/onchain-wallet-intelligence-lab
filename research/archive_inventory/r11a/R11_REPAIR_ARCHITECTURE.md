# R11 evidence-driven repair architecture

## Proposed offline foundation

The successor code separates four layers instead of treating a convenient uniqueness check as event identity:

| Layer | Key / locator | Current action |
|---|---|---|
| raw observation | source object key + verified compressed SHA-256 + record ordinal + event ordinal | always retain for every repeated group |
| archive block | `block_number` plus exact wrapper time and ordered event-vector invariants | classify only |
| matched trade | exact wrapper `block_time` + exact source `coin` namespace + strict uint50 `tid` | compare, never use as source locator |
| wallet fill | wallet + matched-trade key | compare wallet-side observations |

Resource limits are immutable per-instance values. Activity state has an explicit `record()` write API and pure immutable snapshots; no mapping read creates a wallet or adds a day. Source-path hour is not silently promoted to event activity time.

## Conditional repair decision after R11A

R11A does not canonicalize anything. A later R11B repair may choose only the branch empirically supported by the complete diagnostic:

1. If every repeat is `TID_SCOPE_FALSE_POSITIVE`, no observation is dropped. The reducer replaces the legacy weak-key guard with the documented layered identities and counts every valid wallet-side fill.
2. If exact cross-object block replay is proven, canonicalization may occur only at the block layer. One semantic block contributes once to downstream aggregation, while every raw occurrence remains in an immutable provenance multimap. The exact suppression rule, tie-free deterministic ordering and conservation equation require a separate preregistration.
3. If any block-number conflict, canonical wallet-fill payload conflict, schema violation, cap overflow or `UNCLASSIFIABLE` group remains, aggregation fails closed. There is no first-seen, last-seen or payload-hash-only fallback.

A normal matched trade can produce two wallet-side fill observations. Per-wallet fill counts must retain both counterparties in their respective wallets. Venue-wide `wallet_fill_observation_count` and `matched_trade_count` are different measures and must never be conflated.

## Deterministic repaired reducer requirements

The later repaired reducer must:

- order canonical blocks by protocol block identity and raw provenance without relying on input dictionary insertion order;
- preserve exact source `coin` strings and strict integer `tid` values;
- expose source-path, wrapper-block and fill-event clocks separately;
- select and preregister the clock used for activity before computing `active_hour_count` or `active_day_count`;
- conserve input raw observations into unique canonical wallet fills plus explicitly proven replay occurrences;
- conserve wallet fill and side counts, while reporting matched trades separately;
- fail on conflicting replay, malformed pairs, schema drift or incomplete provenance;
- emit deterministic byte-identical sorted output under repeated offline fixture runs.

## Required proof sequence

The order remains R11A diagnostic evidence → separate R11B repair preregistration and review → separate repaired 72-hour single-use validation → evidence closure. Only that repaired validation may determine whether R11 is closed. R12 readiness is a later audit and remains false now.
