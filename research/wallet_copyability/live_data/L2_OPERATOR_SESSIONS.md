# Operator-started collection for arm B: four decisions the owner takes before T0

Status: `PROPOSED`. Nothing in this document is in force until the owner sends one of
the exact approval texts below, unmodified, and records the rows. The frozen
`L2_ANALYSIS_PLAN.md` does not change: these decisions say what its words
"operator-started sweeps; prices from `allMids` polled every five minutes" cover in
practice, over 56 days, on one laptop, by one person.

The rows are called A to D here. The decision log ends at DEC-046; the peer-pool
amendment merged as PR #157 is recorded first, and the owner assigns the numbers that
follow. The session tool records the number the operator passes, so its flags follow
the numbers the owner assigns.

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
  supersedes that file and does not restate the line; DEC-043's row reads the
  supersession as being about the 14-day window, and the frozen plan carries
  "operator-started sweeps". The permission is in the chain by reading, not by a line.

The loop that polls mids is written out as `C:\Users\mathi\owil-data\loop\collect_session.ps1`,
outside the repository: one bounded session a person starts in a visible console, which
stops at its bound, on Ctrl-C or on a stop file, registers nothing and never restarts
itself. It refuses two things without a decision reference: a session longer than
8 hours (`-OvernightDecision DEC-0NN`) and sweeps started by its own clock
(`-ScheduledSweepsDecision DEC-0NN`). It records the reference the operator passes and
verifies none: a session record that names a row which does not authorise it is a
breach visible in the dossier, not a permission. No session has run on this laptop
yet; every operating figure below is a computation, not an observation.

## What the words mean here

- **Operator-started.** A person starts each sweep and each mids session by hand, for
  that occasion, in a visible console. Nothing starts a request on a clock, a schedule,
  a service, a trigger, a hidden window, or by restarting itself. The operator is the
  owner.
- **Bounded.** A session has a stated end (at most the hours the approval names), stops
  by itself at that end, and records its start, its bound, and what ran it (script
  hash, repository commit, branch and dirty state, coin list, decision references).
  The record carries no operator identity; the approval's `operator=OWNER` is the
  claim, and a session started by anyone else is outside it.
- **Unattended execution**, which the template excludes, is execution no person started
  for that occasion: scheduled, triggered, or self-renewing. A bounded session a person
  started, running while that person is asleep, has no precedent in L1 or L2. Whether
  it is also "unattended" in the template's sense is a new reading that only the owner
  can give; it is row B.
- **The gap.** Between two sessions no mid is collected. The tool measures it (the
  previous session's last successful poll, the seconds since, an alarm above twelve
  minutes) and carries the unpriced time, the seconds beyond the 15-minute bound, per
  session and cumulatively into every session record.
- **What an unpriced copy does.** In the runner (`src/copyability/execution.py`) a fill
  with no mid within 15 minutes is not copied at its time: the source position still
  advances, the copy is counted as skipped (stale if an older quote exists), and the
  follower re-aligns at the next priced fill in one catch-up trade; a round trip the
  source completed inside the gap is missed entirely; funding inside the gap is charged
  at the entry price. So a gap does not only widen the interval around `d_i`: for a
  wallet active inside the gap it changes what `d_i` measures, because the copy that
  reaches the venue is a later, larger trade than the one the plan's latency describes.
  The runner reports this per wallet as `stale_price_skips_present` and
  `catch_up_fills_present`.

## The amending approval (exact texts; the owner sends one of them unmodified)

