# Project State

Verified: 2026-08-07 against exact GitHub workflow, artifact and retained-evidence identities.

## Current status

| Dimension | State |
|---|---|
| program | `ONCHAIN-WALLET-INTELLIGENCE` |
| current study | `WALLET-COPYABILITY-STUDY-001` |
| research status | `REQUIRES_FURTHER_TESTING` |
| lifecycle stage | `PRE_ARCHIVE_INVENTORY` |
| experiment status | `PUBLIC_TECHNICAL_PROBE_ATTESTED_ARCHIVE_ACCESS_RESTRICTED` |
| empirical result | `null` |
| integration authorized | `false` |
| paper authorized | `false` |
| shadow authorized | `false` |
| live authorized | `false` |
| leverage authorized | `false` |
| capital allocation authorized | `false` |

## HL-PUBLIC-PROBE-001R1 canonical technical evidence

The bounded read-only technical probe is accepted only as route-level evidence.
It is not a wallet study, market backtest, alpha result or execution authorization.

| Evidence | Exact identity |
|---|---|
| executed PR head | `facd8b26778eb483a4917fc4418069c35b981e8b` |
| checked-out GitHub PR merge tree | `3de0cb4ee963357fa6fae4c215643cc2ce22acdc` |
| head/merge-tree file difference | `0` |
| Research CI run/job | `31179660399` / `92869634707` — `success` |
| public-probe run/job | `31179660372` / `92869634761` — `success` |
| artifact | `8994227729` / `hyperliquid-public-probe-r1-31179660372-1` |
| provider digest and downloaded ZIP SHA-256 | `12d98fd48ac0c9503e213efa8f93ae2f777e00ca11cfb989a4e5a3100ad8ee11` |
| probe-output SHA-256 | `67aa8f6ef1b4399573c775eeb03c0c32bed12def7494c8461893fcab36247d12` |
| contract SHA-256 | `d89f0400756ab6a4a566404290e33cf68a1a75b8fcb26b9832bc0c8d3041546a` |
| collector-bundle SHA-256 | `b7dc72c46e408ac4f54ebe275dd492b8dcd7af26d4c654cd85cbe3a900e7c339` |
| terminal status | `PUBLIC_PROBE_PASS` |
| registered probes | `16/16 PASS` |
| request attempts | `16` |
| declared request weight | `586` |
| remaining declared planning margin | `614` |
| archive access | `ROUTES_CONFIRMED_ACCESS_RESTRICTED` |
| clean-context review | `PASS`, separate-context AI peer review only |

The exact output is retained byte-for-byte through deterministic gzip/base64,
with separate raw, gzip and encoded hashes. The downloaded artifact ZIP matched
the provider digest, every internal file matched the artifact ledger and no raw
response body, credential, private key or wallet-address pattern was retained.

## Material interpretation limits

- All thirteen public `/info` requests returned an accepted coarse JSON shape.
- The three official S3 routes returned recognized access-error XML, not object
  listings. Their route behavior is confirmed, but usable listing/download
  access is not.
- The fixed historical fills, funding and non-funding-ledger fixture queries
  returned structurally valid empty arrays. Non-empty historical event schemas,
  pagination and completeness remain unproven.
- No archive object was listed or downloaded.
- No analytical market dataset was ingested or released.
- No wallet ledger, P&L, ranking, entity cluster, copy simulation or alpha result
  exists.

## Preserved negative engineering evidence

- `31177378135` / `31177376738`: `FAILED_PRE_NETWORK_PACKAGING`; required
  collector/validator modules were missing. Network access did not execute.
- `31179201440` / `31179201416`:
  `FAILED_PRE_NETWORK_AST_TEST_FALSE_POSITIVE`; the test confused `re.compile`
  with the forbidden built-in `compile`. Network access did not execute.
- `31179277245` / `31179276949`: technically passed but is superseded by the
  final hardening and is not the attested run.
- `31181966325`: correctly rejected a non-byte-identical manual evidence copy;
  exact artifact bytes are now retained in reconstructable encoded form.

No failed or superseded run is silently relabeled as the accepted result.

## Exact next gate

The only permitted successor is a separate `HL-ARCHIVE-INVENTORY-001` proposal.
It must remain metadata/access/cost-only and must:

1. resolve the restricted/requester-pays access method from authoritative
   evidence without storing a long-lived AWS secret in the repository;
2. enumerate only bounded object metadata for `node_fills_by_block`,
   `market_data` and `asset_ctxs`;
3. freeze object counts, keys, sizes, timestamps, storage classes, continuation
   semantics and request costs;
4. build a schema-family and temporal-coverage inventory without downloading
   bulk object contents;
5. produce a requester-pays cost model and immutable raw-retention design;
6. stop fail-closed if access, rights, cost, completeness or provenance cannot
   be established; and
7. require a separate reviewed release decision before any historical object
   body is downloaded for analytical use.

Entity resolution remains downstream of demonstrated individual-wallet
copyability. No probabilistic merge may create false consensus in the first
study.
