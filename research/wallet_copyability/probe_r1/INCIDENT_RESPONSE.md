# Incident Response — Hyperliquid Public Probe R1

Every abnormal outcome receives a durable classification. Failed or partial runs are never overwritten.

| ID | Trigger | Immediate result | Required action |
|---|---|---|---|
| `R1-INC-001-CREDENTIAL_CAPABILITY` | secret, auth/cookie header, private key or persisted checkout credential | `PUBLIC_PROBE_FAIL` | stop, secure/rotate if needed, preserve safe evidence, security review |
| `R1-INC-002-EXECUTION_CAPABILITY` | `/exchange`, signing, order or withdrawal capability | `PUBLIC_PROBE_FAIL` | stop; clean branch from canonical main |
| `R1-INC-003-ORIGIN_ESCAPE` | non-allowlisted origin or cross-origin redirect | `PUBLIC_PROBE_FAIL` | preserve route evidence; inspect request construction |
| `R1-INC-004-CAPACITY_BREACH` | bytes, timeout, attempts, requests or declared weight exceed contract | `PUBLIC_PROBE_FAIL` | new preregistered contract revision required |
| `R1-INC-005-CORE_ROUTE_FAILURE` | core response class mismatch | `PUBLIC_PROBE_FAIL` | no inventory; diagnose endpoint/schema/access |
| `R1-INC-006-NONCORE_ROUTE_FAILURE` | core passes, non-core fails | `PUBLIC_PROBE_PARTIAL` | repair fixture/contract or explicit reviewed scope decision |
| `R1-INC-007-ARCHIVE_ACCESS_RESTRICTED` | valid S3 error response | route may pass; archive restricted | design requester-pays/access gate; no completeness claim |
| `R1-INC-008-EVIDENCE_COVERAGE` | missing, duplicate or reordered observation | integrity failure | reject run; inspect collector/artifact |
| `R1-INC-009-HASH_MISMATCH` | contract, collector, body, output, artifact or ledger mismatch | integrity failure | reject run; preserve competing bytes |
| `R1-INC-010-WORKFLOW_IDENTITY` | commit/run/job/artifact cannot be bound | attestation blocked | do not merge or open inventory |
| `R1-INC-011-RAW_DATA_LEAK` | raw balances, fills, positions, P&L or transfers in logs/artifact | security/privacy failure | stop; remove exposed artifact where permitted; repair minimization |
| `R1-INC-012-TEST_DESIGN_DEFECT` | test rejects legitimate negative evidence | pre-run rejection | close PR; clean successor from main |
| `R1-INC-013-WEIGHT_ACCOUNTING_DEFECT` | declared weights do not conservatively cover registered result classes | pre-run rejection | replace contract before any accepted run |

## Repair discipline

Never relabel a failed run, replace output under an existing run identity or materially repair an executed probe in place. A change to routes, response classes, capacity, decision rules or security boundaries requires a new exact revision. Documentation clarification may be additive but cannot change historical result bytes.

Credential, execution-capability, raw-data leak and hash-mismatch incidents block successor work until reviewed. Later retries are distinct workflow runs with distinct evidence.
