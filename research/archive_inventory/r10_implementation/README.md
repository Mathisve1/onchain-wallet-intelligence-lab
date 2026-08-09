# R10 implementation candidate

This directory implements the owner-approved mechanics for `HL-ARCHIVE-POST-BOUNDARY-MULTI-HOUR-FEATURE-R10-001` while remaining non-executing.

## What is implemented

- exact six-object identity and request caps;
- dedicated-role trust and permission policies;
- a bounded SigV4 Requester Pays collector;
- strict LZ4/UTF-8/JSON parsing;
- source-path-hour timestamp validation;
- cross-object per-wallet aggregation with `active_hour_count`;
- fail-closed duplicate `(wallet_address, tid)` diagnostics with no blind deduplication;
- deterministic sorted feature output with exact decimal arithmetic;
- minimized per-hour run summaries and no raw-fill retention;
- byte-frozen STS-only preflight and six-object data-workflow candidates.

The workflow candidates deliberately remain under `r10_implementation/workflows/` and are **not** installed in `.github/workflows/` at this stage. This prevents a GitHub Actions OIDC route from existing before the owner-authorized dedicated AWS role is created and independently attested.

## Current authority

No AWS IAM mutation, STS request, OIDC assumption, S3 request, object download or empirical feature generation has been performed by this implementation branch. Wallet ranking, candidate shortlisting, PnL/alpha interpretation, copyability, market-data/strategy inference and all trading/capital authority remain closed.

## Next gate after canonical merge

The human operator must create exactly `onchain-wallet-intelligence-hl-archive-multihour-r10` from the canonical `R10_OIDC_TRUST_POLICY.json` and `R10_PERMISSION_POLICY.json`, without modifying any existing R4 role. Follow `R10_ROLE_CREATION_RUNBOOK.md` and return the completed `R10_OPERATOR_ATTESTATION_TEMPLATE.txt`.

After that attestation is reviewed and merged, the next repository stage may install only the STS-preflight workflow candidate and create a separate single-use STS-only release. That preflight explicitly denies all S3 operations. Only a later successful preflight and separate execution release/canonical activation may open the approved six-object archive run.
