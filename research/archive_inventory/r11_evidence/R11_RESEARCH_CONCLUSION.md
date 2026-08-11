# R11 research conclusion

**Result:** `R11_72H_PERSISTENCE_PIPELINE_UNRESOLVED`.

The 72-hour transport and record-alignment mechanics succeeded, but the intended wallet-feature dataset was deliberately not released because the R11 aggregator detected at least one repeated normalized `(wallet, tid)` observation. The current retained artifact proves the duplicate condition occurred, but it does not retain enough detail to determine how many duplicates occurred, in which object/hour they occurred, or whether repeated rows are byte/field-identical observations versus distinct legitimate fills sharing the same `tid`.

The next scientifically valid step is a new, separately approved duplicate-TID diagnostic. It must characterize repeated `(wallet, tid)` observations without ranking wallets, calculating performance, or silently deduplicating them. R11 itself must not be rerun.
