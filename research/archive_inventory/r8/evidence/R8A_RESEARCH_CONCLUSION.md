# R8A research conclusion

`MODERN_WALLET_INDEX_BRIDGE_COMPLETE`

The exact modern boundary object `node_fills_by_block/hourly/20250727/8.lz4` was retrieved once by canonical run `31333421763` with zero retries and zero redirects. Frozen integrity checks matched exactly: 1,517,603 compressed bytes, SHA-256 `928e1cd6bd7d69ad7243c263bacee48e53e4762ae9e99ef75f45007f6c0e6105`, 7,380,378 decompressed bytes, and 4,345 top-level block records.

The modern block stream contained **17,516** valid `[address, fill_object]` event pairs and reduced deterministically to **887** unique lowercase wallet addresses with only `wallet_address` and `fill_count` retained. No fill payload, performance field, block number, block timestamp, market data, PnL, ranking, clustering or copyability output was retained.

For the already-retained same-hour legacy R7 wallet index, the aggregate bridge comparison found **688** overlapping wallet addresses, **199** modern-only wallet addresses and **3949** legacy-only wallet addresses. The modern address set being a subset of the legacy set is recorded as `false`. These are address/count aggregate facts only: this does not prove exact fill identity, temporal subset semantics, schema equivalence or semantic equivalence between the two archive formats.

The single-use R8A release is consumed by run `31333421763`. **No second R8A dispatch or rerun is authorized.** Any next step that retains performance/economic fill fields, scans more hours, enriches wallets, ranks wallets, estimates PnL/alpha or studies copyability requires a new separately preregistered and human-approved scope.
