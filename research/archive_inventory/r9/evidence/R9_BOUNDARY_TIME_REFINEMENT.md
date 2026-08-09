# R9 boundary-time refinement

R9 was not authorized as a historical-representativeness study. The `node_fills_by_block/hourly/20250727/8.lz4` object remains a serializer and feature-pipeline fixture, and the R8B fail-closed rule continues to censor the shared `2025-07-27T08` path hour from canonical merged history.

## Newly direct evidence

The permitted per-wallet `first_fill_time` and `last_fill_time` aggregates allow a dataset-wide extrema calculation without retaining individual fill records. Across all 887 deterministic R9 wallet-feature rows:

- earliest retained fill time: `1753606210273` ms = `2025-07-27T08:50:10.273Z`;
- latest retained fill time: `1753606799895` ms = `2025-07-27T08:59:59.895Z`;
- observed modern-boundary feature span: `589622` ms = `589.622` seconds.

Thus the modern boundary object directly proves observed fills only in the final approximately 9 minutes 49.622 seconds of its `20250727/8` path hour.

## Effect on R8B

This materially strengthens the existing R8B inference that the shared path hour is a transition/cutover boundary rather than two complete equivalent copies of the same market-time hour.

It does **not** prove the exact cutover instant, exact fill-level continuity, absence of a gap, absence of overlap, or the legacy object's own minimum/maximum fill timestamps. Therefore the canonical fail-closed rule is unchanged:

- legacy path hours through `2025-07-27T07` are eligible for future legacy-side history;
- modern path hours from `2025-07-27T09` are eligible for future modern-side history;
- both `2025-07-27T08` boundary objects remain excluded from canonical merged history.

No new S3 request is required to reach this refinement; it is derived solely from R9's already authorized retained aggregate feature output.
