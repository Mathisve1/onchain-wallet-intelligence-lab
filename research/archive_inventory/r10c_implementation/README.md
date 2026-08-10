# R10C boundary-record correlation implementation

This directory contains the inert implementation of `HL-ARCHIVE-R10C-BOUNDARY-RECORD-CORRELATION-001`, bound to canonical preregistration merge `a812f7d5b67203c801f856c85b046af8e136c8f3` and canonical approval merge `00dbe69b5c17df8ef42a9b573589add290e559d8`.

The collector is capable of one exact future Requester Pays `GetObject` only after a separate reviewed execution release and canonical activation. It verifies the frozen object size, ETag and compressed SHA-256 before decompression. Processing is limited to raw `local_time`/`block_time` prefix buckets, event-pair shape, the fill object's integer `time` field, frozen BEFORE/INSIDE/AFTER path-hour partitioning, and aggregate record-level correlation counts.

No individual metadata value, fill timestamp, leading event string, wallet address or semantics, block-number value, raw record/event pair, or economic fill field is retained. Metadata timezone parsing/inference and datetime conversion are forbidden. R10 rule amendment/rerun, six-hour execution, historical expansion, wallet ranking, PnL/alpha, copyability, market-data/strategy work and all trading/capital authority remain closed.

The workflow file under `workflows/` is an uninstalled candidate only. It is not present in `.github/workflows` at this implementation stage and cannot create runtime authority. A separate release-candidate review is required before installation, followed by a separate canonical activation before any network request.
