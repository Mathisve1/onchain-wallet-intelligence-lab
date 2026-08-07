# Data Minimization — Hyperliquid Public Probe R1

R1 tests route reachability and coarse response classes only. It is not a wallet-surveillance, performance or labeling dataset.

Raw response bodies may exist only in process memory while enforcing byte limits, calculating SHA-256, identifying JSON/S3 class, extracting top-level keys/counts and classifying the response. Bodies must not be written to disk, logs, artifacts, repository files or model prompts.

Retained evidence is limited to probe identity, method/origin/path, request hash, attempts/weight, UTC timing, HTTP status, response length/hash/content type/class, top-level schema features and bounded error metadata.

Forbidden retained evidence includes balances, positions, fills, prices, sizes, fees, funding, P&L, transfers, vault depositor data, names or natural-person identity inferences, raw L2 levels, cookies, tokens, secrets, private keys, signed payloads and wallet scores.

The minimized artifact is retained for 90 days. Broader or permanent raw retention requires a separate immutable retention contract.

No raw or wallet-specific R1 response is sent to an LLM. AI may review methodology and minimized aggregate evidence only; it cannot calculate P&L, infer ownership, merge clusters or authorize a trade.
