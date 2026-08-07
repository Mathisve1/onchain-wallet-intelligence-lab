# HL-PUBLIC-PROBE-001R1 clean-context review

Status: `CLEAN_CONTEXT_REVIEW_PASS`

Review date: 2026-08-07

Review class: separate-context AI peer review. This is **not** independent external scientific, security, legal or financial review.

## Exact evidence reviewed

- executed PR head: `facd8b26778eb483a4917fc4418069c35b981e8b`;
- checked-out PR merge commit: `3de0cb4ee963357fa6fae4c215643cc2ce22acdc`;
- file difference between those commits: zero;
- Research CI run/job: `31179660399` / `92869634707`, conclusion `success`;
- public-probe run/job: `31179660372` / `92869634761`, conclusion `success`;
- artifact ID/name: `8994227729` / `hyperliquid-public-probe-r1-31179660372-1`;
- provider digest and independently downloaded ZIP SHA-256: `12d98fd48ac0c9503e213efa8f93ae2f777e00ca11cfb989a4e5a3100ad8ee11`;
- probe-output SHA-256: `67aa8f6ef1b4399573c775eeb03c0c32bed12def7494c8461893fcab36247d12`;
- contract SHA-256: `d89f0400756ab6a4a566404290e33cf68a1a75b8fcb26b9832bc0c8d3041546a`;
- collector-bundle SHA-256: `b7dc72c46e408ac4f54ebe275dd492b8dcd7af26d4c654cd85cbe3a900e7c339`.

## Review procedures

The review rechecked:

1. exact contract identity, fixed one-day window, 16-probe order and capacity arithmetic;
2. origin, path, method, redirect and authentication-header restrictions;
3. absence of `/exchange`, signing, order, withdrawal, secret and private-key capabilities;
4. duplicate-key and non-finite JSON rejection;
5. independent endpoint, terminal and archive-access derivation;
6. request, response, contract, collector, output, file-ledger, artifact and ZIP hashes;
7. PR-head versus merge-tree parity;
8. artifact contents and internal SHA-256 ledger;
9. absence of Ethereum-address patterns and raw response bodies in the retained artifact;
10. preservation of all failed and superseded runs in append-only lineage;
11. continued `market_data_ingested=false`, `empirical_result=null` and all authorization booleans false.

## Findings resolved before the accepted run

- `R1-CI-001-MISSING-COLLECTOR-MODULES`: required collector and evidence-validator modules were absent. Both associated runs failed before network access and are retained as negative evidence.
- `R1-CI-002-REGEX-COMPILE-MISCLASSIFIED`: the AST test confused `re.compile` with the forbidden built-in `compile`. Both associated runs failed before network access and are retained as negative evidence.
- PR-head identity was separated from the GitHub-generated merge commit; comparison proves no file difference.
- response JSON now fails closed on duplicate keys and `NaN`/infinite constants.

## Accepted technical conclusion

`HL-PUBLIC-PROBE-001R1` is accepted only as route-level technical evidence:

- terminal status: `PUBLIC_PROBE_PASS`;
- 16 of 16 registered probes passed their frozen coarse response-class contracts;
- total request attempts: `16`;
- total declared request weight: `586`;
- remaining declared planning margin: `614`;
- archive access: `ROUTES_CONFIRMED_ACCESS_RESTRICTED`.

The three official S3 routes returned recognized access-error XML. This confirms the registered route behavior but **does not** prove listing access, archive completeness, requester-pays configuration, data rights, schema stability or affordable retrieval.

## Material limitations

- The historical fixture queries returned structurally valid but empty arrays; non-empty fill, funding and ledger event schemas remain unproven by this run.
- The probe retained structure and hashes, not raw values; it cannot support P&L, wallet ranking or copyability analysis.
- No archive object was listed or downloaded.
- No historical completeness, timestamp accuracy, gap rate, duplicate rate, latency distribution or execution quality was tested.
- No natural-person identity claim, entity-cluster inference or cross-venue hedge conclusion follows.
- No alpha, profitability, paper, shadow, live, leverage or capital-allocation conclusion follows.

## Review decision

No unresolved blocker remains for merging the **technical intake evidence** after strict attestation and final exact-head Research CI pass.

The only permitted successor is a separate, fail-closed archive-access and metadata-inventory proposal. It must resolve restricted/requester-pays access and cost before any bulk archive download or analytical market-data release.
