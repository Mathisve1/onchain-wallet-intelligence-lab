# Operator-started collection for arm B: four decisions the owner takes before T0

Status: `PROPOSED`. Nothing in this document is in force until the owner sends one of
the exact approval texts below, unmodified, and records the rows. The frozen
`L2_ANALYSIS_PLAN.md` does not change: these decisions say what its words
"operator-started sweeps; prices from `allMids` polled every five minutes" cover in
practice, over 56 days, on one laptop, by one person.

The rows are called A to D here. The decision log ends at DEC-046; the peer-pool
amendment merged as PR #157 is recorded first, and the owner assigns the numbers that
follow. The session tool looks a reference up in `DECISION_LOG.md` and refuses one
that is not a row there, so its flags follow the numbers the owner assigns.

## Why the question exists

Arm B prices every copy with the last `allMids` quote at most 15 minutes old. The
plan's sentence in full: "prices from `allMids` polled every five minutes plus the
public tape while a session is connected" (`L2_ANALYSIS_PLAN.md`, arm B); the arm B
runner prices from the `mids` table alone, so the tape clause does not shorten a gap.
So arm B needs a mids poll every five minutes for 56 days, and the study's texts say
who runs that poll:

- `L2_BUILD_PLAN.md`, phase 4: "A sweep never loops; the operator starts each one",
  and `allMids` "is a separate light command ... the operator runs in a loop of their
  own choosing (no scheduler in the repo)"; anti-pattern "no scheduler or sleep loop
  that runs unattended".
- `L2_PROPOSAL.md`, "Cost and gate": "every sweep is operator-initiated because
  scheduled execution stays unauthorised; roughly four sweeps a day", and the gate
  asked for "explicit permission for operator-initiated repeated sweeps".
- `HUMAN_APPROVAL_TEMPLATE.md`: `scheduled_execution_authorized=false`; an approval
  "does not install a workflow, authorize scheduled or unattended execution".
- `L1_LIVE_DATA_COLLECTION_PREREGISTRATION.md`: execution was "one operator-initiated
  session", and "no scheduled or unattended execution is authorized at any point in
  this stage". That session ran for minutes (`evidence/L1_SESSION_001.json`: the two
  watch commands with `max_iterations=1000` lasted 254 s and 209 s). No earlier
  approval contemplated requests running while the person who started them is away.
- `APPROVE_HL_LIVE_DATA_L2_FORWARD_STUDY_001` (DEC-042), line 7:
  `repeated_operator_started_sweeps_authorized=true`. The two-arm approval (DEC-043)
  supersedes that file as a whole (`supersedes=` on its line 3) and does not restate
  the line; DEC-043's row describes the supersession as being about the 14-day window
  and is silent on the sweeps line; the frozen plan says "operator-started sweeps".
  The permission survives by the plan's words and by reading, not by a line.

The loop that polls mids is written out as `C:\Users\mathi\owil-data\loop\collect_session.ps1`,
outside the repository: one bounded session a person starts in a visible console, which
stops at its bound, on Ctrl-C or on a stop file, registers nothing and never restarts
itself. It refuses two things without a decision reference: a session longer than
8 hours (`-OvernightDecision DEC-0NN`) and sweeps started by its own clock
(`-ScheduledSweepsDecision DEC-0NN`). It looks the reference up as a row in
`DECISION_LOG.md` and refuses one that is not there; it does not read what the row
says, so a session record that names a row which does not authorise it is a breach
visible in the dossier, not a permission. It refuses a collector command that is a
shell, a chain or a sweep, records the executable that ran, and finds the previous
session through a pointer beside the database, whatever log directory was used.
No session has run on this laptop yet; every operating figure below is a computation,
not an observation.

## What the words mean here

- **Operator-started.** A person starts each sweep and each mids session by hand, for
  that occasion, in a visible console. Nothing starts a request on a clock, a schedule,
  a service, a trigger, a hidden window, or by restarting itself.
