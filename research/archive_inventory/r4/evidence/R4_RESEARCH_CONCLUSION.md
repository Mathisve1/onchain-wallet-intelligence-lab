# R4 research conclusion

Run `31313913525` completed successfully under the single-use R4 activation on canonical `main` commit `85c7f145a564bdf177568bfc0c329a80c9a9c201`.

The exact legacy and modern boundary objects were both retrieved successfully with Requester Pays, exact ETag checks and exact Content-Length checks. Both compressed objects were recognized as LZ4 frames and decompressed within the preregistered limits.

The modern `node_fills_by_block/hourly/20250727/8.lz4` body was fully parseable under the preregistered UTF-8 NDJSON top-level-object parser: 4,345 records, maximum observed nesting depth 4 and 23 unique field paths were observed without retaining payload values.

The legacy `node_fills/hourly/20250727/8.lz4` body decompressed successfully to 62,169,139 bytes, but it was not parseable under that same preregistered parser. Its terminal bounded classification is `BODY_READABLE_SCHEMA_UNRESOLVED` with failure class `UTF8_NDJSON_OBJECT_SCHEMA_UNRESOLVED`.

Therefore R4 does **not** establish schema equivalence, schema incompatibility, or semantic equivalence between the legacy and modern families. The correct comparison class remains `SCHEMA_UNRESOLVED`, with technical result `TWO_OBJECT_BODY_FORMAT_UNRESOLVED`.

The R4 release is consumed and must not be rerun. A next investigation, if approved later, should be a new separately preregistered legacy-format fingerprint pilot that identifies only the minimum structural characteristics needed to recognize the post-LZ4 legacy serialization without retaining payload values or opening wallet reconstruction, clustering, copyability, P&L/alpha, market-data ingestion or trading authority.
