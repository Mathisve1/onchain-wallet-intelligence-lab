# HL-ARCHIVE-HOURLY-METADATA-INVENTORY-R3-001

R3 is a **static preregistration only**. It performs no AWS/S3 request, installs no executable workflow and authorizes no spend.

## Why R3 exists

Canonical R2 run `31280640653` proved that all five frozen `hl-mainnet-node-data` prefixes are first-page metadata-listable in `ap-northeast-1` with Requester Pays. The three fill/trade families that matter most for the first wallet-history feasibility gate exposed a stable-looking hourly path shape:

```text
node_fills_by_block/hourly/YYYYMMDD/H.lz4
node_fills/hourly/YYYYMMDD/H.lz4
node_trades/hourly/YYYYMMDD/H.lz4
```

R2 intentionally stopped after 25 keys per family and followed no continuation token. Every first page was truncated. R3 therefore asks a narrower question than the old 300-request parent inventory:

> Can we completely enumerate, or explicitly prove we were censored while enumerating, only these three hourly metadata keyspaces within a small fixed envelope?

This is the minimum useful next step before any object body is requested.

## Frozen scope

Only these exact prefixes are in R3:

1. `node_fills_by_block/hourly/`
2. `node_fills/hourly/`
3. `node_trades/hourly/`

`explorer_blocks/`, `replica_cmds/`, `market_data/` and `asset_ctxs/` remain outside this gate.

## Proposed listing envelope

```text
operation = ListObjectsV2
bucket = hl-mainnet-node-data
signing_region = ap-northeast-1
request_payer = requester
maximum_keys_per_request = 1000
maximum_pages_per_family = 16
maximum_total_list_requests = 48
maximum_total_entries = 48000
maximum_total_response_bytes = 33554432
maximum_runtime_seconds = 300
maximum_retries_per_request = 0
pagination = proposed, not authorized
redirect_following = false
StartAfter = forbidden
Delimiter = forbidden
```

The continuation token may only be used ephemerally for the immediately following page of the same frozen prefix. Token values are never retained in repository evidence. A repeated token, cross-family token use, request failure, response-cap breach, runtime breach or page-cap breach fails closed.

## Why 16 pages per family

Sixteen pages at 1,000 keys give a hard capacity of 16,000 keys per family. At an idealized one-object-per-hour cadence this represents roughly 666.7 days. As a sizing reference only, the elapsed hours from each R2 first returned hourly key to `2026-08-09T00:00:00Z` are approximately:

```text
node_fills_by_block = 9,062 hours
node_fills          = 10,570 hours
node_trades         = 12,110 hours
```

This is **not** a claim that the R2 first key is the true archive start or that every hour has exactly one object. It only explains why 16 pages per family is a reasonable bounded first attempt. If the archive contains more keys than expected, the correct result is `CENSORED_BY_LIMIT`, not an inferred complete history.

Compared with the older parent proposal, R3 reduces the maximum request count from 300 to 48 (84% lower), response cap from 256 MiB to 32 MiB, entry cap from 250,000 to 48,000, runtime from 900 to 300 seconds and retries from one to zero.

## Coverage and gap rules

A family is `COMPLETE` only if enumeration reaches a terminal page with `IsTruncated=false` before any cap is hit.

Only after complete enumeration may R3 parse the frozen hourly grammar and make key-gap statements. A `PROVEN_KEY_GAP` may be declared only for an internal UTC date strictly between the earliest and latest observed dates when one or more unique hours `0..23` are absent. Boundary dates are not automatically tested as full days.

For `node_fills` versus `node_fills_by_block`, R3 may compare the last legacy path-hour with the first block-batched path-hour. This is metadata coverage only; it does not prove body-schema equivalence or continuity of the underlying economic records.

## Cost gate

The existing frozen stress model is reused without changing pricing assumptions:

```text
48 / 1000 * USD 0.05 = USD 0.0024 request stress cost
33,554,432 / 1e9 * USD 0.50 = USD 0.016777216 transfer stress cost
stress total = USD 0.019177216
```

A proposed one-time human ceiling of EUR 0.10 is deliberately separate from the technical caps. It is **not approved** in this preregistration.

## Hard boundary

R3 currently has no implementation, no workflow, no release and no network authority. `GetObject`, object bodies, decompression, `explorer_blocks`, `replica_cmds`, the old 300-request inventory, market-data ingestion and every trading/capital stage remain forbidden.

After this preregistration is canonical, the next gate is a fresh exact human scope/budget approval bound to the canonical R3 preregistration commit. Only after that may a separate implementation/review lane begin.
