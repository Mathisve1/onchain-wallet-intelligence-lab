# HL-PUBLIC-PROBE-001R1 clean-context review

Status: `CLEAN_CONTEXT_REVIEW_PASS`

Review date: 2026-08-07

Review class: exact-evidence AI peer review. This is **not** independent external scientific, security, legal or financial review.

## Exact evidence reviewed

- executed and checked-out source head: `9f35a87a65b9b80db544d07ce4e68c33c8343e3b`;
- reviewed/checked-out identity match: `true`;
- owner authorization actor: `Mathisve1`;
- one-time owner marker: consumed and removed after the intended run;
- Research CI run/job: `31192935736` / `92914022092`, conclusion `success`;
- exact pre-run suite: `43/43 PASS` and `REPOSITORY_VALIDATION_PASS` over 75 files;
- public-probe run/job: `31193129277` / `92914689054`, conclusion `success`;
- artifact ID/name: `8999652912` / `hyperliquid-public-probe-r1-31193129277-1`;
- artifact size and expiry: `36,249` bytes / `2026-11-05T15:32:35Z`;
- provider digest and independently downloaded ZIP SHA-256: `5a30c6e9a2b80e49eac6d341e0c93f9e182a408b1f10f81270795054eee5534e`;
- probe-output SHA-256: `c4cd5f6c087da712c4ce5c23351a672704ae402b9b05577830bed8872152c3ac`;
- run-context SHA-256: `851be98f8e71c94ad168fd3386fa66395bd81f83a80aaae62288217f66512ecc`;
- validation-log SHA-256: `9170376f6626bfa5aba7e5982f18756aa87d5b975b01a58a2a59ae10bc849f32`;
- validation-return-code SHA-256: `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`;
- artifact-ledger SHA-256: `fdd84603d989f92cee4a68b98199d2631a67cb35e84b28bc48a18d1d4d94bec2`;
- contract SHA-256: `d89f0400756ab6a4a566404290e33cf68a1a75b8fcb26b9832bc0c8d3041546a`;
- collector-bundle SHA-256: `b7dc72c46e408ac4f54ebe275dd492b8dcd7af26d4c654cd85cbe3a900e7c339`.

## Review procedures

The review independently rechecked:

1. exact contract identity, fixed one-day window, 16-probe order and capacity arithmetic;
2. exact source-head checkout instead of the GitHub synthetic merge ref;
3. repository-owner authorization, same-repository head, draft state, base `main` and exact SHA-bound marker;
4. origin, path, method, redirect and authentication-header restrictions;
5. absence of `/exchange`, signing, order, withdrawal, secret and private-key capabilities;
6. duplicate-key and non-finite JSON rejection;
7. every request SHA-256 by reconstructing the frozen resolved POST payload or GET path/query;
8. every observation's registered identity, order, method, origin, path, weight, expected class and core flag;
9. terminal and archive-access derivation independently from the observations;
10. artifact provider digest, downloaded ZIP SHA-256, exact five-file inventory and internal file ledger;
11. deterministic gzip/base64 retention with separate raw, gzip and encoded hashes;
12. absence of Ethereum-address patterns, credentials, secrets and raw response bodies in retained output;
13. preservation of failed and superseded runs in append-only lineage;
14. continued `market_data_ingested=false`, `empirical_result=null` and all authorization booleans false.

## Findings resolved before the accepted exact-head run

- `R1-CI-001-MISSING-COLLECTOR-MODULES`: required collector and evidence-validator modules were absent. Associated runs failed before network access and remain negative evidence.
- `R1-CI-002-REGEX-COMPILE-MISCLASSIFIED`: the AST test confused `re.compile` with the forbidden built-in `compile`. Associated runs failed before network access and remain negative evidence.
- A previously successful run checked out GitHub's synthetic PR merge ref. Although its tree was byte-equivalent, it is no longer accepted for final attestation because exact source-head identity is now mandatory.
- The manual-only workflow and pull-request-head tests previously contradicted one another. They were replaced by an owner-only `pull_request.edited` marker bound to the exact current source-head SHA.
- The one-time marker was removed immediately after run `31193129277`, so later ordinary PR edits cannot silently rerun the probe.
- Response JSON fails closed on duplicate keys and `NaN`/infinite constants.

## Accepted technical conclusion

`HL-PUBLIC-PROBE-001R1` is accepted only as route-level technical evidence:

- terminal status: `PUBLIC_PROBE_PASS`;
- 16 of 16 registered probes passed their frozen coarse response-class contracts;
- total request attempts: `16`;
- total declared request weight: `586`;
- remaining declared planning margin: `614`;
- archive access: `ROUTES_CONFIRMED_ACCESS_RESTRICTED`.

All thirteen public `/info` requests returned accepted JSON structures. The three official S3 routes returned recognized HTTP 403 access-error XML. This confirms registered route behavior but **does not** prove listing access, archive completeness, requester-pays configuration, data rights, schema stability or affordable retrieval.

## Material limitations

- The fixed historical fills, funding and non-funding-ledger fixture queries returned structurally valid empty arrays; non-empty event schemas remain unproven.
- The probe retained structure and hashes, not raw response values; it cannot support P&L, wallet ranking or copyability analysis.
- No archive object was listed or downloaded.
- No historical completeness, timestamp accuracy, gap rate, duplicate rate, latency distribution or execution quality was tested.
- No natural-person identity claim, entity-cluster inference or cross-venue hedge conclusion follows.
- No alpha, profitability, paper, shadow, live, leverage or capital-allocation conclusion follows.

## Review decision

No unresolved evidence, identity, capability, privacy, capacity or attestation blocker remains for incorporating this technical intake after final exact-head Research CI succeeds.

The only permitted successor is a separate, fail-closed `HL-ARCHIVE-INVENTORY-001` metadata/access/cost proposal. It must resolve restricted/requester-pays access before any bulk archive download or analytical market-data release.
