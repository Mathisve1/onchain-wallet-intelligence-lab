# Data Availability Matrix

Availability is not completeness and does not authorize analytical ingestion.
The claims below are taken from the official source register frozen on
2026-08-07 and must be reconciled against exact technical evidence.

| Need | Intended public route | Published capability | Current gate |
|---|---|---|---|
| Perpetual metadata | `/info` `meta` | universe and margin metadata | response schema and BTC/ETH/SOL presence |
| Current mids | `/info` `allMids` | current mids for listed assets | technical shape only; no price values retained |
| Current L2 book | `/info` `l2Book` | current book levels | shape/depth-count probe only; no prices or sizes retained |
| Market-wide historical fills | `hl-mainnet-node-data/node_fills_by_block` | block-batched fills from a non-validating node | anonymous/requester-pays access, exact object inventory, schema history, gaps and hashes |
| Older historical fills/trades | `node_fills` and `node_trades` | older data exists in different formats | transition dates, incompatible schema and complete coverage |
| Historical L2 snapshots | `hyperliquid-archive/market_data` | selected L2 snapshots | monthly upload timing, missing intervals, timestamp alignment and object inventory |
| Historical asset context | `hyperliquid-archive/asset_ctxs` | asset context snapshots | schema history, completeness and mark/oracle/funding alignment |
| Public account state | `/info` `clearinghouseState` | current positions and margin state | snapshot cannot replace historical ledger |
| Known-wallet recent fills | `/info` `userFills` | recent fills for a known public address | only recent retained window; exact count and aggregation behavior |
| Known-wallet fills by time | `/info` `userFillsByTime` | time-bounded fills | official page contains 500-element general wording and 2,000-fill endpoint wording; 10,000-recent-fill limit also documented |
| Funding | `/info` `userFunding` | public funding history | time-range limit, pagination and ledger reconciliation |
| Deposits/transfers/withdrawals | `/info` `userNonFundingLedgerUpdates` | non-funding ledger includes deposits, transfers and withdrawals | taxonomy, pagination, completeness and cash-flow reconciliation |
| Account-specific fee structure | `/info` `userFees` | current user rates and fee schedule | point-in-time historical fee evidence remains unresolved |
| Confirmed subaccounts | `/info` `subAccounts` and `userRole` | direct master/subaccount relationship and role | absence does not prove independence; documented examples are technical fixtures only |
| Vault role/details | `/info` `userRole` and `vaultDetails` | public vault metadata and relationships | a public vault may represent many followers and market-making strategies |
| Live user events | public WebSocket subscriptions | user fills, funding and ledger updates for known users | published connection/subscription/unique-user ceilings and reconnect gap recovery |
| Market-wide low-latency events | non-validator node | fills, statuses, book diffs and block metadata | 16 vCPU/128 GB/500 GB published baseline; cost not justified before copyability evidence |
| Complete cross-venue exposure | unavailable from one venue | none | irreducible hidden CEX, OTC, options and other-wallet hedge limitation |

## Published resource constraints

The current official rate-limit documentation states:

- 1,200 aggregate REST weight per minute per IP;
- base weight 60 for `userRole`;
- base weight 2 for `l2Book`, `allMids` and `clearinghouseState`;
- base weight 20 for most other info requests; and
- additional result-size weight for fill, funding and other history responses.

The frozen R1 probe registers one request per capability, does not paginate and
keeps declared base weight below its contract ceiling.

## Evidence required before analytical release

Every retained archive object must eventually have:

- source bucket and object path;
- request payload or object key;
- retrieval and first-seen timestamps;
- HTTP and requester-pays status;
- compressed and uncompressed size;
- SHA-256;
- parser and schema version;
- minimum and maximum event time;
- row and distinct-block counts;
- duplicate and overlap counts;
- missing interval report; and
- immutable retention receipt.

A successful public probe proves none of those archive-level properties by
itself.
