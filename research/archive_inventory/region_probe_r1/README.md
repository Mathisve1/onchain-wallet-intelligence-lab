# HL-ARCHIVE-REGION-PROBE-R1-001

This directory preregisters a minimal successor to the consumed R0 archive metadata canary. It exists only to resolve the exact Amazon S3 Region of `hl-mainnet-node-data` before any fresh LIST attempt is considered.

## Why this probe exists

Canonical R0 run `31260043109` used the same attested GitHub→AWS OIDC identity, SigV4 implementation and initial `us-east-1` signing for all seven frozen archive families. The two `hyperliquid-archive` families succeeded. All five `hl-mainnet-node-data` families failed with `S3_AuthorizationHeaderMalformed`. That pattern is strongly consistent with a signing-Region mismatch, but R0 deliberately retained neither raw error bodies nor bucket-Region headers, so the exact Region remains unknown.

The R0 release is consumed. This preregistration does not authorize a retry or a new paid request.

## Proposed one-request experiment

A future implementation may make exactly one direct HTTPS `HEAD /` request corresponding to Amazon S3 `HeadBucket` for bucket `hl-mainnet-node-data`.

AWS documents that `HeadBucket` has no response body and returns `x-amz-bucket-region` with the correct bucket location even when bucket access is not permitted. Requester Pays buckets do not allow anonymous requests, so any eventual probe must use the already-attested short-lived OIDC role; no static AWS credentials are permitted.

Official references:

- <https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadBucket.html>
- <https://docs.aws.amazon.com/AmazonS3/latest/userguide/RequesterPaysBuckets.html>

## Hard proposed envelope

```text
target bucket = hl-mainnet-node-data
operation = HeadBucket
HTTP method = HEAD
maximum S3 HTTP requests = 1
maximum runtime = 30 seconds
retries = 0
redirect following = false
request body = none
response body = none
ListObjectsV2 = false
GetObject = false
HeadObject = false
object-body download = false
pagination = false
decompression = false
market-data ingestion = false
```

The future request should include the requester-pays acknowledgment when signed. Whether the request returns authorization success is not the research objective. The probe succeeds only when exactly one S3 HTTP request was attempted and a syntactically valid non-empty `x-amz-bucket-region` value was retained. Missing/invalid Region is terminal failure; no redirect or retry may follow.

## Data minimization

Only the exact run identity, coarse/exact HTTP status, `x-amz-bucket-region`, optional `x-amz-request-charged`, and observation timestamp may be retained. Raw response headers, AWS request IDs, raw error material, credentials/tokens, object keys, object metadata and object bytes are forbidden.

## Cost and approval

A conservative **proposed** one-time ceiling of `EUR 0.10` is frozen solely as a human safety cap. It is not an estimate of expected cost, is not a monthly budget, and authorizes nothing. `maximum_one_time_budget_eur` remains `null` and `maximum_monthly_budget_eur` remains `0` until a separate exact approval is recorded.

The future approval must bind the exact canonical preregistration commit and the exact one-request contract. Only after that approval may an implementation/workflow be built and separately reviewed. Approval alone still does not execute the request.

## Downstream boundary

Even a successful Region result would not authorize a fresh LIST call. A new LIST canary would require its own bounded implementation/release decision. The larger 300-request inventory, object-body access, market-data ingestion, wallet analysis, entity clustering and all trading/capital stages remain closed.
