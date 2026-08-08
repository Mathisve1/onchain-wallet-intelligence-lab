# HL-ARCHIVE-INVENTORY-001 status

- phase: `REGION_PROBE_R1_HUMAN_APPROVED_AWAITING_IMPLEMENTATION`
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
- Region probe preregistration snapshot: `PREREGISTERED_NOT_AUTHORIZED`
- Region probe current status: `HUMAN_APPROVED_AWAITING_IMPLEMENTATION`
- Region probe target: `hl-mainnet-node-data`
- Region probe operation: `HeadBucket` / `HEAD /`
- Region probe S3 HTTP request cap: `1`
- Region probe runtime cap: `30 seconds`
- Region probe retries / redirects: `0` / `false`
- Region probe approval ID: `APPROVE_HL_ARCHIVE_REGION_PROBE_R1_001`
- Region probe approval reviewed commit: `910997423f5e008f3c7bca65fd739d6aa14d25a7`
- Region probe approval timestamp: `2026-08-08T14:52:00Z`
- Region probe approval text SHA-256: `56c8d01396b12d0dd783dbc1646ebbca947e51a024bb5c8f091cd0b7a889c541`
- Region probe one-time ceiling: `EUR 0.10`
- Region probe monthly ceiling: `EUR 0`
- Region probe implementation phase authorized: `true`
- Region probe implementation installed: `false`
- Region probe workflow installed: `false`
- Region probe executable installed: `false`
- Region probe execution release present: `false`
- Region probe execution authorized: `false`
- Region probe request executed: `false`
- Region probe exact bucket Region: `null`
- fresh paid attempt authorized: `false`
- ListObjectsV2 authorized: `false`
- GetObject authorized: `false`
- HeadObject authorized: `false`
- object-body download authorized: `false`
- broader 300-request inventory authorized: `false`
- market data ingested: `false`
- empirical result: `null`
- all trading/execution authorizations: `false`

## Next gate

The exact human approval is now recorded separately from the immutable preregistration snapshot. It authorizes only the implementation/review phase for a future single `HeadBucket` Region-discovery attempt under an absolute EUR 0.10 ceiling. Approval alone does not install a workflow, does not create an execution release and does not execute AWS/S3.

Next: merge this approval record only after exact-head CI, byte-exact manifest validation and clean-context review. Then build a minimal direct-HTTPS HEAD implementation and manual-only workflow on a separate branch. Runtime execution must remain closed until a later separately reviewed single-use release.

Even a successful Region probe will not authorize a fresh LIST request. The larger 300-request inventory, all object-body access, market-data ingestion and all trading/capital stages remain unauthorized.