- **Bounded.** A session has a stated end (at most the hours the approval names), stops
  by itself at that end, and records its start, its bound, and what ran it (script
  hash, repository commit, branch and dirty state, coin list, decision references, the
  executable that ran). The record carries no operator identity.
- **Attended.** The owner is awake and can stop the session. The tool's eight-hour
  bound is its proxy for that; a session of at most eight hours started at bedtime is
  not attended in this sense, whatever the tool allows, and the attended approval text
  below does not permit it. The record cannot check this; it is the owner's
  attestation.
- **Unattended execution**, which the template excludes, is execution no person started
  for that occasion: scheduled, triggered, or self-renewing. A bounded session a person
  started, running while that person is asleep, has no precedent in L1 or L2. Whether
  it is also "unattended" in the template's sense is a new reading that only the owner
  can give; it is row B.
- **The gap.** Between two sessions no mid is collected. The tool measures it (the
  previous session's last successful poll, the seconds since, an alarm above twelve
  minutes) and carries the unpriced time, the seconds beyond the 15-minute bound, per
  session and cumulatively into every session record, between this tool's own
  successful polls on this database; the database itself, read by the health check,
  is the truth.
- **What an unpriced copy does.** In the runner (`src/copyability/execution.py`) a fill
  with no mid within 15 minutes is not copied at its time: the source position still
  advances, the copy is counted as skipped (stale if an older quote exists), and the
  follower re-aligns at the next priced fill in one catch-up trade; a round trip the
  source completed inside the gap is missed entirely; a funding hour inside the gap is
  charged at the position's average entry price and counted as priced, so that case
  is visible nowhere. So a gap does not only widen the interval around `d_i`: for a
  wallet active inside the gap it changes what `d_i` measures, because the copy that
  reaches the venue is a later, larger trade than the one the plan's latency describes.
  The runner reports this per wallet as `skipped_fills`, `stale_price_skips` and
  `catch_up_fills`, and the statistics block counts the wallets affected as
  `stale_price_skips_present` and `catch_up_fills_present`.

## The amending approval (exact texts; the owner sends one of them unmodified)

The recommended text carries rows A to D as proposed. Replace `<COMMIT>` with the
40-character commit that carries this document, as the template requires; the three
L2 predecessors bound 7-character hashes, which is not the standard here. Change
nothing else. It is retained beside the other approvals with its SHA-256, in row A,
as `APPROVE_HL_LIVE_DATA_L2_ARM_A_WINDOW_001` was under DEC-044. The `after=` line
orders the two amendments of the two-arm approval; no code reads it, as no code reads
`amends=`; both live by the decision row's words.

```
APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001
bound_commit=<COMMIT>
amends=APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001
after=APPROVE_HL_LIVE_DATA_L2_ARM_A_WINDOW_001
operator=OWNER
repeated_operator_started_sweeps_authorized=true
sweep_started_by=OPERATOR_BY_HAND
sweep_pool=FROZEN_POOL_AT_T0
scheduled_sweeps_authorized=false
mids_session_started_by=OPERATOR_IN_VISIBLE_CONSOLE
mids_session_maximum_hours=24
mids_session_attended_hours=8
inter_session_gap_reported=true
scheduled_execution_authorized=false
workflow_installation_authorized=false
frozen_plan_unchanged=true
```

An owner who rejects row B sends this second text instead, unmodified; it differs in
its name and in one value, and row B is then recorded as rejected:

```
APPROVE_HL_LIVE_DATA_L2_ATTENDED_SESSIONS_001
bound_commit=<COMMIT>
amends=APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001
after=APPROVE_HL_LIVE_DATA_L2_ARM_A_WINDOW_001
operator=OWNER
repeated_operator_started_sweeps_authorized=true
sweep_started_by=OPERATOR_BY_HAND
sweep_pool=FROZEN_POOL_AT_T0
scheduled_sweeps_authorized=false
mids_session_started_by=OPERATOR_IN_VISIBLE_CONSOLE
mids_session_maximum_hours=8
mids_session_attended_hours=8
inter_session_gap_reported=true
scheduled_execution_authorized=false
workflow_installation_authorized=false
frozen_plan_unchanged=true
```

