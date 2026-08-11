# R11 research conclusion

**Result:** `R11_72H_PERSISTENCE_PIPELINE_UNRESOLVED`.

The 72-hour transport and record-alignment mechanics succeeded, but the intended wallet-feature dataset was deliberately not released because the R11 aggregator detected at least one repeated normalized `(wallet, tid)` observation. The current retained artifact proves the duplicate condition occurred, but it does not retain enough detail to determine how many duplicates occurred, in which object/hour they occurred, or whether repeated rows are byte/field-identical observations versus distinct legitimate fills sharing the same `tid`.

This is also a formal preregistration deviation: R11 promised to retain `duplicate_wallet_tid_count`, but the unresolved exception handler replaced the aggregate summary with `null`. The original run is therefore canonically consumed and technically attested, but its duplicate diagnostic contract was not complete.

Offline review found two success-path defects that did not publish corrupted rows because the duplicate guard fired before rendering: `DayTrackingStates.__getitem__()` mutates activity state during a read, and prior-hour fills are attributed to the source path hour/day rather than a separately proven event-time activity bucket. The R11 module also mutates shared R10 limit globals at import time. These mechanics are deprecated for successors.

The next scientifically valid step is a new, separately approved identity-and-boundary diagnostic. It must characterize repeated `(wallet, tid)` observations, distinguish raw observation/block/economic-trade/wallet-side identity, and compare source-partition activity with event-time activity without ranking wallets, calculating performance, or silently deduplicating them. R11 itself must not be rerun.
