# Roadmap

## Phase 0 — closed intake

- [x] Freeze the research question and falsification-first hypothesis.
- [x] Separate source-wallet P&L from follower P&L.
- [x] Freeze point-in-time selection and latency sensitivities.
- [x] Define a read-only data and execution boundary.
- [x] Define initial confirmed-link clustering only.
- [x] Create permanent validation and negative tests.

## Phase 1 — public technical evidence

- [ ] Complete the final capacity-safe read-only `/info` and official
  archive-route probe.
- [ ] Retain exact response shapes, hashes, workflow run and job IDs.
- [ ] Resolve API-limit and historical-pagination documentation conflicts.
- [ ] Freeze archive object inventory, estimated requester cost and retention.

## Phase 2 — deterministic wallet ledger

- [ ] Parse fills, funding, deposits, withdrawals, internal transfers,
  subaccount transfers, liquidations and vault events.
- [ ] Reconcile positions, closed P&L, account state and cash flows.
- [ ] Produce gap, duplicate and schema-drift reports.
- [ ] Reject any performance estimate that cannot separate deposits from profit.

## Phase 3 — point-in-time individual copyability

- [ ] Build the eligible wallet universe using only past information.
- [ ] Classify directionality, holding period, leverage and likely market making.
- [ ] Simulate follower execution at 1 s, 5 s, 30 s, 2 m, 5 m and 15 m.
- [ ] Compare against no-trade, buy-and-hold, momentum and matched-random baselines.
- [ ] End with one decision: `GO_TO_ENTITY_CLUSTER_RESEARCH`,
  `REPAIR_AND_RERUN`, or `NO_GO_NO_COPYABLE_ALPHA`.

## Phase 4 — entity resolution

Only after Phase 3 passes:

- confirmed master/subaccount and vault/service relationships;
- recurring capital-flow motifs;
- treasury, beneficiary and execution-engine hypotheses;
- behavioural fingerprints;
- time-versioned probabilistic clusters;
- net cluster exposure and independent-consensus counting.

## Phase 5 — consensus and cross-venue research

- independent smart-money cluster consensus;
- hidden-hedge probability;
- dYdX and other transparent venues;
- CEX deposit/withdrawal context without assuming internal CEX positions;
- AI incremental-value test against deterministic baselines.

## Phase 6 — bounded-autonomy historical comparison

Only after positive point-in-time follower evidence:

- [ ] Freeze `DEX-COPY-AUTONOMY-001` eligible signals and exact parent hashes.
- [ ] Replay the same signals at 0.2, 1, 3, 5, 10, 15, 30, 60, 120 and 300 s.
- [ ] Separate signal alpha, execution alpha and source-wallet alpha.
- [ ] Compare deterministic-only, deterministic-plus-AI-critic, one-click human
  and manual-human modes.
- [ ] Measure p50/p75/p90/p95 end-to-end latency from observed timestamps.
- [ ] End with `GO_TO_SHADOW_DESIGN`, `REPAIR_AND_RERUN`,
  `NO_GO_BOUNDED_AUTONOMY`, or `NO_GO_NO_COPYABLE_ALPHA`.

## Phase 7 — non-signing shadow system

Requires a separate authorization:

- [ ] Realtime source-event detection and full policy evaluation.
- [ ] Exact hypothetical order intent, quote, risk snapshot and expiry.
- [ ] No key, signature, order endpoint or venue action.
- [ ] At least the preregistered sample and calendar duration.
- [ ] Complete missed-event, stale-event and counterfactual decision ledger.

## Phase 8 — adversarial security and fork/testnet execution

Requires separate signed-test authorization:

- [ ] Isolated account/subaccount and disposable agent wallet.
- [ ] External policy service and restricted signer.
- [ ] Action-type allowlist and transfer/withdrawal denial.
- [ ] Replay, nonce, duplicate, stale-data, prompt-injection and outage tests.
- [ ] Kill switch, cancel-all and recovery drills.
- [ ] Exact action/fill reconciliation and zero unexplained actions.

## Phase 9 — isolated live pilot

Requires an independent governance decision after Phases 6–8:

- [ ] Exact human-frozen capital and risk envelope.
- [ ] One venue, one isolated account, BTC/ETH/SOL only.
- [ ] No leverage expansion, borrowing, bridges, withdrawals or client funds.
- [ ] Canary rollout, automatic pause and full audit trail.
- [ ] Execution correctness is evaluated before profitability.

## Phase 10 — optional EVM AMM/DEX successor

Uniswap, PancakeSwap, Safe/Zodiac, private routing and token-contract security
are a separate experiment. Hyperliquid evidence cannot be transferred to
memecoin, AMM, smart-contract or MEV claims without a new preregistration.
