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
review rounds. Since then, #157 to #162 (2026-09-10 to 2026-09-16): the
peer-pool amendment, both arm runners on one core with the report renderer
and the hard-stop report, the proposal of the four operator-session decisions,
the arm B price-coverage note, and the validator's binding of every approval
text to the hash the decision log records. What remains before T0 is the
owner's: the decision rows (the log ends at DEC-046 on 2026-09-16), one
amending approval text, the funnel rehearsal and a dry run of the session
runner. Nothing on `main` schedules or starts a collection run.

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
| Plan amendment (peer pool) | 2026-09-10 | `FROZEN_AMENDED_PRE_T0_ROW_PENDING` | PR #157 (`f2c34ba`): the matched-random peers are drawn from every wallet the coverage ledger certifies over the window, cohort member or not, so the primary contrast cannot cancel the cohort's common return; arm B's sweep therefore covers the whole characterised set (`--sweep-pool`). The decision row, DEC-047, is the owner's and is not yet recorded |
| Arm runners, renderer, hard-stop report | 2026-09-10 | `BUILT_VERIFIED` | PR #158 (`18bfecd`): one arm core (`l2_arm_runner.py`, `l2_arm_report.py`, `l2_arm_statistics.py`) behind `arm_a_runner.py` and `arm_b_runner.py`; `l2_arm_render.py` renders the evidence file in the order DEC-046 fixed and refuses a label the bounds do not give; the freeze writes the hard-stop report with the clock price of delay; five adversarial rounds |
| Session runner (outside the repository) | 2026-09-12 | `BUILT_VERIFIED_OUTSIDE_REPO` | `C:\Users\mathi\owil-data\loop\collect_session.ps1` v3.2 (`e356d1d`), 105 offline tests: one operator-started, bounded mids session; refuses more than 8 h or clock-started sweeps without a decision row that exists in `DECISION_LOG.md`; measures the gap since the previous session and the cumulative unpriced time; lock beside the database; Ctrl-C measured (exit 130). Four adversarial rounds, three rewrites |
| Operator-session decisions | 2026-09-12 | `PROPOSED_ROWS_PENDING` | PR #159 (`77cfc18`): `L2_OPERATOR_SESSIONS.md`, third draft after two adversarial rounds; rows A to D and two exact sixteen-line amending approval texts (`OPERATOR_SESSIONS_001` recommended, `ATTENDED_SESSIONS_001` if overnight sessions are rejected). Nothing is in force until the owner sends one text and records the rows |
| Arm B price coverage | 2026-09-12 | `BUILT_VERIFIED` | PR #160 (`7a98c26`) was merged before its verification finished and was refuted: it claimed the span check covers the window edges (it reads the whole series, so a three-day blackout passed as full coverage), summed unpriced time across coins as if it were elapsed time, and crashed when the benchmark had fewer than two in-window quotes while
another coin had a hole. PR #161 (`2d6628a`) fixed all three: `l2_arm_coverage.py` measures wall-clock unpriced time per coin from the `mids` table, head and tail included, no cross-coin sum; the arm B limitation note states it |
| Validator approval binding | 2026-09-16 | `BUILT_VERIFIED_ROW_PENDING` | PR #162 (`d280441`), four drafts: every retained approval text must hash to a backticked SHA-256 on a `DECISION_LOG.md` line naming it and is parsed as strictly as L1's; the L2 request-type read goes through that parser; the four hashes are pinned as test literals. Closes the known issue DEC-045 named; the row recording that is the owner's |
| Live-data review rounds | 2026-09-06…08 | `SEVENTEEN_FINDINGS_ALL_ADDRESSED` | `20af38f..eb3f30a`, 30 commits, one concern each; fifteen findings on the collector and simulator plus two from a second `src/copyability` pass (skipped copies desynchronising the follower; freeze characterising on an uncertified window); concurrent `sweep_wallet` work landed with the venue's documented surcharge divisors; ruflo hook and manifest-hygiene fixes; every commit verified alone, `1555` tests pass in a clean checkout, `REPOSITORY_VALIDATION_PASS` |
| Live-data merge | 2026-09-08 | `MERGED` | PR #153, merge `2f427c72128a2df15395163ca553ad889596ed01` (`1d21875` + `eb3f30a`), after exact-head ubuntu CI on `eb3f30a` |

## Open gates

Ordered by what unblocks the most.

