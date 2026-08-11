# R11A identity-and-boundary diagnostic

This directory contains the frozen offline scientific contract for the R11A identity-and-boundary diagnostic. Its current status is `PREREGISTERED_NO_EXECUTION`.

- `R11A_IDENTITY_DECISION_DOSSIER.json` freezes the four-layer identity model and rejects the legacy wallet-plus-`tid` key as canonical identity.
- `R11A_IDENTITY_DECISION_DOSSIER.md` explains the decision and its limits.
- `R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_PREREGISTRATION.json` preregisters the exact experiment over the existing 72 R11 objects, the nine-class diagnostic taxonomy, complete repeat-occurrence provenance, conservation outputs, strict unsigned-50-bit `tid` boundary and frozen resource ceilings.

The exact taxonomy is `TID_SCOPE_FALSE_POSITIVE`, `EXPECTED_COUNTERPARTY_PAIR`, `EXACT_BLOCK_REPLAY_ACROSS_OBJECTS`, `EXACT_USER_FILL_REOBSERVATION_FROM_PROVEN_BLOCK_REPLAY`, `CONFLICTING_BLOCK_REPLAY`, `CONFLICTING_USER_FILL`, `INTRA_BLOCK_REPEAT`, `TID_SCHEMA_VIOLATION` and `UNCLASSIFIABLE`. Exact user-fill reobservation is valid only through a retained proof link to exact block replay; payload equality alone is insufficient.

The preregistration is deliberately non-executable. Its ceilings are frozen at 72 one-shot `GetObject` requests, zero retries, 2,107,738,436 compressed bytes, 21,079,958,490 decompressed bytes across exactly two local passes, 5,368,709,120 ephemeral workspace bytes, 134,217,728 retained-artifact bytes, 21,600 runtime seconds and EUR 0.50 one-time / EUR 0 monthly budget caps. These are preregistered maximums, not runtime authority.

Canonical R11 evidence-closure PR 139 is bound to merge commit `f7aa612d2a5638cce0fd197f57efea4b787f87f1`. That binding is a prerequisite, not approval. Owner approval remains absent; exact implementation hashes and the role reuse/successor decision must still be bound by the later approval candidate. No release, installed workflow, dispatch, AWS/S3 request, wallet feature, deduplication, repair or R12 promotion is created here.
