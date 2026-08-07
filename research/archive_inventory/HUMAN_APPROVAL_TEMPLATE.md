# Human approval template — not approved

Do not complete this until the preregistration/implementation is merged and the AWS identity + current pricing evidence have been independently reviewed.

A future approval should explicitly bind:

```text
APPROVE_HL_ARCHIVE_METADATA_CANARY_001
reviewed_commit=<exact canonical main SHA>
maximum_one_time_budget_eur=<explicit amount>
maximum_monthly_budget_eur=0
maximum_list_requests=300
maximum_total_response_bytes=268435456
maximum_runtime_seconds=900
requester_pays_authorized=true
list_objects_v2_authorized=true
get_object_authorized=false
head_object_authorized=false
range_get_authorized=false
object_body_download_authorized=false
decompression_authorized=false
approval_reason_code=METADATA_ACCESS_VOLUME_AND_COST_DISCOVERY_ONLY
```

The approval is invalid if any placeholder remains unresolved. It never authorizes object-body retrieval, wallet analysis, trading, leverage, or capital allocation.
