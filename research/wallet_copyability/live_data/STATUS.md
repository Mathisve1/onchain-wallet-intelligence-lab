# L1 live-data collection status

| Dimension | State |
|---|---|
| pilot | `HL-LIVE-DATA-COLLECTION-L1-001` |
| preregistration | `PREREGISTERED_NO_EXECUTION` at commit `e3610cd494211f6a399caffd7741a2f526b3287a` |
| owner approval | `PRESENT`; exact text SHA-256 `d87df45cd8b0afa597f8ee0848b6f75baf4ca79b0dcd59c2bb4b9fd3b5dede1b` |
| owner decision | `L1-OWNER-DECISION-001`: approval, implementation review and single-use release in one decision (DEC-040) |
| execution release | `RELEASE_HL_LIVE_DATA_COLLECTION_L1_001`, `CONSUMED` by `L1-SESSION-001`; rerun not authorized |
| session window | `2026-09-03T18:20:42Z` to `2026-09-03T18:35:31Z` |
| wallets discovered / backfilled | `839` / `7` (3 backfills failed on HTTP 429 after the approved 3 retries) |
| fills / funding / snapshots / trades / mids | `130457` / `3004` / `35` / `3358` / `273` |
| request weight | `2012` total over `133` attempts, `16` retries; local budget `1200`/min never exceeded |
| envelope | pinched, not widened: venue weights large responses above the documented base weight |
| database | outside the repository; SHA-256 `b5da970da812907e19cc760b1583df007b2bfb87129541fdbde791e2961777c9`; not committed |
| workflow installed | `false` |
| empirical result / wallet ranking / copyability claim | `null` / `false` / `false` |
| trading authorizations | all `false` |

## Coverage caveats

Five of seven backfills hit the venue's 500-row funding cap; their funding is
not complete and the run records predate the truncation flag that now exists.
Fill windows were exhausted for all seven. Position snapshots exist only from
the session onward.

## Next gate

A successor session needs a new owner decision. Before one is requested, the
local weight accounting should charge response size so the venue's throttle is
never reached first. Scoring wallets over certified intervals waits on a
wallet-ranking authorization; the simulator that would do it lives in
`src/copyability` and refuses to score anything the coverage ledger has not
certified.
