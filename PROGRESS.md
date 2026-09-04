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
| L1 owner decision | 2026-09-03 | `APPROVED_RELEASED` | DEC-040; approval SHA-256 `d87df45c…dede1b` bound to `e3610cd`; one decision, three gates, no precedent |
| L1 session 001 | 2026-09-03 | `CONSUMED_INSIDE_ENVELOPE` | 839 wallets discovered, 7 backfilled, 130457 fills, 2012 weight; DB SHA-256 `b5da970d…77c9`; 3 backfills hit HTTP 429, not retried |
| Copyability simulator | 2026-09-03 | `BUILT_FIXTURE_TESTED` | `src/copyability`, 11 modules, deterministic, network-free; latency grid, full cost model, typed P&L separation, certified-interval scoring, look-ahead probe |
| L1 instrument validation | 2026-09-03 | `INSTRUMENT_VALIDATED_SAMPLE_UNUSABLE` | DEC-041; 7 wallets x 6 latencies on equal capital; 4 of 7 probable market makers; funding lower-bound on 5; five real-data breaks catalogued in `evidence/L1_INSTRUMENT_VALIDATION_001.md` |
| L2 proposal | 2026-09-03 | `PROPOSED_NOT_BUILT` | `research/wallet_copyability/live_data/L2_PROPOSAL.md`; waits on one owner decision |
| L2 power analysis | 2026-09-04 | `DESIGN_UNDERPOWERED_AT_14D` | `evidence/L2_POWER_001.json`: 14 d x 130 directional wallets detects only about 1.05 pt per 14 d (27 %/yr); 56 d reaches 0.53; build held for the owner's window choice |
| L2 approval | 2026-09-04 | `APPROVED_BUILD_HELD` | DEC-042; `APPROVE_HL_LIVE_DATA_L2_FORWARD_STUDY_001` SHA-256 `7caa6b24…3deb` bound to `b8c1225`; four owner corrections recorded; analysis plan drafted (`L2_ANALYSIS_PLAN.md`) |
| L1 report artifact | 2026-09-04 | `PUBLISHED_PRIVATE` | https://claude.ai/code/artifact/b95990bc-142c-4c2b-ae5a-4473a22e55f2 |
| Simulator code review | 2026-09-04 | `TEN_FINDINGS_ALL_ADDRESSED` | `code-review` skill, high effort; confirmed: silent zero funding, latency-dependent fill sets, sign-wrong lower-bound label, tautological cost check; plausible: stale prices, assumed depth undisclosed, own fills pricing own copies, truncated prefix dropped, watch coverage inferred from snapshots, study aborted by one wallet |
| L1 instrument revision 2 | 2026-09-04 | `RESCORED` | common decision cutoff, 15-min price age bound, own fills excluded from prices, funding coverage as a share, liquidity labelled assumed; 1734 to 16710 copies per wallet now unpriceable, which is the honest state of a fills-derived price source; 95 copyability tests |
| L2 two-arm approval | 2026-09-04 | `APPROVED_BUILD_HELD` | DEC-043; `APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001` SHA-256 `3ac5e20a…a8b4` bound to `3edfbf3`; 600 candidates, arm A historical (90 d backfill, 30 d characterisation, 7 d buffer, 53 d evaluation), arm B forward 56 d as out-of-sample test; target 0.5 pt / 14 d |
| Candle probe | 2026-09-04 | `MEASURED` | `evidence/L2_CANDLE_PROBE_001.json`: candleSnapshot exists (1m…1d), ~5000 candles per interval rolling — 15 m reaches 52 d, 5 m 17.5 d, 1 m 3.6 d, 1 h 208 d; 110 of 113 cohort coins complete at 15 m with max gap 15 min; the approved 53-day arm A window is not coverable at 15 m, 45 days are |

## Open gates

Ordered by what unblocks the most.

1. **Merge `feature/live-data-pipeline`** — preregistration, decision,
   evidence, discovery, the coverage fixes and `src/copyability` are on the
   branch (draft PR #153). Needs exact-head Linux CI; two `st_blocks` tests
   fail only on Windows.
2. **Arm A window decision** — DEC-043 replaced the 14-day window with two
   arms. The candle probe shows an independent 15-minute price series exists
   only for the last 52 days (rolling), so the approved 53-day historical
   evaluation cannot be covered at the 15-minute age bound. The owner chooses
   A-45 (45 days at 15 m), A-53 (oldest 8 days on 1-hour candles, flagged), or
   arm B alone. Retention rolls daily, so T0 and the candle fetch follow the
   decision immediately. No L2 code is written until then; the analysis plan
   (`L2_ANALYSIS_PLAN.md`) is drafted for all three.
3. **Fixes that precede any collection** — response-size weight charged
   locally, `userFunding` paged past 500 rows, the public tape kept connected
   for evaluation prices, one common window for every wallet.
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
