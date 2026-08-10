# R10A — timestamp-partition diagnostic

R10A is the minimal successor diagnostic to the canonically consumed R10 six-hour run. R10 did not produce a six-hour wallet feature dataset: it retrieved the exact hour-9 object once and then stopped fail-closed because at least one fill `time` fell outside the preregistered source path hour.

R10A does not assume what that mismatch means. In particular, it does not infer whether the object is partitioned by `block_time`, whether `fill.time` can legitimately spill across path-hour boundaries, whether `local_time` has an implied timezone, or whether the mismatch is small or systematic.

The proposed future diagnostic therefore rereads only the exact hour-9 object and retains aggregate timestamp alignment evidence: min/max timestamps, before/inside/after counts, bounded hour-offset histograms, explicit-timezone parse counts, and bounded fill-minus-block-time delta statistics. It retains no wallet addresses, no individual timestamps, no economic fill fields and no raw object/block/event/fill payloads.

The existing dedicated R10 IAM role would be reused without mutation, with a future session policy narrowed to the one exact object. R10A currently has zero runtime authority and has made zero new network requests. Human approval, a separate implementation, a separate execution release and canonical activation are all required before any diagnostic request.

A successful R10A result may inform a later human-reviewed amendment or successor preregistration. It cannot automatically repair R10, rerun R10, open a six-hour ingestion, rank wallets, interpret PnL/alpha, assess copyability, or authorize trading.