The recommended text carries rows A to D as proposed. Replace `<COMMIT>` with the
40-character commit that carries this document, as the template requires; the three
L2 predecessors bound 7-character hashes, which is not the standard here. Change
nothing else. It is retained beside the other approvals with its SHA-256, in row A,
as `APPROVE_HL_LIVE_DATA_L2_ARM_A_WINDOW_001` was under DEC-044.

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
closing_grace_days=3
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
closing_grace_days=3
inter_session_gap_reported=true
scheduled_execution_authorized=false
workflow_installation_authorized=false
frozen_plan_unchanged=true
```

No text is offered for clock-started sweeps (row C recommends against them). An owner
who wants them asks for a different document with a different text.

## The four decisions

### Row A: the approval is accepted, and a series of bounded sessions started by hand is operator-started collection

**Decision.** Accept the owner's exact `APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001`
(seventeen lines, SHA-256 recorded, bound to the commit that carries this document),
amending DEC-043 after DEC-044. Under it, the frozen plan's "operator-started sweeps"
and "`allMids` polled every five minutes" are met by:

- mids sessions of at most eight hours, each started by hand in a visible console,
  self-stopping, run one after another over the 56 days; eight hours is the tool's
  attended bound and such a session needs no decision reference;
- sweeps started by hand from a second window, a few times a day, each run with
  `--sweep-pool` over the pool frozen at T0, because the plan's peer-pool amendment
  requires that "during the 56 days the sweep covers the whole characterised set, not
  the cohort alone"; a sweep without the pool is not an arm B sweep under this row;
- closing sweeps by hand after `T0+56d`, repeated within the three-day closing grace
  until every cohort wallet carries a completed closing sweep; mids after the window
  end are surplus.

The gap between sessions is measured and reported, not hidden; what it does to a copy
is stated above; the arm B report names the gaps and the unpriced time as a limitation.

**Why.** It is what the build plan and the proposal describe, and the tool cannot be
configured past it by a flag alone. What it costs is stated in row B.

### Row B: an overnight session of at most 24 hours is operator-started, on conditions

**Decision (recommended: accept).** A mids session of more than eight and at most
twenty-four hours is operator-started collection when:

1. a person starts it by hand in a visible console and reads its banner;
2. the machine is prepared beforehand: sleep, hibernation and lid action off on mains
   power; Windows Update paused and re-paused before the pause runs out (a pause does
   not span 56 days), or updates installed by hand in a gap between sessions;
3. the person reads the session's summary or status file at the next start;
4. the session records `overnight_decision=<row B's number>` and the gap since the
   previous session;
5. nothing but a person starts the next session. A session that stops during the
   night, on a dead feed (three consecutive failed polls, exit 3), a reboot, a power
   loss or a closed window, is not restarted by anything; the gap runs until the
   person's next start, is recorded as `previous_session_unfinished` and
   `gap_since_previous_s`, and counts in the report's unpriced time;
6. the daily routine is the one that keeps the gap short: `-SessionHours 23.5` started
   at a fixed hour, so the start does not drift later by the day's delay, and
   `-MaxConsecutiveMidsFailures` at most 15, so a venue outage of a few minutes at
   night does not end the session while an outage longer than the 15-minute bound
   still does.

The tool records the reference; it does not verify it.

**Why accept.** The plan asks for a mid every five minutes; the question is how much
of the day a hand-started model can price. By construction, as fractions of time:

| model | unpriced time per day | share of the window |
|---|---|---|
| one attended session of 8 h a day | about 15.75 h (16 h less the 15-minute bound) | 65.6 percent |
| two attended sessions of 8 h back to back (a person present 16 h) | about 7.75 h | 32.3 percent |
| one session of 23.5 h a day, started at a fixed hour | 15 minutes (a 30-minute gap less the bound) | 1.0 percent |

Fractions of time are not fractions of copies. The only fill profile in this
repository is L1's (130,457 fills of 9 wallets over 6.5 days, `evidence/L1_SESSION_001.json`,
read from the database by hour of day): 33.7 percent of those fills fell in 09:00 to
17:00 Brussels time, 85.8 percent in 07:00 to 23:00, and 14.2 percent in the night;
the venue's activity peaks at 14:00 to 18:00 UTC. Nine wallets over a week do not
speak for a cohort of hundreds over eight weeks; they say that the daytime share of
copies is nowhere near the daytime share of hours, and that an attended-only model
reads arm B on a time-of-day selection. What that selection does to `d_i` is stated
under "What an unpriced copy does": for wallets active at night it changes the copy
that is scored, not only the width of the interval. The share of copies actually
affected is unknown until arm B's own fills exist and is reported from the runner's
counters. Against the two-session model, the overnight session saves the night and
the second eight hours of a person's day, for 56 days.

**What accepting costs.** For about sixteen of every twenty-four hours, for 56 days,
requests run against a third-party venue while no person can stop them. A dead feed,
a reboot or a closed window is seen at the next start, not when it happens, and nothing
restarts the session. Fifty-six sessions started by hand at the same hour are, in
effect, a daily schedule a person executes, under an approval that keeps
`scheduled_execution_authorized=false`; the owner is deciding that the person's act
each day is the difference the template protects. This has no precedent in L1 or in
the L2 chain. The recipe in condition 6 is untested: no session has run on this
laptop. Before this row is recorded, one full session of 23.5 hours is run against a
throwaway database, and its gap and failure count are read.

**If rejected.** The owner sends `APPROVE_HL_LIVE_DATA_L2_ATTENDED_SESSIONS_001`
instead; sessions stay within eight hours, two back to back when a person is present;
the arm B report states, in its answer and not in a footnote, the unpriced time, the
time-of-day limitation, and the counts of wallets with `stale_price_skips_present` and
`catch_up_fills_present`; the tool's ceiling is lowered to eight hours in the same
revision that cites the rows.

