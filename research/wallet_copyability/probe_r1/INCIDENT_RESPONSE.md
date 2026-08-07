# Incident Response — Hyperliquid Public Probe R1

Every abnormal outcome receives a durable classification. Failed and partial
runs are never overwritten.

| ID | Trigger | Immediate result | Required action |
|---|---|---|---|
| `R1-INC-001-CREDENTIAL_CAPABILITY` | secret, authentication header, cookie, private key or persisted checkout credential | fail | stop and perform security review |
| `R1-INC-002-EXECUTION_CAPABILITY` | action endpoint, signing, order or withdrawal capability | fail | stop and rebuild from canonical main |
| `R1-INC-003-ORIGIN_ESCAPE` | non-allowlisted origin or cross-origin redirect | fail | preserve safe evidence and inspect request construction |
| `R1-INC-004-CAPACITY_BREACH` | byte, timeout, attempt, request or declared-weight limit exceeded | fail | new preregistered contract revision |
| `R1-INC-005-CORE_ROUTE_FAILURE` | core response-class mismatch | fail | no successor inventory; diagnose route/schema/access |
| `R1-INC-006-NONCORE_ROUTE_FAILURE` | core passes and non-core fails | partial | repair or explicit reviewed scope decision |
| `R1-INC-007-ARCHIVE_ACCESS_RESTRICTED` | recognized S3 access error | route may pass; access restricted | separate access and cost design |
| `R1-INC-008-EVIDENCE_COVERAGE` | missing, duplicate or reordered observation | integrity failure | reject run and inspect artifact |
| `R1-INC-009-HASH_MISMATCH` | contract, collector, request, response, output or artifact mismatch | integrity failure | reject run and preserve competing bytes |
| `R1-INC-010-WORKFLOW_IDENTITY` | reviewed commit, run, job or artifact cannot be bound | attestation blocked | do not promote status |
| `R1-INC-011-RAW_DATA_LEAK` | raw account or market values in logs/artifact | privacy failure | stop, contain and repair minimization |
| `R1-INC-012-TEST_DESIGN_DEFECT` | test rejects legitimate safe behavior | pre-run rejection | repair before any accepted run |

## Repair discipline

Do not relabel a failed run, replace output under an existing run identity or
materially repair an executed probe in place. A change to routes, response
classes, capacity, decision rules or security boundaries requires a new exact
commit and run.

Credential, action-capability, raw-data and hash incidents block successor work
until reviewed. Every retry receives distinct workflow and artifact identities.
