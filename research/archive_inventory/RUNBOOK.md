# Runbook

## Phase A — current: preregistration and implementation

1. Confirm canonical public-probe attestation exists on `main`.
2. Freeze dataset register, access model, metadata fields and cost guard.
3. Run unit/mutation tests and repository validator.
4. Merge only while all network/payment/data-release authorizations remain false.

No AWS request is made in Phase A.

## Phase B — separate approval

Before any authenticated S3 request: refresh official AWS pricing, resolve the billing identity without exposing credentials, review listing-only IAM, bind an exact one-time euro budget and canonical commit, then obtain explicit human approval.

## Phase C — bounded metadata canary

Only after Phase B: delimiter-first prefix discovery; bounded pagination; normalized metadata/request ledger; stop on any guard violation; classify each family complete/censored/denied/unresolved; calculate counts/bytes only where justified.

## Phase D — review

End with exactly `ARCHIVE_INVENTORY_PASS`, `ARCHIVE_INVENTORY_PARTIAL`, or `ARCHIVE_INVENTORY_FAIL`. No outcome automatically authorizes object-body retrieval.
