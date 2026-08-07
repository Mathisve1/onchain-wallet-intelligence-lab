# Roadmap

## Phase 0 — closed intake

- [x] Freeze the research question and falsification-first hypothesis.
- [x] Separate source-wallet P&L from follower P&L.
- [x] Freeze point-in-time selection and latency sensitivities.
- [x] Define a read-only data and execution boundary.
- [x] Define initial confirmed-link clustering only.
- [x] Create permanent validation and negative tests.

## Phase 1 — public technical evidence

- [ ] Run the read-only `/info` and official archive-availability probe.
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
