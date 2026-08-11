# R11 root-cause status before R11A

The original run proves that at least one legacy `(wallet, tid)` projection repeated. It does not prove why. The exception path discarded the preregistered repeat count and retained no occurrence-level block time, coin, payload or raw locator for the affected observations.

The semantic key defect is already proven: Hyperliquid documents the matched-trade identity as exact `(block_time, coin, tid)`, so wallet plus `tid` omits two required scope fields. Whether the actual R11 repeats are scope false positives, exact block replay, an intra-block repeat, a conflicting payload, or a mixture remains `UNKNOWN`.

The 94 previous-hour block records and 490 pre-path-hour fills do not by themselves prove replay. Source-object rotation can place a prior protocol block in the next path-hour object. Replay requires repeated `block_number` plus exact wrapper time and ordered event-vector comparison.

The historical day tracker has a separate proven source defect: rendering a wallet through `DayTrackingStates.__getitem__` adds the ambient last day during a read. The canonical run hit its duplicate guard before the render loop, so no retained wallet rows were corrupted; the feature artifact is empty. A successful path would have overcounted `active_day_count` for wallets not active on the last processed day.

R11A is therefore necessary to produce the missing complete repeat taxonomy. Until it runs, root cause, repair selection, R11 closure and R12 readiness remain false.
