# IAM boundary — proposal only

No AWS identity is created or bound in this phase.

A future canary identity should have only `s3:ListBucket` on the two documented archive buckets, restricted to the exact registered prefixes. Object-body permissions must not be granted. The machine-readable design is `IAM_POLICY_TEMPLATE.json`.

The external bucket owner still controls whether the authenticated requester is allowed to list the bucket. Therefore this requester-side policy is necessary but not sufficient evidence of access.

Prefer a short-lived role/session for later execution rather than a long-lived access key. Credential material must never be committed, printed, uploaded as an artifact, or passed to an LLM.

The future runner must prove that object-body and mutation actions remain explicitly denied before any paid call is allowed.
