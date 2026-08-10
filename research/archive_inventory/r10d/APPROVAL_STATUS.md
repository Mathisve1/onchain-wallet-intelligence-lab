# R10D approval status

Status: `OWNER_APPROVED_IMPLEMENTATION_BUILT_AWAITING_SEPARATE_EXECUTION_RELEASE`

Pilot: `HL-ARCHIVE-R10D-RECORD-ANCHORED-MULTI-HOUR-FEATURE-REPAIR-001`

The exact owner approval is retained under `research/archive_inventory/r10d_approval/` and is bound to preregistration merge `b8e8d1080be27ff9db3fb639804b4040fdc7c2a0`. The implementation candidate is built, but this stage still performs no AWS/OIDC action, no Requester Pays request, no object download and no wallet-feature retention.

The approved repair removes the invalid universal rule that every fill timestamp must lie inside its source path hour. It replaces that rule with a fail-closed record-anchored check: every raw `local_time` prefix must match the source path hour; raw `block_time` may match only the path hour or the immediately previous hour; path-hour block records may contain only inside-hour fill timestamps; previous-hour block records may contain only immediately-previous-hour fill timestamps; next/other prefixes, after-hour fills, or any other mismatch fail closed. No numeric millisecond tolerance is authorized.

Execution is not authorized by the approval. A separate execution release and separate canonical activation remain mandatory.
