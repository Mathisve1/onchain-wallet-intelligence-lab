# R8 / R8A approval status

R8 status: **STATIC DESIGN CANONICAL** at `526f92cf3666c8bb616ecb61b6f9881387c1d7ed`.

R8A status: **HUMAN APPROVED — IMPLEMENTATION LANE ONLY — NO RUNTIME AUTHORITY**.

Human approval `APPROVE_HL_ARCHIVE_MODERN_WALLET_INDEX_BRIDGE_R8A_001` is bound to canonical R8 merge `526f92cf3666c8bb616ecb61b6f9881387c1d7ed` with exact approval-text SHA-256 `cb39246e2e5f345b14f87c15ac2c4d6aa993bcc9fbd28076f5f57eff94420e64`.

The approval permits implementation and a later separately reviewed single-use release path for exactly one modern `node_fills_by_block/hourly/20250727/8.lz4` object, with at most EUR 0.10 one-time cost, one Requester Pays GetObject and zero retries. It does **not** itself authorize workflow dispatch, AWS OIDC, GetObject, object-body download, decompression, address retention or wallet-index reconstruction.

Future retained record-derived output is limited to normalized lowercase `wallet_address`, `fill_count`, plus aggregate unique-wallet and valid-event-pair counts. Block timestamps/numbers, fill objects and all performance/economic payload values remain forbidden.

Historical multi-hour ingestion, performance-field value retention, public-API enrichment, entity clustering, wallet ranking, copyability analysis, PnL/alpha analysis, market-data ingestion, strategy inference and all trading/capital authority remain closed.
