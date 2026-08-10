# R10D approval status

Status: `AWAITING_SEPARATE_HUMAN_APPROVAL`

Pilot: `HL-ARCHIVE-R10D-RECORD-ANCHORED-MULTI-HOUR-FEATURE-REPAIR-001`

R10D is a static preregistration only. It performs no AWS/OIDC action, no Requester Pays request, no object download, no decompression, no wallet-feature processing and no trading action.

The proposed repair removes the invalid universal rule that every fill timestamp must lie inside its source path hour. It replaces that rule with a fail-closed record-anchored check: every raw `local_time` prefix must match the source path hour; raw `block_time` may match only the path hour or the immediately previous hour; path-hour block records may contain only inside-hour fill timestamps; previous-hour block records may contain only immediately-previous-hour fill timestamps; next/other prefixes, after-hour fills, or any other mismatch fail closed. No numeric millisecond tolerance is authorized.

Human approval is required before implementation. Approval still does not authorize execution; a separate execution release and separate canonical activation remain mandatory.
