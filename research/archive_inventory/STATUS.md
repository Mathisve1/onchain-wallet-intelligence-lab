# HL-ARCHIVE-INVENTORY-001 status

- phase: `R0_SINGLE_USE_EXECUTION_RELEASE_UNDER_REVIEW`
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
- R0 human approval: `APPROVED_SCOPE_AND_BUDGET`
- approval canonical record commit: `62e0750382216afb5875ad52cb7443d43265e862`
- approval reviewed commit: `9af4b21863e47fb3bb2997ce77b9940eecf4597f`
- approval timestamp: `2026-08-08T10:10:00Z`
- approval text SHA-256: `d70008eac7521b324f61161bcc0075e28cc3a116dd30f0c52b48d8cf5eb6ed46`
- human-approved one-time ceiling: `EUR 1.00`
- monthly ceiling: `EUR 0`
- R0 implementation: `INSTALLED_ON_CANONICAL_MAIN`
- implementation canonical commit: `cd5c46b25502b671693dd5ebb091e7273399bccf`
- implementation exact-head CI: `41dcd5c2788af60ce9337b0c7eff4395264c4682`
- implementation CI run / job: `31257261899` / `93102453441`
- implementation tests: `108/108 PASS`
- transport: `DIRECT_SIGV4_HTTPS_NO_REDIRECT_FOLLOW`
- maximum S3 HTTP requests: `7`
- max keys/request: `25`
- max total entries: `175`
- max response bytes: `8388608`
- max runtime seconds: `180`
- retries: `0`
- pagination: `false`
- HTTP redirects followed: `false`
- release ID: `RELEASE_HL_ARCHIVE_METADATA_CANARY_R0_001`
- release status: `SINGLE_USE_RELEASE_CANDIDATE_FOR_CANONICAL_MAIN`
- single-use window start: `2026-08-08T10:10:00Z`
- single-use window source: `CANONICAL_HUMAN_APPROVAL_RECORDED_AT_UTC`
- one workflow dispatch authorized: `true`
- rerun authorized: `false`
- noncanonical branch network execution authorized: `false`
- R0-scoped requester-pays authorized after release merge: `true`
- R0-scoped ListObjectsV2 authorized after release merge: `true`
- broader 300-request inventory authorized: `false`
- GetObject authorized: `false`
- object-body download authorized: `false`
- S3 requests executed: `0`
- inventory result: `null`
- market data ingested: `false`
- empirical result: `null`
- all trading/execution authorizations: `false`

## Next gate

This release candidate must pass exact-head CI, byte-exact manifest validation, R0-specific release validation and clean-context review. Only after it merges to canonical `main` may exactly one manual `Hyperliquid Archive Metadata Canary R0` dispatch be started against the exact release merge SHA.

The single-use window is anchored to the canonical human approval timestamp, not the release timestamp. The first R0 dispatch on `main` since that window consumes the release regardless of PASS/FAIL. A rerun or second dispatch requires a fresh reviewed release before any new paid request.

The larger 300-request inventory envelope, object-body access, market-data ingestion and all trading/capital stages remain separately unauthorized even if R0 succeeds.