1. **Decision rows and one approval text** — the owner's, in this order:
   DEC-047 for the peer-pool amendment (text in PR #157); a row recording
   that DEC-045's known issue is closed by #162 and what that check does and
   does not cover; one of the two amending approval texts in
   `L2_OPERATOR_SESSIONS.md` sent unmodified with its 40-character commit, and
   rows A to D with the numbers the owner assigns. The session runner refuses
   an overnight session whose row is not in the log, and the validator
   refuses an approval text whose hash is not on a log line naming it, so
   these rows unblock the dry run and the first live session.
2. **Funnel rehearsal and dry run** — a rehearsal of the funnel (discover,
   characterise, freeze) on a small candidate set, recommended in the
   operator's action list rather than prescribed by any document here, is
   the only way to learn before T0 whether 600 candidates yield the plan's
   200 evaluable wallets; below that is a pre-registered hard stop. Then one full session of 23.75 hours against a
   throwaway database, read as row B specifies, before row B is recorded.
3. **L2 collection run** — the pipeline is built, reviewed and merged. Next:
   discovery sessions, a 90-day characterisation backfill, the freeze with
   its 200-wallet hard stop, the arm A candle fetch and the arm A runner,
   all from the frozen plan at `1833f34` as amended. Arm B then runs 56 days
   of operator-started sessions and sweeps with health checks only. The
   margin between arm A's 52-day window and the venue's 52.2-day candle
   retention is 0.2 days, which leaves no room to fetch the candles later
   than the T0 day.
   Every step is started by the operator; nothing on `main` schedules it.
4. **R11A implementation merge** — review and merge the fully inert R11A
   implementation and workflow candidate, kept outside `.github/workflows`.
5. **R11A owner approval** — one hash-bound approval of the diagnostic scope,
   role reuse and the 72-request / zero-retry envelope.
6. **R11A activation and run** — separate workflow-installation,
   release-candidate and single-use activation stages, then one diagnostic run.
7. **R11 closure and R12 readiness** — evidence-gated, after the diagnostic
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

### Completeness critic (2026-09-10)

The critic that had died on the account limit in rounds two and three finally
ran. It re-verified every round-three fix against the code (all confirmed
landed) and found four blockers that no lens had looked for, because they are
not in the runners at all: they are in the order the study is operated.

- **The build plan made arm B unrunnable by construction.** Phase 9 put the
  first `mids` run *after* the freeze and after arm A's hours of scoring, while
  arm B's first quote must sit within the 15-minute freshness bound of T0 and
  cannot be collected afterwards. The plan's own order guaranteed a dead
  decisive arm that nobody would notice until day 56. Phase 9 now polls mids
  before the freeze, and the freeze refuses a T0 with no benchmark mid at or
  before it, so the order is binding rather than advisory.
- **The closing grace was a hidden three-day deadline.** A closing sweep that
  finished later than that made arm B permanently unrunnable, and the refusal
  named the wrong cause. It is now `--closing-grace-days`, written into the
  file, and the message says which wallets were not reached and what to do.
- **One unreachable wallet blocked the whole decisive arm.** The closure guard
  counted only completed sweep rows, so a wallet whose closing walk kept
  failing was a wall in front of the other 299. The plan's remedy is that such
  a wallet is excluded and counted. The guard now asks whether the closing pass
  *reached* each wallet; one that failed is reached, then refused by the
  ledger and counted, and the file names it.
- **The pool arm B needs was never collectable.** The sweep walks the freeze
  record's cohort and nothing else, so no non-cohort wallet could ever be
  certified over the forward window: the peer pool would be the cohort, and the
  run would break on day 56 with the 56 days already spent. The freeze now
  records the characterised set it read, and `sweep --sweep-pool` walks it.
  Recording and being able to sweep the set is not the same as deciding that
  the peers are drawn from it; that is still the owner's amendment (PR #157),
  and the flag stays opt-in until it is accepted.

Also from the critic: a freeze record without an instrument scope disabled every
scope check, so `scope` is now required like `ledger_snapshot`; and `health.py`,
the only inspection the approval permits during collection, now reports arm B's
three preconditions (the benchmark's first mid against T0, the pool wallets
never swept, and the wallets whose sweeps keep failing) so none of them is
discovered on day 56.

Left open deliberately, with the critic's ranking: the arm A report renderer
that the plan's fixed report order requires has no producer yet (needed before
arm A is read, which is hours after T0); the runtime and checkpoint sidecars sit
in the tree the manifest hashes, so a live run makes governance read
OUT_OF_DATE until it finishes; and the pool-collapse guard is exact equality, so
one non-cohort wallet in a large pool silences it rather than reporting the
cohort share.

