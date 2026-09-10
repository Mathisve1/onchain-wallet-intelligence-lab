# L2 analysis plan (preregistered before T0)

Status: `FROZEN`. Frozen on 2026-09-04 under DEC-043 and DEC-044, before any
evaluation request; amended once on 2026-09-05 under DEC-046, still before T0 and
before any collection request, to add the owner's pre-registered reading of arm A
(the section "How arm A is read, fixed before it is seen"); amended a second time
on 2026-09-09, still before T0 and before any collection request, under the
decision the owner records on accepting it, to fix the peer pool of the
matched-random baseline (the section "Peer pool for the matched-random
baseline, fixed before it is drawn"). The commit that contains this frozen text is cited in the T0
evidence together with the cohort hash. Nothing in it changes after T0. It carries no
validator and no tamper tests by owner instruction; its authority is that hash.

## The question

Does copying a directional Hyperliquid wallet, at a stated latency and after every
follower cost, earn more than copying a random wallet of similar activity? One
question, one primary measure, one decision rule, answered twice: once on history
(arm A, the early read) and once forward (arm B, which decides).

## One cohort, frozen at T0

Up to 600 candidates are discovered from the public tape over several sessions and
pre-filtered at discovery: a candidate enters the cohort only if its first
characterisation pass says it rests fewer than 60 percent of its fills and does not
combine two-sided fills within 60 seconds with a median holding time of five minutes
or less. Rebate-dependent wallets (rebate income at least 25 percent of gross closed
P&L over the characterisation set) are excluded. The cohort list, its hash and the
instant `T0` are recorded before any evaluation request. Nothing is added or removed
afterwards; a wallet that later proves unscorable is reported as such.

**Hard stop before evaluation.** Discover and filter first, then count. If fewer than
200 wallets are evaluable after the instrument-scope and coverage filters, the study
does not proceed to evaluation; it returns to the owner to widen the candidate pool
while the candle retention clock still allows it. That window cannot be recovered
afterwards.

## Instrument scope

In scope: perpetuals with a funding rate observed in the characterisation set and a
complete 15-minute candle series over the evaluation window (`L2-CANDLE-PROBE-001`:
complete series, maximum gap exactly 15 minutes, for 110 of 113 L1 coins; young
listings are in scope only from their first candle). Out of scope: spot indices
(`@`-prefixed), HIP-3 equity perpetuals (`xyz:`), and the three coins the probe could
not measure. Out-of-scope fills are excluded and counted per wallet; a wallet with
under 50 percent of its characterisation notional in scope is not evaluated.

## Arm A — historical, the early read (variant A-45)

Backfill 90 days of fills before T0 for every cohort wallet. Characterise on the
oldest 30 days (T0−90 to T0−60). Evaluate **T0−52 to T0−7** (45 days) on 15-minute
`candleSnapshot` candles fetched on the day T0 is set, with a 15-minute price-age
bound throughout; no mixed-resolution series. The 7 days before T0 are a buffer so
the discovery window lies outside the evaluation. Days between T0−60 and T0−52 are
not evaluated: the venue retains only 52 days of 15-minute candles, and hourly
candles cannot resolve a 30-second copy from a 15-minute one, which is the question.

Survivorship: the cohort is discovered at T0 from wallets active then, so wallets
that stopped trading during the historical window could not be discovered and are
absent by construction. Arm A's estimate is therefore inflated by an unknown amount.
In plain language: this arm cannot see wallets that quit. The plan measures an order
of magnitude: the share of cohort wallets whose last fill in the evaluation window
lies more than 7 days before its end (stopped inside the window), and the share
whose fill count in the last 14 evaluation days is under a quarter of their
characterisation rate (faded). Both are reported beside the primary result.

## Arm B — forward, decisive

The same frozen cohort over [T0, T0+56 days]. Fills polled over REST
(`userFillsByTime`) in operator-started sweeps; prices from `allMids` polled every
five minutes plus the public tape while a session is connected; funding from
`userFunding` paged past the 500-row cap. Arm B's result is read only after day 56,
however arm A came out.

## Primary measure

Per wallet `i`, at the primary latency of 30 seconds:

    d_i = R_i minus M_i

where `R_i` is the follower's net return on the capital the copy actually deployed
(cost basis, peak) over the arm's evaluation window and `M_i` is the mean of the same
measure over the wallet's matched-random peers (seeded, same window, same costs).
Primary statistic: mean of `d_i` over the evaluated set, two-sided one-sample t-test,
alpha 0.05, computed separately for arm A and arm B. Secondary latencies (1 s, 5 s,
2 min, 5 min, 15 min), buy-and-hold and momentum are reported and do not decide.

## Peer pool for the matched-random baseline, fixed before it is drawn

The primary measure contrasts each cohort wallet with its matched-random peers.
The frozen text says the peers are wallets of similar activity over the same
window at the same costs; it does not say which wallets they are drawn from.
This amendment fixes that, before any peer is drawn.

- **The pool.** Every wallet in the study database whose coverage ledger
  certifies the arm's whole evaluation window, cohort member or not. Which
  wallets those are follows from what was collected: for arm A, the wallets
  characterised before T0, whose backfills cover `T0-52d` to `T0-7d`; for
  arm B, the wallets the sweeps cover from T0 to `T0+56d`. The selection that
  formed the cohort is not a condition either way, so the pool contains the
  cohort and the characterised wallets the selection filtered out.
- **The peers of wallet `i`.** Drawn from the pool without `i` itself, among
  the wallets whose fill count over the window lies within 50 percent either
  side of `i`'s own; 20 of them, sampled with a seed derived from the frozen
  cohort hash; each scored over the same window, the same costs, the same
  latency and the same price-age bound as `i`. Fewer than 20 eligible: all of
  them, and the count is written per wallet. None: `i` has no `M_i`, enters no
  primary statistic, and is counted as refused, never scored zero.
- **Why the cohort cannot be its own pool.** With the cohort as its own pool,
  the mean of `d_i` subtracts the cohort's own mean return from itself, and
  any return the cohort earns in common, which is the copyable part, is
  cancelled by construction. A Monte Carlo at three times the target effect
  read as zero under that convention.
- **One rule, both arms, and what it costs in arm B.** Arm A's pool is
  certified by the backfills that already exist. Arm B's pool is certified
  only by the sweeps, so during the 56 days the sweep covers the whole
  characterised set, not the cohort alone; otherwise arm B's pool collapses
  to the cohort and the contrast is lost in the decisive arm. The pool's
  wallet list is frozen at T0 beside the cohort, with its own hash.
- **Recorded, not corrected.** Each arm's evidence file carries the pool's
  size and SHA-256 and the per-wallet peer counts. The two arms' pools may
  differ in size through attrition; the difference is disclosed in the
  limitations and is not adjusted for.

## Declared target effect and minimum detectable effect

Target effect: **0.5 points per 14-day equivalent** (13 percent a year). From
`L2-POWER-001` (directional sd 3.03 points over 7 days, scaled by sqrt(T/7)), the
MDE at power 0.80 in points per 14 days:

| evaluated wallets | arm A, 45 days | arm B, 56 days |
|---|---|---|
| 200 | 0.47 | 0.42 |
| 300 | 0.39 | 0.35 |
| 400 | 0.33 | 0.30 |

With 300 or more evaluated wallets both arms resolve the target. Below 200 the
hard stop above applies.

## Decision rule: B decides, A measures

- `GO_TO_ENTITY_CLUSTER_RESEARCH` when arm B's lower 95 percent confidence bound on
  the mean `d` at 30 s reaches 0.5 points per 14 days. Arm A cannot overrule this.
- `NO_GO_NO_COPYABLE_ALPHA` when arm B's upper 95 percent confidence bound stays
  below 0.5. Arm A cannot overrule this either.
- Anything else from arm B is `REPAIR_AND_RERUN`, with the repair named before any
  rerun.
- Arm A is the early read. `mean d_A minus mean d_B` is the measured survivorship
  inflation, reported as a number: a result, not a gate.
- A large gap between the arms in either direction does not reject anything by
  itself, but obliges a written diagnosis of where it comes from before any GO is
  acted on. The case "A negative, B positive" is named explicitly in the report,
  never handled silently.

## How arm A is read, fixed before it is seen

The owner recorded, before T0 and before any result exists, how each possible
outcome of arm A is read. The bar does not move afterwards; a later reading that
differs from this one is a change of mind, not an insight.

1. **Fewer than 200 evaluable wallets after filtering.** The run stops before
   any evaluation and returns to the owner, who widens the pool. The report
   states the clock price of the delay: how many evaluation days the candle
   retention (about 52 days at 15 minutes, rolling) loses per day of delay. No
   underpowered study is run "to have something".
2. **Arm A negative** (upper 95 percent bound below 0.5 points per 14 days).
   A strong signal, not a disappointment: survivorship biases this arm upward,
   so a negative outcome in the arm that should read too high is harder to
   explain away than a negative in the clean arm. Arm B continues and decides.
   No search for a variant that works.
3. **Arm A positive** (lower 95 percent bound above 0.5). Interesting, not
   actionable. B decides, weeks later. The survivorship measurement is
   reported beside it and matters more than the point estimate. Nothing is
   built on one contaminated arm.
4. **Arm A inconclusive** (the interval contains 0.5). Reported as
   inconclusive, without reinterpretation.
5. **Something breaks in the build or the collection.** Stop and report.

### Excluded in advance

- **No subgroup hunting.** If the primary measure at 30 s misses the target,
  no latency, coin, wallet class or time window is searched for one that
  meets it. Such cuts may be computed and shown, but every one of them carries
  the label `EXPLORATORY`, can never carry a GO, and is at most a hypothesis
  for a next, separately preregistered study.
- **No lowering of the target afterwards.** 0.5 points per 14 days stands. If
  the data show that 0.35 would have been detectable with more wallets, that
  is a lesson for the next study, not a reinterpretation of this one.

### Report order for arm A

Delivered only when arm A is complete, in this order: the answer in one
sentence; the confidence interval; the survivorship measurement (both
measures declared above); n after every filter stage; what broke; only then
the tables.

## Stop rule and what is not allowed

Each arm stops at its declared window end. No interim look at any result; only
operational health (sweep failures, coverage gaps, candle gaps, unscorable wallets)
is inspected during collection, by a script that prints counts and no returns.
Wallets whose coverage ledger cannot certify the full window at the end are excluded
and counted; if fewer than 200 remain in an arm, that arm is reported as a case
study and decides nothing. No wallet-level claims. No change to thresholds, scope,
measure, latency or windows after T0. No result leaves the repository before both
windows close and the disclosures are written.
