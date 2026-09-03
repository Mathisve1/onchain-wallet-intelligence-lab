# Progress

A running record of where the work stands, updated as each stage closes. It is
a navigation aid, not an authority: `PROJECT_STATE.md` remains the canonical
state, `DECISION_LOG.md` the canonical decisions and
`governance/REPOSITORY_MANIFEST.sha256` the canonical file set. Where this file
and those disagree, they win.

## Where we are

| | |
|---|---|
| repository | `Mathisve1/onchain-wallet-intelligence-lab` |
| working clone | `C:\Users\mathi\Desktop\owil-repo` |
| lifecycle stage | `PRE_ARCHIVE_INVENTORY` |
| research status | `REQUIRES_FURTHER_TESTING` |
| empirical result | `null` |
| market data ingested | `false` |
| trading authorizations | all `false` |

Two tracks are open at once and they do not block each other.

**Archive track** — reconstructing wallet ledgers from the S3 archive. Blocked
at R11: its single-use 72-object run completed every request but emitted no
wallet features after detecting repeated legacy `wallet+tid` observations, and
the preregistered duplicate-count retention promise was not met. R11A freezes a
four-layer identity diagnostic over exactly those same 72 objects and awaits
implementation merge, then one hash-bound owner approval.

**Live-data track** — observing the public venue in real time over the
read-only `/info` endpoint and public websocket. The pipeline is built and
tested but has no governance record, so it cannot merge yet. L1 is that record.

## Stage log

Newest last. Each row is a stage that actually closed, with the evidence that
closed it.

| Stage | Date | Outcome | Evidence |
|---|---|---|---|
| Phase 0 — closed intake | 2026-08-06 | `CLOSED` | DEC-001…DEC-009 |
| Public technical probe R1 | 2026-08-07 | `PUBLIC_PROBE_PASS` | run `31200124642` / job `92937868268` / artifact `9002459643` |
| AWS OIDC identity | 2026-08-08 | `ATTESTED_STS_IDENTITY_MATCH` | run `31250176507` / job `93085194965` / artifact `9019744292` |
| Archive metadata canary R0 | 2026-08-08 | `ATTESTED_CONSUMED_PARTIAL_FAILURE` | run `31260043109`; 2 of 7 prefixes listable, 5 failed on signing Region |
| Region probe R1 | 2026-08-08 | `REGION_PROBE_R1_PASS` | run `31273770895`; `hl-mainnet-node-data` is `ap-northeast-1` |
| Node-data canary R2 | 2026-08-08 | `FIVE_PREFIX_METADATA_LISTABLE` | run `31280640653`; 5/5 requests, 125 entries |
| Multi-hour feature R10 → R10D | 2026-08-09…11 | `CONSUMED_COMPLETE_LEGACY_REDUCER_MECHANICS` | R10D run `31420197671`; canonical-identity equivalence still `UNKNOWN` |
| 72-hour persistence R11 | 2026-08-11 | `CONSUMED_UNRESOLVED` | run `31436753081`; 72/72 GETs, zero wallet-feature rows |
| R11 evidence closure | 2026-08-11 | `CLOSED` | merge `f7aa612d2a5638cce0fd197f57efea4b787f87f1` |
| R11A identity diagnostic | 2026-08-11 | `PREREGISTERED_NO_EXECUTION` | DEC-038; no approval, workflow or release |
| Live-data pipeline build | 2026-09-03 | `BUILT_UNGOVERNED` | branch `feature/live-data-pipeline`, head `5397434`; 199 tests pass |
| L1 live-data preregistration | 2026-09-03 | `PREREGISTERED_NO_EXECUTION` | DEC-039; `L1_PREREGISTRATION_VALID`; 25 governance tests; 893 manifest files |

## Open gates

Ordered by what unblocks the most.

1. **L1 owner approval** — one hash-bound human approval of the L1 envelope,
   using the exact text in
   `research/wallet_copyability/live_data/HUMAN_APPROVAL_TEMPLATE.md`. Only the
   owner can give this; it cannot be produced from inside the repo. Until it
   exists the pipeline stays inert.
2. **L1 single-use execution release** — bound to the canonical implementation
   commit, after approval. Merging the implementation is not a release.
3. **R11A implementation merge** — review and merge the fully inert R11A
   implementation and workflow candidate, kept outside `.github/workflows`.
4. **R11A owner approval** — one hash-bound approval of the diagnostic scope,
   role reuse and the 72-request / zero-retry envelope.
5. **R11A activation and run** — separate workflow-installation,
   release-candidate and single-use activation stages, then one diagnostic run.
6. **R11 closure and R12 readiness** — evidence-gated, after the diagnostic
   resolves the duplicate root cause.

## Known issues

- `tests/test_archive_inventory_r11a_activity_storage_schema.py` and
  `tests/test_archive_inventory_r11a_storage_schema.py` fail on Windows.
  `research/archive_inventory/r11a_implementation/storage.py` reads
  `stat.st_blocks`, which CPython only populates on POSIX. Pre-existing,
  unrelated to the live-data work, and green in Linux CI. Everything else
  passes: 1217 of 1219 local, 199 of 199 live-data.
- `C:\Users\mathi\Desktop\onchain-wallet-intelligence-lab-main` is a stale
  extracted copy, not a clone. It predates `results.py`,
  `test_live_data_coverage.py` and the whole `r11a_corrective` work. Do not
  edit it; `owil-repo` is the repository.

## Standing boundaries

These hold at every stage above and are not renegotiated by progress.

- Read-only. No credential, no signature, no order endpoint, no write path.
- No wallet ranking, alpha claim or copyability interpretation before Phase 3
  passes its own gate.
- Every network execution needs its own preregistration, its own hash-bound
  human approval and its own single-use release. A consumed release is never
  rerun and never rewritten.
- Deterministic code is canonical for ledgers, P&L, clusters and risk. AI
  summarizes and challenges; it does not compute the canonical numbers.
