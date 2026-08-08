# HL-ARCHIVE-INVENTORY-001 status

- phase: `R0_ATTESTED_PARTIAL_FAILURE_REGION_DISCOVERY_REQUIRED`
- parent public probe: `ATTESTED_PUBLIC_PROBE_PASS`
- parent archive route status: `ROUTES_CONFIRMED_ACCESS_RESTRICTED`
- parent archive status: `PREREGISTERED_METADATA_ONLY_NO_EXECUTION`
- AWS account ID: `630956766927`
- GitHub OIDC federation: `PROVEN_BY_CANONICAL_STS_RUN`
- expected role: `onchain-wallet-intelligence-hl-archive-metadata-canary`
- STS identity check status: `ATTESTED_STS_IDENTITY_MATCH`
- AWS identity bound: `true`
- persistent S3 inline policy: `USER_CONFIRMED_NOT_API_VERIFIED`
- R0 canary: `HL-ARCHIVE-METADATA-CANARY-R0-001`
- R0 approval: `APPROVED_SCOPE_AND_BUDGET_CONSUMED`
- approval reviewed commit: `9af4b21863e47fb3bb2997ce77b9940eecf4597f`
- approval timestamp: `2026-08-08T10:10:00Z`
- approval text SHA-256: `d70008eac7521b324f61161bcc0075e28cc3a116dd30f0c52b48d8cf5eb6ed46`
- human-approved one-time ceiling: `EUR 1.00`
- monthly ceiling: `EUR 0`
- R0 implementation canonical commit: `cd5c46b25502b671693dd5ebb091e7273399bccf`
- R0 release canonical commit: `bc8a47a1cdeb1163657ea243d6694286d6612bed`
- release ID: `RELEASE_HL_ARCHIVE_METADATA_CANARY_R0_001`
- release status: `CONSUMED_BY_RUN_31260043109`
- canonical run / job / artifact: `31260043109` / `93109335453` / `9022511541`
- artifact SHA-256: `40b26e33833b54a872a75be066a87b7e57a0e2f3930adada76ca3829a1142c8e`
- terminal status: `R0_METADATA_CANARY_FAIL`
- attestation status: `ATTESTED_CONSUMED_PARTIAL_FAILURE_REGION_UNRESOLVED`
- AWS OIDC configure outcome: `success`
- S3 HTTP requests: `7`
- successful requests: `2`
- failed requests: `5`
- retained metadata entries: `50`
- total response bytes: `14229`
- runtime seconds: `2.439212`
- retries: `0`
- pagination followed: `false`
- HTTP redirects followed: `false`
- object body requested: `false`
- market data ingested: `false`
- `hyperliquid-archive/market_data/`: `SUCCESS_25_ENTRIES_TRUNCATED_REQUESTER_PAYS`
- `hyperliquid-archive/asset_ctxs/`: `SUCCESS_25_ENTRIES_TRUNCATED_REQUESTER_PAYS`
- all five `hl-mainnet-node-data` families: `S3_AuthorizationHeaderMalformed`
- `hl-mainnet-node-data` exact Region: `UNRESOLVED`
- root-cause assessment: `STRONGLY_CONSISTENT_WITH_SIGNING_REGION_MISMATCH_NOT_YET_PROVEN`
- R0 execution ready: `false`
- current R0-scoped Requester Pays authorization: `false`
- current R0-scoped ListObjectsV2 authorization: `false`
- fresh paid attempt authorized: `false`
- broader 300-request inventory authorized: `false`
- GetObject authorized: `false`
- object-body download authorized: `false`
- empirical result: `null`
- all trading/execution authorizations: `false`

## Next gate

The existing release is consumed and cannot be reused. Preserve and merge the attested R0 evidence first. Then preregister a separate Region-discovery successor for `hl-mainnet-node-data`. The preferred minimum is one direct `HeadBucket` request retaining only coarse status and `x-amz-bucket-region`; no body, LIST pagination, object retrieval or market-data ingestion. That new network request requires fresh explicit approval.

The larger 300-request inventory, all object-body access, market-data ingestion and all trading/capital stages remain unauthorized.
