# L2 analysis plan (preregistered before T0)

Status: `DRAFT_AWAITING_ARM_A_WINDOW_DECISION`. This file is frozen, and its commit
hash recorded as `T0`, before the first evaluation request is sent. Nothing in it
changes after T0. It carries no validator and no tamper tests by owner instruction;
its authority is that its hash is recorded in the T0 evidence. Approval:
`APPROVE_HL_LIVE_DATA_L2_TWO_ARM_STUDY_001` (DEC-043).

## The question

Does copying a directional Hyperliquid wallet, at a stated latency and after every
follower cost, earn more than copying a random wallet of similar activity? One
question, one primary measure, one decision rule, answered twice: once on history
(arm A) and once forward (arm B), with arm B the out-of-sample test of arm A.

## One cohort, frozen at T0

Up to 600 candidates are discovered from the public tape over several sessions and
pre-filtered at discovery: a candidate enters the cohort only if its first
characterisation pass says it rests fewer than 60 percent of its fills and does not
combine two-sided fills within 60 seconds with a median holding time of five minutes
or less. Rebate-dependent wallets (rebate income at least 25 percent of gross closed
P&L over the characterisation set) are excluded. The cohort list, its hash and the
instant `T0` are recorded before any evaluation request. Nothing is added or removed
afterwards; a wallet that later proves unscorable is reported as such.

## Instrument scope

In scope: perpetuals with a funding rate observed in the characterisation set and a
complete 15-minute candle series over the evaluation window (`L2-CANDLE-PROBE-001`
found complete series, maximum gap exactly 15 minutes, for 110 of 113 L1 coins;
young listings with short series are in scope only from their first candle).
Spot indices (`@`-prefixed) and HIP-3 equity perpetuals are out of scope: their
funding and liquidity are not what the cost model describes. Out-of-scope fills are
excluded and counted per wallet; a wallet with under 50 percent of its
characterisation notional in scope is not evaluated.

## Arm A — historical

Backfill 90 days of fills before T0 for every cohort wallet. Characterise on the
oldest 30 days (T0−90 to T0−60). Leave the 7 days before T0 empty as a buffer so
the discovery window lies outside the evaluation. Evaluate the days between.

Prices come from `candleSnapshot`, independent of the sample. Measured on
2026-09-04: the venue retains about 5000 candles per interval, rolling — 15-minute
candles reach 52 days back, 1-hour candles 208 days. So the approved 53-day
evaluation window (T0−60 to T0−7) is not fully coverable at the 15-minute price-age
bound. The owner chooses one of:

- **A-45**: evaluate T0−52 to T0−7 (45 days) at 15-minute candles, age bound 15
  minutes throughout.
- **A-53**: evaluate T0−60 to T0−7 (53 days); the oldest 8 days use 1-hour candles
  with a 60-minute age bound and are flagged as such in every outcome.
- **No arm A**: arm B alone, 56 days, target 0.5.

Because retention rolls forward one day per day, arm A's candles are fetched on the
day T0 is set; a delay of a week loses a week of the evaluation window.

Survivorship: the cohort is discovered at T0 from wallets active then, so wallets
that stopped trading during the historical window could not be discovered and are
absent by construction. Arm A's estimate is therefore inflated by an unknown amount.
The plan measures an order of magnitude: the share of cohort wallets whose last fill
in the evaluation window lies more than 7 days before its end (stopped inside the
window), and the share whose fill count in the last 14 evaluation days is under a
quarter of their characterisation rate (faded). Both are reported beside the primary
result and stated in plain language: "this arm cannot see wallets that quit".

## Arm B — forward, out of sample

The same frozen cohort over [T0, T0+56 days]. Fills polled over REST
(`userFillsByTime`) in operator-started sweeps; prices from `allMids` polled every
five minutes plus the public tape while a session is connected; funding from
`userFunding` paged past the 500-row cap. Arm B is the out-of-sample test of arm A:
its result is read only after day 56, however arm A came out.

## Primary measure

Per wallet `i`, at the primary latency of 30 seconds:

    d_i = R_i minus M_i

where `R_i` is the follower's net return on the capital the copy actually deployed
(cost basis, peak) over the arm's evaluation window and `M_i` is the mean of the same
measure over the wallet's matched-random peers (seeded, same window, same costs).
Primary statistic: mean of `d_i` over the evaluated set, two-sided one-sample t-test,
alpha 0.05, computed separately for arm A and arm B. Secondary latencies (1 s, 5 s,
2 min, 5 min, 15 min), buy-and-hold and momentum are reported and do not decide.

## Declared target effect and minimum detectable effect

Target effect: **0.5 points per 14-day equivalent** (13 percent a year). From
`L2-POWER-001` (directional sd 3.03 points over 7 days, scaled by sqrt(T/7)), the
MDE at power 0.80 in points per 14 days:

| evaluated wallets | 45 days | 53 days | 56 days |
|---|---|---|---|
| 200 | 0.47 | 0.44 | 0.42 |
| 300 | 0.39 | 0.36 | 0.35 |
| 400 | 0.33 | 0.31 | 0.30 |

With 300 or more evaluated wallets every arm resolves the target. Below 200 the
target is out of reach and the arm is reported as underpowered for it.

## Coupling of the arms

- `GO_TO_ENTITY_CLUSTER_RESEARCH` requires both arms positive at p below 0.05 with
  mean `d` at least 0.5 points per 14 days at 30 s, and arm B within one standard
  error of arm A.
- `NO_GO_NO_COPYABLE_ALPHA` is declared when arm B's upper 95 percent confidence
  bound lies below 0.5, whatever arm A showed.
- Arm A positive and arm B not: reported as survivorship inflation, with the gap
  `mean d_A minus mean d_B` as its measured size. That is a result, not a failure.
- Anything else is `REPAIR_AND_RERUN`, with the repair named before any rerun.

## Stop rule and what is not allowed

Each arm stops at its declared window end. No interim look at any result; only
operational health (sweep failures, coverage gaps, candle gaps, unscorable wallets)
is inspected during collection, by a script that prints counts and no returns.
Wallets whose coverage ledger cannot certify the full window at the end are excluded
and counted; if fewer than 200 remain in an arm, that arm is reported as a case
study and decides nothing. No wallet-level claims. No change to thresholds, scope,
measure, latency or windows after T0. No result leaves the repository before both
windows close and the disclosures are written.
