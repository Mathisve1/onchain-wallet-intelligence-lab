# R10D implementation

This directory implements the owner-approved `HL-ARCHIVE-R10D-RECORD-ANCHORED-MULTI-HOUR-FEATURE-REPAIR-001` repair as an inert candidate only.

The implementation preserves the original R10 six-object request order, byte/request/runtime caps, wallet-feature reducer, exact-decimal aggregation, duplicate-wallet+TID fail-closed behavior and no-ranking/no-trading boundaries. The only substantive research repair is the path-hour alignment rule: metadata values are compared by raw lexical prefixes only, every `local_time` must match the source path hour, `block_time` may match only that path hour or the immediately previous hour, path-hour block records may contain only inside-hour fills, and previous-hour block records may contain only fills from the immediately previous epoch hour. No numeric millisecond tolerance exists.

Hour 9 is additionally bound to the exact R10C aggregate fixture and preknown compressed SHA-256. Hours 10–14 have no predeclared boundary pattern; they must independently satisfy the same fail-closed rule.

The workflow in `workflows/` is frozen as an uninstalled candidate. This implementation performs no AWS/OIDC operation, no Requester Pays request, no object download, no wallet-feature retention and no trading action. A separate execution release and separate canonical activation remain mandatory.
