# Operator-started collection for arm B: four decisions the owner takes before T0

Status: `PROPOSED`. Nothing in this document is in force until the owner sends the
amending approval text below, unmodified, and records the four decision rows. The
frozen `L2_ANALYSIS_PLAN.md` does not change: these decisions say what its words
"operator-started sweeps; prices from `allMids` polled every five minutes" cover in
practice, over 56 days, on one laptop, by one person.

## Why the question exists

Arm B prices every copy with the last `allMids` quote at most 15 minutes old. A copy
without such a quote is not priced: the runner skips it as stale and counts it. So
arm B needs a mids poll every five minutes for 56 days, and the study's own texts
say who runs that poll:

- `L2_BUILD_PLAN.md`, phase 4: "A sweep never loops; the operator starts each one",
  and `allMids` "is a separate light command ... the operator runs in a loop of their
  own choosing (no scheduler in the repo)"; anti-pattern "no scheduler or sleep loop
  that runs unattended".
- `L2_PROPOSAL.md`, "Cost and gate": "every sweep is operator-initiated because
  scheduled execution stays unauthorised; roughly four sweeps a day", and the gate
  asked for "explicit permission for operator-initiated repeated sweeps".
- `HUMAN_APPROVAL_TEMPLATE.md`: `scheduled_execution_authorized=false`; an approval
  "does not install a workflow, authorize scheduled or unattended execution".
- `APPROVE_HL_LIVE_DATA_L2_FORWARD_STUDY_001` (DEC-042), line 7:
  `repeated_operator_started_sweeps_authorized=true`. The two-arm approval (DEC-043)
  supersedes that file and does not restate the line.

The loop that polls mids is written out as `C:\Users\mathi\owil-data\loop\collect_session.ps1`,
outside the repository: one bounded session a person starts in a visible console, which
stops at its bound, on Ctrl-C or on a stop file, registers nothing and never restarts
itself. It refuses two things without a decision reference: a session longer than 8 hours
(`-OvernightDecision DEC-0NN`) and sweeps started by its own clock
(`-ScheduledSweepsDecision DEC-0NN`). The four decisions below are the references it
is waiting for.

## What the words mean here

- **Operator-started.** A person starts each sweep and each mids session by hand, for
  that occasion, in a visible console. Nothing starts a request on a clock, a schedule,
  a service, a trigger, a hidden window, or by restarting itself.
- **Bounded.** A session has a stated end (at most the hours the approval names), stops
  by itself at that end, and records its start, its bound, and what ran it (script
  hash, repository commit, branch and dirty state, coin list, decision references).
- **Unattended execution**, which the template excludes, is execution no person started
  for that occasion: scheduled, triggered, or self-renewing. A bounded session a person
  started, running while that person is away from the screen, is *unwatched*; whether
  it is also "unattended" in the template's sense is what DEC-049 decides, not what
  the tool assumes. The L1 envelope already contained a watch of up to
  `maximum_watch_iterations=1000` at `snapshot_interval_seconds=60`, sixteen hours and
  forty minutes, under `scheduled_execution_authorized=false`: a long bounded run a
  person started was inside that envelope, a scheduled one was not.
- **The gap.** Between two sessions no mid is collected. The tool measures it (the
  previous session's last successful poll, the seconds since, an alarm above twelve
  minutes) and carries the unpriced time, the seconds beyond the 15-minute bound, per
  session and cumulatively into every session record. The dossier reports it.

## The amending approval (exact text; the owner sends it unmodified)

Replace `<COMMIT>` with the 40-character commit that carries this document. Change
nothing else. It is recorded like `APPROVE_HL_LIVE_DATA_L2_ARM_A_WINDOW_001` was under
DEC-044: retained beside the other approvals, with its SHA-256, in a decision row.

```
APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001
bound_commit=<COMMIT>
amends=APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001
repeated_operator_started_sweeps_authorized=true
sweep_started_by=OPERATOR_BY_HAND
scheduled_sweeps_authorized=false
mids_session_started_by=OPERATOR_IN_VISIBLE_CONSOLE
mids_session_maximum_hours=24
mids_session_attended_hours=8
session_series_is_operator_started=true
inter_session_gap_reported=true
scheduled_execution_authorized=false
workflow_installation_authorized=false
arm_b_unchanged=true
```

