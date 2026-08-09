# R5 research conclusion

Run `31321019885` completed successfully under the single-use R5 activation on canonical `main` commit `5eb6c8fad622832bc63a6503add8026be7ebd5a0`.

The exact legacy boundary object `node_fills/hourly/20250727/8.lz4` was retrieved with exactly one Requester Pays `GetObject`, zero retries and zero redirects. The observed content length, ETag, compressed SHA-256 and decompressed byte count matched the frozen R4/R5 expectations, and the object was successfully processed as an LZ4 frame within the approved caps.

R5 structurally parsed `162,815` nonempty UTF-8 line-delimited JSON records. Every observed record had a top-level JSON array of arity `2`, and every ordered element-type signature was `string,object`. The bounded empirical format classification is therefore `UTF8_NDJSON_PAIR_STRING_OBJECT`, with research conclusion `LEGACY_FORMAT_RESOLVED_AS_NDJSON_PAIR_STRING_OBJECT`.

Only structural aggregates were retained: field-path names, type sets, presence counts, array-shape counts and a structural-signature hash. No raw compressed object, decompressed payload, record payload, payload value, string value, numeric value or wallet address was retained.

R5 resolves the narrow serialization/container question left open by R4. It does **not** establish the semantic meaning of the leading string, does not label it as a wallet or user identifier, and does not establish schema or semantic equivalence with modern `node_fills_by_block`. Wallet reconstruction, entity clustering, copyability, P&L/alpha analysis, market-data ingestion and every trading/capital stage remain closed.

The R5 release is consumed and must not be rerun. A next investigation, if separately preregistered, should first use static provenance and official implementation/documentation evidence to determine the meaning of the leading string and the legacy writer semantics without issuing another paid archive request or opening wallet/trading authority.