### The report renderer and the transient run files (2026-09-10)

Two of the three items the completeness critic left open are closed.

`live_data_collector/l2_arm_render.py` renders a completed arm's evidence file
in the order `L2_ANALYSIS_PLAN.md` fixed and DEC-046 recorded as binding: the
answer in one sentence, the confidence interval, the survivorship measurement,
n after every filter stage, what broke, and only then the tables. The evidence
file is sorted alphabetically, which is right for a machine and wrong for that
rule, so the renderer lays the same values out in the owner's order. It
computes nothing: every figure is copied as written, and a test asserts that no
number appears in the report that the evidence does not carry. The answer
sentence is chosen by the file's own status, reading and decision fields, so a
case study cannot be rendered as a reading and arm B's answer is its decision
rather than an arm A label. It refuses a checkpoint, because the plan delivers
a report only when the arm is complete, and it names what an incomplete file
lacks.

The manifest no longer hashes the files an arm writes while it runs. A
checkpoint exists between two wallets and an aborted file until the run is
repeated; hashing them made the repository read `OUT_OF_DATE` for the hours an
arm takes, which trains a reader to ignore the one signal that says the tree
was altered. Both patterns are excluded by name and are in `.gitignore`; the
evidence file and its runtime record are still hashed, because they are
committed.

The renderer was then verified adversarially and refuted on every lens, which
is the point of rendering a result at all: a clean page with a headline answer
is the most forwardable thing this study produces. What the round found, and
what the renderer now does:

- It re-applies the plan's reading and decision rules to the interval the file
  prints and refuses a label those bounds do not give. The module that states a
  result must not be where a wrong one is laundered into prose.
- It refuses a target that is not the plan's, an arm carrying the other arm's
  verdict, a status it does not know, a schema it was not written for, and a
  file whose disclosures or limitations are empty.
- A run that broke, a dry run and an unmeasurable primary have their verdict
  row withheld. The first version printed a live reading label two lines under
  an answer that said no reading was produced.
- It adds what the plan requires and the first version dropped: the instrument
  scope as a filter stage with the fills it removed per wallet, the price
  provenance, arm B's closure block, the survivorship definitions with the
  denominator each share uses, the EXPLORATORY label the plan fixes for every
  non-primary cut, the no-copyability-claim sentence, and the A-negative/B-GO
  case as prose rather than a boolean in a table.
- Every report opens with the plan's stop rule, its question and the definition
  of d, so a reader who has not read the plan cannot mistake what they hold.
  Table cells are escaped, so a pipe or a newline in a refusal cannot hide it.

The critic also found that outcome 1 of the pre-registered reading, the hard
stop under 200 evaluable wallets, had no report producer anywhere, and that the
one figure the plan requires that report to state was computed nowhere. The
freeze now writes it beside the record: the funnel, and the clock price of the
delay measured against the probe's 15-minute retention of 52.2 days, so the
owner can see what a week of widening the pool costs arm A.

Left from the critic's list, and both are the owner's rather than mine: the
pool-collapse guard is exact equality, so one non-cohort wallet in a large pool
silences it instead of reporting the cohort share; and DEC-046 fixes a report
order for arm A only, so extending it to arm B, where the survivorship section
also carries the inflation against arm A, wants a decision.

## Session runner, owner decisions, price coverage, approval binding (2026-09-11 to 2026-09-16)

Four pieces landed between the arm runners and T0. Each was verified
adversarially before it was offered, with one exception recorded below because
it is the kind of thing this log exists to record.

