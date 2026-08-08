# Human approval template — HL-ARCHIVE-NODEDATA-METADATA-CANARY-R2-001

This template is inert. It is not approval and does not authorize implementation, workflow installation, AWS/S3 execution or spending.

After this preregistration is canonically merged, approval must bind the exact canonical preregistration commit and preserve every boundary below.

```text
APPROVE_HL_ARCHIVE_NODEDATA_CANARY_R2_001
reviewed_commit=<CANONICAL_R2_PREREGISTRATION_COMMIT>
maximum_one_time_budget_eur=0.10
maximum_monthly_budget_eur=0
maximum_list_requests=5
maximum_keys_per_request=25
maximum_total_entries=125
maximum_total_response_bytes=8388608
maximum_runtime_seconds=120
maximum_retries_per_request=0
pagination_authorized=false
http_redirect_following_authorized=false
target_bucket=hl-mainnet-node-data
signing_region=ap-northeast-1
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
larger_300_request_inventory_authorized=false
approval_reason_code=FIVE_NODEDATA_PREFIX_FIRST_PAGE_CORRECT_REGION_METADATA_ACCESS_ONLY
```

The future approval authorizes at most the listed scope and budget. It does not itself install executable code or a workflow; implementation and a single-use execution release remain separate reviewed gates.
