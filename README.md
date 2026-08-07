# On-Chain Wallet Intelligence Lab

Private research repository for point-in-time on-chain wallet intelligence,
entity clustering, follower-copyability analysis and prospective
policy-constrained execution, beginning with Hyperliquid perpetuals.

## Research objective

Determine whether a wallet or economically linked wallet cluster can be selected
using only information available at the selection timestamp and then copied by a
follower after executable bid/ask pricing, latency, fees, funding, slippage and
capacity.

A profitable source wallet is not automatically copyable. Source performance
and follower performance are always reported separately.

## Governance model

The approved prospective architecture is **bounded autonomy**:

- the human remains governor, capital owner and sole authority for policy,
  capital, allowlists, model promotion and stage promotion;
- AI may eventually select and manage trades only inside a pre-authorized,
  versioned and technically enforced risk envelope;
- deterministic code remains canonical for ledgers, P&L, follower-EV, sizing,
  policy checks, action construction and reconciliation;
- the AI cannot expand its own authority, access a master key, move funds,
  change leverage, raise limits or override a block;
- unknown, stale, conflicting or unreconciled state means `SKIP` or `BLOCK`.

This is a target architecture, not a current execution permission.

## Current hard boundary

This repository is presently research-only and read-only.

- No private keys, API-wallet secrets or exchange credentials.
- No signed actions or order endpoints.
- No paper, shadow, testnet or live order submission.
- No leverage or capital-allocation authorization.
- No market dataset or empirical result has been released.
- The bounded-autonomy package authorizes research and architecture work only.

## Current studies

### `WALLET-COPYABILITY-STUDY-001`

Frozen at `PRE_DATA`. Initial scope: BTC, ETH and SOL perpetuals on Hyperliquid.
It measures follower outcomes at 1 second, 5 seconds, 30 seconds, 2 minutes,
5 minutes and 15 minutes.

### `DEX-COPY-AUTONOMY-001`

Additive parent-linked study. It asks whether a deterministic policy-constrained
executor at 0.2, 1, 3, 5, 10, 15, 30, 60, 120 and 300 seconds retains
incremental net follower value relative to human approval, using the same
signals, costs and wallet selection as the parent study.

The 0.2-second arm is a diagnostic engineering lower bound, not a promise of
achievable live latency.

## Reading order

1. `PROJECT_STATE.md`
2. `research/wallet_copyability/PREREGISTRATION.md`
3. `research/wallet_copyability/DATA_CONTRACT.json`
4. `research/bounded_autonomy/README.md`
5. `governance/adr/ADR-BOUND-AUTONOMY-001.md`
6. `governance/BOUND_AUTONOMY_POLICY.json`
7. `research/bounded_autonomy/PREREGISTRATION.md`
8. `research/bounded_autonomy/THREAT_MODEL.md`
9. `research/bounded_autonomy/EXECUTION_ARCHITECTURE.md`
10. `research/bounded_autonomy/GO_NO_GO_GATES.md`
11. `RISK_POLICY.md`
12. `ROADMAP.md`
13. `DECISION_LOG.md`
14. `MIGRATION_PROVENANCE.md`
