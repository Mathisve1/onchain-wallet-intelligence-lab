# Runbook — Hyperliquid Public Probe R1

## 1. Preconditions

1. The exact branch must descend from canonical `main` at `c08f7dc9419857770e53cd760f447394ecfa1bae`.
2. PR #1 and PR #2 remain closed and rejected pre-run.
3. The PR is draft.
4. `PROBE_CONTRACT.json`, collector, validator, tests and workflow are present on the same exact head.
5. `PENDING_EVIDENCE.json` and `ATTESTATION_TEMPLATE.json` contain no run IDs, hashes or observations.
6. All repository tests and `governance/validate_repository.py` pass before network access.

## 2. Execution

The dedicated workflow executes the exact head. No local operator supplies credentials or environment values.

Workflow sequence:

1. read-only checkout with no persisted credential;
2. pinned Python 3.12.13;
3. all tests, pending-evidence validation and repository validation;
4. bounded public probe;
5. independent output validation;
6. exact run-context and file-hash generation;
7. artifact upload even when validation fails;
8. final fail-closed enforcement.

## 3. Required workflow evidence

Retain:

- exact head SHA;
- workflow run ID and attempt;
- job ID and conclusion;
- job step conclusions;
- full decoded job log;
- artifact ID, name, expiry and provider digest;
- downloaded artifact ZIP SHA-256;
- contained file list, sizes and SHA-256;
- `probe-run-context.json`;
- `hl-public-probe-r1.json`;
- validation log and return code;
- `ARTIFACT_FILES.sha256`.

## 4. Independent inspection

The reviewer must independently:

1. verify artifact file hashes against `ARTIFACT_FILES.sha256`;
2. recompute the probe output SHA-256;
3. rerun `validate_evidence.py` against the downloaded output and exact reviewed source;
4. verify every probe ID/order, count and response class;
5. verify security assertions are exact and false;
6. verify total attempts and declared weight stay within ceilings;
7. verify terminal and archive-access states are derived;
8. verify no raw wallet values appear in output, logs or artifact;
9. verify no market result or authorization is present.

## 5. Attestation

Create a successor attestation only from independently verified evidence. It must bind exact commit, run, attempt, job, artifact ID/name/digest, artifact ZIP SHA-256, output SHA-256, terminal state, archive-access state, pass/fail counts, contract SHA-256 and collector bundle SHA-256.

Do not overwrite `ATTESTATION_TEMPLATE.json`. Add a distinct immutable evidence record under `research/wallet_copyability/probe_r1/evidence/`.

## 6. Decision rule

- `PUBLIC_PROBE_PASS` plus valid evidence and review: may propose archive inventory.
- `PUBLIC_PROBE_PARTIAL`: repair or explicitly narrow non-core scope, then rerun under a new exact head.
- `PUBLIC_PROBE_FAIL`: stop; no archive inventory.
- evidence/hash/identity mismatch: classify as integrity failure regardless of route observations.

`ROUTES_CONFIRMED_ACCESS_RESTRICTED` means route behavior is confirmed but archive listing/download access is not yet available. It cannot be promoted to an inventory PASS.

## 7. Merge rule

The implementation PR cannot merge merely because the probe workflow is green. Merge requires exact attestation, final-head CI, clean-context review and no unresolved thread. Merge remains administrative incorporation of a technical gate, not strategy validation.
