# R3 decision record

Date: 2026-08-09
Status: accepted for static preregistration review only

## Decision

Use `HL-ARCHIVE-HOURLY-METADATA-INVENTORY-R3-001` as the next archive gate after the successful consumed R2 canary rather than opening the older 300-request inventory proposal.

R3 is limited to `node_fills_by_block/hourly/`, `node_fills/hourly/` and `node_trades/hourly/` because canonical R2 evidence shows these three wallet-history-relevant families expose hourly date/hour keypaths and every R2 first page was truncated. The proposed R3 envelope is at most 16 pages per family, 1,000 keys per page, 48 LIST requests total, 48,000 retained metadata entries, 32 MiB aggregate response bytes, 300 seconds and zero retries.

Continuation-token following is proposed only within the immediately preceding successful page of the same frozen prefix; token values are not retained. A family is complete only when `IsTruncated=false` is reached before the cap. Otherwise the result is censored/incomplete and no complete-coverage or gap claim is allowed.

The existing frozen stress pricing model implies a maximum synthetic stress cost of USD 0.019177216 at the technical response/request caps. EUR 0.10 is only a proposed human one-time ceiling and is not authorized by this decision.

`explorer_blocks`, `replica_cmds`, `market_data`, `asset_ctxs`, object-body access, decompression, the older 300-request envelope, market-data ingestion and all trading/capital capabilities remain out of scope and unauthorized.

This static preregistration does not authorize implementation, workflow installation, an execution release or any AWS/S3 request. After canonical merge, a fresh exact human scope/budget approval bound to the canonical R3 preregistration SHA is required before a separate implementation/review lane can begin.
