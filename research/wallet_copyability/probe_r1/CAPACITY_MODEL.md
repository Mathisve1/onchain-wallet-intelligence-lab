# Capacity Model — Hyperliquid Public Probe R1

## Objective

Keep the exact R1 `/info` workload below the captured planning budget of 1,200
weighted requests per minute even if every registered API route uses its single
permitted retry. The S3 routes do not consume this `/info` weight budget but
remain inside the total HTTP-request ceiling.

## Registered planning weights

| Probe | Declared weight | Basis |
|---|---:|---|
| `meta` | 20 | base information weight |
| `all_mids` | 2 | low-weight market request |
| `master_user_role` | 60 | registered user-role weight |
| `master_subaccounts` | 50 | base plus result-size allowance |
| `subaccount_user_role` | 60 | registered user-role weight |
| `subaccount_state` | 2 | low-weight state request |
| `master_user_fees` | 20 | base information weight |
| `subaccount_fills_by_time` | 120 | base plus maximum result allowance |
| `subaccount_funding` | 50 | one-day result allowance |
| `subaccount_non_funding_ledger` | 120 | maximum result allowance |
| `vault_user_role` | 60 | registered user-role weight |
| `vault_details` | 20 | base information weight |
| `l2_book_btc` | 2 | low-weight market request |
| three S3 routes | 0 | outside `/info` budget |
| **First-attempt total** | **586** | frozen sum |

## Worst-case arithmetic

```text
registered HTTP routes                  16
Hyperliquid /info routes                13
official S3 routes                       3
maximum attempts per route               2
registered worst HTTP request count     32
contract HTTP ceiling                   36

first-attempt declared /info weight    586
two-attempt worst declared weight    1,172
captured planning budget             1,200
safety margin                            28
contract declared-weight ceiling      1,180
```

The collector checks the prospective request count and declared weight before
every attempt. A third attempt, extra route or weight beyond the contract
ceiling stops before that network call.

## Retry rule

A second attempt is allowed only after:

- transport failure;
- HTTP 429; or
- HTTP 5xx.

There is no retry after a deterministic schema mismatch or ordinary 4xx
response. Retries are sequential with a bounded delay.

## Interpretation boundary

The registered weights are conservative experiment controls, not a guarantee
of permanent venue rules or the exact charge of every future response. A
material change in official limits or response behavior requires a reviewed
contract revision and a new run identity.
