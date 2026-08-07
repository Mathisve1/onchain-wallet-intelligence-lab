# Runbook — Hyperliquid Public Probe R1

## Preconditions

1. The branch descends from canonical main `c08f7dc9419857770e53cd760f447394ecfa1bae`.
2. PR #1, #2 and #3 remain closed as rejected pre-run attempts.
3. The active PR is draft.
4. The exact contract, collector, independent validator, tests and workflow are on one head.
5. Pending evidence and attestation contain no run identities or result claims.
6. All tests and repository validation pass before network access.

## Workflow sequence

1. read-only checkout without persisted credential;
2. pinned Python 3.12.13;
3. full tests, pending-evidence/attestation checks and repository validation;
4. bounded public probe;
5. independent output validation;
6. exact run-context and file-hash generation;
7. artifact upload even after failure;
8. final non-failing-core enforcement.

## Required workflow evidence

Retain exact head SHA, workflow run/attempt, job ID/conclusion, step conclusions, decoded log, artifact ID/name/digest/expiry, downloaded ZIP SHA-256, contained file list/sizes/hashes, run context, probe output, validation log/return code and `ARTIFACT_FILES.sha256`.

## Independent inspection

The reviewer recomputes artifact file hashes and output SHA-256, reruns `validate_evidence.py`, verifies exact probe order and response classes, confirms security flags are exact and false, confirms total attempts/weight remain bounded, derives terminal/archive states independently, and checks that no raw wallet values or market claims appear.

## Attestation

Do not overwrite the template. Add a new immutable record under `research/wallet_copyability/probe_r1/evidence/` binding commit, run, attempt, job, artifact, provider digest, ZIP hash, output hash, terminal/archive status, counts, contract hash and collector hash.

## Decision

- PASS plus exact evidence and review: archive-inventory proposal may be drafted.
- PARTIAL: repair or separately narrow scope, then rerun.
- FAIL: stop; no inventory.
- any identity/hash mismatch: integrity failure regardless of endpoint observations.

`ROUTES_CONFIRMED_ACCESS_RESTRICTED` means the routes are technically recognized but archive listing/download access is not established.

## Merge

A green workflow alone is insufficient. Merge requires exact attestation, final-head CI, clean-context review and no unresolved finding. Merge remains administrative incorporation of a technical gate, not strategy validation.
