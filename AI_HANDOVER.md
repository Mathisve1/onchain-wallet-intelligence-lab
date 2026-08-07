# AI Handover

Verified: 2026-08-07.

## Repository and canonical state

- Repository: `Mathisve1/onchain-wallet-intelligence-lab`.
- Canonical branch: `main`.
- Canonical main at this handover: `c08f7dc9419857770e53cd760f447394ecfa1bae`.
- Candidate governance PR: `#6` from
  `agent/bounded-autonomy-governance-20260807`.
- Do not modify `Mathisve1/quant-trading-lab` for this research track; the
  on-chain wallet-intelligence work was migrated to this dedicated repository.
- Do not merge PR #6 merely because CI passes. It remains a draft until the
  registered review gates are explicitly completed.

## Current empirical truth

```text
market_data_ingested = false
empirical_result = null
historical_market_release_authorized = false
historical_replay_authorized = false
shadow_authorized = false
signed_testnet_actions_authorized = false
live_authorized = false
bounded_autonomous_live_execution_authorized = false
leverage_authorized = false
capital_allocation_authorized = false
```

No profitability, copyable-alpha or execution claim exists.

## Current active technical gate

Canonical gate ID: `HL-PUBLIC-PROBE-001R1`.

The active technical work is still the final capacity-safe, credential-free and
read-only Hyperliquid public probe in the separate probe PR. Complete and attest
that gate before opening analytical market data or building a wallet ledger.

Do not let the bounded-autonomy architecture jump this sequence:

1. accepted public technical evidence;
2. official archive inventory and cost/gap contract;
3. deterministic wallet/account ledger;
4. point-in-time individual follower-copyability result;
5. only then bounded-autonomy historical latency comparison;
6. non-signing shadow;
7. adversarial permission and signed testnet proof;
8. separately authorized isolated live pilot.

## Binding governance interpretation

- `DEC-008` remains current and keeps every execution authorization closed.
- `DEC-009` remains current for canonical ledgers, P&L, clusters, sizing, risk,
  policy evaluation, action construction and reconciliation.
- `DEC-010` through `DEC-015` approve bounded autonomy only as a prospective
  human-governed architecture and additive research track.
- The human is governor, capital owner and recovery authority.
- AI cannot access a master key, transfer or withdraw funds, manage agent
  wallets, change leverage, change allowlists or risk limits, promote itself or
  override a block.
- Unknown, missing, stale, conflicting, out-of-distribution or unreconciled
  state is always `BLOCK`.
- Exact live numerical limits are `UNSET_LIVE_BLOCKER`; never invent defaults.

## Parent-study immutability

`WALLET-COPYABILITY-STUDY-001` is the parent empirical study. Its preregistration,
data contract, wallet universe, point-in-time rule, fees, funding, source-event
definition and terminal result may not be rewritten to favor
`DEX-COPY-AUTONOMY-001`.

The autonomy study compares execution modes on exactly the same eligible source
signals. It separates source alpha, selection alpha, latency/execution alpha and
AI incremental value.

## Current execution-design boundary

Research may document and test non-executing schemas only. The prospective path
is:

```text
AI/contextual critic
-> closed typed intent
-> deterministic policy/risk firewall
-> exact one-time short-lived permit
-> isolated restricted signer
-> closed venue adapter
-> order/fill/position reconciliation
```

The initial intent contract permits only closed Hyperliquid IOC-limit order,
cancel and reduce/close designs. Transfer, withdrawal, agent management,
leverage/margin changes, vault actions, builder-fee changes and arbitrary
exchange actions are forbidden.

## Vendor conclusion to preserve

- Native Hyperliquid API wallet + isolated subaccount + custom policy service +
  restricted signer is the primary testnet engineering candidate, not a
  production approval.
- MetaMask Agent Wallet is an Early Access comparison candidate only if exact
  Hyperliquid controls and latency can be independently tested.
- Cobo is a policy/MPC benchmark pending verified Hyperliquid support.
- Almanak is a gateway/policy reference; HyperEVM documentation is not proof of
  HyperCore perpetual execution.
- Safe/Zodiac and Coinbase are future EVM/Base references, not initial
  Hyperliquid executors.
- Vendor documentation is capability evidence only, not an independent audit or
  profitability result.

## Required validation before changing stage

Read, in order:

1. `PROJECT_STATE.md`;
2. `governance/RESEARCH_REGISTRY.json`;
3. `governance/BOUND_AUTONOMY_POLICY.json`;
4. `governance/adr/ADR-BOUND-AUTONOMY-001.md`;
5. `research/wallet_copyability/PREREGISTRATION.md`;
6. `research/wallet_copyability/DATA_CONTRACT.json`;
7. `research/bounded_autonomy/EXPERIMENT_CONTRACT.json`;
8. `research/bounded_autonomy/PREREGISTRATION.md`;
9. `research/bounded_autonomy/GO_NO_GO_GATES.md`;
10. `SECURITY.md` and `RISK_POLICY.md`.

Then verify the exact remote branch, commit, open PRs, review threads, Actions
runs, artifacts and repository manifest. Never trust a chat status over the
remote state.

## Prohibited shortcuts

- no direct commit to `main`;
- no silent repair of a failed or preregistered experiment;
- no credentials or signing dependency in a read-only branch;
- no generic exchange-action adapter;
- no omission of missed, blocked, expired, failed or partial trades;
- no hindsight-selected wallet or future cluster relationship;
- no vendor marketing claim represented as audited security;
- no positive backtest represented as authorization;
- no merge, stage promotion or capital allocation without explicit human
  governance.
