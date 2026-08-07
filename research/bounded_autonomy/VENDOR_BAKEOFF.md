# Execution-infrastructure bake-off

## Rule

No vendor is selected from marketing material. Official documentation is used
to define testable capability hypotheses. Scores remain `UNSCORED` until an
exact version is exercised in a controlled environment.

## Weighted rubric

| Criterion | Weight |
|---|---:|
| exact Hyperliquid/venue compatibility | 20 |
| non-bypassable action and spending policy | 20 |
| key isolation and recovery | 15 |
| measured end-to-end latency | 15 |
| kill switch and revocation | 10 |
| complete audit/reconciliation evidence | 10 |
| testnet/fork and deterministic simulation support | 5 |
| portability and vendor-lock-in risk | 5 |

A candidate with a critical policy, key, recovery or reconciliation gap is
`NO_GO` regardless of total score.

## Candidates

### A. Hyperliquid API/agent wallet plus custom policy gateway

**Provisional role:** `PRIMARY_NATIVE_ENGINEERING_CANDIDATE`

Official documentation describes API wallets as signers on behalf of a master
account or subaccount and recommends a separate API wallet for each trading
process/subaccount. It also documents nonce lifecycle and address-reuse risks.

Advantages:

- venue-native signing and order flow;
- expected lowest integration and transport overhead;
- isolated subaccount can contain the capital blast radius;
- official Python SDK exists.

Unresolved/required controls:

- official sources reviewed here do not establish a project-sufficient granular
  order-only/spend-limit policy on the API wallet itself;
- exact ability of an agent wallet to sign transfer, withdrawal, leverage,
  vault, agent-management and other exchange actions must be tested;
- a custom policy firewall, restricted signer and closed adapter are mandatory;
- key storage, revocation, nonce allocation and replay behavior require
  adversarial testnet evidence.

### B. MetaMask Agent Wallet

**Provisional role:** `BENCHMARK_AND_POSSIBLE_ACCESS_CONTROLLED_PILOT`

Official June 2026 material describes an Early Access product supporting
Hyperliquid and EVM DeFi. Guard Mode uses user-defined daily spend limits,
protocol allowlists and 2FA escalation outside policy.

Required evidence:

- exact Hyperliquid action coverage and enforcement semantics;
- whether policy checks are local, onchain or vendor-mediated for Hyperliquid;
- API/CLI stability, latency and availability;
- exact key/recovery model and export consequences;
- machine-readable audit trail;
- behavior during provider, policy and 2FA outage;
- public availability and commercial terms at decision time.

Early access and vendor-provided security claims prevent treating it as
production proof.

### C. Cobo Agentic Wallet

**Provisional role:** `POLICY_AND_MPC_BENCHMARK`

Official material describes MPC-backed wallets, human-defined Pacts, spending
controls, contract/operation restrictions, auditability and emergency freeze
across many chains.

Required evidence:

- explicit Hyperliquid HyperCore support;
- exact action-function granularity;
- signing and policy latency;
- failure and recovery semantics;
- export/migration and vendor-lock-in boundaries;
- independent security review for the exact deployment.

Without verified Hyperliquid support it is not an initial executor candidate.

### D. Almanak SDK/gateway

**Provisional role:** `ARCHITECTURE_AND_POLICY_REFERENCE`

Official documentation describes a gateway-only architecture, intent
compilation, policy-enforced agent tools, Safe/Zodiac permission manifests,
backtesting and paper/fork infrastructure. The published supported matrix names
HyperEVM, not verified Hyperliquid HyperCore perpetual execution.

Use:

- study intent schemas, PolicyEngine separation, gateway isolation, simulation,
  circuit breakers and observability;
- audit whether components can be reused without importing a generic signer or
  unsupported venue assumption.

Not a direct HyperCore executor until exact support is proven.

### E. Safe, Zodiac and ERC-7579 modules

**Provisional role:** `FUTURE_EVM_AMM_DEX_TRACK`

Safe modules can implement spending caps, whitelists and rate limits. Module
guards can block module transactions, but official Safe documentation warns
that a broken guard can deny service and therefore requires auditing and a
recovery mechanism.

Safe is valuable for a later EVM Uniswap/PancakeSwap architecture. It does not
replace Hyperliquid HyperCore account controls in the initial study.

### F. Coinbase Agentic Wallet and Spend Permissions

**Provisional role:** `FUTURE_BASE_OR_PAYMENT_TRACK_NOT_INITIAL_HYPERLIQUID`

Official documentation describes per-call/per-session agent limits, Base swaps,
x402 payments and Base smart-account spend permissions. The current documented
agent tools do not provide the required Hyperliquid Core execution surface.

Do not select for the initial track.

## Required hands-on tests

For every remaining candidate:

1. create disposable test identity/account;
2. enumerate every exposed action;
3. prove allowed order/cancel paths;
4. prove transfer, withdrawal, agent-management and leverage denial;
5. measure p50/p75/p90/p95 policy, signing and acknowledgement latency;
6. test expiry, replay, duplicate and out-of-order requests;
7. revoke access and measure time to effective disablement;
8. simulate vendor/network outage;
9. export complete action and policy logs;
10. verify recovery without the AI process;
11. document exact version, configuration and hashes;
12. score using the frozen rubric.

## Provisional recommendation

For the first Hyperliquid testnet design, compare:

```text
native API wallet
+ isolated subaccount
+ custom deterministic policy service
+ restricted signer
```

against MetaMask Agent Wallet if Early Access and exact Hyperliquid controls are
available.

Cobo is retained as a policy/MPC benchmark. Almanak, Safe and Coinbase are
architecture or future-chain references, not assumed drop-in HyperCore
executors.
