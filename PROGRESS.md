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
read-only `/info` endpoint and public websocket. Merged to `main` on
2026-09-08 (PR #153): the L1 preregistration, owner decision and consumed
release, the `src/copyability` simulator, the L2 two-arm collector and two
review rounds. What remains is the L2 collection run under the approved
envelope, which nothing on `main` schedules or starts on its own.

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
| Arm A window decision | 2026-09-04 | `DECIDED_A45` | DEC-044; `APPROVE_HL_LIVE_DATA_L2_ARM_A_WINDOW_001` SHA-256 `df082701…ecc96` bound to `3311338`; arm A = T0-52 to T0-7 on 15-minute candles, 15-minute freshness, no mixed resolution; B decisive, A is the early read and the survivorship measurement; `L2_ANALYSIS_PLAN.md` frozen at `1833f34` |
| L2 pipeline build | 2026-09-04 | `BUILT_VERIFIED` | DEC-045; phases 1 to 8 of `L2_BUILD_PLAN.md`: size-weighted rate limiting, paged funding, `candleSnapshot` with schema v4, arm B `sweep` and `mids`, cohort discover/characterise/freeze with the 200-wallet hard stop, arm A candle fetch, opening positions in the simulator, arm B health script; every phase blind-verified; 1522 tests pass locally (two Windows-only `st_blocks` failures remain) |
| Plan amendment (reading rules) | 2026-09-05 | `FROZEN_AMENDED_PRE_T0` | DEC-046; owner's reading of arm A, the `EXPLORATORY` rule and the report order written into `L2_ANALYSIS_PLAN.md` before T0 |
| Live-data review rounds | 2026-09-06…08 | `SEVENTEEN_FINDINGS_ALL_ADDRESSED` | `20af38f..eb3f30a`, 30 commits, one concern each; fifteen findings on the collector and simulator plus two from a second `src/copyability` pass (skipped copies desynchronising the follower; freeze characterising on an uncertified window); concurrent `sweep_wallet` work landed with the venue's documented surcharge divisors; ruflo hook and manifest-hygiene fixes; every commit verified alone, `1555` tests pass in a clean checkout, `REPOSITORY_VALIDATION_PASS` |
| Live-data merge | 2026-09-08 | `MERGED` | PR #153, merge `2f427c72128a2df15395163ca553ad889596ed01` (`1d21875` + `eb3f30a`), after exact-head ubuntu CI on `eb3f30a` |

## Open gates

Ordered by what unblocks the most.

1. **L2 collection run** — the pipeline is built, reviewed twice and merged
   (`2f427c7`); the collection modules have had their `code-review`. Next:
   discovery sessions, a 90-day characterisation backfill, the freeze with
   its 200-wallet hard stop, the arm A candle fetch and the arm A runner,
   all from the frozen plan at `1833f34`. Arm B then runs 56 days of
   operator-started sweeps with health checks only. Every step is started
   by the operator; nothing on `main` schedules it.
2. **Validator hardening** — the L1 validator honours the DEC-043 widening
   from the approval file's key line without checking that file's SHA-256
   against DEC-043; add the comparison before the arm A report.
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

## Live-data review (2026-09-06)

A code review of the `feature/live-data-pipeline` branch found fifteen defects
across `src/live_data`, `src/copyability` and the L2 collector. All fifteen
were reproduced before being fixed, and each carries a regression test. They
are committed one per concern so any single one can be reverted alone.

The four that would have changed a reported number or hidden a real outage:

- `run_study` never passed `opening_positions`, so the only orchestration path
  a study runs still scored a fill closing a pre-window position as an inverted
  open — the defect the 2026-09-04 round documented as fixed. `replay_positions`
  existed for exactly this and had no caller outside its own test. On the new
  regression scenario the scored gross moves from `-90` to `+9`.
- Arm B health filtered sweeps by `wallet_address`, which a sweep run never
  sets, so every wallet reported a permanently stale sweep once `--stale-hours`
  elapsed regardless of sweep health, and per-wallet failures inside a completed
  run counted as zero. The tests built rows in a shape the collector never
  writes, so they confirmed the bug rather than catching it.
- The candle probe scored a `~5000`-row-capped response against 90 days of
  candles, so a perfect series scored `0.579` and every cohort coin landed in
  `uncovered`; it also charged a flat 20 weight where a full response costs
  103, which is the recorded cause of its own three HTTP 429s. The committed
  code could not have produced `L2_CANDLE_PROBE_001.json`; it now can. The
  retained evidence was not touched and the probe was not re-run.
- The fills walk recorded coverage past a millisecond it had knowingly skipped,
  so the ledger certified intervals containing a gap the collector had itself
  written down.

Completed on 2026-09-08 from concurrent work left uncommitted in the clone:

- A sweep now writes one `sweep_wallet` run row per wallet in the exact shape
  `backfill_wallet` uses, beside the cohort-level `sweep` summary. The summary
  alone was unreadable downstream: the coverage ledger and the health check
  key on `wallet_address` and `coverage["window"]`. Both consumers read the
  new rows, and where they exist the digest embedded in the summary is not
  read a second time, so nothing is counted twice. `load_funding_truncation`
  reads them too: a sweep that hits the funding cap truncates the wallet just
  as a backfill would.
- The response-size surcharge in `hyperliquid_rest.py` moves from one guessed
  divisor (60 rows per unit for every list response, recorded in DEC-045) to
  the venue's documented per-type values: one unit per 20 items for
  `userFills`, `userFillsByTime` and `userFunding`, one per 60 for
  `candleSnapshot`. Verified against the venue's rate-limits page on
  2026-09-08. A 500-row fills page therefore costs 45 weight, not 28; the
  budget itself (1200 per minute) and every base weight are unchanged, and the
  L1 validator still passes.
- The candle walk stops, and says so in the run's notes, when a page makes no
  backwards progress, instead of spending the page cap re-fetching the same
  candles and reporting a clean stop.

Second pass over `src/copyability` (2026-09-08; the dedicated reviewer for
that package never ran in the first round):

- A copy the simulator could not price left the follower's position behind
  the source's, so the source's later exit was copied as an *opening* trade
  on the opposite side — the inverted-position defect of 2026-09-04 again,
  triggered mid-window rather than at its edge, and the L1 evidence records
  thousands of unpriceable copies per wallet. The follower now mirrors the
  source's position at every priced action: a missed round trip is not
  traded at all, and a missed entry is caught up at the next priced action in
  that coin (counted in `catch_up_fills`). Fully priced copies are unchanged.
  `L1_INSTRUMENT_VALIDATION_001` predates this and is not re-run.
- `cohort.characterise` certified the characterisation window by assertion,
  and the freeze pipeline never consulted the coverage ledger, so a wallet
  whose backfill stopped inside the window was classified on the fragment
  that was collected — an active wallet reading as idle, and idle reading as
  `INSUFFICIENT_FILLS`. `select_cohort` now takes the ledger's `certify`;
  the freeze passes it, and such a wallet is excluded first as
  `WINDOW_UNOBSERVED`, a new stage counter.

Two governance notes from the same round:

- `governance/regenerate_manifest.py` and `seal_r11a_v2_preregistration.py`
  wrote their artifacts in text mode, which rewrites every line as CRLF on
  Windows. No `--check` catches it, because `read_text` normalises newlines on
  the way back in. Both now pass an explicit newline.
- `governance/seal_r11a_implementation.py` has the same defect on this
  branch, and the sealed `storage.py` has the Windows `st_blocks` failure;
  both are already fixed on the open R11A stack (`#148`–`#152`, tip
  `c03fcad`), whose snapshot this branch predates. Nothing to do here.
- Corrected on 2026-09-08 after a wrong turn: `seal_r11a_implementation.py
  --check` reports `OUT_OF_DATE` against the live tree **by design**. The
  contract is an immutable seal of the then-current implementation test;
  `governance/r11a_repository_provenance.py` pins that historical hash and
  projects the old bytes back into an authenticated copy before
  `validate_r11a_implementation.py` runs there, which is the governing check
  (ubuntu CI on the stack). A re-seal to the live bytes (PR `#154`) was
  rejected by that check and withdrawn. Also: the G2 owner-approval record
  pins the combined digest of every file under `.github/workflows`, so no
  workflow file on that stack changes outside the approval process.
- `validate_l1_live_data_preregistration.py` accepted a watch command that
  omitted `max_iterations` (the default of 0 satisfied the cap) and raised
  `TypeError` on a non-integer cap. Every watch step must now record an
  integer cap in `(0, 1000]`.

## Arm A runner (2026-09-09)

Phase 7's runner did not exist. DEC-045 and the stage log record phases 1 to 8
as built and blind-verified; the opening-position and candle-price pieces of
phase 7 were, but the script that runs arm A over the frozen cohort and writes
`evidence/L2_ARM_A_001.json` was never written. Built on 2026-09-09 as
`live_data_collector/arm_a_runner.py`, `arm_a_report.py` and
`arm_a_statistics.py`, with an offline synthetic-store test suite, and put
through an adversarial verification round before it was accepted. Two blockers
came out of that round:

- **Matched-random peers were not scored under the target's convention.**
  `simulate._baseline_returns` never forwarded the common decision cutoff or
  the 15-minute price-age bound to `baselines.matched_random`, so a peer fill
  after the cutoff, or a peer copy priced on a quote the target would have
  refused as stale, moved `M_i` while `R_i` excluded it. A pre-existing
  `src/copyability` defect, reproduced and fixed with regression tests; every
  study that reported `matched_random` before this date carried it.
- **The peer pool cannot be the cohort itself.** With peers drawn from the
  cohort, `mean(d_i)` is algebraically blind to any return the cohort earns in
  common (a Monte Carlo at three times the target effect read as zero). The
  plan says peers are "wallets of similar activity" and does not fix the pool;
  the runner now draws them from every characterised wallet the ledger
  certifies over the window, records the pool's size and hash, and says so in
  the file's limitations. **Owner decision before T0:** confirm that pool
  definition, ideally as a pre-T0 amendment to `L2_ANALYSIS_PLAN.md` in the
  manner of DEC-046, so the primary measure's contrast is fixed before any
  number exists.

The runner also verifies the freeze record's own hash, refuses a cohort under
the plan's minimum unless told in so many words that it is an underpowered dry
run, labels a sub-minimum primary a case study rather than a read, measures
survivorship on every fill with the cohort as denominator, carries the four
never-drop disclosures and the candle provenance beside the primary, bounds
everything it reads to T0, checkpoints after every wallet, and keeps wall-clock
out of the evidence so identical inputs give a byte-identical file. Expect
hours of single-threaded runtime on a 300-wallet cohort.

## Arm B runner and the shared arm core (2026-09-09)

Arm B's runner was built by generalising arm A's rather than copying it. The
run is now one module, `live_data_collector/l2_arm_runner.py`, driven by an
`ArmSpec` that each arm declares in its own thin file (`arm_a_runner.py`,
`arm_b_runner.py`); the report and statistics helpers were renamed to
`l2_arm_report.py` and `l2_arm_statistics.py` and the evidence keys that named
candles now name the price source (`price_source`, `price_provenance`,
`price_series_span_by_coin`). Both arms are computed by the same code, so a
difference between their files is a difference in the data.

What arm B adds, in order of what the plan requires of it:

- **A closure guard.** The approval forbids interim result inspection, so the
  runner raises before reading a fill unless the coverage ledger certifies at
  least one cohort wallet over the whole of `[T0, T0+56d]`. Exit 2, no file.
- **Mids as the price series**, with the same 15-minute freshness bound as arm
  A, and a provenance block that counts the polled rows per coin and their mean
  spacing instead of candle fetch runs.
- **The decision rule.** B decides: `GO_TO_ENTITY_CLUSTER_RESEARCH` if the
  rounded lower bound of the 95 percent interval is at or above 0.5 points per
  14 days, `NO_GO_NO_COPYABLE_ALPHA` if the rounded upper bound is below it,
  `REPAIR_AND_RERUN` otherwise, and `null` for a case study or an unmeasurable
  primary. Arm A's file keeps `decision: null` by construction.
- **Survivorship inflation** against arm A's file when `--arm-a-json` is given:
  `mean d_A - mean d_B` as a number, plus a flag for the A-negative, B-GO
  pattern that obliges a written diagnosis. Never a gate.

Building the closure guard exposed a defect in the coverage ledger.
`sweep.py` resumes a wallet at `latest_fill + 1`, and a walk cut at the page
cap is covered until the last fill's own millisecond, so consecutive sweep rows
meet as `[a, b]` and `[b+1, c]`. `CoverageLedger._merge` treated that as a gap.
On integer-millisecond timestamps no millisecond is unobserved there, and on
real data a single page-cap cut anywhere in the 56 days would have made arm B
refuse forever. The merge rule now treats one-millisecond adjacency as
touching; a two-millisecond gap is still a gap, and the tests say which is
which.

### Second adversarial pass (2026-09-09)

Three of four lenses ran (the completeness critic hit the account's session
limit twice; a third round is owed). One blocker and a set of should-fixes, all
applied in the shared core:

- **Peers were priced only on the cohort's coins.** The market was built over
  the coins the cohort traded, so a pool wallet with a fill on any other
  in-scope coin threw inside the baseline, was swallowed, dropped out of
  `M_i`, and was still listed under `matched_peers_by_wallet`. On real data
  that is the broad-book peers, systematically. The market is now built over
  every pool wallet's in-scope coins; `baselines.matched_random` returns the
  peers that entered the mean and the sampled peers that dropped, with the
  reason; the file writes per wallet the contributing peers, the drops, their
  count and the cohort share of the peers, and for the pool its cohort and
  non-cohort counts and the mean cohort share.
- **Arm A's ledger was not bounded.** A `sweep_wallet` row written weeks after
  T0 could certify a wallet the T0 run refused and move the pool, the
  refusals and every `d_i`. Arm A now builds its ledger and its
  funding-truncation map from backfill rows only, and each file carries a
  `ledger_snapshot` (runs consulted, latest finish, hash of the run ids);
  a test writes a post-T0 sweep and asserts the pool hash and every `d_i`
  are unchanged.
- The plan's minimum of 200 is not the freeze record's to lower: a record
  frozen with a smaller `minimum_evaluable` is refused, not evaluated at it.
- An unspanned benchmark is missing data, not a result: refusal, no file
  (buy-and-hold and momentum apply no age bound at their exit mark). What
  still breaks after that carries `BROKE_SEE_WHAT_BROKE`, no decision, and
  `broke=n` on the log line. The checkpoint is stamped `PARTIAL_CHECKPOINT`
  with `decision: null`, is written before progress is reported, and on any
  stop is kept as `.aborted.json`; no exception escapes without the stopped
  line.
- The span rule now admits what the freeze's post-check admits (two intervals
  on close-stamped candles), the matched-random tolerance is threaded through
  `StudyConfig` instead of being disclosed beside it, the out-of-scope count is
  bounded to the evaluation window, and `DRY_RUN_UNDERPOWERED` is stamped
  only when the cohort really is under the minimum. Arm B's closure guard also
  requires the latest completed collection run to have finished at or after
  the window end.