**The session runner** lives outside the repository, at
`C:\Users\mathi\owil-data\loop\` in its own git, because the approval template
excludes scheduled or unattended execution and the build plan names a sleep
loop that runs unattended as an anti-pattern. It is one operator-started,
bounded mids session that stops at its bound, on Ctrl-C or on a stop file,
registers nothing and never restarts itself. Four adversarial rounds rewrote it
three times. The first version fired sweeps on a timer and called itself
attended; the second could not see the one gap the model structurally creates,
the time between two sessions; the third could be walked around with a
different log directory, a shell as the collector command, or an invented
decision number. Version 3.2 measures the gap since the previous session and
carries the unpriced time across sessions, refuses more than 8 hours or
clock-started sweeps without a decision row that exists in `DECISION_LOG.md`,
requires the collector command to be the collector itself, and finds the
previous session through a pointer beside the database. Two PowerShell 5.1
facts were measured rather than assumed: after Ctrl-C the first cmdlet in a
`finally` block ends it silently and the process exits 0, so that block uses no
cmdlet and yields exit 130 with its summary; Ctrl-Break opens the debugger.

**The four owner decisions** on what "operator-started" covers over 56 days on
one laptop are proposed in `L2_OPERATOR_SESSIONS.md` (#159): a series of
attended sessions of at most 8 hours (row A), an overnight session of at most
24 hours on conditions (row B, recommended, with its cost stated both ways),
no clock-started sweeps (row C), and a restatement of the repeated-sweeps
permission that stands only in the superseded FORWARD_STUDY_001 (row D). Two
rounds refuted the first two drafts: a false L1 precedent (a watch iteration is
a websocket pump step, not a minute) was
withdrawn (its two watch runs lasted 254 s and 209 s inside a session of about
fifteen minutes), the attended alternative was priced fairly on the L1 fill profile
(33.7 percent of fills in 09:00 to 17:00 Brussels, 14.2 percent at night, 0 to
40 percent per wallet), and the dry run was made executable under row A.

**The price-coverage note** in the arm B report is the pre-T0 change that
document commits to. PR #160 was opened and merged while its verification was
still running, and the verification then refuted it: the note claimed the span
check covers the window's edges when it reads the whole series and let a
three-day blackout pass as full coverage; it summed unpriced time across coins
and rendered the sum as elapsed time, so the plan's own healthy shape read as
110 hours where the truth was 4.6; and it crashed after scoring every wallet
when the benchmark had fewer than two in-window quotes while another coin
had a hole. PR #161 fixed all three
the same day. The rule since then is that a change is offered only after the
panel has read it.

**The approval binding** (#162) closes the known issue DEC-045 named: the
validator read the L2 approval's request-type line without checking that the
file was the one the owner approved. It took four drafts, and the history is in
the commits. The first three parsed `DECISION_LOG.md` as a table and each was
refuted by a disagreement between `str.split("|")` and the Markdown a reader
sees: a binding in a fifth column the renderer drops, an escaped pipe that
shifts every cell index so a row rendering "rejected" still bound, invisible
characters in a status cell or a hash, a real row wrapped in a fence to unbind
it. Skipping what the parser could not read was itself the bypass. The version
that holds asks one mechanical question: does each retained approval still hash
to a backticked lowercase SHA-256 stated on a log line naming it? Its limits are
in its docstring: the accepted set only grows, so a row restating a superseded
hash keeps the superseded text acceptable; every `APPROVE_HL_LIVE_DATA_*` token
on a hash-bearing line is read as an approval that ought to be retained, so a
rejection recorded with its hash would fail until an exception exists; and an
edit of text and record together is not caught. Against that last one the four
approval hashes are pinned as literals in the test suite, which CI runs, and the
manifest is byte-exact. One draft's tests mutated the owner's signed approval
texts in the working tree and restored them in a `finally`; a killed process
would have left `l2Book`, a request type DEC-039 excludes by name, in a signed
approval. The tests now run against a copy in a temporary directory.

## Known issues

- `tests/test_archive_inventory_r11a_activity_storage_schema.py` and
  `tests/test_archive_inventory_r11a_storage_schema.py` fail on Windows.
  `research/archive_inventory/r11a_implementation/storage.py` reads
  `stat.st_blocks`, which CPython only populates on POSIX. Pre-existing,
  unrelated to the live-data work, and green in Linux CI. Everything else
  passes: 1695 passed with those two deselected on the command line, measured
  locally on 2026-09-16 after the merge of #162, out of 1697 collected.
- The approval binding in `governance/validate_l1_live_data_preregistration.py`
  (#162) accepts any hash the log states on a line naming an approval, so a row
  restating a superseded hash keeps the superseded text acceptable; and it reads
  every `APPROVE_HL_LIVE_DATA_*` token on a hash-bearing line as an approval
  that ought to be retained, so a rejection or proposal recorded with its hash
  would fail the validator until that rule is given an exception. Both are
  disclosed in the module docstring and in PR #162; neither is a live defect
  today, and the second becomes one the day the owner records such a row.
- `DECISION_LOG.md` ends at DEC-046. The peer-pool amendment (#157), the
  closure of DEC-045's known issue (#162) and the four operator-session
  decisions (#159) have no row yet; the rows are the owner's to write.
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
