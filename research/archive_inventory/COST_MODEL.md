# Cost model

Pricing captured 2026-08-08 from official AWS S3 sources. This document freezes a conservative pre-approval model; it does **not** authorize spend.

AWS states that S3 LIST requests are charged at the same rate as S3 Standard PUT/COPY/POST requests. An official AWS cost reference currently uses USD 0.005 per 1,000 PUT/COPY/POST/LIST requests. Requester Pays shifts successful eligible request and data-transfer charges to the authenticated requester. `ListObjectsV2` returns at most 1,000 keys and accepts `RequestPayer=requester`.

The target Hyperliquid bucket Regions are deliberately unresolved because discovering them through S3 is itself outside the current pre-S3 gate. Therefore the budget does not assume a particular Region, the first-100-GB monthly transfer allowance, credits, discounts, tax treatment or a favorable FX rate.

## R0 micro-canary

Instead of opening the full preregistered inventory envelope immediately, `HL-ARCHIVE-METADATA-CANARY-R0-001` is limited to exactly one first-page `ListObjectsV2` request for each of the seven frozen dataset families:

```text
maximum_list_requests = 7
maximum_keys_per_request = 25
maximum_total_entries = 175
maximum_total_response_bytes = 8,388,608
maximum_runtime_seconds = 180
maximum_retries_per_request = 0
pagination = forbidden
object_body_operations = forbidden
```

The R0 purpose is only to verify actual Requester Pays listing access, the persistent listing policy, first-page key shape and charge signaling before any pagination is considered.

## Cost calculation

Reference request-only cost at USD 0.005/1,000:

```text
7 / 1000 * 0.005 = USD 0.000035
```

Because the bucket Region is unresolved, the authorization model deliberately uses synthetic stress ceilings rather than claiming the reference rates are the exact applicable rates:

```text
stress_LIST_rate = USD 0.05 / 1,000 requests
stress_transfer_rate = USD 0.50 / GB
response_transfer_gb = 8,388,608 / 1,000,000,000 = 0.008388608 GB
stress_request_cost = 7 / 1000 * 0.05 = USD 0.00035
stress_transfer_cost = 0.008388608 * 0.50 = USD 0.004194304
stress_total = USD 0.004544304
```

The stress LIST price is 10x the captured USD 0.005/1,000 reference. The stress transfer price is deliberately far above the USD 0.09/GB transfer example visible on the AWS S3 pricing page. The perpetual first 100 GB/month aggregate data-transfer-out allowance is not relied upon.

## Human budget gate

Proposed, but not approved:

```text
proposed_maximum_one_time_budget_eur = 1.00
maximum_one_time_budget_eur = null
maximum_monthly_budget_eur = 0
paid_request_authorized = false
requester_pays_authorized = false
list_objects_authorized = false
```

No USD/EUR conversion is required to assert the current model because EUR 1.00 is a separate human authorization ceiling while the hard technical usage caps are the primary stop mechanism. The canary implementation must refuse to run unless a later immutable approval binds the exact canonical commit and the EUR 1.00 ceiling.

AWS Budgets or billing alerts may be used as secondary monitoring but are not treated as an instantaneous spending circuit breaker.
