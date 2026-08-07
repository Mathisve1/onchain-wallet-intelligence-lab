# Project State

Verified: 2026-08-07 against canonical main run `31200124642` on reviewed commit `c11046bf288687c6945fe9b8f17141204d24aae6`.

## Current status

| Dimension | State |
|---|---|
| program | `ONCHAIN-WALLET-INTELLIGENCE` |
| current study | `WALLET-COPYABILITY-STUDY-001` |
| research status | `REQUIRES_FURTHER_TESTING` |
| lifecycle stage | `PRE_ARCHIVE_INVENTORY` |
| experiment status | `PUBLIC_TECHNICAL_PROBE_ATTESTED_ARCHIVE_ACCESS_RESTRICTED` |
| public-probe implementation | `INSTALLED_ON_CANONICAL_MAIN` |
| implementation pull request | `#7` |
| implementation commit | `33683532ca3e6cf7512a728157791d3bfef1375f` |
| canonical reviewed commit | `c11046bf288687c6945fe9b8f17141204d24aae6` |
| canonical workflow run / job | `31200124642` / `92937868268` |
| canonical artifact | `9002459643` |
| public-probe result | `PUBLIC_PROBE_PASS` |
| archive access result | `ROUTES_CONFIRMED_ACCESS_RESTRICTED` |
| empirical result | `null` |
| integration authorized | `false` |
| paper authorized | `false` |
| shadow authorized | `false` |
| live authorized | `false` |
| leverage authorized | `false` |
| capital allocation authorized | `false` |

## Canonical technical evidence

The canonical workflow was manually dispatched from `refs/heads/main`. Before network access it proved:

```text
inputs.reviewed_commit = c11046bf288687c6945fe9b8f17141204d24aae6
github.sha = c11046bf288687c6945fe9b8f17141204d24aae6
git rev-parse HEAD = c11046bf288687c6945fe9b8f17141204d24aae6
```

The run completed with:

```text
pass_count = 16
fail_count = 0
total_request_attempts = 16
total_declared_request_weight = 586
remaining_declared_weight_margin = 614
probe_output_sha256 = cce83a5eb5f960bc1274b949fdcd532b9168af7ff270b4d71ba6f521995bed89
artifact_zip_sha256 = 388ad766d0e71f315533362ed0605b6d6d6cf13895656e84b9aa0afc80cf8fe6
```

The independently downloaded artifact ZIP matched GitHub's provider digest exactly. Internal retained artifact files also matched the workflow-generated SHA-256 ledger.

All thirteen registered `/info` probes returned the preregistered coarse JSON response class. All three official S3 archive routes returned recognized HTTP 403 S3 access-error responses. This confirms route behavior only; it does not prove list permission, archive completeness, requester-pays configuration, object counts, retrievable volume or cost.

The fixed historical fills, funding and non-funding-ledger fixture queries were structurally valid but empty. Therefore non-empty historical event schemas, pagination and completeness remain unresolved.

## Hard boundary

```text
market_data_ingested = false
empirical_result = null
integration_authorized = false
paper_authorized = false
shadow_authorized = false
live_authorized = false
leverage_authorized = false
capital_allocation_authorized = false
```

No archive object has been listed or downloaded. No wallet ledger, wallet P&L, ranking, copyability result, entity cluster or alpha claim exists.

## Exact next gate

The only permitted successor is a separately preregistered `HL-ARCHIVE-INVENTORY-001` proposal. It must remain metadata/access/cost-only and must establish the restricted/requester-pays access method, bounded listing limits, object metadata fields, temporal coverage, schema families, estimated retrieval cost and fail-closed stop rules before any historical object body may be downloaded.

Any paid requester-pays request, bulk object retrieval, analytical market-data release, wallet-performance calculation or execution stage requires a separate reviewed decision.

Entity-resolution research remains downstream of demonstrated individual-wallet copyability. No probabilistic wallet merge may create false consensus in the first study.
