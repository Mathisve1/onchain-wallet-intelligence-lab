# Data Minimization — Hyperliquid Public Probe R1

R1 tests route reachability and coarse response classes only. It is not a wallet-surveillance, performance or labeling dataset.

Raw response bodies may exist only in process memory while enforcing the byte ceiling, calculating SHA-256, identifying JSON/S3 class, extracting top-level keys/counts and classifying the response. Bodies must not be written to disk, logs, artifacts, repository files or model prompts.

Retained evidence is limited to probe/core identity, method/origin/path, exact request fingerprint, attempts/weight, UTC timing, HTTP status, response length/hash/content type/class, top-level schema features and bounded error metadata.

Forbidden retained evidence includes balances, positions, liquidation levels, exact fills, prices, sizes, fees, funding, P&L, deposits, withdrawals, transfers, vault depositor records, raw L2 levels, owner names or natural-person identity inferences, cookies, tokens, credentials, private keys, signed payloads and wallet ranking/copyability scores.

The minimized workflow artifact is retained for 90 days. Permanent raw retention requires a separate immutable retention contract and cannot be authorized by R1.

No raw or wallet-specific R1 response is supplied to a language model. AI may later review methodology and minimized aggregate evidence, but cannot calculate canonical P&L, infer ownership, merge clusters or authorize a trade.
