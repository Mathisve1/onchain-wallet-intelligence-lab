# R6A approval status

Status: `HUMAN_APPROVED_IMPLEMENTATION_LANE_ONLY_NO_RUNTIME`

Human approval `APPROVE_HL_ARCHIVE_LEGACY_USER_KEY_LEXICAL_R6A_001` was received on 2026-08-09 and is bound to canonical R6A preregistration merge `870fdf3e10a761d6c4589d43def8e436f3a129b5`.

Exact approval text SHA-256: `b24c67f527a320e533408fd821d10b5e2ea01d020c837e87ae5e5bbd386c94ed`.

The approved future ceiling is one Requester Pays `GetObject` for exact object `node_fills/hourly/20250727/8.lz4`, with exact ETag/content-length/compressed-SHA/decompressed-byte-count checks, zero retries, lexical aggregate counting only, and EUR 0.10 one-time / EUR 0 monthly ceilings.

The only approved evidence outputs are aggregate counts for record count, `[string, object]` record count, leading-string count, length-42 count, `0x` + 40-hex count, lowercase `0x` + 40-hex count, and nonmatching count. No leading string, wallet address, hash of a leading string, distinct-address set, payload value, record payload, raw compressed object or decompressed body may be retained.

This approval opens only the implementation and later separately reviewed release path. It does **not** itself authorize a workflow dispatch, AWS/S3 request, object download, decompression, current lexical classification or AWS IAM mutation.

Current runtime authority remains zero. Separate implementation review, explicit least-privilege role/session-scope revalidation, separate single-use release and manual canonical-main dispatch gates remain mandatory.

Wallet reconstruction, entity clustering, copyability, P&L/alpha, market-data ingestion and all integration/paper/shadow/live/leverage/capital-allocation authorizations remain false.
