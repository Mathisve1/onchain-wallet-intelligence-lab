# Cost model

This phase binds the method, not a final dollar/euro figure. AWS S3 bills request operations and data transfer separately; Requester Pays can shift eligible request and transfer costs to the authenticated requester.

For an approved metadata canary:

```text
request_cost_usd = list_request_count / 1000 * applicable_list_rate_usd_per_1000
response_transfer_gb = total_response_bytes / 1_000_000_000
transfer_cost_usd = response_transfer_gb * applicable_transfer_rate_usd_per_gb
estimated_canary_cost_usd = request_cost_usd + transfer_cost_usd
```

Taxes, FX, free-tier effects, credits and account-specific discounts are excluded unless separately evidenced.

The public probe did not bind the bucket Region or requesting AWS billing context. Current official price rows and FX therefore must be captured immediately before any paid canary. Until then:

```text
maximum_one_time_budget_eur = null
maximum_monthly_budget_eur = 0
paid_request_authorized = false
```

AWS billing alerts are not the primary stop control. Request, page, entry, response-byte and runtime caps must stop the process independently.
