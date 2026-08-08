# HL-ARCHIVE-METADATA-CANARY-R0-001

This directory contains the bounded implementation candidate for the first authenticated Hyperliquid archive metadata canary.

## Purpose

R0 verifies whether the seven frozen S3 prefix families can be listed through the attested GitHub→AWS OIDC role and captures only first-page object metadata. It does not retrieve object bodies and does not ingest market data.

The implementation is subordinate to:

- canonical user approval `APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001`;
- reviewed approval commit `9af4b21863e47fb3bb2997ce77b9940eecf4597f`;
- canonical approval-record commit `62e0750382216afb5875ad52cb7443d43265e862`;
- exact approval-text SHA-256 `d70008eac7521b324f61161bcc0075e28cc3a116dd30f0c52b48d8cf5eb6ed46`;
- the frozen seven-family `DATASET_REGISTER.json`;
- `METADATA_CANARY_R0_CONTRACT.json`;
- `R0_IMPLEMENTATION_CONTRACT.json`;
- a **separate post-merge** `R0_EXECUTION_RELEASE.json`, which is intentionally absent from this implementation candidate.

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
```

The collector deliberately does **not** use the AWS CLI or an AWS S3 SDK for the seven LIST operations. Botocore contains S3 region-redirect handling, which could turn a single CLI invocation into more than one HTTP request when the bucket Region differs from the configured Region. R0 instead creates one SigV4-signed HTTPS `ListObjectsV2` request per family with Python's standard library and uses `http.client`, which does not automatically follow redirects.

The initial signing Region is `us-east-1`. If S3 returns a wrong-Region/redirect response, R0 records only a coarse failure class and does **not** retry or follow the redirect. That run may therefore fail, but it cannot spend the approved request envelope by silently retrying.

## SigV4 and Requester Pays

Every S3 request:

- is HTTPS;
- is SigV4 signed with the short-lived OIDC role credentials already exported by `configure-aws-credentials`;
- signs the empty GET payload hash;
- includes `x-amz-security-token` for temporary credentials;
- includes `x-amz-request-payer: requester`;
- sends query parameters `list-type=2`, exact approved `prefix`, and `max-keys=25`;
- never includes a continuation token.

A success is accepted only when the returned bucket, prefix, `MaxKeys`, `KeyCount`, XML structure and every returned key are internally consistent, and the response includes `x-amz-request-charged: requester`.

## Deliberate non-capabilities

R0 cannot call `GetObject`, `HeadObject`, `GetObjectAttributes`, range GET, `ListObjectVersions`, `ListBuckets`, uploads, deletes, restores or decompression. The OIDC session policy is narrower than the persistent IAM role and grants only `s3:ListBucket` for the seven frozen prefixes with `s3:max-keys <= 25`.

The collector never retains continuation-token values or bucket-Region headers. It records only whether a continuation token was present. Raw errors are not retained; errors are reduced to a coarse status class. Raw credentials, OIDC tokens and STS identity payloads are never written to the artifact.

## Post-merge execution release

Merging the implementation does **not** itself make R0 executable. The workflow requires `research/archive_inventory/r0/R0_EXECUTION_RELEASE.json` to exist before OIDC. That file can only be created in a separate post-merge release PR after the exact implementation merge commit is known.

The release must be `RELEASED_FOR_EXACTLY_ONE_CANONICAL_R0_RUN`, bind the implementation commit and exact approved caps, and contain a release timestamp. Before AWS authentication the workflow also uses its read-only GitHub Actions permission to verify that:

1. `github.run_attempt == 1`; and
2. the current run is the **only** R0 `workflow_dispatch` on `main` created since that release timestamp.

Therefore a GitHub “Re-run jobs” attempt or a second manual dispatch cannot reuse the same execution release. A failed/partial first dispatch requires a fresh separately reviewed release before any second paid R0 attempt.

## Execution lifecycle

The workflow is manual-only and requires the supplied `reviewed_commit` to equal both the GitHub dispatch SHA and the checked-out canonical `main` SHA. No R0 network call can be triggered automatically by a pull request or push.

This implementation candidate must pass static/unit/manifest/governance review and be merged to canonical `main`. A separate execution-release PR must then pass CI/review and merge. Only after both gates are canonical may one manually dispatched R0 run occur. A successful R0 never authorizes the larger 300-request inventory, object-body access, wallet analysis or any trading stage.
