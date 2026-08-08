# HL-ARCHIVE-METADATA-CANARY-R0-001

This directory contains the bounded implementation candidate for the first authenticated Hyperliquid archive metadata canary.

## Purpose

R0 verifies whether the seven frozen S3 prefix families can be listed through the attested GitHub→AWS OIDC role and captures only first-page object metadata. It does not retrieve object bodies and does not ingest market data.

The implementation is subordinate to:

- canonical user approval `APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001`;
- reviewed approval commit `9af4b21863e47fb3bb2997ce77b9940eecf4597f`;
- exact approval-text SHA-256 `d70008eac7521b324f61161bcc0075e28cc3a116dd30f0c52b48d8cf5eb6ed46`;
- the frozen seven-family `DATASET_REGISTER.json`;
- `METADATA_CANARY_R0_CONTRACT.json`;
- `R0_IMPLEMENTATION_CONTRACT.json`.

## Hard runtime envelope

```text
operation = ListObjectsV2 only
request_payer = requester
dataset families = 7
maximum explicit LIST commands = 7
maximum keys/request = 25
maximum retained entries = 175
maximum serialized CLI response bytes = 8,388,608
maximum collector runtime = 180 seconds
AWS_MAX_ATTEMPTS = 1
retries = 0
pagination = false
continuation-token following = false
```

`AWS_MAX_ATTEMPTS=1` is required because AWS defines max attempts as total attempts including the initial request; a value of one disables SDK/CLI retries. The workflow additionally passes `--no-paginate` to each `list-objects-v2` command.

## Deliberate non-capabilities

R0 cannot call `GetObject`, `HeadObject`, `GetObjectAttributes`, range GET, `ListObjectVersions`, `ListBuckets`, uploads, deletes, restores or decompression. The OIDC session policy is narrower than the persistent IAM role and grants only `s3:ListBucket` for the seven frozen prefixes with `s3:max-keys <= 25`.

The collector never retains continuation-token values. It records only whether one was present. Raw AWS stderr is not retained; errors are reduced to a coarse status class. Raw credentials, OIDC tokens and STS identity payloads are never written to the artifact.

## Execution lifecycle

The workflow is manual-only and requires the supplied `reviewed_commit` to equal both the GitHub dispatch SHA and the checked-out canonical `main` SHA. No R0 network call should be made from a pull-request branch.

This implementation candidate must pass static/unit/manifest/governance review and be merged to canonical `main` before one manually dispatched R0 run is permitted. A successful R0 never authorizes the larger 300-request inventory, object-body access, wallet analysis or any trading stage.
