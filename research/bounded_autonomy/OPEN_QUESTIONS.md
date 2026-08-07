# Open questions and blockers

No question in this file may be resolved by assumption.

## Venue permissions

1. Which exact Hyperliquid exchange actions can an approved API/agent wallet sign
   for a master account or subaccount?
2. Can an API wallet sign transfers, withdrawals, leverage updates, vault
   actions, builder-fee approvals or agent-management actions?
3. Is there any venue-native order-only, instrument, notional, frequency or
   spend policy for an API wallet?
4. What is the exact revocation and expiry behavior under in-flight requests?
5. How are nonce pruning, deregistration and replay handled under every key
   lifecycle?
6. Can an isolated subaccount fully contain loss and action authority?

These require official clarification and adversarial testnet evidence.

## Data and timing

7. Can the accepted data sources reconstruct a complete source position change
   and executable follower depth at every latency arm?
8. What share of historical latency is observed versus modeled?
9. Which node/API architecture is required for reliable p90/p95 detection?
10. How are reconnect gaps and sequence disagreements reconciled?
11. Can source events be detected quickly enough without depending on one
    best-effort provider?

## Economics

12. Does positive source performance survive follower fees, funding, spread,
    depth, partial fills and missed trades?
13. What is the alpha half-life by wallet style and instrument?
14. How much capacity remains after other followers and correlated source
    signals?
15. Does faster execution merely shift losses into a worse tail?
16. Does the AI critic add value over deterministic models after latency and
    model cost?
17. How stable are eligible wallets after follower activity becomes visible?

## Security and operations

18. Which signer isolation design is feasible without exposing a general-purpose
    exchange key?
19. Can every forbidden action be denied independently by policy, signer and
    adapter?
20. How quickly and reliably can signing be revoked and open orders cancelled?
21. What happens when the policy service, signer, venue API or model is
    unavailable?
22. How are orphan orders and positions recovered without increasing risk?
23. Which third-party components have independent audits for the exact version?
24. What is the secure upgrade and rollback process?

## Vendor questions

25. Does MetaMask Agent Wallet expose machine-readable Hyperliquid policy,
    action and audit semantics suitable for this design?
26. Is its Early Access latency and availability compatible with the primary
    arms?
27. Does Cobo Agentic Wallet explicitly support Hyperliquid HyperCore and the
    required action granularity?
28. Which Almanak policy/gateway components can be reused without assuming
    HyperCore execution support?
29. Which Safe/Zodiac modules are appropriate only for the later EVM track?
30. Does any Coinbase wallet component add value outside the future Base/EVM
    successor?

## Governance and legal

31. What exact own-account operating structure and jurisdictional requirements
    apply before a live pilot?
32. Which actions would change the project from own-account tooling into a
    regulated service for others?
33. What incident, record-retention and access-control policy is required?
34. Who can activate recovery and risk-limit changes when the primary governor
    is unavailable?

## EVM successor

35. Which EVM chain and AMM should be first after Hyperliquid?
36. How will token-contract, tax, proxy, honeypot, liquidity and MEV risk be
    incorporated?
37. Which smart-account and private-routing design provides the strongest
    enforceable envelope?
38. How will AMM copyability be separated from the Hyperliquid result?

Until answered through versioned evidence, these remain blockers at their
respective gates.
