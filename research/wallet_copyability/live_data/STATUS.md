# L1 live-data collection status

| Dimension | State |
|---|---|
| pilot | `HL-LIVE-DATA-COLLECTION-L1-001` |
| status | `PREREGISTERED_NO_EXECUTION` |
| owner approval | `NOT_PRESENT` |
| execution release | `ABSENT` |
| workflow installed | `false` |
| REST requests executed | `0` |
| websocket connections opened | `0` |
| database rows written | `0` |
| market data ingested | `false` |
| empirical result | `null` |
| maximum one-time / monthly budget | `EUR 0` / `EUR 0` |
| trading authorizations | all `false` |

## Implementation

The deterministic core is `src/live_data` and carries no network dependency: its
only absolute imports are standard library, it constructs no transport and it
has no executable entry point. The concrete transports live in
`research/wallet_copyability/live_data_collector` and are injected by the
caller, which is what keeps `src/` offline-testable end to end.

199 live-data tests pass, covering config validation, request-body construction,
weight accounting, retry charging, websocket routing, storage idempotency,
coverage tracking and the read-only guard.

## Next gate

One hash-bound owner approval of the exact envelope in
`L1_LIVE_DATA_COLLECTION_PREREGISTRATION.json`, using the exact text in
`HUMAN_APPROVAL_TEMPLATE.md`. Until that exists, no observation session is
authorized and this pilot executes nothing.
