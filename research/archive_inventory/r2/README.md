# Correct-region node-data metadata canary R2

`HL-ARCHIVE-NODEDATA-METADATA-CANARY-R2-001` is a static, non-executing successor to the attested Region probe R1.

## Why R2 exists

R0 executed seven bounded metadata LIST requests. The two `hyperliquid-archive` families succeeded under `us-east-1`, while all five `hl-mainnet-node-data` families returned `S3_AuthorizationHeaderMalformed`. Region probe R1 then independently observed `x-amz-bucket-region: ap-northeast-1` for `hl-mainnet-node-data` using exactly one authenticated HEAD request and no response body.

R2 is designed only to test whether those same five node-data prefix families become listable when the request is signed in the attested bucket Region `ap-northeast-1`.

## Frozen R2 scope

- exact bucket: `hl-mainnet-node-data`;
- exact signing Region: `ap-northeast-1`;
- exact prefixes: `node_fills_by_block/`, `node_fills/`, `node_trades/`, `explorer_blocks/`, `replica_cmds/`;
- exactly one first-page `ListObjectsV2` request per prefix;
- maximum 5 requests total;
- maximum 25 keys per request / 125 entries total;
- Requester Pays acknowledgement required;
- zero retries, zero pagination, zero redirect following;
- no GetObject, HeadObject, GetObjectAttributes, range GET, decompression or object-body download;
- no market-data ingestion, wallet analysis or trading/capital authorization.

## Cost/governance boundary

The proposed EUR 0.10 one-time ceiling is deliberately conservative and is not a predicted AWS charge. The preregistration does not authorize any spend. A fresh exact-commit human approval is required before implementation, and implementation still cannot self-release execution.

Official billing references frozen for review:
- Amazon S3 pricing: https://aws.amazon.com/s3/pricing/
- Amazon S3 Requester Pays: https://docs.aws.amazon.com/AmazonS3/latest/userguide/RequesterPaysBuckets.html

## Current state

`PREREGISTERED_CORRECT_REGION_METADATA_CANARY_NOT_AUTHORIZED`

No R2 workflow, collector, AWS request, artifact or result exists in this preregistration phase.
