# Threat model

| Threat | Fail-closed control |
|---|---|
| Runaway pagination | total/page/runtime caps and repeated-token rejection |
| Accidental object download | operation allowlist contains only ListObjectsV2; explicit IAM object-body deny |
| Prefix escape | bucket+prefix must match frozen dataset register exactly |
| Credential leakage | no credential code or values in repo; later runner must redact auth/session data |
| 403 misclassified as Requester Pays proof | authenticated canary classifies access separately |
| Incomplete listing called complete | every family/partition carries completion/censoring state |
| Missing key called a gap from capped sample | only complete partitions can support `PROVEN_KEY_GAP` |
| Region/pricing drift | pricing evidence refreshed before paid execution |
| Unexpected huge listing responses | aggregate response-byte cap |
| Retry amplification | one retry max per logical request; every attempt counts before response |
| Wallet-selection bias | no wallet addresses or wallet outcomes in inventory selection |
| Scope creep into market analysis | market_data_ingested and empirical_result remain false |
