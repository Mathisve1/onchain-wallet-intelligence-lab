# R11 72-hour data workflow implementation

This directory records the post-preflight installation stage for the approved R11 three-day persistence pilot. The installed GitHub Actions data route is byte-identical to the frozen implementation candidate and remains inert until a separate execution release candidate and a separate canonical single-use activation are merged.

Canonical R11 STS preflight evidence is consumed successfully and proves the dedicated R11 role is assumeable from `main` while S3 was denied. This implementation stage itself performs no AWS OIDC, STS or S3 request, downloads no object bytes and creates no wallet-feature rows.

The approved future envelope remains exactly 72 `node_fills_by_block` hourly objects over 2025-07-28 through 2025-07-30 UTC, at most 72 Requester Pays GetObject requests, zero retries, €0.50 one-time / €0 monthly, 2,107,738,436 compressed bytes, 16 GiB decompressed bytes and 5,400 seconds. The persistent IAM allowlist remains the exact 72 objects; the future session policy can only intersect it through the three approved date prefixes.

Ranking, candidate shortlisting, PnL/alpha interpretation, copyability, public API enrichment, entity clustering, broader historical ingestion, market-data/strategy work and all trading, leverage and capital-allocation authority remain closed.