Two lines carry a choice. `mids_session_maximum_hours=24` is the recommendation of
DEC-049 below; the owner who rejects overnight sessions writes `8` there and rejects
DEC-049. `scheduled_sweeps_authorized=false` is the recommendation of DEC-050; the
owner who wants clock-started sweeps writes `true` there and accepts DEC-050 in its
other reading. Everything else is a restatement of what the study already says.

## The four decisions

### DEC-048: a series of bounded sessions, each started by hand, is operator-started collection

**Decision.** The frozen plan's "operator-started sweeps" and "`allMids` polled every
five minutes" are met by mids sessions of at most eight hours, each started by hand in
a visible console, self-stopping, run one after another over the 56 days; and by
sweeps started by hand from a second window, a few times a day, one closing sweep
after `T0+56d`. No decision reference is needed for such a session: eight hours is the
tool's attended bound. The gap between sessions is measured and reported, not hidden;
copies inside it are stale-skipped and counted, and the arm B report names the
cumulative unpriced time as a limitation of the attended model.

**Why.** It is what the build plan and the proposal describe, and the tool cannot be
configured past it by a flag alone. What it costs is stated in DEC-049.

### DEC-049: an overnight session of at most 24 hours is operator-started, on conditions

**Decision (recommended: accept).** A mids session of more than eight and at most
twenty-four hours is operator-started collection when (1) a person starts it by hand
in a visible console and reads its banner, (2) the machine is prepared beforehand
(sleep, hibernation and lid action off on mains power; Windows Update active hours or
pause set for the study), (3) the person reads the session's summary or status file at
the next start, (4) the session records `overnight_decision=DEC-049` and the gap
since the previous session, and (5) nothing starts the next session but a person.
The tool accepts such a session only with `-OvernightDecision DEC-049`.

**Why accept.** With attended sessions alone, about sixteen of every twenty-four hours
carry no mid, so roughly two thirds of the cohort's copies are unpriced and skipped,
and the third that is priced is the operator's waking hours in Europe: a time-of-day
selection the venue's activity does not share. Arm B would then be read on a
systematically chosen slice of the window. A session of twenty-four hours started each
morning leaves a gap of minutes. The session has the shape the L1 envelope already
allowed (a long bounded run a person started, no schedule), and every one of them is
in the dossier with its start, its bound, its gap and who started it.

**If rejected.** Sessions stay within eight hours; the amending approval says
`mids_session_maximum_hours=8`; the arm B report states the unpriced share and the
time-of-day limitation in its answer, not in a footnote.

### DEC-050: the script's clock does not start sweeps

**Decision (recommended: accept this reading).** Sweeps are started by hand only.
The tool's `-SweepEveryHours` stays refused, and its refusal cites this row. Fills and
funding carry the venue's own timestamps, so the cadence of sweeps changes nothing in
the measurement; it changes only how complete the ledger is on a given day, and the
closing sweep after `T0+56d` is what the day-56 read waits for. A sweep run by the
mids session would block the polls for as long as it takes, and a sweep of more than
fifteen minutes would open a price gap the tool could only report afterwards. There
is nothing to gain and a frozen model to keep.

**If the owner wants clock-started sweeps instead.** The amending approval says
`scheduled_sweeps_authorized=true`, the row says so, the tool takes
`-ScheduledSweepsDecision DEC-050` and discloses on its banner, every session, that
the script's clock starts sweeps. That reading is a departure from `L2_BUILD_PLAN.md`
phase 4 and should say so in the row.

### DEC-051: the permission for repeated operator-started sweeps is restated in the current chain

**Decision.** The explicit line `repeated_operator_started_sweeps_authorized=true`,
present in `APPROVE_HL_LIVE_DATA_L2_FORWARD_STUDY_001` (DEC-042) and absent from the
superseding `APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001` (DEC-043), is restated by the
amending approval above for arm B's window `[T0, T0+56d]` and its closing sweep, with
the cadence the build plan gives. From that row on, the tool, the runbook and the
README cite this approval and the frozen plan, and no longer a superseded text.

**Why.** The study's authority for a repeated request pattern should be readable from
the current approval chain, not inferred from a file that was superseded.

## The rows, ready to record

