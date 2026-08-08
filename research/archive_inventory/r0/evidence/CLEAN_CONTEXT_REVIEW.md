# R0 clean-context review — run 31260043109

## Identity and artifact

- canonical reviewed/dispatch/checkout commit: `bc8a47a1cdeb1163657ea243d6694286d6612bed`
- workflow run / job / attempt: `31260043109` / `93109335453` / `1`
- artifact: `9022511541` (`hyperliquid-archive-metadata-r0-31260043109-1`)
- GitHub provider digest and independently downloaded ZIP SHA-256 both equal `40b26e33833b54a872a75be066a87b7e57a0e2f3930adada76ca3829a1142c8e`
- internal artifact ledger matches all retained source files

## Runtime boundary

The run passed all pre-OIDC approval, release, exact-main-SHA and single-use gates. AWS OIDC role assumption succeeded. The collector made exactly seven S3 HTTP requests and used zero retries, zero pagination and zero redirect follows. It requested no object body and ingested no market data.

The single-use release is consumed by this dispatch regardless of the terminal failure. No rerun or second dispatch is authorized from the existing release.

## Observed result

Two requests succeeded, both on `hyperliquid-archive`:

- `market_data/`: 25 metadata entries, truncated, continuation token present but not followed, Requester Pays confirmed;
- `asset_ctxs/`: 25 metadata entries, truncated, continuation token present but not followed, Requester Pays confirmed.

Five requests failed, all on `hl-mainnet-node-data`, all with the coarse class `S3_AuthorizationHeaderMalformed`:

- `node_fills_by_block/`
- `node_fills/`
- `node_trades/`
- `explorer_blocks/`
- `replica_cmds/`

This pattern is strongly consistent with a signing-Region mismatch for `hl-mainnet-node-data`: the identical OIDC identity, SigV4 implementation and initial `us-east-1` signing worked for both `hyperliquid-archive` requests but not for any request to the other bucket. The exact Region remains unresolved because the preregistered R0 intentionally discarded raw error bodies and bucket-Region headers.

## Security / research interpretation

This is an informative partial failure, not a market or alpha result. It demonstrates authenticated Requester Pays metadata listing for `hyperliquid-archive`, and demonstrates that the current initial signing Region cannot be accepted for `hl-mainnet-node-data`. It does not authorize object retrieval, decompression, market-data ingestion, the larger 300-request inventory, wallet P&L, clustering or trading.

## Next gate

Before any new paid LIST attempt, preregister an exact bucket-Region discovery step. The preferred narrow mechanism is one `HeadBucket` request against `hl-mainnet-node-data`, retaining only `x-amz-bucket-region` plus coarse HTTP status. AWS documents that `HeadBucket` returns the correct bucket-location header even when the caller lacks bucket permissions. That future request is not authorized by this attestation and requires separate review/approval.