No text is offered for clock-started sweeps (row C recommends against them); they
would need a different document and a different text. The closing grace after
`T0+56d` is not in either text: it is the runner's input (`--closing-grace-days`,
default 3), recorded in the evidence file, and row A says how it is used.

## The four decisions

### Row A: the approval is accepted, and a series of bounded sessions started by hand is operator-started collection

**Decision.** Accept the owner's exact `APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001`
(sixteen lines, SHA-256 recorded, bound to the commit that carries this document),
amending DEC-043 after DEC-044. Under it, the frozen plan's "operator-started sweeps"
and "`allMids` polled every five minutes" are met by:

- mids sessions of at most eight hours, each started by hand in a visible console
  while the owner is awake and can stop it, self-stopping, run one after another over
  the 56 days; eight hours is the tool's attended bound and such a session needs no
  decision reference;
- sweeps started by hand from a second window, a few times a day, each run with
  `--sweep-pool` over the pool frozen at T0, because the plan's peer-pool amendment
  requires that "during the 56 days the sweep covers the whole characterised set, not
  the cohort alone"; a sweep without the pool is not an arm B sweep under this row;
  a sweep is started just after a successful poll, because the session and the sweep
  are two processes with separate rate buckets;
- closing sweeps by hand after `T0+56d`, repeated within the runner's closing grace
  (three days by default) until every cohort wallet carries a completed closing
  sweep; a wallet without one by then is excluded and counted, and the grace is
  widened only for a reason written into the evidence file; mids after the window
  end are surplus.

Three things this row decides that nothing decided before:

- `operator=OWNER`: the owner starts every session and every sweep for 56 days, with
  no delegate. The record cannot verify who started a session; a missed day is a gap
  of up to a day, measured and reported.
- one exception for the dry run of row B: a single session of up to 23.75 hours,
  mids only, against a throwaway database outside the repository, started by the
  owner with `-OvernightDecision` naming this row, is authorised under this row so
  that row B is decided on an observation, not a computation. Its pass criteria are
  in row B.
- once the tool revision named below exists, this row is completed with the revised
  tool's SHA-256 and the loop repository's commit, so the first live session's
  `script_sha256` has a reference to be checked against.

The gap between sessions is measured and reported, not hidden; what it does to a copy
is stated above; the arm B report names the gaps and the unpriced time as a limitation.

**Why.** It is what the build plan and the proposal describe, and the tool cannot be
configured past it by a flag alone. What it costs is stated in row B.

### Row B: an overnight session of at most 24 hours is operator-started, on conditions

**Decision (recommended: accept).** A mids session of more than eight and at most
twenty-four hours is operator-started collection when:

1. the owner starts it by hand in a visible console and reads its banner;
2. the machine is prepared beforehand: sleep, hibernation and lid action off on mains
   power; Windows Update paused (a pause is at most 35 days on Windows 10 Home, to be
   verified on the machine before the first session) and, when the pause ends, updates
   installed by hand in a gap between sessions;
3. the owner reads the session's summary or status file at the next start;
4. the session records `overnight_decision=<row B's number>` and the gap since the
   previous session;
5. nothing but the owner starts the next session. A session that stops during the
   night, on a dead feed (`-MaxConsecutiveMidsFailures` consecutive failed polls,
   exit 3), a reboot, a power loss or a closed window, is not restarted by anything;
   the gap runs until the owner's next start, is recorded as
   `previous_session_unfinished` and `gap_since_previous_s`, and counts in the
   report's unpriced time;
