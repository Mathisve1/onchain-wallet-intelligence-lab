# R10B batch-metadata lexical diagnostic implementation

This directory implements the already owner-approved R10B diagnostic while deliberately retaining zero current runtime authority.

The collector may eventually make exactly one Requester Pays `s3:GetObject` request for the immutable hour-9 object, but only after a separate execution release and canonical activation. The implementation itself performs no network request and no IAM mutation.

The runtime algorithm is intentionally lexical rather than semantic. It validates each top-level block record, reads only the `local_time` and `block_time` strings, classifies their raw textual forms, compares raw date-hour prefixes, tracks exact-string equality, and retains only aggregate counts and string-length bounds. It does not parse or infer a timezone, convert metadata timestamps to datetimes, inspect the contents of `events`, retain block numbers, process fill timestamps, retain wallet addresses, process economic fill fields, or retain raw payloads.

The workflow in `workflows/` is a frozen candidate, not an installed GitHub Actions workflow. It is manual-only, uses the existing R10 role with a one-object `s3:GetObject` session policy, and remains unusable until a separate release snapshot and canonical activation exist.

No R10 rule amendment, R10 rerun, six-hour execution, historical expansion, wallet ranking, candidate shortlisting, PnL/alpha analysis, copyability analysis, market-data ingestion, strategy inference, paper/shadow/live trading, leverage, or capital allocation is authorized by this implementation.
