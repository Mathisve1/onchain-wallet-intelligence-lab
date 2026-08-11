# On-Chain Wallet Intelligence Lab

Private research repository for point-in-time on-chain wallet intelligence,
entity clustering and follower-copyability analysis, beginning with Hyperliquid
perpetuals.

## Research objective

Determine whether a wallet or economically linked wallet cluster can be selected
using only information available at the selection timestamp and then copied by a
follower after executable bid/ask pricing, latency, fees, funding and slippage.

A profitable source wallet is not automatically copyable. Source performance
and follower performance are always reported separately.

## Hard boundary

This repository is research-only.

- No private keys, API wallet secrets or exchange credentials.
- No signed actions or order endpoints.
- No paper, shadow or live order submission.
- No leverage or capital allocation authorization.
- AI may summarize evidence and produce counterarguments; deterministic code
  remains canonical for ledgers, P&L, clustering and risk controls.
- A human remains the only possible future trade-decision authority.

## Current archive gate

R11 is canonically `CONSUMED_UNRESOLVED`; its exact artifact is retained and its
single-use release has zero remaining request budget. R11A is
`PREREGISTERED_NO_EXECUTION` over exactly the same 72 objects. It may diagnose
identity scope, archive-block overlap and repeat provenance only. No owner
approval, installed workflow, release, AWS/S3 authority, empirical root-cause
claim, deduplication, repair, wallet ranking or R12 promotion exists.

## Current study

`WALLET-COPYABILITY-STUDY-001` is frozen at `PRE_DATA`. The first scope is BTC,
ETH and SOL perpetuals on Hyperliquid, with follower-latency sensitivities of
1 second, 5 seconds, 30 seconds, 2 minutes, 5 minutes and 15 minutes.

No market dataset or empirical result has been released.

## Reading order

1. `PROJECT_STATE.md`
2. `research/archive_inventory/r11a/README.md`
3. `research/archive_inventory/r11a/R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_PREREGISTRATION.json`
4. `research/archive_inventory/r11a/R11A_IDENTITY_DECISION_DOSSIER.md`
5. `research/wallet_copyability/PREREGISTRATION.md`
6. `ROADMAP.md`
7. `DECISION_LOG.md`
8. `MIGRATION_PROVENANCE.md`