### Row C: the script's clock does not start sweeps

**Decision (recommended: accept this reading).** Sweeps are started by hand only.
The tool's `-SweepEveryHours` stays refused, and after the revision below its refusal
cites this row. Fills and funding carry the venue's own timestamps, so the spacing of
sweeps does not enter the primary measure; it sets two other things. It sets the
resolution of the top-10 position snapshots (`clearinghouseState`, one per sweep per
top wallet), a secondary series. And it rests on the assumption that a wallet's fills
since the last sweep remain retrievable through `userFillsByTime` whatever the spacing;
no text in this repository verifies the venue's retrievable-fill horizon per wallet,
the health check's per-wallet fill counts are the only detector, and the busiest pool
wallets (1,865 fills in fifteen minutes was measured for one) are where a horizon
would bite first. Both argue for sweeps a few times a day by hand, not for a clock: a
sweep run by the mids session would block the polls for as long as it takes, and a
sweep of more than fifteen minutes would open a price gap the tool could only report
afterwards. One operating note: the mids session and a hand-started sweep are two
processes with separate rate buckets, so a long pool sweep can push the poller into
`429`; start sweeps just after a successful poll and watch the session for exit 3.

### Row D: the permission for repeated operator-started sweeps is restated in the current chain

**Decision.** A clarifying restatement. The permission is already in the chain by
reading: DEC-042's row records it, DEC-043's row supersedes "the 14-day window" and
not the permission, and the frozen plan says "operator-started sweeps". The explicit
line `repeated_operator_started_sweeps_authorized=true` is nevertheless absent from
`APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001`; the amending approval restates it for arm
B's window `[T0, T0+56d]` and its closing sweeps, with the cadence
`L2_BUILD_PLAN.md` phase 4 gives, so that an auditor reads it from a line, not from a
reading. From this row on, the tool, its README and the operator's runbook cite the
amending approval and the frozen plan as the authority for repeated sweeps.

## The rows, ready to record

The decision log is a table with one paragraph per row. These are the rows as
proposed, with `DEC-0NN` where the owner assigns the number; the owner changes what
the owner decides otherwise and fills in the date, the SHA-256 and the commit.

