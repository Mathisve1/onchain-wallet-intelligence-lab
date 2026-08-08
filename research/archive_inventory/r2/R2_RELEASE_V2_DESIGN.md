# R2 successor release hardening design

This document is non-executing design only. It does not authorize AWS/S3 execution.

## Required changes before a successor release may be reviewed

- Preserve canonical implementation `142ce50be20507761c4cce37b325ac69d57f8b25` unchanged.
- Preserve target bucket `hl-mainnet-node-data`, signing Region `ap-northeast-1`, the five frozen prefixes and all existing request/entry/byte/runtime caps unchanged.
- Preserve zero retries, zero pagination, zero redirect following, no object-body access, no decompression, no market-data ingestion and all trading/capital authorizations false.
- Treat the first release as consumed despite zero AWS/S3 execution.
- Create a distinct successor release identifier; never mutate the old release record into an unused state.
- Bind the successor release to the same human-approved scope/budget because no approved S3 request budget was consumed by the pre-OIDC failure.
- Require a fresh reviewed successor release before another dispatch; no `Re-run` of the failed run is authorized.

## Identity gate hardening

Before AWS OIDC, collect the non-secret values:

- raw reviewed commit input;
- `github.ref`;
- `github.sha`;
- checked-out `git rev-parse HEAD`.

Then fail with a distinct error message and exit code for each invariant instead of relying on silent `test` commands. A proposed mapping is:

- 41: reviewed commit is not exactly 40 lowercase hexadecimal characters;
- 42: dispatch ref is not `refs/heads/main`;
- 43: reviewed commit differs from dispatch SHA;
- 44: checked-out HEAD differs from reviewed commit.

The workflow must still stop before Python setup, release validation and AWS OIDC on any identity mismatch.

## Review gate

A successor release remains non-executable until its exact-head Research CI, repository manifest validation, dedicated R2 validation and clean-context review are green and the successor release is canonically merged to `main`.
