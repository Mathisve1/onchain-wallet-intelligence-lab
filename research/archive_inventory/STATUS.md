# HL-ARCHIVE-INVENTORY-001 status

- phase: `R2_HUMAN_APPROVAL_UNDER_REVIEW_NO_EXECUTION`
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
- R0 implementation canonical commit: `cd5c46b25502b671693dd5ebb091e7273399bccf`
- R0 release canonical commit: `bc8a47a1cdeb1163657ea243d6694286d6612bed`
- R0 release status: `CONSUMED_BY_RUN_31260043109`
- R0 canonical run / job / artifact: `31260043109` / `93109335453` / `9022511541`
- R0 attestation canonical commit: `105673b91d233ffcfd19a7bf3d881dbee6d85c6a`
- R0 result: `ATTESTED_CONSUMED_PARTIAL_FAILURE_REGION_UNRESOLVED`
- R0 execution ready: `false`
- current R0-scoped Requester Pays authorization: `false`
- current R0-scoped ListObjectsV2 authorization: `false`
- Region probe: `HL-ARCHIVE-REGION-PROBE-R1-001`
- Region probe preregistration canonical commit: `910997423f5e008f3c7bca65fd739d6aa14d25a7`
- Region probe approval canonical commit: `b86156d71ef438441e6d3903a8bbc2da564a2046`
- Region probe implementation canonical commit: `91687b4c803e331d4b2ef8493df731c99e25a0e5`
- Region probe release canonical commit: `f32901ac1946ff6456c44b3a1f75e4a7b641fa39`
- Region probe release status: `CONSUMED_BY_RUN_31273770895`
- Region probe canonical run / job / artifact: `31273770895` / `93143945097` / `9026393705`
- Region probe attestation canonical commit: `9378f625648592bd4a5890f47a98b36028cbd433`
- Region probe terminal result: `REGION_PROBE_R1_PASS`
- Region probe HTTP result: `400` / `4xx`
- Region probe exact bucket Region: `ap-northeast-1`
- Region probe S3 HTTP requests / retries / redirects: `1` / `0` / `false`
- Region probe response body read: `false`
- Region probe LIST/object data requested: `false`
- Region probe execution ready: `false`
- Region probe current Requester Pays authorization: `false`
- R2 canary: `HL-ARCHIVE-NODEDATA-METADATA-CANARY-R2-001`
- R2 preregistration canonical commit: `39b40cccc7e9a3fdbc439d06fb188e946d9da2aa`
- R2 preregistration snapshot: `PREREGISTERED_CORRECT_REGION_METADATA_CANARY_NOT_AUTHORIZED`
- R2 current status: `HUMAN_APPROVAL_UNDER_REVIEW_NO_EXECUTION`
- R2 target bucket: `hl-mainnet-node-data`
- R2 signing Region: `ap-northeast-1`
- R2 frozen prefixes: `node_fills_by_block/`, `node_fills/`, `node_trades/`, `explorer_blocks/`, `replica_cmds/`
- R2 maximum ListObjectsV2 requests: `5`
- R2 maximum keys/request / total entries: `25` / `125`
- R2 maximum aggregate response bytes: `8388608`
- R2 maximum runtime: `120 seconds`
- R2 retries / pagination / redirects: `0` / `false` / `false`
- R2 approval ID: `APPROVE_HL_ARCHIVE_NODEDATA_CANARY_R2_001`
- R2 approval reviewed commit: `39b40cccc7e9a3fdbc439d06fb188e946d9da2aa`
- R2 approval recorded timestamp: `2026-08-08T19:48:00Z`
- R2 approval text SHA-256: `728f4e21c045eb10e883bdf0f2e970686f0e6b6cc4dc67a4f214a882cf1831c6`
- R2 one-time ceiling: `EUR 0.10`
- R2 monthly ceiling: `EUR 0`
- R2 human scope/budget approval: `RECORDED_ON_REVIEW_BRANCH_NOT_YET_CANONICAL`
- R2 implementation phase after approval merge: `AUTHORIZED_TO_BUILD_AND_REVIEW_ONLY`
- R2 implementation installed: `false`
- R2 workflow installed: `false`
- R2 execution release present: `false`
- R2 execution ready: `false`
- R2 current paid request authorization: `false`
- R2 current Requester Pays authorization: `false`
- R2 current ListObjectsV2 authorization: `false`
- R2 S3 requests executed: `0`
- R2 metadata entries observed: `0`
- GetObject authorized: `false`
- HeadObject authorized: `false`
- GetObjectAttributes authorized: `false`
- range GET authorized: `false`
- ListObjectVersions authorized: `false`
- ListAllMyBuckets authorized: `false`
- object-body download authorized: `false`
- decompression authorized: `false`
- broader 300-request inventory authorized: `false`
- market data ingested: `false`
- empirical result: `null`
- all trading/execution authorizations: `false`

## Next gate

The fresh R2 approval is being recorded on a dedicated review branch and is exact-commit/hash bound to canonical preregistration `39b40cccc7e9a3fdbc439d06fb188e946d9da2aa`. The approval covers only the frozen five-prefix first-page metadata scope and EUR 0.10 one-time / EUR 0 monthly budget.

This approval branch contains no R2 collector, no R2 network workflow and no R2 execution release. No AWS/S3 request may occur from this PR or its CI. Operational Requester Pays, paid-request and `ListObjectsV2` flags remain false.

Next: exact-head CI, byte-exact manifest validation and clean-context review. Only after this approval record is canonically merged may a separate minimal R2 implementation/workflow be built and reviewed. That implementation must still fail closed before OIDC until a later exact-implementation-bound single-use release is canonically present.

The larger 300-request inventory, all object-body access, market-data ingestion and all trading/capital stages remain unauthorized.