The decision log is a table with one paragraph per row. These are the rows as
proposed; the owner changes what the owner decides otherwise and fills in the date,
the SHA-256 and the commit.

| ID | Date | Status | Decision |
|---|---|---|---|
| DEC-048 | `<date>` | accepted | A series of bounded mids sessions for arm B, each of at most 8 hours, each started by hand in a visible console and self-stopping, together with sweeps started by hand from a second window a few times a day and one closing sweep after `T0+56d`, is operator-started collection under the frozen `L2_ANALYSIS_PLAN.md` ("operator-started sweeps; prices from `allMids` polled every five minutes") and `L2_BUILD_PLAN.md` phase 4. The session tool (`collect_session.ps1`, outside the repository, hash recorded per session) needs no decision reference for such a session. The gap between sessions is measured by the tool (previous session's last successful poll, seconds since, alarm above twelve minutes) and carried as cumulative unpriced time into every session record; copies inside a gap are stale-skipped and counted; the arm B report names the cumulative unpriced time as a limitation. Definitions per `L2_OPERATOR_SESSIONS.md`. |
| DEC-049 | `<date>` | accepted | Accept the owner's exact `APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001` (fourteen lines, retained beside the other approvals, SHA-256 `<sha256>`), bound to commit `<commit>`, amending DEC-043: a mids session of more than 8 and at most 24 hours is operator-started collection when a person starts it by hand in a visible console and reads its banner, the machine is prepared beforehand (sleep, hibernation and lid action off on mains; Windows Update active hours or pause set), the person reads the summary or status at the next start, the session records `overnight_decision=DEC-049` and the gap since the previous session, and nothing but a person starts the next one. Accepted because attended sessions alone leave about sixteen hours a day unpriced and read arm B on the operator's waking hours, a time-of-day selection; a 24-hour session started each morning leaves a gap of minutes; the shape is the one the L1 envelope allowed (`maximum_watch_iterations=1000` at 60 s under `scheduled_execution_authorized=false`). Scheduled, triggered or self-renewing execution stays unauthorised. The tool accepts such a session only with `-OvernightDecision DEC-049`. |
| DEC-050 | `<date>` | accepted | Sweeps for arm B are started by hand only; the session tool's clock does not start them. `-SweepEveryHours` stays refused and the refusal cites this row. Fills and funding carry the venue's timestamps, so sweep cadence does not touch the measurement, only the ledger's completeness on a given day, and the closing sweep after `T0+56d` is what the day-56 read waits for; a sweep inside the mids session would block the polls and one over fifteen minutes would open a price gap. `scheduled_sweeps_authorized=false` in `APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001`. |
| DEC-051 | `<date>` | accepted | The permission `repeated_operator_started_sweeps_authorized=true`, explicit in `APPROVE_HL_LIVE_DATA_L2_FORWARD_STUDY_001` (DEC-042) and not restated by the superseding `APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001` (DEC-043), is restated for arm B's window `[T0, T0+56d]` and its closing sweep by `APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001` (DEC-049), with the cadence `L2_BUILD_PLAN.md` phase 4 gives (a sweep every few hours by hand, `allMids` every five minutes). The session tool, the runbook and its README cite that approval and the frozen plan as the authority for repeated sweeps, and no longer the superseded text. |

## What changes when the rows are recorded

- `collect_session.ps1`: nothing in the code. The operator passes
  `-SessionHours 24 -OvernightDecision DEC-049` for an overnight session (DEC-049
  accepted) and never `-SweepEveryHours` (DEC-050). The README's parameter table and
  the runbook name the references.
- The arm B report (`l2_arm_render.py`, disclosures): the cumulative unpriced time
  from the session records is named as a limitation, with the number of sessions and
  the longest gap. This is a report line, not a new measure; it is added before the
  day-56 read and does not touch the frozen plan.
- The approval file `APPROVE_HL_LIVE_DATA_L2_OPERATOR_SESSIONS_001.txt` is retained
  beside the others; the manifest is regenerated; the four rows go into
  `DECISION_LOG.md` by the owner's hand, as every row does.

## What this document does not do

It does not change the frozen plan, the two-arm approval, the build plan or the tool.
It does not authorise a scheduler, a service, a hidden window, a self-restarting
session or any execution a person did not start for that occasion. It does not open
any look at a return, a ranking or a comparison before day 56.