- The tests lens ran mutation testing and found the suite pinned length, not
  edges, and subsets, not sets. Added: strict peer sets, the literal window,
  the frozen parameter block compared against the `StudyConfig` actually
  built, T0 bounding (funding and fills written after T0 leave the file
  byte-identical), survivorship on out-of-scope fills through the runner,
  the first edge of the span rule, stale skips under the freshness bound,
  checkpoint ordering, the abort path, the record-supplied minimum, the
  characterisation-window check, and the scope split with priceable coins.

Still open from that pass, for the owner with the pool decision: the pool
contains wallets the selection kept out of the cohort (market makers,
rebate-dependent, under-characterised), whose taker copies are bad a priori
and pull `M_i` down; the file now discloses the composition, the plan
amendment (PR #157) fixes the rule, and neither corrects for it.

### Third adversarial pass (2026-09-09)

Four lenses of five (the completeness critic hit the account limit again, as in
round two; a critic pass is still owed). Refuted, with four blockers. Two came
from round two's own fixes, which is the argument for running the round:

- **A wallet that deploys nothing aborted the whole arm.** Round two changed
  the matched-random return type; the nothing-deployed path still returned the
  old shape, so the first idle or fully-out-of-scope cohort wallet raised an
  `AttributeError` that took the run down with exit 2 and no file. The cohort
  cannot be edited after T0, so one such wallet would have made the arm
  unrunnable. Arm B expects stopped wallets by design.
- **The peers named in the file were the wrong latency's.** The study kept the
  peers of the last latency simulated (15 minutes), and the file wrote them as
  the peers behind the primary at 30 seconds. A peer inside the primary's mean
  could be listed as dropped. The simulator now keeps the matched-random
  result per latency and the file writes the primary's, labelled with it.
- **A post-T0 backfill still moved arm A's pool.** Round two bounded arm A's
  ledger by collection mode, which a backfill written after T0 (a re-backfill,
  a widened pool) passes. The bound is now time: rows finished by T0, and the
  freeze records a hash of exactly those rows, which arm A refuses to run
  without matching. The freeze also refuses a T0 that precedes its own last
  collection row.
- **The survivorship inflation subtracted any file that said arm A.** A
  different cohort, another plan commit, a dry run, a broke file and a
  checkpoint all produced `available: true` and a number. Arm A's file is now
  read and judged before the hours of scoring, so a wrong file refuses in
  seconds, and `a_negative_b_positive` follows arm A's written reading and arm
  B's written decision rather than the two point estimates.

Also applied: arm B's closure guard now requires a completed closing sweep row
for **every** cohort wallet, not one certified wallet and any completed run, so
a sweep that died at wallet 250 of 300 can no longer produce a decision that a
later rerun contradicts; a pool that contains no wallet outside the cohort
breaks the run rather than labelling it, because the mean cancels exactly the
common return the study is looking for; arm B's file no longer carries arm A's
reading vocabulary (its verdict is its decision, and `reading` is null); the
mids series is disclosed as a deviation from the plan's wording, and its
provenance counts polls separately from sweeps and reports the widest gap and
how many exceed the freshness bound; the span rule takes both edges from the
arm, so arm B tolerates the freshness bound at the end as well as the start;
`--overwrite` is required to replace an evidence file and an abort is kept as
`.aborted-<n>.json`; a Ctrl-C is reported and keeps its partial before it
propagates; the freeze records a hash of each scope coin list, so the same
number of different coins no longer passes the scope check.

Two collector defects were found underneath all this. The sweep resumed from
the newest stored fill, which steps over a page-cap cut (proven only to the
millisecond before that fill) and over anything a websocket session wrote, so
the skipped range was never requested again; it now resumes from the earlier of
the newest fill and the last millisecond a walk proved observed. And the
loader's forced-cursor guard keyed on whether a walk completed rather than on
which bound rule wrote it; collection now marks its coverage with the rule, and
the ledger trusts a marked bound and distrusts an unmarked one. The websocket
mode no longer certifies anything for L2: a watch row claims its interval from
the run's start rather than from the subscription it was given.

The tests lens mutation-tested the suite again. Pinned since: the peers that
contributed and those that dropped, the decisive path for both arms (every run
in the suite was a case study, so a wiring regression that never decided passed),
a coin leaving scope changing no number, the closure guard's two halves
separately, the tolerance actually reaching the peer selection, the exact
ledger-snapshot digest, the disclosure denominators, both span edges, and the
arm B scope bound.

## Known issues

- `tests/test_archive_inventory_r11a_activity_storage_schema.py` and
  `tests/test_archive_inventory_r11a_storage_schema.py` fail on Windows.
  `research/archive_inventory/r11a_implementation/storage.py` reads
  `stat.st_blocks`, which CPython only populates on POSIX. Pre-existing,
  unrelated to the live-data work, and green in Linux CI. Everything else
  passes: 1545 of 1547 local after the 2026-09-06 review round.
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
