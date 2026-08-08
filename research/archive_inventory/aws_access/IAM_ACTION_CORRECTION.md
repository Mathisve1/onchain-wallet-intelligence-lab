# IAM action correction

AWS IAM does not define `s3:SelectObjectContent` as a standalone policy action. The S3 `SelectObjectContent` API is authorized by `s3:GetObject`.

The archive metadata role already explicitly denies `s3:GetObject`, so removing the invalid `s3:SelectObjectContent` token does not weaken the object-body boundary.

Correction status: `POLICY_SYNTAX_REPAIRED_NO_SCOPE_EXPANSION`.
