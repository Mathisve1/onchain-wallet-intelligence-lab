# Official Source Map — Hyperliquid Public Probe R1

Captured for the R1 contract on 2026-08-07. The live response, not remembered documentation text, controls the technical evidence. Documentation defines the allowed claim boundary and expected response families.

| Subject | Official source | Use in R1 | What it does not prove |
|---|---|---|---|
| Public information requests | `https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint` | request identities and public account/market response classes | complete historical records or stable future schemas |
| Rate limits | `https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits` | conservative declared request weights and bounded request count | guaranteed capacity or exemption from changing limits |
| Historical archives | `https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data` | official S3 origin and dataset-family discovery | completeness, timeliness, requester-pays cost or absence of gaps |
| WebSocket subscriptions | `https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions` | later live-collector design context only | market-wide user discovery through per-user subscriptions |
| Fees | `https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees` | future point-in-time follower-cost research | an account-specific fee tier for this study |
| Funding | `https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding` | future funding-ledger interpretation | complete wallet economics or hidden cross-venue hedges |
| Node output | `https://github.com/hyperliquid-dex/node` | later event-stream and block-metadata architecture | need for a node before copyability is demonstrated |

## Evidence hierarchy

1. exact response bytes hashed by the governed workflow;
2. exact request bytes and timestamped response-shape evidence;
3. official documentation and official code repository;
4. project interpretation, clearly labeled as such.

No third-party dashboard, leaderboard, label provider or social-media claim is canonical evidence for R1.

## Documentation conflicts

Endpoint row limits, time-range behavior and archive layouts can change. R1 records actual response classes but does not resolve pagination or completeness. Those questions remain explicitly deferred to the archive-inventory and deterministic-ledger gates.
