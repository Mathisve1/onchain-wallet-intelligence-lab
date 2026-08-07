# Latency and execution research model

Status: design only. No performance or profitability claim.

## Principle

The relevant delay is not model latency alone. It is the full interval from the earliest admissible observation of a source signal to the follower fill/reconciliation state.

```text
T_total =
  T_observe
+ T_decode
+ T_feature_read
+ T_deterministic_eligibility
+ T_model_or_AI
+ T_policy_recheck
+ T_permit
+ T_sign
+ T_transport
+ T_venue_accept
+ T_fill_or_cancel
+ T_reconcile
```

Every component must be measured with monotonic timestamps at its own boundary. Wall-clock timestamps are retained separately for cross-system correlation.

## Registered research latency arms

The successor research design keeps the previously proposed arms:

```text
0.2 s, 1 s, 3 s, 5 s, 10 s, 15 s, 30 s, 60 s, 120 s, 300 s
```

The 0.2-second arm is theoretical/diagnostic unless a later measured non-signing shadow pipeline proves that the complete admissible path can operate at that delay. No architecture document may silently relabel a theoretical arm as achievable.

## Two execution modes

### D — deterministic autonomy baseline

No LLM is on the critical path. A previously eligible source signal is evaluated through deterministic point-in-time filters, statistical model outputs already available in the feature store, risk arithmetic, permit creation and execution.

Purpose: establish whether removing human approval creates value by itself.

### A — deterministic autonomy plus AI critic

The deterministic eligible set is the ceiling. AI may only:

- return `PASS`;
- return `VETO`;
- lower confidence;
- attach structured risk codes.

It cannot add a trade that deterministic policy rejected, enlarge position size, widen slippage or extend expiry.

If a registered experiment requires an AI response and the critic times out, the outcome is `SKIP_AI_TIMEOUT`, not silent fallback to automatic execution.

## Initial engineering targets, not empirical claims

These targets are used only to size components before shadow measurement:

| Component | Design target p50 | Design target p95 | Failure behavior |
|---|---:|---:|---|
| event receipt + decode | <= 100 ms | <= 300 ms | skip/stale |
| feature-cache read | <= 20 ms | <= 75 ms | block |
| deterministic eligibility/risk | <= 20 ms | <= 75 ms | block |
| local statistical inference | <= 20 ms | <= 100 ms | block |
| AI critic | <= 750 ms | <= 3 s | skip if required |
| policy recheck + permit | <= 25 ms | <= 100 ms | block |
| signer | <= 25 ms | <= 100 ms | block |
| network submit + venue ack | measure only | measure only | reconcile |
| fill/cancel | market-dependent | market-dependent | explicit outcome |

These are **engineering hypotheses**. They have zero evidentiary weight until measured in a controlled shadow/test environment.

## Why a minute is not the primary target

A one-minute bound is technically easy for ordinary software, but economically irrelevant if source alpha decays in a few seconds. The system therefore measures follower outcome as a function of delay rather than adopting one universal execution deadline.

A source/wallet style is not eligible for an autonomous strategy merely because it is profitable at source. It must demonstrate positive future follower expectancy at the measured execution-delay distribution.

## Timestamp contract

Each signal/action record should eventually carry at least:

- `source_event_time_ms` — venue event timestamp when available;
- `first_observed_monotonic_ns`;
- `decode_done_monotonic_ns`;
- `features_ready_monotonic_ns`;
- `eligibility_done_monotonic_ns`;
- `ai_started_monotonic_ns` / `ai_done_monotonic_ns` if used;
- `policy_done_monotonic_ns`;
- `permit_issued_monotonic_ns`;
- `sign_started_monotonic_ns` / `sign_done_monotonic_ns`;
- `submit_monotonic_ns`;
- `venue_ack_monotonic_ns`;
- `first_fill_monotonic_ns`;
- `terminal_fill_or_cancel_monotonic_ns`;
- `reconciled_monotonic_ns`.

Missing timestamps never get imputed for canonical latency claims.

## Network path

Hyperliquid officially recommends WebSockets for lowest-latency realtime data and supports signed post requests through WebSocket as an alternative to HTTP. Both transports must later be benchmarked under the exact same policy/signer path.

The architecture must not assume WebSocket continuity. Hyperliquid documentation explicitly tells automated users to handle server disconnects and use snapshots/info requests to recover missed data.

## Submission experiment

When signed testnet is separately authorized, benchmark at minimum:

1. HTTP `/exchange` action submission;
2. WebSocket signed post submission;
3. identical IOC-limit actions and sizes;
4. identical geographic deployment;
5. warmed and cold connections separately;
6. p50/p75/p90/p95/p99 acknowledgement latency;
7. failure/reconnect/duplicate rates;
8. full receipt-to-reconciliation latency.

Transport choice is selected from measured end-to-end behavior, not documentation claims.

## Queueing and overload

The system must have bounded queues. If processing falls behind:

- old signals expire rather than queue indefinitely;
- risk-increasing intents are dropped once their maximum age is exceeded;
- emergency cancel/reduce messages have separate priority;
- rate-limit budgets are reserved for cancellation/reconciliation;
- the AI critic cannot consume resources required by safety services.

## Latency-economic output

The later parent-linked experiment must report, for each registered delay arm and wallet/style cohort:

- eligible-signal count;
- executed/blocked/expired/missed count;
- entry price drift;
- fill ratio;
- net follower return;
- tail loss;
- capture ratio versus source;
- result after doubled costs;
- capacity at proposed research size.

No latency optimization is promoted if it improves mean return while materially worsening tail risk, reconciliation integrity or unauthorized-action surface.