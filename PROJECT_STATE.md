# Project State

Verified: 2026-08-08 against canonical `main` commit `3522edb19541c727670daed2a0bc7e5f4f9d0417`, canonical public-probe evidence, and the user's confirmation that the exact AWS role, reviewed trust policy and inline policy `HLArchiveMetadataCanaryListOnly` were created. AWS role/OIDC federation is not independently verified until `HL-AWS-OIDC-IDENTITY-001` passes.

## Current status

| Dimension | State |
|---|---|
| program | `ONCHAIN-WALLET-INTELLIGENCE` |
| current study | `WALLET-COPYABILITY-STUDY-001` |
| research status | `REQUIRES_FURTHER_TESTING` |
| lifecycle stage | `PRE_ARCHIVE_INVENTORY` |
| experiment status | `PUBLIC_TECHNICAL_PROBE_ATTESTED_ARCHIVE_ACCESS_RESTRICTED` |
| public-probe implementation | `INSTALLED_ON_CANONICAL_MAIN` |
| public-probe implementation commit | `33683532ca3e6cf7512a728157791d3bfef1375f` |
| canonical public-probe reviewed commit | `c11046bf288687c6945fe9b8f17141204d24aae6` |
| canonical public-probe workflow run / job | `31200124642` / `92937868268` |
| canonical public-probe artifact | `9002459643` |
| public-probe result | `PUBLIC_PROBE_PASS` |
| archive access result | `ROUTES_CONFIRMED_ACCESS_RESTRICTED` |
| archive inventory study | `HL-ARCHIVE-INVENTORY-001` |
| archive inventory status | `PREREGISTERED_METADATA_ONLY_NO_S3_EXECUTION` |
| archive preregistration commit | `0e8a678644c29548a38ebfa1c0af91d4a9a92c09` |
| AWS account ID | `630956766927` |
| GitHub OIDC provider | `USER_CONFIRMED_CREATED_NOT_API_VERIFIED` |
| expected GitHub OIDC subject | `repo:Mathisve1@163474992/onchain-wallet-intelligence-lab@1326362646:ref:refs/heads/main` |
| OIDC subject/federation independently proven | `false` |
| expected AWS role | `onchain-wallet-intelligence-hl-archive-metadata-canary` |
| expected role ARN | `arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-metadata-canary` |
| role + reviewed trust + inline policy | `USER_CONFIRMED_NOT_API_VERIFIED` |
| STS identity check | `HL-AWS-OIDC-IDENTITY-001` |
| STS identity check status | `PREREGISTERED_MANUAL_RUN_ALLOWED_NO_RESULT` |
| AWS identity bound | `false` |
| OIDC identity check authorized | `true` |
| requester-pays authorized | `false` |
| ListObjectsV2 authorized | `false` |
| GetObject authorized | `false` |
| object-body download authorized | `false` |
| empirical result | `null` |
| integration authorized | `false` |
| paper authorized | `false` |
| shadow authorized | `false` |
| live authorized | `false` |
| leverage authorized | `false` |
| capital allocation authorized | `false` |

## Canonical technical evidence

The canonical public probe remains immutable and attested. `HL-ARCHIVE-INVENTORY-001` remains metadata/access/cost-only research. No historical archive object has been listed or downloaded.

## AWS OIDC boundary

The user confirmed that AWS account `630956766927` is active and that the exact role `onchain-wallet-intelligence-hl-archive-metadata-canary` now exists with the reviewed trust relationship and inline policy `HLArchiveMetadataCanaryListOnly`. These AWS control-plane facts remain human-attested until the repository's STS-only identity gate succeeds.

The trust boundary remains restricted to:

```text
provider = token.actions.githubusercontent.com
audience = sts.amazonaws.com
repository = Mathisve1/onchain-wallet-intelligence-lab
repository_id = 1326362646
repository_owner_id = 163474992
ref = refs/heads/main
subject = repo:Mathisve1@163474992/onchain-wallet-intelligence-lab@1326362646:ref:refs/heads/main
```

The persistent role policy permits only the preregistered `s3:ListBucket` scope and explicitly denies object reads/mutations. However, `HL-AWS-OIDC-IDENTITY-001` goes further: its 900-second assumed-role session carries an inline `Deny s3:*` policy, so the identity-verification session cannot use S3 at all.

## STS-only verification boundary

```text
network_identity_check_authorized = true
explicit_allowed_aws_cli_call = aws sts get-caller-identity
s3_denied_for_identity_check_session = true
requester_pays_authorized = false
list_objects_authorized = false
paid_request_authorized = false
get_object_authorized = false
head_object_authorized = false
range_get_authorized = false
object_body_download_authorized = false
decompression_authorized = false
maximum_one_time_budget_eur = null
maximum_monthly_budget_eur = 0
market_data_ingested = false
empirical_result = null
```

## Exact next gate

1. Review and merge the manual-only `HL-AWS-OIDC-IDENTITY-001` workflow implementation.
2. Manually dispatch it from exact canonical `main` with the exact current `main` SHA.
3. Require `STS_IDENTITY_MATCH` for AWS account `630956766927` and the exact assumed-role ARN; retain only minimized identity evidence.
4. Only after successful attestation: refresh/freeze exact applicable S3 pricing and obtain a separate explicit one-time human Requester Pays budget approval.
5. Only after that may a bounded metadata `ListObjectsV2` canary be implemented/enabled.

No S3 call, Requester Pays request, object-body retrieval, market-data ingestion, wallet performance calculation, entity clustering or trading stage is currently open.

Entity-resolution research remains downstream of demonstrated individual-wallet copyability. No probabilistic wallet merge may create false consensus in the first study.
