# R10 data execution evidence status

Canonical run `31377732916` executed once from `main` at dispatch commit `64a04363e2c885f3a419f5cc4a789dd157fed229` and the GitHub Actions job completed successfully as a governed research run. The research result itself is **unresolved**, not a completed six-hour wallet feature dataset.

The run made exactly one successful Requester Pays `GetObject` request for `node_fills_by_block/hourly/20250727/9.lz4` (18,147,822 compressed bytes), used zero retries, and stopped fail-closed before the second object because at least one fill `time` did not satisfy the preregistered strict source-path-hour rule. The artifact retained no wallet-feature rows; `r10-wallet-features.ndjson` is byte-empty.

The single-use R10 execution release is consumed and rerun remains forbidden. The unused portion of the original six-request envelope is not reusable without a new preregistration, approval and release. No ranking, shortlisting, PnL/alpha interpretation, copyability analysis, market-data enrichment or trading/capital authority is opened by this result.

Prior R9 evidence shows the earlier boundary fixture's observed fill times ranged from `2025-07-27T08:50:10.273Z` through `2025-07-27T08:59:59.895Z`, but that does not resolve the R10 hour-9 mismatch semantics. The next correct research step is a separately preregistered, minimal timestamp-partition diagnostic that retains only aggregate alignment evidence needed to determine how `node_fills_by_block/hourly/...` path hours relate to block and fill timestamps.
