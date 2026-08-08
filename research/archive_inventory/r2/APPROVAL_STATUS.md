# Correct-region node-data metadata canary R2 approval status

`APPROVE_HL_ARCHIVE_NODEDATA_CANARY_R2_001` is a canonical human scope/budget approval bound to R2 preregistration commit `39b40cccc7e9a3fdbc439d06fb188e946d9da2aa`. The approval was canonically merged as `151e08f54037ca7d3a0a9c17d3bdfb84d707a66e`.

The exact approval text SHA-256 is `728f4e21c045eb10e883bdf0f2e970686f0e6b6cc4dc67a4f214a882cf1831c6`.

Approved envelope: exact bucket `hl-mainnet-node-data`, signing Region `ap-northeast-1`, exactly one first-page `ListObjectsV2` request for each of the five frozen prefixes, maximum 5 requests total, maximum 25 keys per request / 125 entries total, 8 MiB aggregate response bytes, 120 seconds, zero retries, no pagination and no redirect following, with Requester Pays acknowledgement and a EUR 0.10 maximum one-time / EUR 0 monthly budget.

The five approved prefix families remain exactly `node_fills_by_block/`, `node_fills/`, `node_trades/`, `explorer_blocks/` and `replica_cmds/`.

The immutable approval snapshot itself installed no workflow or executable and created no single-use execution release. It opened only the implementation/review phase. A later implementation candidate now exists separately on the R2 implementation review branch; that does not mutate or widen this approval snapshot.

Runtime remains closed. `R2_EXECUTION_RELEASE.json` is absent, the implementation SHA is still pending canonical merge, and operational paid-request, Requester Pays and `ListObjectsV2` authorization remain false. GetObject, HeadObject, GetObjectAttributes, range GET, object-version or account-wide bucket listing, object-body download, decompression, market-data ingestion and the larger 300-request inventory remain forbidden. All trading/capital stages remain false.
