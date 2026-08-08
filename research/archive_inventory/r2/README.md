# Correct-region node-data metadata canary R2

`HL-ARCHIVE-NODEDATA-METADATA-CANARY-R2-001` is the bounded successor to the attested Region probe R1.

## Why R2 exists

R0 executed seven bounded metadata LIST requests. The two `hyperliquid-archive` families succeeded under `us-east-1`, while all five `hl-mainnet-node-data` families returned `S3_AuthorizationHeaderMalformed`. Region probe R1 then independently observed `x-amz-bucket-region: ap-northeast-1` for `hl-mainnet-node-data` using exactly one authenticated HEAD request and no response body.

R2 tests only whether those same five node-data prefix families are first-page listable when the request is signed in the attested bucket Region `ap-northeast-1`.

## Canonical lineage

- R2 preregistration: `39b40cccc7e9a3fdbc439d06fb188e946d9da2aa`;
- R2 human approval: `151e08f54037ca7d3a0a9c17d3bdfb84d707a66e`;
- approval ID: `APPROVE_HL_ARCHIVE_NODEDATA_CANARY_R2_001`;
- approval text SHA-256: `728f4e21c045eb10e883bdf0f2e970686f0e6b6cc4dc67a4f214a882cf1831c6`;
- current implementation status: `IMPLEMENTATION_CANDIDATE_UNDER_REVIEW_NO_EXECUTION`;
- canonical implementation commit: not yet established;
- execution release: absent.

## Frozen R2 scope

- exact bucket: `hl-mainnet-node-data`;
- exact signing Region: `ap-northeast-1`;
- exact regional endpoint: `hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com`;
- exact prefixes: `node_fills_by_block/`, `node_fills/`, `node_trades/`, `explorer_blocks/`, `replica_cmds/`;
- exactly one first-page `ListObjectsV2` request per prefix;
- maximum 5 requests total;
- maximum 25 keys per request / 125 entries total;
- maximum 8 MiB aggregate LIST response bytes;
- maximum 120 seconds collector runtime;
- Requester Pays acknowledgement required;
- zero retries, zero pagination, zero continuation following, zero HTTP redirect following;
- continuation-token values are never retained;
- no GetObject, HeadObject, GetObjectAttributes, range GET, object-version listing, account-wide bucket listing, decompression or object-body download;
- no market-data ingestion, wallet analysis or trading/capital authorization.

## Implementation candidate

The candidate reuses the proven R0 standard-library SigV4 metadata transport but narrows it to the five approved node-data prefixes and signs directly for `ap-northeast-1`. It uses the regional virtual-hosted endpoint so the implementation does not depend on following a wrong-Region redirect.

The request counter is incremented before every network transport. The collector parses only the bounded `ListBucketResult` metadata required by the contract. Successful Requester Pays responses must explicitly report `x-amz-request-charged: requester`. A continuation token may only be represented as a boolean indicating presence; its value is neither retained nor followed.

The workflow is manual-only and exact-canonical-main-SHA-bound. Its future AWS session is further narrowed to `s3:ListBucket` on `hl-mainnet-node-data` for exactly the five approved prefix patterns with `s3:max-keys <= 25`. No persistent IAM expansion is required by this implementation candidate.

## Execution remains closed

Human scope/budget approval is not an execution release. During implementation review:

```text
EXPECTED_IMPLEMENTATION_COMMIT = PENDING_CANONICAL_IMPLEMENTATION_MERGE
R2_EXECUTION_RELEASE.json = absent
execution_authorized = false
paid_request_authorized = false
requester_pays_authorized = false
list_objects_v2_authorized = false
s3_requests_executed = 0
```

The workflow must prove the later exact canonical implementation SHA and a separately reviewed single-use release before it may request AWS OIDC credentials. Therefore PR/CI review cannot execute R2.

After a clean canonical implementation merge, a separate release must bind the actual merge SHA, this approval and every R2 limit. Only then may one manual canonical dispatch be considered. The first dispatch consumes that release regardless of PASS/FAIL; no rerun or second dispatch is implied.

## Cost/governance boundary

The approved EUR 0.10 one-time ceiling is a conservative governance ceiling, not a predicted AWS charge. Monthly budget remains EUR 0. The larger 300-request inventory remains separately unauthorized.

Official billing references retained for review:
- Amazon S3 pricing: https://aws.amazon.com/s3/pricing/
- Amazon S3 Requester Pays: https://docs.aws.amazon.com/AmazonS3/latest/userguide/RequesterPaysBuckets.html
