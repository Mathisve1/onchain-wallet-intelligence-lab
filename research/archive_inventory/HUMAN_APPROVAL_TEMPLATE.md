# Human approval template — not approved

Do not treat this template as authorization. `HL-AWS-OIDC-IDENTITY-001` is attested and the conservative R0 pricing model is frozen, but Requester Pays and S3 listing remain closed until the user explicitly supplies an approval matching every line below.

## Proposed R0 approval

```text
APPROVE_HL_ARCHIVE_METADATA_CANARY_R0_001
reviewed_commit=<exact canonical main SHA after pricing-gate merge>
maximum_one_time_budget_eur=1.00
maximum_monthly_budget_eur=0
maximum_list_requests=7
maximum_keys_per_request=25
maximum_total_entries=175
maximum_total_response_bytes=8388608
maximum_runtime_seconds=180
maximum_retries_per_request=0
pagination_authorized=false
requester_pays_authorized=true
list_objects_v2_authorized=true
get_object_authorized=false
head_object_authorized=false
get_object_attributes_authorized=false
range_get_authorized=false
list_object_versions_authorized=false
list_all_my_buckets_authorized=false
object_body_download_authorized=false
decompression_authorized=false
market_data_ingestion_authorized=false
approval_reason_code=SEVEN_FAMILY_FIRST_PAGE_METADATA_ACCESS_AND_COST_DISCOVERY_ONLY
```

The approval is invalid if the reviewed commit is not the exact current canonical `main` SHA, any required line is omitted, any limit is larger, or any forbidden capability is opened.

## What this would authorize

Only seven first-page S3 `ListObjectsV2` requests: one for each already frozen dataset family, with `RequestPayer=requester`, no pagination and no retry. It never authorizes object-body retrieval, historical market-data ingestion, wallet analysis, clustering, trading, leverage or capital allocation.

The larger preregistered 300-request inventory envelope remains a separate future approval even if R0 succeeds.
