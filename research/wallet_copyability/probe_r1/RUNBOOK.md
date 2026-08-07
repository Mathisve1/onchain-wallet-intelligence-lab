# Runbook — Hyperliquid Public Probe R1

## Phase A — implementation review

1. Confirm the branch descends from canonical `main`.
2. Confirm the PR contains implementation, preregistration, pending templates
   and negative lineage only.
3. Confirm there is no final attestation, workflow-run directory or archive
   inventory.
4. Run all unit, mutation, static-capability and repository-manifest checks.
5. Complete a clean-context code and governance review.
6. Merge the implementation to `main` only after all gates pass.

## Phase B — canonical manual run

1. Read the exact post-merge `main` commit SHA.
2. Dispatch `Hyperliquid Public Probe R1` manually.
3. Enter that exact 40-character SHA in `reviewed_commit`.
4. The workflow checks out the supplied SHA and compares it with
   `git rev-parse HEAD`.
5. Static safety, pending-template and repository gates must pass before any
   public request.
6. Execute the bounded 16-route probe.
7. Validate output independently before terminal enforcement.
8. Upload the immutable artifact even when later validation fails.

## Required workflow evidence

Retain:

- exact reviewed and checked-out commit;
- workflow name, run ID and attempt;
- job ID and conclusion;
- individual step conclusions;
- artifact ID, name, provider digest and expiry;
- independently downloaded artifact ZIP SHA-256;
- artifact-contained file names, sizes and SHA-256 values;
- run context;
- exact probe output;
- validation log and return code;
- `ARTIFACT_FILES.sha256`.

## Phase C — independent inspection

The reviewer must:

1. recompute the artifact ZIP hash;
2. recompute every internal file hash;
3. rerun `validate_evidence.py` on the exact output;
4. verify contract and collector-bundle hashes;
5. derive endpoint, terminal and archive-access states independently;
6. verify exact probe order, attempts and weight;
7. inspect the artifact for raw values, credentials and unauthorized fields;
8. confirm all market and execution authorizations remain closed.

## Phase D — separate evidence PR

Do not modify `ATTESTATION_TEMPLATE.json`. Add a new immutable attestation and
retained evidence under a separate branch created from the canonical main-run
commit. Bind every exact identity listed above.

A passed technical run may set only:

```text
PUBLIC_PROBE_PASS
PUBLIC_PROBE_PARTIAL
PUBLIC_PROBE_FAIL
```

and one independent archive-access class. It cannot create a wallet result,
market release or trading authorization.

## Decision

- exact PASS plus evidence and clean review: an archive-inventory proposal may
  be drafted separately;
- PARTIAL: repair or make an explicit reviewed scope decision, then rerun;
- FAIL: stop and repair;
- any identity or hash mismatch: integrity failure regardless of route output.
