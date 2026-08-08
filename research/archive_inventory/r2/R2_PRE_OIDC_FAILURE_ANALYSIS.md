# R2 pre-OIDC dispatch failure analysis

## Status

The first canonical R2 execution attempt failed closed before AWS OIDC and before the R2 collector executed.

Observed from the GitHub Actions job UI supplied by the operator:

- `EXACT_REVIEWED_COMMIT=0dd6f32ab3a202b0c58f37821d1038ac917d84ce`
- `DISPATCH_REF=refs/heads/main`
- `DISPATCH_SHA=0dd6f32ab3a202b0c58f37821d1038ac917d84ce`
- step `Verify canonical main dispatch and exact reviewed identity` returned exit code 1
- all steps from `Set up pinned Python` through `Execute bounded five-prefix R2 collector` were skipped
- `Finalize minimized R2 evidence` and `Upload minimized R2 evidence` completed
- `Enforce exact successful R2 result` failed as expected for non-execution

## Proven boundary

Because the AWS role-assumption step and collector step were both skipped, this attempt executed:

- zero AWS OIDC role assumptions for R2;
- zero S3 HTTP requests;
- zero `ListObjectsV2` requests;
- zero metadata-entry observations;
- zero Requester Pays S3 requests;
- no object-body access;
- no market-data ingestion.

The prior single-use release must nevertheless be treated as consumed conservatively because a workflow dispatch occurred and the release explicitly prohibited reruns.

## Identity-gate diagnosis

The visible values prove that the expected reviewed commit, dispatch ref and dispatch SHA were intended to be canonical `main` and the same 40-character commit SHA. The prior gate used silent `set -e` tests, so the job log does not identify which individual assertion failed or expose the actual checked-out `HEAD` value.

A successor release must therefore not reuse the old dispatch. It must add explicit pre-OIDC diagnostics for:

1. reviewed-commit format;
2. dispatch ref identity;
3. reviewed-commit versus dispatch SHA;
4. checked-out `HEAD` versus reviewed commit.

All diagnostics must remain non-secret and execute before AWS OIDC. The successor release must remain within the unchanged five-prefix / five-request / EUR 0.10 approved envelope and must not broaden any S3, object, market-data, trading or capital authorization.
