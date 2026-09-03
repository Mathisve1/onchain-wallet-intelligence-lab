# L2 analysis plan (preregistered before T0)

Status: `DRAFT_AWAITING_WINDOW_DECISION`. This file is frozen, and its commit hash
recorded as `T0`, before the first evaluation request is sent. Nothing in it
changes after T0. It carries no validator and no tamper tests by owner instruction;
its authority is that its hash is recorded in the T0 evidence.

## The question

Does copying a directional Hyperliquid wallet, at a stated latency and after every
follower cost, earn more than copying a random wallet of similar activity? One
question, one primary measure, one decision rule.

## Primary measure

Per wallet `i` in the evaluation set, at the primary latency of 30 seconds:

    d_i = R_i minus M_i

where `R_i` is the follower's net return on the capital the copy actually deployed
(cost basis, peak), over the evaluation window, and `M_i` is the mean of the same
measure over that wallet's matched-random peers (seeded, same window, same costs).
The primary statistic is the mean of `d_i` over the evaluation set with a
two-sided one-sample t-test, alpha 0.05. Secondary latencies (1 s, 5 s, 2 min,
5 min, 15 min) and the buy-and-hold and momentum comparisons are reported but do
not decide.

## Minimum detectable effect (declared, from L2-POWER-001)

Dispersion source: the three directional wallets in the L1 pilot, sd 3.03 points
over 7 days, scaled by sqrt(T/7). MDE at power 0.80, in points per 14-day
equivalent:

| window | n = 100 | n = 130 | n = 200 |
|---|---|---|---|
| 14 days | 1.20 | 1.05 | 0.85 |
| 28 days | 0.85 | 0.74 | 0.60 |
| 56 days | 0.60 | 0.53 | 0.42 |
| 91 days | 0.47 | 0.41 | 0.33 |

A realistic sustained edge after copy costs is 0.3 to 0.5 points per 14 days
(8 to 13 percent a year). The approved 14-day window therefore detects only a
large edge, of order 1 point per 14 days (26 percent a year). The window is the
owner's decision and is left open here; the declared target effect follows it:

- 14 days: target effect 1.0 point per 14 days. Reads as a screen for a large edge.
- 56 days: target effect 0.5 point per 14 days. Reads as a test of a realistic edge.

## Evaluation set

Wallets that at T0 satisfy all of: classified `DIRECTIONAL` on the characterisation
set (maker share below 0.60, and not both two-sided share at least 0.50 and median
holding at most 5 minutes); not rebate-dependent (source rebate income below 25
percent of source gross closed P&L on the characterisation set); at least 20
characterisation fills; at least 50 percent of characterisation notional in
in-scope instruments. In-scope instruments: perpetuals with a funding rate observed
in the characterisation set and at least one `allMids` price per 5 minutes over
the window; spot indices (`@`-prefixed) and HIP-3 equity perpetuals are out of
scope and their fills are excluded and counted. The evaluation set is frozen at T0
and its hash recorded; wallets are not added or removed afterwards.

## Stop rule and NO_GO

- The study stops at the declared window end. No interim look at any result; only
  operational health (sweep failures, coverage gaps, price gaps) is inspected
  during the window, by a script that prints counts and no returns.
- A wallet whose coverage ledger cannot certify the full window at the end is
  excluded and counted; if fewer than 40 wallets remain certified, the study is
  reported as a case study and no decision is made.
- `GO_TO_ENTITY_CLUSTER_RESEARCH` requires the primary statistic to be positive with
  p below 0.05 and a mean `d` of at least the declared target effect, at 30 s.
- `NO_GO_NO_COPYABLE_ALPHA` is declared when the upper 95 percent confidence bound
  of the mean `d` at 30 s lies below the declared target effect.
- Anything else is `REPAIR_AND_RERUN`, with the repair named before any rerun.

## What is not allowed

No wallet-level claims: the design cannot resolve a single wallet in any feasible
window (94 windows of 14 days for one wallet at 1 point). No change to thresholds,
scope, measure or latency after T0. No result leaves the repository before the
window closes and the disclosure is written.
