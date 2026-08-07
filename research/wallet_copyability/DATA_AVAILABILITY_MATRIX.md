# Data Availability Matrix

Availability is not completeness and does not authorize analytical ingestion.

| Need | Intended public route | Current gate |
|---|---|---|
| Market-wide historical fills | official block-based fill archives | exact object inventory, schema history, gaps, hashes and requester cost |
| Historical L2 snapshots | official market-data archives | timestamp alignment, coverage and missing intervals |
| Asset context | official asset-context archives/API | mark, oracle and funding schema alignment |
| Public account state | public info endpoint | snapshots cannot replace a historical ledger |
| Known-wallet fills | public user fill endpoints | exact result limits, time pagination and retention window |
| Funding | public funding history | pagination and reconciliation |
| Deposits/transfers/withdrawals | public non-funding ledger updates | event taxonomy and completeness |
| Confirmed subaccounts | public subaccount and role information | absence does not prove independence |
| Vaults | public role and vault details | public vault may represent many users |
| Live user events | public WebSocket subscriptions | address-subscription scale and gap recovery |
| Market-wide low-latency events | optional non-validator node | cost not justified before copyability evidence |
| Complete cross-venue exposure | unavailable from one venue | irreducible hidden-hedge limitation |

Every retained object requires route, request payload, retrieval time, first-seen
time where live, HTTP status, byte length, SHA-256, parser/schema version,
minimum/maximum event time, row count, duplicates and a gap report.
