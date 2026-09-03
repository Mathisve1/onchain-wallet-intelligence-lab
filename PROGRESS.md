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

## R11A review (2026-09-03)

The R11A work is not one branch but a stack of five open draft PRs, each
containing the one below it. `#152` is the tip and contains `#151`, `#150` and
`#149`, which in turn sit on `#148`. Two branches, `research/r11a-v2-implementation`
and `research/r11a-corrective-core-v2`, both dated 2026-08-11, are outside the
stack and look superseded by the corrective R7 line.

| PR | Branch | What it adds |
|---|---|---|
| `#148` | `research/r11a-corrective-r3` | R11A R7 corrective package; base of the stack |
| `#149` | `governance/r11a-post-green-g1` | Post-GREEN owner-approval readiness binding |
| `#150` | `governance/r11a-owner-approval-001` | Records the exact G1 owner approval |
| `#151` | `governance/r11a-post-approval-validator-alignment` | Aligns the post-approval validator chain |
| `#152` | `governance/r11a-owner-review-model-correction` | Corrects the owner-review model; cumulative tip |

What the review found, on the tip:

- The stack records a **hash-bound owner approval** dated 2026-08-26, sourced as
  `EXPLICIT_CHAT_APPROVAL_EXACT_BLOCK` and attributed to the owner by name. It
  binds software GREEN head `443500de54917417276c39a635ae444458d03b0b`, an
  EUR 0.50 one-time ceiling, and a 72-object / zero-retry / no-LIST / no-HEAD
  envelope. Its own `record_review_status` is still
  `AWAITING_INDEPENDENT_EXACT_HEAD_REVIEW`. Merging it flips
  `r11a_owner_approval_present` from `false` to `true`.
- The approval targets diagnostic `HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-002`,
  not the `-001` frozen on `main`. The corrective line has moved on from the
  preregistration currently recorded in `PROJECT_STATE.md`.
- The tip **installs `.github/workflows/r11a-r7-dev.yml`** and modifies `ci.yml`.
  The frozen gate text says no `.github/workflows` installation may appear at
  this stage. In substance the file is inert — `permissions: contents: read`
  only, so OIDC is structurally impossible, and it carries no AWS, S3, secret or
  `id-token` reference, running its tests under a network-deny harness — but it
  contradicts the gate as literally written, and it is hard-scoped to PR `#148`,
  which makes it dead weight once that PR closes.
- The actual diagnostic workflow candidate remains correctly outside
  `.github/workflows`, and `r11a_workflow_installed`, `r11a_release_present`,
  `r11a_aws_oidc_authorized` and `r11a_get_object_authorized` all stay `false`
  on the tip.

Not merged. Merging a recorded human approval, and resolving the gate-text
conflict, are both owner decisions rather than review outcomes.

## Known issues

- `tests/test_archive_inventory_r11a_activity_storage_schema.py` and
  `tests/test_archive_inventory_r11a_storage_schema.py` fail on Windows.
  `research/archive_inventory/r11a_implementation/storage.py` reads
  `stat.st_blocks`, which CPython only populates on POSIX. Pre-existing,
  unrelated to the live-data work, and green in Linux CI. Everything else
  passes: 1217 of 1219 local, 199 of 199 live-data.
- `C:\Users\mathi\Desktop\onchain-wallet-intelligence-lab-main` is an unpacked
  zip with no `.git`. Its contents match `origin/main`, so it looks current,
  but it can never produce a branch, commit or PR and it lacks everything on
  the feature branches. `owil-repo` is the repository; do not work in the zip.

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
