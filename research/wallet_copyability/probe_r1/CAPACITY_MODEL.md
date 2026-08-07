# Capacity Model — Hyperliquid Public Probe R1

## Objective

Keep the exact R1 `/info` workload below the published planning budget of 1,200 weighted requests per minute even if every registered API probe uses its single permitted retry.

S3 archive-route GETs are excluded from Hyperliquid `/info` weight accounting but remain inside the total HTTP request ceiling.

## Registered planning weights

| Probe | Declared weight | Basis |
|---|---:|---|
| `meta` | 20 | base information weight |
| `all_mids` | 2 | published low-weight market request |
| `master_user_role` | 60 | published `userRole` weight |
| `master_subaccounts` | 50 | base plus conservative result-size allowance |
| `subaccount_user_role` | 60 | published `userRole` weight |
| `subaccount_state` | 2 | published low-weight account-state request |
| `master_user_fees` | 20 | base information weight |
| `subaccount_fills_by_time` | 120 | base plus maximum result-size allowance |
| `subaccount_funding` | 50 | base plus conservative one-day result-size allowance |
| `subaccount_non_funding_ledger` | 120 | base plus maximum result-size allowance |
| `vault_user_role` | 60 | published `userRole` weight |
| `vault_details` | 20 | base information weight |
| `l2_book_btc` | 2 | published low-weight market request |
| three S3 probes | 0 | outside `/info` API |
| **Total first attempt** | **586** | frozen sum |

## Worst-case arithmetic

```text
16 registered HTTP requests
13 Hyperliquid /info requests
3 official S3 route requests
maximum attempts per probe = 2
maximum HTTP requests = 16 × 2 = 32
contract HTTP ceiling = 36

base declared /info weight = 586
worst declared /info weight = 586 × 2 = 1,172
published planning budget = 1,200
safety margin = 1,200 − 1,172 = 28
contract declared-weight ceiling = 1,180
```

The 1,180 contract ceiling is lower than the published planning budget and higher than the exact 1,172 worst case. Any third attempt, added route or increased declared weight fails contract validation.

## Retry semantics

A second attempt is allowed only after:

- transport failure;
- HTTP 429; or
- HTTP 5xx.

There is no retry after a deterministic 2xx schema mismatch or HTTP 4xx other than 429. Retries execute sequentially with bounded exponential delay.

## Why unbounded `userFills` is excluded

The non-time-bounded `userFills` route may return a large recent result set and makes response-size weight less predictable. R1 therefore uses only `userFillsByTime` over the frozen one-day interval. This is enough to test the public historical response class without opening broad collection.

## Claim boundary

These weights are conservative experiment controls, not a representation of actual charged weight for every future response. If official rules or observed response limits change, the current run remains historical evidence and a new contract revision is required.
