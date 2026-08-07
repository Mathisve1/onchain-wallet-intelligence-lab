# Incident Response — Hyperliquid Public Probe R1

Every abnormal outcome receives a durable classification. No failed or partial run is silently overwritten.

## Incident classes

| ID | Trigger | Immediate status | Required action |
|---|---|---|---|
| `R1-INC-001-CREDENTIAL_CAPABILITY` | secret, token, Authorization/Cookie header, private key or persisted checkout credential appears | `PUBLIC_PROBE_FAIL` | stop; rotate any exposed credential; preserve logs; security review |
| `R1-INC-002-EXECUTION_CAPABILITY` | `/exchange`, signing, order or withdrawal capability appears | `PUBLIC_PROBE_FAIL` | stop; do not run; new clean branch from canonical main |
| `R1-INC-003-NETWORK_ORIGIN_ESCAPE` | non-allowlisted origin or cross-origin redirect | `PUBLIC_PROBE_FAIL` | preserve evidence; inspect request construction and redirect chain |
| `R1-INC-004-CAPACITY_BREACH` | byte, timeout, retry, request-count or declared-weight ceiling exceeded | `PUBLIC_PROBE_FAIL` | stop; adjust only through a new preregistered contract revision |
| `R1-INC-005-CORE_ROUTE_FAILURE` | any core probe does not match its response class | `PUBLIC_PROBE_FAIL` | no inventory; diagnose endpoint, schema or access change |
| `R1-INC-006-NONCORE_ROUTE_FAILURE` | all core probes pass but at least one non-core probe fails | `PUBLIC_PROBE_PARTIAL` | inspect whether fixture, endpoint or response contract is stale; rerun or narrow explicitly |
| `R1-INC-007-ARCHIVE_ACCESS_RESTRICTED` | valid S3 error response on one or more archive routes | route probe may pass; archive status restricted | design requester-pays/access inventory gate; no completeness claim |
| `R1-INC-008-EVIDENCE_COVERAGE` | missing, duplicate or reordered observation | integrity failure / `PUBLIC_PROBE_FAIL` | reject run; inspect collector or artifact truncation |
| `R1-INC-009-HASH_MISMATCH` | contract, collector, response, output, artifact or file-ledger hash mismatch | integrity failure / `PUBLIC_PROBE_FAIL` | reject run; preserve all competing bytes and provenance |
| `R1-INC-010-WORKFLOW_IDENTITY` | reviewed commit, run, job or artifact cannot be bound exactly | attestation blocked | do not merge or open inventory |
| `R1-INC-011-RAW_DATA_LEAK` | raw balances, fills, positions, prices, P&L or transfer data appears in logs/artifact | security and privacy failure | stop, delete exposed artifact where permitted, preserve minimal incident metadata, repair minimization |
| `R1-INC-012-TEST_DESIGN_DEFECT` | test rejects legitimate negative evidence or otherwise does not test intended capability | pre-run rejection | close PR without merge; clean successor from canonical main |

## Evidence preservation

For any incident, retain the exact commit, workflow/run/job identity, logs, artifact metadata and hashes. When privacy or secret exposure requires artifact deletion, retain only safe metadata: incident class, timestamps, commit, run/job/artifact IDs, deletion action and non-sensitive hashes when permissible.

## Repair discipline

- Never relabel a failed run as passed.
- Never replace output bytes under the same run identity.
- Never repair a materially defective experiment/probe in place after execution.
- Use a new exact commit; use a new probe revision when request scope, security boundary, expected response class, decision rule or capacity ceiling changes.
- Documentation-only clarification may be additive, but cannot alter the historical result.

## Escalation

Credential, execution-capability, raw-data leak and hash-mismatch incidents block all successor work until reviewed. A route outage may be retried only under the frozen retry rule in the same run; later retry is a new run and must remain separately attributable.
