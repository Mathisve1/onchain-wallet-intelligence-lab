# Runbook — Hyperliquid Public Probe R1

## Preconditions

1. The branch descends from canonical main `c08f7dc9419857770e53cd760f447394ecfa1bae`.
2. PR #1, #2 and #3 remain closed as rejected pre-run attempts.
3. The active PR is draft, targets `main` and is hosted in this repository rather than a fork.
4. The exact contract, collector, independent validator, tests and workflow are on one head.
5. Pending evidence and attestation contain no run identities or result claims.
6. All tests and repository validation pass before network access.
7. The repository owner authorizes exactly that green head by adding this exact marker to the PR body:

```text
<!-- RUN_HL_PUBLIC_PROBE_R1:<40-character-lowercase-head-sha> -->
```

Any marker whose SHA differs from the current PR head is ineffective.

## Authorization lifecycle

1. Freeze and record the exact green source-head SHA.
2. Add the exact marker to the draft PR body through an owner-authenticated edit.
3. The workflow runs only for the `pull_request.edited` event and additionally requires owner actor, draft state, base `main`, a same-repository head and an exact marker/head match.
4. The workflow checks out the source head explicitly, compares `git rev-parse HEAD` with the event head and records reviewed and checked-out commits separately.
5. Remove the marker immediately after the intended run. The removal event cannot execute the probe because the authorization condition becomes false.
6. Any later rerun requires a new explicit owner decision and must be recorded as a distinct run; no old run may be silently replaced.

## Workflow sequence

1. verify the exact owner authorization context;
2. read-only exact-source-head checkout without persisted credentials;
3. pinned Python 3.12.13;
4. full tests, pending-evidence/attestation checks and repository validation;
5. bounded public probe;
6. independent output validation;
7. exact run-context and file-hash generation;
8. artifact upload even after failure;
9. final non-failing-core enforcement.

## Required workflow evidence

Retain exact head SHA, authorization actor/event evidence from the job log, workflow run/attempt, job ID/conclusion, step conclusions, decoded log, artifact ID/name/digest/expiry, downloaded ZIP SHA-256, contained file list/sizes/hashes, run context, probe output, validation log/return code and `ARTIFACT_FILES.sha256`.

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
