# Human approval template — HL-ARCHIVE-REGION-PROBE-R1-001

This template is **not an approval**. It freezes the exact form a future explicit approval must take after the preregistration is canonical and its exact commit SHA is known.

The approver must provide all lines below with `<CANONICAL_PREREGISTRATION_COMMIT>` replaced by the exact reviewed canonical commit:

```text
APPROVE_HL_ARCHIVE_REGION_PROBE_R1_001
reviewed_commit=<CANONICAL_PREREGISTRATION_COMMIT>
maximum_one_time_budget_eur=0.10
maximum_monthly_budget_eur=0
maximum_head_bucket_requests=1
maximum_runtime_seconds=30
maximum_retries=0
http_redirect_following_authorized=false
target_bucket=hl-mainnet-node-data
head_bucket_authorized=true
requester_pays_acknowledgement_authorized=true
list_objects_v2_authorized=false
get_object_authorized=false
head_object_authorized=false
object_body_download_authorized=false
market_data_ingestion_authorized=false
larger_300_request_inventory_authorized=false
```

Approval must be recorded separately and hash-bound to the exact text. It authorizes only the scope/budget needed to proceed to a separately reviewed implementation. It does **not** by itself install a workflow or execute `HeadBucket`.

The prior R0 approval/release is consumed and cannot be reused for this probe.
