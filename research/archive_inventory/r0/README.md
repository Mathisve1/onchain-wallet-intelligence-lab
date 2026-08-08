# HL-ARCHIVE-METADATA-CANARY-R0-001

This directory contains the canonical bounded R0 implementation plus its separately reviewed single-use execution release candidate.

## Purpose

R0 verifies whether the seven frozen S3 prefix families can be listed through the attested GitHub→AWS OIDC role and captures only first-page object metadata. It does not retrieve object bodies and does not ingest market data.

The implementation is subordinate to:

- canonical approval `APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001`;
- reviewed approval commit `9af4b21863e47fb3bb2997ce77b9940eecf4597f`;
- canonical approval-record commit `62e0750382216afb5875ad52cb7443d43265e862`;
- approval timestamp `2026-08-08T10:10:00Z`;
- exact approval-text SHA-256 `d70008eac7521b324f61161bcc0075e28cc3a116dd30f0c52b48d8cf5eb6ed46`;
- canonical implementation merge `cd5c46b25502b671693dd5ebb091e7273399bccf`;
- the frozen seven-family `DATASET_REGISTER.json`;
- `METADATA_CANARY_R0_CONTRACT.json`;
- `R0_IMPLEMENTATION_CONTRACT.json`;
- separate runtime authority `R0_EXECUTION_RELEASE.json`.

The approval and preregistration files remain immutable historical snapshots. They are not rewritten to pretend that implementation or execution had already occurred when they were created.

## Hard runtime envelope

```text
operation = ListObjectsV2 only
request_payer = requester
dataset families = 7
maximum S3 HTTP requests = 7
maximum keys/request = 25
maximum retained entries = 175
maximum serialized S3 response bytes = 8,388,608
maximum collector runtime = 180 seconds
retries = 0
pagination = false
continuation-token following = false
HTTP redirects followed = false
one-time ceiling = EUR 1.00
monthly ceiling = EUR 0
```

The collector deliberately does **not** use the AWS CLI or an AWS S3 SDK for the seven LIST operations. It creates one SigV4-signed HTTPS `ListObjectsV2` request per family with Python's standard library and `http.client`, which does not automatically follow redirects.

The initial signing Region is `us-east-1`. If S3 returns a wrong-Region/redirect response, R0 records only a coarse failure class and does not retry or follow the redirect. A run may therefore fail without silently expanding the approved request count.

## SigV4 and Requester Pays

Every S3 request is HTTPS, uses the short-lived OIDC role credentials exported in-memory for the job, includes the temporary-session token and `x-amz-request-payer: requester`, and sends `list-type=2`, the exact approved prefix and `max-keys=25`. No continuation token is sent.

A success is accepted only when bucket, prefix, `MaxKeys`, `KeyCount`, XML structure and every returned key are internally consistent and the response confirms requester charging. Continuation-token values and bucket-Region headers are not retained.

## Deliberate non-capabilities

R0 does not authorize `GetObject`, `HeadObject`, `GetObjectAttributes`, range GET, `ListObjectVersions`, account-wide bucket listing, uploads, deletes, restores, decompression or object-body download. The OIDC session policy grants only exact-prefix `s3:ListBucket` with `s3:max-keys <= 25`.

Raw credentials, OIDC tokens and raw error bodies are never retained. The artifact contains only minimized metadata/evidence.

## Single-use execution release

The canonical implementation does not self-release execution. `R0_EXECUTION_RELEASE.json` is the sole runtime authority for this R0 attempt and binds exact implementation commit `cd5c46b25502b671693dd5ebb091e7273399bccf` plus the existing approved caps.

The release's consumption window begins at the immutable human-approval timestamp `2026-08-08T10:10:00Z`, **not** at release authoring or merge time. Before AWS OIDC the workflow verifies that `github.run_attempt == 1` and that the current run is the only R0 `workflow_dispatch` on `main` created since that approval timestamp. The history check is read-only and itself performs no AWS call.

Consequently the first dispatch consumes this release regardless of whether the eventual R0 result is PASS or FAIL. “Re-run jobs” or a second manual dispatch cannot reuse it; a fresh separately reviewed release is required before any second paid attempt.

## Execution lifecycle

The workflow is manual-only and requires the supplied `reviewed_commit` to equal both the dispatch SHA and checked-out canonical `main` SHA. No R0 network call can be triggered automatically by a pull request or push.

This release candidate must pass exact-head CI, manifest validation, release/governance tests and clean-context review, then merge to canonical `main`. Only then may one manual R0 dispatch occur. A successful R0 does not authorize the larger 300-request inventory, object-body access, market-data ingestion, wallet analysis or any trading/capital stage.