| ID | Date | Status | Decision |
|---|---|---|---|
| DEC-0NN (A) | `<date>` | accepted | Accept the owner's exact `APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001` (seventeen lines, retained beside the other approvals, SHA-256 `<sha256>`), bound to commit `<commit>`, amending DEC-043 after DEC-044. Under it, a series of bounded mids sessions for arm B, each of at most 8 hours, each started by hand by the owner in a visible console and self-stopping, together with sweeps started by hand from a second window a few times a day, each with `--sweep-pool` over the pool frozen at T0 (the plan's peer-pool amendment: the sweep covers the whole characterised set), and closing sweeps by hand after `T0+56d` repeated within a three-day closing grace until every cohort wallet carries a completed closing sweep, is operator-started collection under the frozen `L2_ANALYSIS_PLAN.md` ("operator-started sweeps; prices from `allMids` polled every five minutes") and `L2_BUILD_PLAN.md` phase 4. The session tool (`collect_session.ps1`, outside the repository, hash recorded per session) needs no decision reference for such a session; it records the references the operator passes and verifies none. The gap between sessions is measured by the tool (previous session's last successful poll, seconds since, alarm above twelve minutes) and carried as cumulative unpriced time into every session record. A copy without a mid within the 15-minute bound is not copied at its time; the follower re-aligns at the next priced fill, round trips inside the gap are lost, funding inside it is charged at the entry price; the runner reports this per wallet and the arm B report names the gaps as a limitation. Definitions per `L2_OPERATOR_SESSIONS.md`. |
| DEC-0NN (B) | `<date>` | accepted | Under `APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001` (row A), a mids session of more than 8 and at most 24 hours is operator-started collection when the owner starts it by hand in a visible console and reads its banner; the machine is prepared beforehand (sleep, hibernation and lid action off on mains; Windows Update paused and re-paused before the pause ends, or updated by hand between sessions); the owner reads the summary or status at the next start; the session records `overnight_decision=DEC-0NN` and the gap since the previous session; nothing but a person starts the next one, and a session that stops during the night (dead feed, reboot, power loss, closed window) is not restarted by anything, its gap running until the next hand start and counting as unpriced time; the routine is `-SessionHours 23.5` at a fixed hour with `-MaxConsecutiveMidsFailures` at most 15. Accepted because, as fractions of time, one attended session a day leaves about 15.75 hours unpriced (65.6 percent of the window), two back to back about 7.75 hours (32.3 percent), and a 23.5-hour session about 15 minutes (1.0 percent); because the only fill profile available (L1, 130,457 fills, 9 wallets, 6.5 days) puts 33.7 percent of fills in 09:00 to 17:00 Brussels time and 14.2 percent in the night, so an attended-only model reads arm B on a time-of-day selection that changes which copy is scored for night-active wallets; and with the cost stated: about sixteen hours a day for 56 days in which no person can stop the requests, failures seen only at the next start, and a hand-executed daily series under `scheduled_execution_authorized=false`, which has no precedent in L1 or L2. The owner decides that the person's act each day is the difference the template protects. One full 23.5-hour session against a throwaway database is run before this row is recorded, and its gap and failure count are read. The tool records the reference and verifies none. |
| DEC-0NN (C) | `<date>` | accepted | Sweeps for arm B are started by hand only; the session tool's clock does not start them (`scheduled_sweeps_authorized=false` in row A's approval). `-SweepEveryHours` stays refused and, after the tool revision named in `L2_OPERATOR_SESSIONS.md`, the refusal cites this row. Sweep spacing does not enter the primary measure (fills and funding carry the venue's timestamps); it sets the resolution of the secondary top-10 position snapshots and rests on the unverified assumption that a wallet's fills since the last sweep remain retrievable, for which the health check's per-wallet counts are the only detector; a sweep inside the mids session would block the polls and one over fifteen minutes would open a price gap. Sweeps are started just after a successful poll because the two processes do not share a rate bucket. |
| DEC-0NN (D) | `<date>` | accepted | Clarifying restatement: the permission for repeated operator-started sweeps, explicit in `APPROVE_HL_LIVE_DATA_L2_FORWARD_STUDY_001` (DEC-042) and carried by reading in DEC-043 (which supersedes the 14-day window, not the permission) and by the frozen plan's "operator-started sweeps", is restated as a line for arm B's window `[T0, T0+56d]` and its closing sweeps by `APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001` (row A), with the cadence `L2_BUILD_PLAN.md` phase 4 gives (a sweep every few hours by hand, `allMids` every five minutes). The session tool, its README and the operator's runbook cite that approval and the frozen plan as the authority for repeated sweeps. |

## What changes when the rows are recorded

- **The session tool, one revision before the first live session.** The refusal of
  `-SweepEveryHours` names row C's number beside the `DEC-0NN` placeholder; the
  docstring, the banner line about daily sessions and the README's authority paragraph
  cite `APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001` and rows A and D instead of the
  superseded FORWARD_STUDY_001 line; the README's parameter table names row B's number
  for `-OvernightDecision` and its daily command (`-SessionHours 23.5
  -OvernightDecision DEC-0NN`, the fixed hour, `-MaxConsecutiveMidsFailures 15`), says
  under row C that `-SweepEveryHours` is never passed, and replaces "Windows Update
  active hours" by the pause-and-re-pause rule. If row B is rejected, the same revision
  lowers the tool's ceiling to eight hours. The revision's script hash is recorded in
  the first live session's record, as every session's is. The operator's runbook is
  the README beside the tool, and the runbook page derived from it.
- **The arm B report, one change before T0, reviewed like phase work under DEC-045.**
  `l2_arm_report.py` already measures each coin's mids series over the window
  (`max_gap_ms`, `gaps_over_max_age`). The limitation note for arm B adds, from that
  same table, the unpriced time (the sum of gap minus fifteen minutes over the gaps
  above the bound, per coin, and for the benchmark coin), the number of such gaps and
  the longest one, and states the counts of wallets with `stale_price_skips_present`
  and `catch_up_fills_present` from the disclosures block. The figure is the evidence
  file's own, from the hashed database; the session records outside the repository
  are operating context that should agree with it, and are cited, not read, by the
  runner.
- **Before row B is recorded.** One full session of 23.5 hours against a throwaway
  database, its gap and failure count read from its record.
- The approval file `APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001.txt` (or the
  attended text) is retained beside the others; the manifest is regenerated; the rows
  go into `DECISION_LOG.md` by the owner's hand, as every row does.

## What this document does not do

It does not change the frozen plan, the two-arm approval or the build plan. It does not
authorise a scheduler, a service, a hidden window, a self-restarting session or any
execution a person did not start for that occasion. It does not open any look at a
return, a ranking or a comparison before day 56.