6. the daily routine is the one that keeps the gap short: `-SessionHours 23.75`
   started at a fixed UTC hour (the clock change of 2026-10-25 moves local time, not
   the routine), so the start does not drift later by the day's delay: the last poll
   lands one interval before the bound, at 23 h 40 min, the next start twenty minutes
   later, five of them beyond the 15-minute bound; and `-MaxConsecutiveMidsFailures`
   at most 90. With 60-second retries, fifteen failures stop the session 14 to about
   30 minutes after the first failed poll (a call that fails on `429` takes up to
   about 75 s), so a venue outage of twenty minutes at 03:00 would cost the rest of
   the night; ninety keeps the session polling once a minute through an outage of up
   to about ninety minutes, at most one request of weight 2 a minute, and stops after
   that as structurally broken. The stop exists so that a broken collector does not
   keep calling the venue unwatched; ninety failures is that bound sized to a night.

Of these, conditions 4 and 6 are checkable from the session records
(`overnight_decision`, `gap_since_previous_s`, `session_s`,
`max_consecutive_mids_failures`, the start timestamps); conditions 1, 2, 3 and 5 are
the owner's attestations, which the dossier cannot show.

**Why accept.** The plan asks for a mid every five minutes; the question is how much
of the day a hand-started model can price. By construction, on the tool's five-minute
grid with the last poll one interval before the bound and the next start by hand
exactly a day after the previous one, as fractions of time:

| model | unpriced time per day | share of the 56-day window |
|---|---|---|
| one attended session of 8 h a day | about 15 h 50 min | 66.0 percent |
| two attended sessions of 8 h back to back (the owner awake 16 h) | about 7 h 50 min | 32.6 percent |
| one session of 23.5 h a day at a fixed UTC hour | about 20 min | 1.4 percent |
| one session of 23.75 h a day at a fixed UTC hour (the routine of condition 6) | about 5 min | 0.35 percent, 4.7 h over 56 days |

Fractions of time are not fractions of copies. The only fill profile in this
repository is L1's: 130,457 fills of nine wallet addresses over 6.5 days in the L1
database named by `evidence/L1_SESSION_001.json`, read by hour of day. An eight-hour
session at 09:00 to 17:00 Brussels time prices 33.7 percent of those fills, the same
as its share of hours; placed on the venue's peak, at 13:00 to 21:00 Brussels time,
61.6 percent. A sixteen-hour day at 07:00 to 23:00 prices 85.8 percent, and 87.0
percent at its best placement. The night, 23:00 to 07:00, holds 14.2 percent of the
fills, and that share is not spread evenly: by wallet it runs from 0 to 40 percent
(three of the nine wallets have no night fills, one has 40 percent). The venue's
activity peaks at 15:00 to 19:00 UTC; 16:00 and 17:00 alone carry 27 percent. Two
caveats: nine wallets over a week do not speak for a cohort of hundreds over eight
weeks, and those nine were selected as the most active wallets in one fifteen-minute
tape at 18:20 UTC (DEC-041), which tilts the profile toward those hours.

What the profile says is therefore not that an attended model prices few copies; a
sixteen-hour day prices most of them. It says that what an attended model leaves out
is a wallet-dependent selection: for the wallets that trade at night, the copies that
are not priced are re-entered later as catch-up trades, so the model changes what
`d_i` measures for those wallets, not only the width of its interval. The share of
copies affected is unknown until arm B's own fills exist and is reported from the
runner's counters. Against the two-session model, the overnight session saves the
night's 14 percent and the second eight hours of the owner's day, for 56 days.

**What accepting costs.** For about sixteen of every twenty-four hours, for 56 days,
requests run against a third-party venue while no person can stop them. A dead feed,
a reboot or a closed window is seen at the next start, not when it happens, and nothing
restarts the session. Fifty-six sessions started by hand at the same hour are, in
effect, a daily schedule a person executes, under an approval that keeps
`scheduled_execution_authorized=false`; the owner is deciding that the person's act
each day is the difference the template protects. This has no precedent in L1 or in
the L2 chain. The recipe in condition 6 is untested: no session has run on this
laptop.

