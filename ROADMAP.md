# Roadmap

## Phase 0 — closed intake

- [x] Freeze the research question and falsification-first hypothesis.
- [x] Separate source-wallet P&L from follower P&L.
- [x] Freeze point-in-time selection and latency sensitivities.
- [x] Define a read-only data and execution boundary.
- [x] Define initial confirmed-link clustering only.
- [x] Create permanent validation and negative tests.
- [x] Move the program into a dedicated private repository.

## Phase 1A — public technical probe R1

- [x] Freeze the exact 18-request probe contract.
- [x] Freeze the three-origin network allowlist and cross-origin redirect block.
- [x] Freeze response byte, retry, request-count and declared-weight ceilings.
- [x] Use official documentation example addresses only as public technical
  fixtures, with no real-world identity claim.
- [x] Retain response hashes, schemas, aggregate counts and time bounds only.
- [x] Add an independently validated terminal-state derivation.
- [x] Add an immutable artifact workflow with pinned actions.
- [x] Add adversarial tests against hidden fields, manual PASS relabeling,
  unknown probes, false relationship passes, extra origins and action endpoints.
- [ ] Execute the exact reviewed branch through GitHub Actions.
- [ ] Download and independently inspect the exact artifact.
- [ ] Bind run ID, numeric job ID, artifact ID, artifact digest and output SHA-256.
- [ ] Commit the exact technical output and rerun full CI.
- [ ] Complete clean-context review before merge.

## Phase 1B — official archive inventory

Opens only after Phase 1A produces reviewed PASS or an explicitly accepted
PARTIAL that identifies a bounded repair path.

- [ ] Enumerate `node_fills_by_block`, older fill formats, `market_data` and
  `asset_ctxs` object families.
- [ ] Freeze object paths, sizes, timestamps, schemas and requester-pays status.
- [ ] Estimate download, transfer, compute and retention costs before retrieval.
- [ ] Produce object-level gap, overlap and schema-transition reports.
- [ ] Freeze immutable raw storage, request ledger and hash-bound receipts.
- [ ] Keep `market_data_ingested=false` until a separate analytical release.

## Phase 2 — deterministic wallet ledger

- [ ] Parse fills, funding, deposits, withdrawals, internal transfers,
  subaccount transfers, liquidations and vault events.
- [ ] Reconcile positions, closed P&L, account state and cash flows.
- [ ] Produce gap, duplicate and schema-drift reports.
- [ ] Reject any performance estimate that cannot separate deposits from profit.
- [ ] Require byte-identical reruns and independent ledger spot checks.

## Phase 3 — point-in-time individual copyability

- [ ] Build the eligible wallet universe using only past information.
- [ ] Classify directionality, holding period, leverage and likely market making.
- [ ] Simulate follower execution at 1 s, 5 s, 30 s, 2 m, 5 m and 15 m.
- [ ] Include bid/ask, depth, slippage, fees, funding, partial fills and missed
  executions.
- [ ] Compare against no-trade, buy-and-hold, momentum and matched-random
  baselines.
- [ ] End with exactly one decision: `GO_TO_ENTITY_CLUSTER_RESEARCH`,
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
