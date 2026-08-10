# R10B execution evidence

This directory records the exact single-use result of `HL-ARCHIVE-R10B-BATCH-METADATA-LEXICAL-DIAGNOSTIC-001`.

Canonical run `31395720147` completed successfully from main dispatch SHA `de5f6ff5aabcb40650fa8c1f9b94dd305e9ff556`. The one authorized Requester Pays `GetObject` matched the frozen hour-9 object identity, ETag, size and compressed SHA-256. The retained evidence is aggregate lexical metadata only.

The observed object contains 36,029 block records. Every `local_time` and `block_time` string matches the preregistered `ISO8601_NAIVE_FRACTION` lexical class. All 36,029 `local_time` strings match the raw `2025-07-27T09:` prefix. For `block_time`, 36,028 match `2025-07-27T09:` and exactly one matches `2025-07-27T08:`. `local_time` and `block_time` differ as raw strings on all 36,029 records. Therefore the exact terminal research conclusion is `BATCH_METADATA_LEXICALLY_CROSSES_PATH_HOUR`.

This evidence does not assign timezone semantics to either metadata field, does not establish which field defines the S3 path hour, and does not connect the one previous-hour `block_time` record to the two pre-hour fill timestamps observed by R10A. It does not justify a 51 ms tolerance, amend the R10 alignment rule, authorize an R10 rerun or six-hour run, or open wallet ranking, PnL/alpha, copyability, market-data, strategy or trading/capital authority.

The R10B execution release is consumed separately in `research/archive_inventory/r10b_runtime/R10B_EXECUTION_RELEASE_CONSUMPTION.json`; the original release snapshot remains immutable. Any additional network request requires a new preregistration, human approval and separate execution release.