**The dry run, before this row is recorded.** Under row A's exception: one session of
23.75 hours, mids only, against a throwaway database outside the repository, started
by the owner at the fixed UTC hour with `-OvernightDecision` naming row A and
`-MaxConsecutiveMidsFailures 90`; then a second, short session started twenty minutes
after the first ended. Read: the first session's `session_start` (`session_s` 85500,
`overnight_decision`, `max_consecutive_mids_failures` 90, `test_overrides` false) and
`session_end`; the second session's `session_start`. Pass: `session_end.reason` is
"session end", `stopped_early` false, `counts.mids_fail` 0, `counts.mids_skipped` 0,
`longest_mids_gap_s` under 900, and the second session's `gap_since_previous_s`
between 1,100 and 1,500 seconds. Anything else is read before this row is recorded,
and the routine or the row changes.

**If rejected.** The owner sends `APPROVE_HL_LIVE_DATA_L2_ATTENDED_SESSIONS_001`
instead; sessions stay within eight hours, two back to back when the owner is awake,
none started at bedtime; the arm B report states, in its answer and not in a footnote,
the unpriced time, the time-of-day limitation, and the counts of wallets with
`stale_price_skips_present` and `catch_up_fills_present`; the tool's ceiling is
lowered to eight hours in the same revision that cites the rows.

### Row C: the script's clock does not start sweeps

**Decision (recommended: accept this reading).** Sweeps are started by hand only.
The tool's `-SweepEveryHours` stays refused, and after the revision below its refusal
cites this row. Fills and funding carry the venue's own timestamps, so the spacing of
sweeps does not enter the primary measure; it sets two other things. It sets the
resolution of the top-10 position snapshots (`clearinghouseState`, one per sweep per
top wallet), a secondary series. And it rests on the assumption that a wallet's fills
since the last sweep remain retrievable through `userFillsByTime` whatever the spacing;
no text in this repository verifies the venue's retrievable-fill horizon per wallet,
the health check's per-wallet fill counts are the only detector, and the busiest
wallets are where a horizon would bite first (1,865 fills in fifteen minutes was
measured for one L1 market-maker wallet, `fills_after_cutoff` in
`evidence/L1_INSTRUMENT_VALIDATION_001.json`). Both argue for sweeps a few times a
day by hand, not for a clock: a sweep run by the mids session would block the polls
for as long as it takes, and a sweep of more than fifteen minutes would open a price
gap the tool could only report afterwards. One operating note: the mids session and a
hand-started sweep are two processes with separate rate buckets, so a long pool sweep
can push the poller into `429`; start sweeps just after a successful poll and watch
the session for exit 3.

### Row D: the permission for repeated operator-started sweeps is restated in the current chain

**Decision.** A clarifying restatement. The explicit line
`repeated_operator_started_sweeps_authorized=true` stands in
`APPROVE_HL_LIVE_DATA_L2_FORWARD_STUDY_001` (DEC-042); the superseding
`APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001` supersedes that file as a whole and does
not restate the line; DEC-043's row describes the supersession as of the 14-day
window and is silent on the sweeps line; the frozen plan says "operator-started
sweeps". The permission survives by the plan's words and by this restatement, which is
why the row exists: the amending approval restates it as a line for arm B's window
`[T0, T0+56d]` and its closing sweeps, with the cadence `L2_BUILD_PLAN.md` phase 4
gives, so that an auditor reads it from a line, not from a reading. From this row on,
the tool, its README and the runbook page derived from it cite the amending approval
and the frozen plan as the authority for repeated sweeps.

## The rows, ready to record

The decision log is a table with one paragraph per row. These are the rows as
proposed, with `DEC-0NN` where the owner assigns the number; the owner changes what
the owner decides otherwise and fills in the date, the SHA-256 and the commit.

