# Project State

Verified: 2026-08-07 against exact source-head workflow, downloaded artifact and retained-evidence identities.

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

The bounded read-only technical probe is accepted only as route-level evidence. It is not a wallet study, market backtest, alpha result or execution authorization.

| Evidence | Exact identity |
|---|---|
| executed and checked-out source head | `9f35a87a65b9b80db544d07ce4e68c33c8343e3b` |
| reviewed/checked-out identity match | `true` |
| exact-head Research CI run/job | `31192935736` / `92914022092` — `success` |
| pre-run suite and repository validation | `43/43 PASS`; 75-file manifest; `REPOSITORY_VALIDATION_PASS` |
| public-probe run/job | `31193129277` / `92914689054` — `success` |
| artifact | `8999652912` / `hyperliquid-public-probe-r1-31193129277-1` |
| artifact size / expiry | `36,249` bytes / `2026-11-05T15:32:35Z` |
| provider digest and downloaded ZIP SHA-256 | `5a30c6e9a2b80e49eac6d341e0c93f9e182a408b1f10f81270795054eee5534e` |
| probe-output SHA-256 | `c4cd5f6c087da712c4ce5c23351a672704ae402b9b05577830bed8872152c3ac` |
| run-context SHA-256 | `851be98f8e71c94ad168fd3386fa66395bd81f83a80aaae62288217f66512ecc` |
| artifact-ledger SHA-256 | `fdd84603d989f92cee4a68b98199d2631a67cb35e84b28bc48a18d1d4d94bec2` |
| contract SHA-256 | `d89f0400756ab6a4a566404290e33cf68a1a75b8fcb26b9832bc0c8d3041546a` |
| collector-bundle SHA-256 | `b7dc72c46e408ac4f54ebe275dd492b8dcd7af26d4c654cd85cbe3a900e7c339` |
| terminal status | `PUBLIC_PROBE_PASS` |
| registered probes | `16/16 PASS` |
| request attempts | `16` |
| declared request weight | `586` |
| remaining declared planning margin | `614` |
| archive access | `ROUTES_CONFIRMED_ACCESS_RESTRICTED` |
| independent artifact verification | `PASS`, exact ZIP/file/request/state recomputation |
| clean-context review | `PASS`, AI peer review only; not independent external review |

The exact output is retained byte-for-byte through deterministic gzip/base64, with separate raw, gzip and encoded hashes. The downloaded artifact ZIP matched the provider digest, all five files matched the exact inventory, the four payload files matched the producer ledger and all request hashes were independently reconstructed from the frozen contract.

The owner authorization marker was bound to the exact source head and removed immediately after the intended run. Later ordinary PR edits cannot reuse it silently.

## Material interpretation limits

- All thirteen public `/info` requests returned an accepted coarse JSON structure.
- The three official S3 routes returned recognized HTTP 403 access-error XML, not object listings. Their route behavior is confirmed, but usable listing/download access is not.
- The fixed historical fills, funding and non-funding-ledger fixture queries returned structurally valid empty arrays. Non-empty historical event schemas, pagination and completeness remain unproven.
- No archive object was listed or downloaded.
- No analytical market dataset was ingested or released.
- No wallet ledger, P&L, ranking, entity cluster, copy simulation or alpha result exists.
- No raw response body, Ethereum-address pattern, credential, secret, private key or signed action was retained or used.

## Preserved negative and superseded engineering evidence

- `31177378135` / `31177376738`: `FAILED_PRE_NETWORK_PACKAGING`; required collector/validator modules were missing. Network access did not execute.
- `31179201440` / `31179201416`: `FAILED_PRE_NETWORK_AST_TEST_FALSE_POSITIVE`; the test confused `re.compile` with the forbidden built-in `compile`. Network access did not execute.
- `31179277245` / `31179276949`: technically passed but is superseded by later hardening.
- `31179660399` / `31179660372`: technically passed on a byte-equivalent GitHub PR merge ref, but is superseded because the final contract now requires the exact source head itself to be checked out and attested.
- `31181966325`: correctly rejected a non-byte-identical manual evidence copy.
- `31186776679`: correctly exposed the contradiction between a manual-only trigger and pull-request-head assertions.
- `31192125770` and `31192714815`: fail-closed manifest diagnostics used only to bind subsequent exact trees; they are not probe results.

No failed or superseded run is silently relabeled as the accepted result.

## Exact next gate

The only permitted successor is a separate `HL-ARCHIVE-INVENTORY-001` proposal. It must remain metadata/access/cost-only and must:

1. resolve the restricted/requester-pays access method from authoritative evidence without storing a long-lived AWS secret in the repository;
2. enumerate only bounded object metadata for `node_fills_by_block`, `market_data` and `asset_ctxs`;
3. freeze object counts, keys, sizes, timestamps, storage classes, continuation semantics and request costs;
4. build a schema-family and temporal-coverage inventory without downloading bulk object contents;
5. produce a requester-pays cost model and immutable raw-retention design;
6. stop fail-closed if access, rights, cost, completeness or provenance cannot be established; and
7. require a separate reviewed release decision before any historical object body is downloaded for analytical use.

Entity resolution remains downstream of demonstrated individual-wallet copyability. No probabilistic merge may create false consensus in the first study.
