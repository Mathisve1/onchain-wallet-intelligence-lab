# R3 hourly metadata inventory approval status

`APPROVE_HL_ARCHIVE_HOURLY_METADATA_INVENTORY_R3_001` was supplied as an explicit human scope/budget approval bound to canonical R3 preregistration commit `ab4d42be02fe49d7f90f933317ef856f0322fd85`.

The exact approval text SHA-256 is `3c3931133fb8b0dd322d7a296b7b70fca65dd341401a6eda2b6372938ed6cd10`.

Approved scope: exact bucket `hl-mainnet-node-data`, signing Region `ap-northeast-1`, and only these three hourly prefixes: `node_fills_by_block/hourly/`, `node_fills/hourly/`, and `node_trades/hourly/`.

Approved hard ceilings are 48 `ListObjectsV2` requests total, 16 pages per family, 1,000 keys per request, 48,000 retained entries, 32 MiB aggregate response bytes, 300 seconds, zero retries, and EUR 0.10 one-time / EUR 0 monthly budget. Pagination and continuation-token following are scope-approved only within the same frozen prefix, using only the token returned by the immediately preceding successful page. Continuation-token values may not be retained, and repeated tokens must fail closed. Redirects, `StartAfter` and `Delimiter` are not authorized.

This approval opens only the implementation/review lane after canonical merge of this approval record. It does not install executable code, install a workflow, create an execution release, assume an AWS role, or execute an S3 request. Runtime paid-request, Requester Pays and `ListObjectsV2` authority remain false.

`GetObject`, `HeadObject`, `GetObjectAttributes`, range GET, object-version listing, account-wide bucket listing, object-body download, decompression, explorer-block inventory, replica-command inventory, market-data ingestion, the larger 300-request inventory and all trading/capital stages remain unauthorized.