| ID | Date | Status | Decision |
|---|---|---|---|
| DEC-0NN (A) | `<date>` | accepted | Accept the owner's exact `APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001` (sixteen lines, retained beside the other approvals, SHA-256 `<sha256>`), bound to commit `<commit>`, amending DEC-043 after DEC-044. Under it, a series of bounded mids sessions for arm B, each of at most 8 hours, each started by hand by the owner in a visible console while the owner is awake and can stop it, and self-stopping, together with sweeps started by hand from a second window a few times a day just after a successful poll, each with `--sweep-pool` over the pool frozen at T0 (the plan's peer-pool amendment: the sweep covers the whole characterised set), and closing sweeps by hand after `T0+56d` repeated within the runner's closing grace (three days by default, widened only for a reason written into the evidence) until every cohort wallet carries a completed closing sweep, is operator-started collection under the frozen `L2_ANALYSIS_PLAN.md` ("operator-started sweeps; prices from `allMids` polled every five minutes") and `L2_BUILD_PLAN.md` phase 4. `operator=OWNER` is new: the owner starts every session and sweep for 56 days, with no delegate; the record cannot verify who started a session, and a missed day is a gap of up to a day, measured. The session tool (`collect_session.ps1`, outside the repository, hash recorded per session) needs no decision reference for such a session; it looks any reference up as a row in `DECISION_LOG.md` and reads nothing of what the row says. One exception under this row: a single dry-run session of up to 23.75 hours, mids only, against a throwaway database outside the repository, started by the owner with `-OvernightDecision` naming this row, before row B is recorded. The gap between sessions is measured by the tool (previous session's last successful poll, seconds since, alarm above twelve minutes) and carried as cumulative unpriced time into every session record. A copy without a mid within the 15-minute bound is not copied at its time; the follower re-aligns at the next priced fill, round trips inside the gap are lost, funding inside it is charged at the average entry price; the runner reports this per wallet and the arm B report names the gaps as a limitation. This row is completed with the revised tool's SHA-256 and loop-repository commit before the first live session. Definitions per `L2_OPERATOR_SESSIONS.md`. |
| DEC-0NN (B) | `<date>` | accepted | Under `APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001` (row A), a mids session of more than 8 and at most 24 hours is operator-started collection when the owner starts it by hand in a visible console and reads its banner; the machine is prepared beforehand (sleep, hibernation and lid action off on mains; Windows Update paused, and updated by hand in a gap when the pause ends); the owner reads the summary or status at the next start; the session records `overnight_decision=DEC-0NN` and the gap since the previous session; nothing but the owner starts the next one, and a session that stops during the night (`-MaxConsecutiveMidsFailures` consecutive failed polls, reboot, power loss, closed window) is not restarted by anything, its gap running until the next hand start and counting as unpriced time; the routine is `-SessionHours 23.75` at a fixed UTC hour with `-MaxConsecutiveMidsFailures` at most 90 (one request of weight 2 a minute through an outage of up to about ninety minutes, then a stop as structurally broken). Conditions 4 and 6 are checkable from the session records; 1, 2, 3 and 5 are the owner's attestations. Accepted because, as fractions of time on the five-minute grid, one attended session a day leaves about 15 h 50 min unpriced (66.0 percent of the window), two back to back about 7 h 50 min (32.6 percent), and a 23.75-hour session about 5 minutes (0.35 percent); because the only fill profile available (L1, 130,457 fills, nine wallet addresses, 6.5 days, selected from one fifteen-minute tape) puts 14.2 percent of fills in the night and from 0 to 40 percent per wallet, so an attended model leaves out a wallet-dependent selection whose copies re-enter as catch-up trades and change what `d_i` measures for those wallets; and with the cost stated: about sixteen hours a day for 56 days in which no person can stop the requests, failures seen only at the next start, and a hand-executed daily series under `scheduled_execution_authorized=false`, which has no precedent in L1 or L2. The owner decides that the person's act each day is the difference the template protects. Before this row was recorded, the dry run under row A was read: one 23.75-hour session against a throwaway database ended at its bound with no failed or skipped poll and a longest gap under 900 s, and the next start twenty minutes later measured a gap between 1,100 and 1,500 s. |
| DEC-0NN (C) | `<date>` | accepted | Sweeps for arm B are started by hand only; the session tool's clock does not start them (`scheduled_sweeps_authorized=false` in row A's approval). `-SweepEveryHours` stays refused and, after the tool revision named in `L2_OPERATOR_SESSIONS.md`, the refusal cites this row. Sweep spacing does not enter the primary measure (fills and funding carry the venue's timestamps); it sets the resolution of the secondary top-10 position snapshots and rests on the unverified assumption that a wallet's fills since the last sweep remain retrievable, for which the health check's per-wallet counts are the only detector; a sweep inside the mids session would block the polls and one over fifteen minutes would open a price gap. Sweeps are started just after a successful poll because the two processes do not share a rate bucket. |
| DEC-0NN (D) | `<date>` | accepted | Clarifying restatement: the permission for repeated operator-started sweeps, explicit in `APPROVE_HL_LIVE_DATA_L2_FORWARD_STUDY_001` (DEC-042), is not restated by the superseding `APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001`, which supersedes that file as a whole; DEC-043's row describes the supersession as of the 14-day window and is silent on the sweeps line; the frozen plan says "operator-started sweeps". The permission survives by the plan's words and is restated as a line for arm B's window `[T0, T0+56d]` and its closing sweeps by `APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001` (row A), with the cadence `L2_BUILD_PLAN.md` phase 4 gives (a sweep every few hours by hand, `allMids` every five minutes). The session tool, its README and the runbook page cite that approval and the frozen plan as the authority for repeated sweeps. |

## What changes when the rows are recorded, and who does it

- **The session tool, one revision before the first live session**, made by the
  assistant in a session the owner starts, verified by the tool's own offline suite
  and by the owner's read of the diff, and recorded in row A by SHA-256 and loop
  commit. The refusal of `-SweepEveryHours` names row C's number beside the `DEC-0NN`
  placeholder; the docstring, the banner line about daily sessions and the README's
  authority paragraph cite `APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001` and rows A
  and D instead of the superseded FORWARD_STUDY_001 line; the docstring's and README's
  "three failures" sentences say the configured count; the README's parameter table
  names row B's number for `-OvernightDecision` and its daily command
  (`-SessionHours 23.75 -OvernightDecision DEC-0NN -MaxConsecutiveMidsFailures 90`
  at the fixed UTC hour), says under row C that `-SweepEveryHours` is never passed,
  and replaces "start the next session as soon as the previous one ends" by the
  fixed-hour routine. If row B is rejected, the same revision lowers the tool's
  ceiling to eight hours. The operator's manual is the README beside the tool; the
  runbook page is derived from it.
- **The arm B report, one change before T0**, made by the assistant and put through
  the same blind verification the arm runners had (PR #158), not under DEC-045, which
  did not cover them. `l2_arm_report.py` already measures each coin's mids series over
  the window (`max_gap_ms`, `gaps_over_max_age`, from gaps between consecutive
  observations inside the window; the two edges are covered by the span check). The
  limitation note for arm B adds, from that same table, the unpriced time (the sum of
  gap minus fifteen minutes over the interior gaps above the bound, per coin, and for
  the benchmark coin), the number of such gaps and the longest one, and states the
  counts of wallets with `stale_price_skips_present` and `catch_up_fills_present`
  from the disclosures block. The figure is the evidence file's own, from the hashed
  database; the session records outside the repository are operating context that
  should agree with it, and are cited, not read, by the runner.
- **Before row B is recorded.** The dry run under row A, read as row B specifies.
- The approval file `APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001.txt` (or the
  attended text) is retained beside the others; the manifest is regenerated; the rows
  go into `DECISION_LOG.md` by the owner's hand, as every row does.

## What this document does not do

It does not change the frozen plan, the two-arm approval or the build plan. It does not
authorise a scheduler, a service, a hidden window, a self-restarting session or any
execution a person did not start for that occasion. It does not open any look at a
return, a ranking or a comparison before day 56.
