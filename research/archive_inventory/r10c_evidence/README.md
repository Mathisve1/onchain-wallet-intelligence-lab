# R10C execution evidence

This directory records the exact single-use result of `HL-ARCHIVE-R10C-BOUNDARY-RECORD-CORRELATION-001`.

Canonical run `31410638224` completed successfully from main dispatch SHA `07f988af8db67addf5d551b5b402186c0abafadb`. The one authorized Requester Pays `GetObject` matched the frozen hour-9 object identity, ETag, size and compressed SHA-256. The retained evidence is aggregate boundary-correlation evidence only.

The exact object contains 36,029 block records and 223,950 fill timestamps. Exactly two fill timestamps are before the path-hour lower bound, 223,948 are inside it, and none are after it. Exactly one block record contains any before-hour fill. That same single record is the only `local_time=path-hour` / `block_time=previous-hour` raw-prefix record, and it contains both pre-hour fills. The other 36,028 records are `local_time=path-hour` / `block_time=path-hour` and contain all 223,948 inside-hour fills. The exact terminal conclusion is `EXACT_TWO_PRE_HOUR_FILLS_COLOCATE_WITH_SINGLE_PREVIOUS_BLOCK_TIME_RECORD`.

This evidence does not assign timezone semantics to `local_time` or `block_time`, does not establish which field defines the S3 path hour, does not prove the pattern generalizes beyond this immutable object, and does not justify a general 51 ms tolerance or any R10 rule amendment by itself. It does not authorize an R10 rerun or six-hour execution, wallet ranking, PnL/alpha, copyability, market-data, strategy or any trading/capital action.

The R10C execution release is consumed separately in `research/archive_inventory/r10c_runtime/R10C_EXECUTION_RELEASE_CONSUMPTION.json`; the original release snapshot remains immutable. Any additional network request requires a new preregistration, human approval and separate execution release.
