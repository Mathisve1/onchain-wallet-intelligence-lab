# Latency experiment

## Purpose

Measure how quickly copyable alpha decays and whether removing per-trade human
approval creates material **net** value after all added infrastructure,
rejection and operational costs.

## Required timestamps

Every source event and hypothetical or future real action requires:

| Timestamp | Meaning |
|---|---|
| `source_event_time` | venue event time of the executed source fill |
| `source_block_time` | canonical block/ledger time where applicable |
| `source_first_seen_at` | first local observation of the source event |
| `ingest_completed_at` | raw event persisted and hashed |
| `decode_completed_at` | source position change decoded |
| `feature_snapshot_at` | point-in-time features frozen |
| `model_started_at` / `model_completed_at` | statistical and AI inference window |
| `policy_started_at` / `policy_completed_at` | deterministic policy window |
| `quote_observed_at` | executable follower quote/depth snapshot |
| `intent_created_at` | typed intent identity fixed |
| `permit_created_at` | exact one-time permit fixed |
| `signing_started_at` / `signing_completed_at` | restricted signer window |
| `submitted_at` | action sent to venue |
| `venue_ack_at` | venue acknowledgement |
| `first_fill_at` / `last_fill_at` | fill interval |
| `reconciled_at` | order, fill and position state reconciled |

Clocks must be UTC, monotonic where possible and continuously checked for drift.

## Registered grid

```text
0.2 s
1 s
3 s
5 s
10 s
15 s
30 s
60 s
120 s
300 s
```

The grid applies independently to entry and exit. Entry and exit may use
different empirically observed latency distributions.

## Interpretation

- `0.2 s` is an engineering lower-bound diagnostic.
- `1–10 s` is the primary bounded-autonomy window.
- `15–60 s` covers slower policy, infrastructure and one-click cases.
- `120–300 s` covers manual decision workflows and slower alpha.

No latency arm is called feasible until live non-signing shadow measurements
show the full pipeline at its preregistered percentile.

## Historical replay

Historical replay must:

1. observe the source executed fill;
2. advance to the exact latency cutoff;
3. use the first executable follower bid/ask and depth after the cutoff;
4. walk depth at the frozen follower size;
5. model partial and missed fills;
6. simulate source-proportional and independent risk exits;
7. charge all costs over the follower holding interval;
8. retain every blocked, expired and missed event.

Historical public data generally cannot reconstruct every local observation and
network timestamp. Modeled components are explicitly labeled and may not be
represented as observed latency.

## Live shadow calibration

Before any signed stage, shadow mode must measure:

- p50, p75, p90, p95 and maximum by component;
- provider disagreement;
- reconnect and backfill behavior;
- model warm/cold latency;
- policy and quote refresh latency;
- proposal expiry rate;
- order-intent staleness;
- missed source events;
- clock drift;
- simulated fill versus later observed depth/fill.

The empirical latency distribution replaces assumed human or machine latency in
the final comparison.

## Fair comparison

All execution modes receive:

- the same eligible source events;
- the same point-in-time data cutoff;
- the same follower size;
- the same fee/funding/slippage model;
- the same exit definitions;
- the same blocked-event accounting.

Human modes use measured approval time. Autonomous modes do not receive extra
future data while the human is deciding.

## Required reports

- follower-EV curve by latency;
- alpha half-life and confidence interval;
- copy-capture curve;
- missed/blocked rate by latency;
- cost share by component;
- capacity by latency;
- results by wallet class, instrument and regime;
- incremental value from deterministic autonomy;
- incremental value, if any, from the AI critic;
- sensitivity to p90/p95 latency and 2x costs.
