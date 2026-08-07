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

## Current study

`WALLET-COPYABILITY-STUDY-001` is frozen at `PRE_DATA`. The first scope is BTC,
ETH and SOL perpetuals on Hyperliquid, with follower-latency sensitivities of
1 second, 5 seconds, 30 seconds, 2 minutes, 5 minutes and 15 minutes.

The active gate is `HL-PUBLIC-PROBE-001R1`. It verifies public technical
capability and retains response hashes and structural metadata only. No market
dataset or empirical result has been released.

## Reading order

1. `PROJECT_STATE.md`
2. `research/wallet_copyability/PREREGISTRATION.md`
3. `research/wallet_copyability/DATA_CONTRACT.json`
4. `research/wallet_copyability/PROBE_CONTRACT.json`
5. `research/wallet_copyability/PROBE_METHODOLOGY.md`
6. `research/wallet_copyability/TECHNICAL_PROBE_EVIDENCE.json`
7. `research/wallet_copyability/COPY_EXECUTION_MODEL.md`
8. `research/wallet_copyability/ENTITY_CLUSTERING_BOUNDARY.md`
9. `ROADMAP.md`
10. `DECISION_LOG.md`
11. `MIGRATION_PROVENANCE.md`

## Validation

```bash
python -m unittest discover -s tests -v
python governance/validate_probe_evidence.py
python governance/validate_repository.py
```

The repository manifest must cover every tracked file except the manifest
itself. Every external GitHub Action is pinned to a full commit SHA.
