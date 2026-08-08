# Project State

Verified: 2026-08-08 against canonical archive-preregistration commit `0e8a678644c29548a38ebfa1c0af91d4a9a92c09` plus user-confirmed AWS account/OIDC-provider setup. AWS role existence is not independently verified.

## Current status

| Dimension | State |
|---|---|
| program | `ONCHAIN-WALLET-INTELLIGENCE` |
| current study | `WALLET-COPYABILITY-STUDY-001` |
| research status | `REQUIRES_FURTHER_TESTING` |
| lifecycle stage | `PRE_ARCHIVE_INVENTORY` |
| experiment status | `PUBLIC_TECHNICAL_PROBE_ATTESTED_ARCHIVE_ACCESS_RESTRICTED` |
| archive inventory study | `HL-ARCHIVE-INVENTORY-001` |
| archive inventory status | `PREREGISTERED_METADATA_ONLY_NO_EXECUTION` |
| AWS account ID | `630956766927` |
| GitHub OIDC provider | `USER_CONFIRMED_CREATED_NOT_API_VERIFIED` |
| expected AWS role | `onchain-wallet-intelligence-hl-archive-metadata-canary` |
| expected role ARN | `arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-metadata-canary` |
| AWS identity bound | `false` |
| OIDC identity check authorized | `false` |
| requester-pays authorized | `false` |
| ListObjectsV2 authorized | `false` |
| GetObject authorized | `false` |
| object-body download authorized | `false` |
| public-probe result | `PUBLIC_PROBE_PASS` |
| archive access result | `ROUTES_CONFIRMED_ACCESS_RESTRICTED` |
| empirical result | `null` |
| integration authorized | `false` |
| paper authorized | `false` |
| shadow authorized | `false` |
| live authorized | `false` |
| leverage authorized | `false` |
| capital allocation authorized | `false` |

## Canonical technical evidence

The canonical public probe remains immutable and attested. `HL-ARCHIVE-INVENTORY-001` is canonically preregistered as metadata/access/cost-only research. No historical archive object has been listed or downloaded.

## Proposed AWS OIDC access boundary

The user confirmed that AWS account `630956766927` is active, root MFA/payment prerequisites are satisfied, and the GitHub OIDC provider has been created. This repository cannot independently query those AWS control-plane facts, so they remain human-attested until a separately reviewed identity-only verification is executed.

The proposed role is restricted to:

```text
provider = token.actions.githubusercontent.com
audience = sts.amazonaws.com
repository = Mathisve1/onchain-wallet-intelligence-lab
repository_id = 1326362646
repository_owner_id = 163474992
ref = refs/heads/main
subject = repo:Mathisve1/onchain-wallet-intelligence-lab:ref:refs/heads/main
```

The proposed permission policy permits only `s3:ListBucket` for the seven preregistered prefixes, requires `s3:max-keys <= 1000`, and explicitly denies prefix escape, version listing, account-wide bucket enumeration, object-body reads and mutation.

## Hard boundary

```text
aws_identity_bound = false
network_identity_check_authorized = false
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

1. Review and merge the account-specific OIDC trust/permission boundary.
2. Human creates exactly one role named `onchain-wallet-intelligence-hl-archive-metadata-canary` using the reviewed policies; no AWS access keys or GitHub AWS secrets.
3. Separately preregister and run an STS-only OIDC identity verification against the exact canonical main commit. It must not touch S3.
4. Only after identity verification: refresh/freeze exact applicable S3 pricing and obtain explicit one-time human Requester Pays budget approval.
5. Only after that: implement/enable the bounded metadata `ListObjectsV2` adapter and canary.

No paid S3 call, object-body retrieval, market-data ingestion, wallet performance calculation, entity clustering or trading stage is currently open.

Entity-resolution research remains downstream of demonstrated individual-wallet copyability. No probabilistic wallet merge may create false consensus in the first study.
