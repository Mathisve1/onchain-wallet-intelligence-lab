# Point-in-time wallet-style classification

## Objective

Identify source activity that is economically interpretable and potentially
copyable at follower latency. A high source return or win rate is not an
eligibility rule.

Every classification is timestamped and may use only evidence whose
`first_seen_at` is not later than the selection cutoff.

## Primary classes

| Class | Description | Initial autonomy eligibility |
|---|---|---|
| `DIRECTIONAL_SWING` | Position changes held for minutes to days with interpretable directional exposure | eligible after all gates |
| `DIRECTIONAL_INTRADAY` | Directional exposure held long enough to test 1–300 s follower latency | eligible after all gates |
| `SYSTEMATIC_REBALANCER` | Repeated, non-atomic changes that may encode a slower allocation signal | research-only until hidden hedge tests pass |
| `MARKET_MAKER` | Two-sided inventory and spread-capture behavior | excluded from copy mode |
| `ATOMIC_OR_NEAR_ATOMIC_ARBITRAGE` | Profit depends on contemporaneous multi-leg execution | excluded |
| `LIQUIDATION_OR_RESCUE_FLOW` | Position changes driven by forced liquidation or account rescue | excluded |
| `HIGH_FREQUENCY_EXECUTION_BOT` | Advantage depends on sub-second queueing, order replacement or microstructure | excluded from human and normal bounded-autonomy modes |
| `VAULT_SERVICE_OR_ROUTER` | Shared service, vault, treasury or routing address | excluded as an independent trader |
| `HEDGED_OR_EXTERNAL_EXPOSURE_UNKNOWN` | Visible position is likely offset elsewhere | excluded from directional copy claim |
| `INSUFFICIENT_HISTORY` | Sample, cost basis or position reconstruction is incomplete | blocked |
| `STYLE_DRIFT` | Current behavior materially differs from the frozen eligible style | blocked pending reclassification |

## Features

The deterministic classifier may use, point in time:

- position-direction persistence;
- holding-time distribution;
- order and fill frequency;
- two-sided turnover;
- inventory mean reversion;
- open/close asymmetry;
- realized versus unrealized P&L;
- funding exposure;
- leverage and liquidation proximity;
- concentration by instrument;
- source-to-market timing;
- master/subaccount or official vault role;
- recurring transfer and capital-flow motifs after the entity-resolution gate;
- copy-capture and alpha-decay curves from development data only.

Text labels and AI explanations are non-canonical.

## Hard exclusions

A source event is not eligible when:

- the canonical ledger is incomplete;
- deposit or transfer flows cannot be separated from profit;
- the source reverses before the follower can enter;
- expected follower capacity is below the frozen minimum size;
- the source is a confirmed service, vault or market-making structure;
- the edge requires atomic multi-leg execution;
- hidden-hedge probability exceeds the frozen threshold;
- the wallet or cluster has entered `STYLE_DRIFT`;
- the source event or required market state is stale;
- the follower-EV lower bound is non-positive;
- the event breaches any deterministic risk rule.

## Style drift

Style is recalculated on a rolling basis using only past data. Drift tests cover:

- holding-time shift;
- instrument-mix shift;
- leverage shift;
- turnover and order-frequency shift;
- two-sidedness shift;
- source/follower capture deterioration;
- new master/subaccount, vault or service relationship;
- new concentration or liquidation behavior.

A drift alarm pauses new signals from that source. Historical performance is not
rewritten.

## Multiple-wallet independence

Addresses are not counted as independent merely because they are different.
Before entity-resolution research passes, only confirmed links are merged and
all unresolved dependence is reported as a sensitivity. Later probabilistic
clusters must be time-versioned and cannot use future links.
